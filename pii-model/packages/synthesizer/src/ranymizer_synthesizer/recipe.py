# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Config-driven NeMo Data Designer recipe — Swedish PII training data for GLiNER2.

The old monolithic ``build_config()`` is now ``build_recipe(config)``: *what*
gets synthesised — the genres, registers, surface layouts, label set, and whether
the LLM judge runs — comes from a :class:`SynthesisConfig`, not from constants
baked into the recipe body. With the default config the output is byte-equivalent
to the original recipe.

Output parquet columns:
    num_subjects         how many people the fragment is about (multi-person minority).
    content_kind         "pii" / "no_pii" — the no_pii minority trains hard negatives.
    seed_locale          "sv_SE" / "foreign" — locale of the person/subject seeds.
    seed_*               seed PII the LLM is told to use (incl. card, iban, ip,
                         username, dob).
    seed_subjects        bundled per-subject seed PII for multi-person fragments.
    text_type, register, text_layout
                         diversifiers (genre, register, surface layout).
    text                 the generated Swedish fragment.
    entities             {label: [mentions]} parsed from the LLM JSON.
    entities_validated   True iff every mention is a substring of `text`.
    records              per-subject structured records parsed from the LLM JSON.
    records_validated    True iff every record's mentions are substrings of `text`.
    pii_quality_judge_result + flat *_score columns
                         LLM-judge rubrics for downstream filtering (judge only).
