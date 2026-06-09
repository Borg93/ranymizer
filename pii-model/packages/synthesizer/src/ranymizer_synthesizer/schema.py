# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Pydantic generation-output models for the Swedish PII synthesizer.

These are *generation* concerns (the JSON shape the LLM must emit), not the core
taxonomy — the label vocabulary itself lives in ``ranymizer_pii_core``.

``entities`` is a SPARSE ``list`` of ``{label, mentions}`` records: the model emits
one entry per label it actually used and omits the rest. That sparse output cuts
decode tokens vs. always writing all 17 labels with empty lists, and it matches
GLiNER2's schema-driven format (an absent label simply means "not extracted here").
A *list of records* is used rather than a free ``{label: mentions}`` map because
the map has varying keys (and is empty on no-PII rows), which pyarrow cannot
persist as a parquet struct; a ``list[EntityMention]`` stores cleanly (empty list,
or a list of consistent two-field structs).

:func:`canonical_sparse_entities` folds that list back into the canonical
``{label: [mentions]}`` dict the rest of the pipeline expects — keeping only labels
in core's ``LABEL_NAMES`` (single source of truth, no drift), dropping empties, and
coercing each mention to ``str``. NDD drives generation from this model's JSON
schema (it never instantiates the model), so the recipe applies that function in a
custom column and stores the dict as a JSON string.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from ranymizer_pii_core import LABEL_NAMES, PERSON_RECORD_FIELDS

_VALID_LABELS = frozenset(LABEL_NAMES)


def canonical_sparse_entities(value: object) -> dict[str, list[str]]:
    """Canonical, SPARSE ``{label: [mentions]}`` from the raw ``entities`` cell.

    Accepts the ``list[{label, mentions}]`` the LLM emits (or a plain dict, for
    direct use). Keeps only labels in core's ``LABEL_NAMES``, drops empty mention
    lists, and coerces each mention to ``str`` (the model sometimes emits card
    PANs as bare ints). Non-canonical or empty entries are dropped, never raised.
    """
    items: list[tuple[object, object]] = []
    if isinstance(value, dict):
        items = list(value.items())
    elif isinstance(value, (list, tuple)):
        for entry in value:
            if isinstance(entry, dict):
                fields = {str(k): v for k, v in entry.items()}
                items.append((fields.get("label"), fields.get("mentions")))
            else:
                items.append(
                    (getattr(entry, "label", None), getattr(entry, "mentions", None))
                )
    out: dict[str, list[str]] = {}
    for label, mentions in items:
        if label in _VALID_LABELS and isinstance(mentions, (list, tuple)):
            cleaned = [str(m) for m in mentions if m is not None and str(m) != ""]
            if cleaned:
                out[str(label)] = cleaned
    return out


class CompanySeed(BaseModel):
    name: str = Field(..., description="Realistic Swedish company name (AB).")
    org_nr: str = Field(..., description="Org. number XXXXXX-XXXX.")
    bankgiro: str = Field(..., description="Bankgiro NNN-NNNN or NNNN-NNNN.")


class EntityMention(BaseModel):
    """One PII label that occurs in `text`, with its verbatim mentions."""

    label: str = Field(
        ..., description="The PII label (one of the listed labels) that occurs."
    )
    mentions: list[str] = Field(
        ..., description="Each verbatim substring of `text` carrying this label."
    )


class PersonRecord(BaseModel):
    """One individual + the identifiers that belong to THEM (each verbatim in `text`)."""

    name: str = Field(
        ..., description="The person's full name, exactly as written in text."
    )
    personnummer: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None


# Fail fast if this model's fields ever drift from the core taxonomy.
if tuple(PersonRecord.model_fields) != PERSON_RECORD_FIELDS:
    raise RuntimeError(
        "PersonRecord fields must match ranymizer_pii_core.PERSON_RECORD_FIELDS "
        f"(schema={tuple(PersonRecord.model_fields)!r}, core={PERSON_RECORD_FIELDS!r})"
    )


class TextWithEntities(BaseModel):
    """Top-level LLM output for one row."""

    text: str = Field(..., description="The Swedish text fragment we generated.")
    entities: list[EntityMention] = Field(
        default_factory=list,
        description=(
            "One entry per PII label that occurs in `text`. Include ONLY labels "
            "you actually used; omit every label that does not occur."
        ),
    )
    records: list[PersonRecord] = Field(
        default_factory=list,
        description="One entry per individual mentioned; identifiers grouped under their owner.",
    )
