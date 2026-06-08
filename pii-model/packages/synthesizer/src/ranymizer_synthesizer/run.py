# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Drive the config-driven recipe against an injected OpenAI-compatible endpoint.

Two entry points share one setup:
  - :func:`preview` returns a small in-memory sample — no files written.
  - :func:`create`  runs and persists a full dataset.

Both build the recipe from a :class:`SynthesisConfig` and register the injected
:class:`~ranymizer_pii_core.ModelEndpoint` as a local OpenAI-compatible NDD
provider. The endpoint is never hardcoded — it is the single value object the CLI
threads through to both generation and the judge.
"""

from __future__ import annotations

from pathlib import Path

import data_designer.config as dd
from data_designer.config.preview_results import PreviewResults
from data_designer.interface import DataDesigner, DatasetCreationResults
from ranymizer_pii_core import ModelEndpoint

from .config import SynthesisConfig
from .recipe import build_recipe
from .seeds import seed_faker

#: NDD provider name for the registered local OpenAI-compatible endpoint.
PROVIDER_NAME = "local-openai"

#: NDD alias the recipe binds its generation/judge columns to.
_MODEL_ALIAS = "synth"


def _build_designer(
    config: SynthesisConfig,
    endpoint: ModelEndpoint,
    artifact_path: Path,
) -> tuple[DataDesigner, dd.DataDesignerConfigBuilder]:
    """Shared setup behind :func:`preview` and :func:`create`.

    Seeds Faker (when ``config.faker_seed`` is set), builds the recipe, and
    registers ``endpoint`` as a local OpenAI-compatible NDD provider. Returns the
    ``DataDesigner`` rooted at ``artifact_path`` plus the recipe builder to run.
    """
    if config.faker_seed is not None:
        seed_faker(config.faker_seed)

    config_builder = build_recipe(config, model_alias=_MODEL_ALIAS)
    config_builder.add_model_config(
        dd.ModelConfig(
            alias=_MODEL_ALIAS,
            model=endpoint.model,
            provider=PROVIDER_NAME,
            skip_health_check=True,
            inference_parameters=dd.ChatCompletionInferenceParams(
                temperature=endpoint.temperature,
                max_tokens=endpoint.max_tokens,
                timeout=endpoint.timeout,
                max_parallel_requests=endpoint.max_parallel_requests,
            ),
        )
    )
    provider = dd.ModelProvider(
        name=PROVIDER_NAME,
        endpoint=endpoint.base_url,
        provider_type="openai",
        api_key=endpoint.api_key,
    )

    artifact_path.mkdir(parents=True, exist_ok=True)
    designer = DataDesigner(
        artifact_path=str(artifact_path), model_providers=[provider]
    )
    return designer, config_builder


def preview(
    config: SynthesisConfig,
    endpoint: ModelEndpoint,
    *,
    num_records: int,
    artifact_path: Path,
) -> PreviewResults:
    """Generate a small in-memory sample — no dataset is written.

    Returns the NDD preview result; read ``.dataset`` for the rows.
    """
    designer, config_builder = _build_designer(config, endpoint, artifact_path)
    return designer.preview(config_builder, num_records=num_records)


def create(
    config: SynthesisConfig,
    endpoint: ModelEndpoint,
    *,
    num_records: int,
    dataset_name: str,
    artifact_path: Path,
) -> DatasetCreationResults:
    """Generate and persist a full dataset at ``artifact_path/<dataset_name>``."""
    designer, config_builder = _build_designer(config, endpoint, artifact_path)
    return designer.create(
        config_builder,
        num_records=num_records,
        dataset_name=dataset_name,
    )
