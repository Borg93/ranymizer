# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""
One-off: run the Swedish PII recipe against the HuggingFace Inference
Endpoint hosting `unsloth/Qwen3.6-27B-MTP-GGUF`.

The endpoint is OpenAI-compatible, so we register it as a stock NDD
ModelProvider with `provider_type="openai"`. The endpoint is currently
public — `HF_TOKEN` is honoured if set but optional.

Run:
    .venv/bin/python scripts/run_hf_preview.py            # 5-row preview
    .venv/bin/python scripts/run_hf_preview.py --num 20   # bigger preview
"""

from __future__ import annotations

import json
import os
import sys
from argparse import ArgumentParser
from pathlib import Path

# Make `configs/` importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data_designer.config as dd  # noqa: E402
from data_designer.interface import DataDesigner  # noqa: E402

from configs.ndd_swedish_pii import build_config  # noqa: E402

HF_ENDPOINT = "https://u2bsy1pt4m2oulrz.us-east-2.aws.endpoints.huggingface.cloud/v1/"
HF_MODEL = "unsloth/Qwen3.6-27B-MTP-GGUF"
PROVIDER_NAME = "hf-qwen-endpoint"
MODEL_ALIAS = "hf-qwen"


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--num", type=int, default=5, help="Preview row count.")
    args = parser.parse_args()

    # Public endpoint; HF_TOKEN is honoured if present but not required.
    hf_token = os.environ.get("HF_TOKEN") or None

    # 1. Build the recipe with our alias.
    config = build_config(model_alias=MODEL_ALIAS)

    # 2. Register the HF-hosted model under that alias.
    # Qwen3.6 MTP is a reasoning model — most of its first hundreds of tokens
    # go into `reasoning_content`, not the final JSON. With max_tokens<2k the
    # model truncates BEFORE emitting structured content and NDD sees empty
    # output. 8k gives it room for both the chain-of-thought and the
    # multi-field structured response.
    config.add_model_config(
        dd.ModelConfig(
            alias=MODEL_ALIAS,
            model=HF_MODEL,
            provider=PROVIDER_NAME,
            skip_health_check=True,
            inference_parameters=dd.ChatCompletionInferenceParams(
                temperature=0.7,
                max_tokens=8192,
                timeout=300,
                max_parallel_requests=4,
            ),
        )
    )

    # 3. Tell the DataDesigner about the HF provider (OpenAI-compatible).
    hf_provider = dd.ModelProvider(
        name=PROVIDER_NAME,
        endpoint=HF_ENDPOINT,
        provider_type="openai",
        api_key=hf_token,
    )
    designer = DataDesigner(model_providers=[hf_provider])

    # 4. Preview.
    print(f"Running preview ({args.num} rows) against {HF_MODEL} …")
    results = designer.preview(config, num_records=args.num)

    df = results.dataset
    print(f"\nGenerated {len(df)} rows. Columns: {list(df.columns)}\n")

    # 5. Pretty-print each sample's text, entities, validator + judge.
    score_cols = [
        "swedish_naturalness_score",
        "seed_grounding_score",
        "label_completeness_score",
    ]
    for i, row in df.iterrows():
        print("─" * 70)
        print(
            f"# row {i}  text_type={row.get('text_type')!r}  register={row.get('register')!r}"
        )
        print(f"  validated:       {row.get('entities_validated')}")
        for col in score_cols:
            print(f"  {col:30s} {row.get(col)}")
        print(f"\n  TEXT:\n    {row.get('text')}\n")
        ents = row.get("entities")
        if isinstance(ents, str):
            try:
                ents = json.loads(ents)
            except Exception:
                pass
        print("  ENTITIES:")
        if isinstance(ents, dict):
            for k, v in ents.items():
                if v:
                    print(f"    {k}: {v}")
        else:
            print(f"    (raw) {ents}")
        print()


if __name__ == "__main__":
    main()
