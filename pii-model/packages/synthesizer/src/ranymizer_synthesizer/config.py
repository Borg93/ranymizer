# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""The synthesis config — *what* gets generated, as data not code.

:class:`SynthesisConfig` is the single knob the recipe reads: the label set, the
genre/register/layout diversifiers, and whether to attach the LLM judge. Defaults
reproduce the original hardcoded recipe exactly (the IMY-aware Swedish PII setup),
so ``build_recipe(SynthesisConfig())`` is byte-equivalent to the old
``build_config()``. Override any field to retarget the dataset without touching
the recipe.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator
from ranymizer_pii_core import LABEL_NAMES

# Vulnerable-population genres (socialtjänst, LSS, skola, bistånd, journal) so
# the model sees PII in the document classes IMY flags as high-risk (Slutrapport
# IMY-2024-5156 §6.3, criterion 7), plus the legal (domstolsbeslut/polisanmälan)
# and form/table (körkort/Skatteverket-blankett/kontoutdrag table) genres. The
# weights are copied verbatim from the original recipe.
_DEFAULT_GENRES: dict[str, float] = {
    "support email": 1.2,
    "invoice line": 1.0,
    "kontoutdrag entry": 1.0,
    "form screenshot caption": 1.0,
    "internal Slack message": 1.0,
    "customer ticket": 1.2,
    "kvitto/receipt note": 0.8,
    "id-kort preview text": 0.6,
    "address-change notification": 0.8,
    "doctor appointment summary": 0.8,
    # Legal/medical genres weighted ~2.0 so Art. 9/Art. 10 (health, religion,
    # criminal) labels actually surface in the synthetic corpus.
    "socialtjänstanteckning": 2.0,
    "LSS-utredning": 2.0,
    "skolärende": 0.9,
    "biståndsbeslut": 2.0,
    "journalanteckning": 2.0,
    # Legal genres — give the Art. 10 `criminal` label natural context.
    "domstolsbeslut": 2.0,
    "polisanmälan": 2.0,
    # Form/table genres — document-specific KIE field vocabulary.
    "körkort": 0.8,
    "Skatteverket-blankett": 0.9,
    "kontoutdrag table": 1.0,
    # Coverage genres — exist to surface the currently-missing card_number/iban/
    # ip_address/username/email/date_of_birth/organisationsnummer/bank labels by
    # giving the LLM a context where each naturally appears.
    "leverantörsfaktura": 1.3,
    "kontoutdrag med kortköp": 1.2,
    # Card-payment receipt — the document type that naturally carries a card PAN,
    # so the otherwise-0 card_number label finally surfaces (invoices reference
    # bank/IBAN, never a card number).
    "kortbetalning – kvitto": 1.2,
    "inloggnings- och kontouppgifter": 1.1,
    "IT-supportärende med loggrad": 1.0,
    "id-kort/körkort med födelsedatum": 1.0,
}

# Surface layout — NON-PROSE dominates (~87 %) because real Ranymizer inputs are
# screenshots of forms/tables/ID cards, not paragraphs. Prose is kept at ~12 %
# so the model still sees PII woven into running text. weights → prose 0.8,
# key_value 1.6, form_row 1.6, table_row 1.4, list 1.0 (sum 6.4): key_value
# ~25 %, form_row ~25 %, table_row ~22 %, list ~16 %, prose ~12 %
# (Skatteverket-blankett, kontoutdrag, ID-kort).
_DEFAULT_LAYOUTS: dict[str, float] = {
    "prose": 0.8,
    "key_value": 1.6,
    "form_row": 1.6,
    "table_row": 1.4,
    "list": 1.0,
}

_DEFAULT_REGISTERS: tuple[str, ...] = (
    "formal",
    "informal",
    "bureaucratic",
    "mobile chat",
)


class SynthesisConfig(BaseModel):
    """Declarative description of one synthetic Swedish-PII dataset.

    Every field defaults to the original recipe's hardcoded behaviour. The one
    exception is ``subject_counts``: its default now includes a multi-subject
    minority, so an empty config is no longer byte-identical to the original
    single-subject-only recipe — that is intended. Override fields to retarget
    the dataset.
    """

    labels: tuple[str, ...] = Field(
        default=LABEL_NAMES,
        description="PII label set the entities schema/judge cover (defaults to the core taxonomy).",
    )
    layouts: dict[str, float] = Field(
        default_factory=lambda: dict(_DEFAULT_LAYOUTS),
        description="Surface-layout categories → sampling weights.",
    )
    genres: dict[str, float] = Field(
        default_factory=lambda: dict(_DEFAULT_GENRES),
        description="text_type genres → sampling weights.",
    )
    subject_counts: dict[str, float] = Field(
        default_factory=lambda: {"1": 0.7, "2": 0.2, "3": 0.1},
        description="num_subjects categories -> sampling weights (multi-person minority).",
    )
    no_pii_fraction: float = Field(
        default=0.08,
        ge=0.0,
        le=1.0,
        description="Fraction of rows that are clean NO-PII negatives (true negatives for the detector).",
    )
    foreign_locale_fraction: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Fraction of person/phone seeds drawn from a non-Swedish locale.",
    )
    registers: tuple[str, ...] = Field(
        default=_DEFAULT_REGISTERS,
        description="Writing registers sampled uniformly.",
    )
    judge: bool = Field(
        default=True,
        description="Attach the LLM-judge quality column + per-rubric score columns.",
    )
    faker_seed: int | None = Field(
        default=None,
        description="If set, seed Faker (+ stdlib random) for reproducible seed values.",
    )

    @field_validator("labels", "registers")
    @classmethod
    def _non_empty_tuple(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            raise ValueError("must not be empty")
        if len(set(v)) != len(v):
            raise ValueError(f"must not contain duplicates: {v!r}")
        return v

    @field_validator("layouts", "genres")
    @classmethod
    def _positive_weights(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("must not be empty")
        bad = {k: w for k, w in v.items() if w <= 0}
        if bad:
            raise ValueError(f"weights must be > 0: {bad!r}")
        return v

    @model_validator(mode="after")
    def _labels_known(self) -> SynthesisConfig:
        unknown = tuple(label for label in self.labels if label not in LABEL_NAMES)
        if unknown:
            raise ValueError(
                f"unknown labels not in the core taxonomy: {unknown!r} "
                f"(known: {LABEL_NAMES!r})"
            )
        return self
