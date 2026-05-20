# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""
Run the NeMo Data Designer recipe to produce synthetic Swedish PII training data.

Output: `data/raw/<dataset_name>/.../*.parquet` — pass that to
`02_to_gliner2_jsonl.py` next.

Prerequisites:
    - OPENAI_API_KEY (default model alias is "openai-text"), or
    - NVIDIA_API_KEY (use --model-alias nvidia-text / nvidia-super), or
    - a local vLLM endpoint (use --model-alias vllm).

Run:
    uv run scripts/01_generate_synthetic.py --num-records 1000
    uv run scripts/01_generate_synthetic.py --num-records 200000 --model-alias nvidia-super
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

# Make `configs/` importable when run as a script (no install needed).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from configs.ndd_swedish_pii import build_config  # noqa: E402
from data_designer.interface import DataDesigner  # noqa: E402


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--model-alias", type=str, default="openai-text")
    parser.add_argument("--num-records", type=int, default=1000)
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="swedish_pii_synthetic",
        help="Name of the dataset directory under data/raw/",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Run a 5-row preview instead of full generation (debug).",
    )
    args = parser.parse_args()

    artifact_path = Path(__file__).resolve().parent.parent / "data" / "raw"
    artifact_path.mkdir(parents=True, exist_ok=True)

    config = build_config(model_alias=args.model_alias)
    designer = DataDesigner(artifact_path=str(artifact_path))

    if args.preview:
        results = designer.preview(config, num_records=5)
        print("\nPreview (5 rows):")
        results.display_sample_record()
        return

    results = designer.create(
        config,
        num_records=args.num_records,
        dataset_name=args.dataset_name,
    )
    print(f"\nDataset saved to: {results.artifact_storage.final_dataset_path}")
    print("Next step: scripts/02_to_gliner2_jsonl.py")


if __name__ == "__main__":
    main()
