# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""
NeMo Data Designer recipe — Swedish PII training data for GLiNER2.

Public surface (also re-exported for backwards compat):
    build_config(model_alias)        — returns a `DataDesignerConfigBuilder`.
    LABELS, LABEL_DESCRIPTIONS       — label vocabulary (see _ndd/labels.py).
    _SWEDISH_FIRST_NAMES, _SWEDISH_SURNAMES,
    _SWEDISH_STREETS,    _SWEDISH_CITIES   — used by the dataset card emitter.

The recipe lives in modules under `configs/_ndd/`:
    labels.py            LABELS + LABEL_DESCRIPTIONS + pydantic models.
    seed_pools.py        Static seed lists (names, streets, sensitive pools).
    seed_generators.py   Luhn-valid personnummer + NDD-decorated row generators.
    validators.py        Substring validator (entities_validated).
    prompts.py           Text-generation + LLM-judge prompts & rubrics.

Output parquet columns:
    seed_*               seed PII the LLM is told to use.
    text_type, register, text_layout
                         diversifiers (genre, register, surface layout).
    text                 the generated Swedish fragment.
    entities             {label: [mentions]} parsed from the LLM JSON.
    entities_validated   True iff every mention is a substring of `text`.
    pii_quality_judge_result + flat *_score columns
                         LLM-judge rubrics for downstream filtering.

Prerequisites:
    - OPENAI_API_KEY (default), NVIDIA_API_KEY, or a local vLLM endpoint.