"""

from __future__ import annotations

import data_designer.config as dd

from .config import SynthesisConfig
from .pools import (
    _CRIMINAL_POOL,
    _DATE_POOL,
    _HEALTH_POOL,
    _RELIGION_ETHNICITY_POOL,
    _URL_POOL,
)
from .prompts import (
    PII_JUDGE_PROMPT,
    PII_JUDGE_SCORES,
    PII_JUDGE_SYSTEM_PROMPT,
    TEXT_GEN_PROMPT,
    TEXT_GEN_SYSTEM_PROMPT,
)
from .schema import TextWithEntities
from .seeds import (
    gen_seed_address,
    gen_seed_card,
    gen_seed_company,
    gen_seed_dob,
    gen_seed_email,
    gen_seed_iban,
    gen_seed_ip,
    gen_seed_person,
    gen_seed_personnummer,
    gen_seed_phone,
    gen_seed_subjects,
    gen_seed_username,
)
from .validators import validate_entities, validate_records


def build_recipe(
    config: SynthesisConfig, *, model_alias: str = "synth"
) -> dd.DataDesignerConfigBuilder:
    """Full recipe: Swedish seeds → LLM generation → substring validate → judge.

    The diversifier values+weights (genres, layouts, registers) and the label set
    are taken from ``config``; the LLM judge column is added only when
    ``config.judge``.
    """
    builder = dd.DataDesignerConfigBuilder()
    _add_seed_columns(builder, config)
    _add_generation_columns(builder, config, model_alias)
    return builder


def _add_seed_columns(
    config_builder: dd.DataDesignerConfigBuilder, config: SynthesisConfig
) -> None:
    """Diversifiers + Swedish PII seed values (no LLM — safe to preview offline)."""
    # ─────────────────────────────────────────────────────────────────────
    # 1. Diversifiers — genre, register, and surface layout (from config).
    # ─────────────────────────────────────────────────────────────────────
    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="text_type",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=list(config.genres),
                weights=list(config.genres.values()),
            ),
        )
    )

    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="register",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=list(config.registers)),
        )
    )

    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="text_layout",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=list(config.layouts),
                weights=list(config.layouts.values()),
            ),
        )
    )

    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="num_subjects",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=list(config.subject_counts),
                weights=list(config.subject_counts.values()),
            ),
        )
    )

    # content_kind — a "no_pii" minority trains hard negatives so the model
    # learns that Swedish prose without PII should yield no spans.
    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="content_kind",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=["pii", "no_pii"],
                weights=[1 - config.no_pii_fraction, config.no_pii_fraction],
            ),
        )
    )

    # seed_locale — a "foreign" minority so the model sees non-Swedish names /
    # subjects. Sampled BEFORE seed_person/seed_subjects, which now depend on it.
    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="seed_locale",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(
                values=["sv_SE", "foreign"],
                weights=[
                    1 - config.foreign_locale_fraction,
                    config.foreign_locale_fraction,
                ],
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
    config_builder.add_column(
        dd.CustomColumnConfig(name="seed_person", generator_function=gen_seed_person)
    )
    config_builder.add_column(
        dd.CustomColumnConfig(name="seed_email", generator_function=gen_seed_email)
    )
    config_builder.add_column(
        dd.CustomColumnConfig(name="seed_phone", generator_function=gen_seed_phone)
    )
    config_builder.add_column(
        dd.CustomColumnConfig(
            name="seed_personnummer", generator_function=gen_seed_personnummer
        )
    )
    config_builder.add_column(
        dd.CustomColumnConfig(name="seed_company", generator_function=gen_seed_company)
    )
    config_builder.add_column(
        dd.CustomColumnConfig(name="seed_address", generator_function=gen_seed_address)
    )
    config_builder.add_column(
        dd.CustomColumnConfig(name="seed_card", generator_function=gen_seed_card)
    )
    config_builder.add_column(
        dd.CustomColumnConfig(name="seed_iban", generator_function=gen_seed_iban)
    )
    config_builder.add_column(
        dd.CustomColumnConfig(name="seed_ip", generator_function=gen_seed_ip)
    )
    config_builder.add_column(
        dd.CustomColumnConfig(
            name="seed_username", generator_function=gen_seed_username
        )
    )
    config_builder.add_column(
        dd.CustomColumnConfig(name="seed_dob", generator_function=gen_seed_dob)
    )
    config_builder.add_column(
        dd.CustomColumnConfig(
            name="seed_subjects", generator_function=gen_seed_subjects
        )
    )

    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="seed_date",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=list(_DATE_POOL)),
        )
    )
    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="seed_url",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=list(_URL_POOL)),
        )
    )
    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="seed_health",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=list(_HEALTH_POOL)),
        )
    )
    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="seed_religion_ethnicity",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=list(_RELIGION_ETHNICITY_POOL)),
        )
    )
    config_builder.add_column(
        dd.SamplerColumnConfig(
            name="seed_criminal",
            sampler_type=dd.SamplerType.CATEGORY,
            params=dd.CategorySamplerParams(values=list(_CRIMINAL_POOL)),
        )
    )


def _add_generation_columns(
    config_builder: dd.DataDesignerConfigBuilder,
    config: SynthesisConfig,
    model_alias: str,
) -> None:
    """LLM text+label generation, the substring validator, and the quality judge."""
    # ─────────────────────────────────────────────────────────────────────
    # 3. LLM column — write the text AND the labels in one call.
    # ─────────────────────────────────────────────────────────────────────
    config_builder.add_column(
        dd.LLMStructuredColumnConfig(
            name="generation",
            model_alias=model_alias,
            system_prompt=TEXT_GEN_SYSTEM_PROMPT,
            prompt=TEXT_GEN_PROMPT,
            output_format=TextWithEntities,
            # Reasoning models (Qwen3.6 MTP, DeepSeek R1, gpt-oss) emit a
            # chain-of-thought block alongside the final JSON. Pulling it
            # into a separate column keeps NDD from mistaking it for the
            # structured response.
            extract_reasoning_content=True,
        )
    )

    # Flatten generation.{text, entities} into top-level columns for downstream.
    config_builder.add_column(
        dd.ExpressionColumnConfig(name="text", expr="{{ generation.text }}")
    )
    config_builder.add_column(
        dd.ExpressionColumnConfig(name="entities", expr="{{ generation.entities }}")
    )
    config_builder.add_column(
        dd.ExpressionColumnConfig(name="records", expr="{{ generation.records }}")
    )
    config_builder.add_column(
        dd.CustomColumnConfig(
            name="records_validated", generator_function=validate_records
        )
    )

    # ─────────────────────────────────────────────────────────────────────
    # 4. Validator — cheap substring check.
    # ─────────────────────────────────────────────────────────────────────
    config_builder.add_column(
        dd.CustomColumnConfig(
            name="entities_validated",
            generator_function=validate_entities,
        )
    )

    # ─────────────────────────────────────────────────────────────────────
    # 5. LLM judge — soft quality signal for downstream filtering (optional).
    # ─────────────────────────────────────────────────────────────────────
    if not config.judge:
        return

    config_builder.add_column(
        dd.LLMJudgeColumnConfig(
            name="pii_quality_judge_result",
            model_alias=model_alias,
            system_prompt=PII_JUDGE_SYSTEM_PROMPT,
            prompt=PII_JUDGE_PROMPT,
            scores=PII_JUDGE_SCORES,
            extract_reasoning_content=True,
        )
    )

    # Flat *_score columns are driven by the rubric definition itself, so adding
    # or renaming a rubric in PII_JUDGE_SCORES is the only edit needed — the
    # column names can never drift from the judge's actual scores.
    for score in PII_JUDGE_SCORES:
        name = f"{score.name}_score"
        config_builder.add_column(
            dd.ExpressionColumnConfig(
                name=name,
                expr=(
                    f"{{{{ pii_quality_judge_result.{score.name}.score"
                    f" if pii_quality_judge_result.{score.name}.score is not none"
                    f" else '' }}}}"
                ),
            )
        )