"""

from __future__ import annotations

import data_designer.config as dd

from ._ndd.labels import (  # noqa: F401  (re-exported)
    CompanySeed,
    EntitiesOutput,
    LABEL_DESCRIPTIONS,
    LABELS,
    TextWithEntities,
)
from ._ndd.prompts import (
    PII_JUDGE_PROMPT,
    PII_JUDGE_SCORES,
    PII_JUDGE_SYSTEM_PROMPT,
    TEXT_GEN_PROMPT,
    TEXT_GEN_SYSTEM_PROMPT,
)
from ._ndd.seed_generators import (  # noqa: F401  (helpers exposed for tests)
    gen_seed_address,
    gen_seed_company,
    gen_seed_email,
    gen_seed_person,
    gen_seed_personnummer,
    gen_seed_phone,
    make_address,
    make_bankgiro,
    make_orgnummer,
    make_personnummer,
    make_phone,
)
from ._ndd.seed_pools import (
    _DATE_POOL,
    _HEALTH_POOL,
    _RELIGION_ETHNICITY_POOL,
    _URL_POOL,
)
from ._ndd.validators import validate_entities


def build_config(model_alias: str = "openai-text") -> dd.DataDesignerConfigBuilder:
    config = dd.DataDesignerConfigBuilder()

    # ─────────────────────────────────────────────────────────────────────
    # 1. Diversifiers — genre, register, and surface layout.
    # ─────────────────────────────────────────────────────────────────────
    # Vulnerable-population genres (socialtjänst, LSS, skola, bistånd,
    # journal) so the model sees PII in the document classes IMY flags as
    # high-risk (Slutrapport IMY-2024-5156 §6.3, criterion 7).
    config.add_column(
        dd.SamplerColumnConfig(
            name="text_type",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=[
                    "support email",
                    "invoice line",
                    "kontoutdrag entry",
                    "form screenshot caption",
                    "internal Slack message",
                    "customer ticket",
                    "kvitto/receipt note",
                    "id-kort preview text",
                    "address-change notification",
                    "doctor appointment summary",
                    "socialtjänstanteckning",
                    "LSS-utredning",
                    "skolärende",
                    "biståndsbeslut",
                    "journalanteckning",
                ],
                weights=[
                    1.2,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.2,
                    0.8,
                    0.6,
                    0.8,
                    0.8,
                    0.9,
                    0.7,
                    0.9,
                    0.9,
                    1.0,
                ],
            ),
        )
    )

    config.add_column(
        dd.SamplerColumnConfig(
            name="register",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=["formal", "informal", "bureaucratic", "mobile chat"]
            ),
        )
    )

    # Surface layout — prose still dominates (~38 %) but key/value, form,
    # table and list layouts each get ~10-30 % so the model learns to
    # detect PII in non-prose OCR output (Skatteverket forms, kontoutdrag,
    # ID cards). Real Ranymizer inputs are screenshots, not paragraphs.
    config.add_column(
        dd.SamplerColumnConfig(
            name="text_layout",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=["prose", "key_value", "form_row", "table_row", "list"],
                weights=[2.0, 1.5, 1.2, 1.0, 0.7],
            ),
        )
    )

    # ─────────────────────────────────────────────────────────────────────
    # 2. Seed PII values — these are the real "ground truth".
    # ─────────────────────────────────────────────────────────────────────
    # All seed_* generators are CustomColumnConfig with an explicit
    # `required_columns` so NDD's async scheduler routes them through the
    # per-row dispatch (cell_by_cell) path. Without an upstream dependency
    # the scheduler treats a custom column as from-scratch and passes a
    # DataFrame instead of a row dict, clashing with the function signature.
    config.add_column(
        dd.CustomColumnConfig(name="seed_person", generator_function=gen_seed_person)
    )
    config.add_column(
        dd.CustomColumnConfig(name="seed_email", generator_function=gen_seed_email)
    )
    config.add_column(
        dd.CustomColumnConfig(name="seed_phone", generator_function=gen_seed_phone)
    )
    config.add_column(
        dd.CustomColumnConfig(
            name="seed_personnummer", generator_function=gen_seed_personnummer
        )
    )
    config.add_column(
        dd.CustomColumnConfig(name="seed_company", generator_function=gen_seed_company)
    )
    config.add_column(
        dd.CustomColumnConfig(name="seed_address", generator_function=gen_seed_address)
    )

    config.add_column(
        dd.SamplerColumnConfig(
            name="seed_date",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=list(_DATE_POOL)),
        )
    )
    config.add_column(
        dd.SamplerColumnConfig(
            name="seed_url",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=list(_URL_POOL)),
        )
    )
    config.add_column(
        dd.SamplerColumnConfig(
            name="seed_health",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=list(_HEALTH_POOL)),
        )
    )
    config.add_column(
        dd.SamplerColumnConfig(
            name="seed_religion_ethnicity",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=list(_RELIGION_ETHNICITY_POOL)),
        )
    )

    # ─────────────────────────────────────────────────────────────────────
    # 3. LLM column — write the text AND the labels in one call.
    # ─────────────────────────────────────────────────────────────────────
    config.add_column(
        dd.LLMStructuredColumnConfig(
            name="generation",
            model_alias=model_alias,
            system_prompt=TEXT_GEN_SYSTEM_PROMPT,
            prompt=TEXT_GEN_PROMPT,
            output_format=TextWithEntities,
        )
    )

    # Flatten generation.{text, entities} into top-level columns for downstream.
    config.add_column(
        dd.ExpressionColumnConfig(name="text", expr="{{ generation.text }}")
    )
    config.add_column(
        dd.ExpressionColumnConfig(name="entities", expr="{{ generation.entities }}")
    )

    # ─────────────────────────────────────────────────────────────────────
    # 4. Validator — cheap substring check.
    # ─────────────────────────────────────────────────────────────────────
    config.add_column(
        dd.CustomColumnConfig(
            name="entities_validated",
            generator_function=validate_entities,
        )
    )

    # ─────────────────────────────────────────────────────────────────────
    # 5. LLM judge — soft quality signal for downstream filtering.
    # ─────────────────────────────────────────────────────────────────────
    config.add_column(
        dd.LLMJudgeColumnConfig(
            name="pii_quality_judge_result",
            model_alias=model_alias,
            system_prompt=PII_JUDGE_SYSTEM_PROMPT,
            prompt=PII_JUDGE_PROMPT,
            scores=PII_JUDGE_SCORES,
        )
    )

    for rubric in ("swedish_naturalness", "seed_grounding", "label_completeness"):
        config.add_column(
            dd.ExpressionColumnConfig(
                name=f"{rubric}_score",
                expr=(
                    f"{{{{ pii_quality_judge_result.{rubric}.score"
                    f" if pii_quality_judge_result.{rubric}.score is not none"
                    f" else '' }}}}"
                ),
            )
        )

    return config
