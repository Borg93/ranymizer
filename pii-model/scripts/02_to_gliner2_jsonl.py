# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""
Convert NDD output (parquet) → GLiNER2 `InputExample` JSONL.

Drops rows where `entities_validated` is False, normalises the entities dict,
attaches the same `entity_descriptions` we use at inference, and splits
90/5/5 → train/val/test.

Run:
    uv run scripts/02_to_gliner2_jsonl.py \
        --raw-path data/raw/swedish_pii_synthetic
"""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from configs.ndd_swedish_pii import LABELS, LABEL_DESCRIPTIONS  # noqa: E402
from gliner2.training.data import InputExample, TrainingDataset  # noqa: E402


def _load_parquets(raw_path: Path) -> pd.DataFrame:
    """NDD writes `parquet-files/*.parquet` under the dataset dir."""
    parquet_dir = raw_path / "parquet-files"
    if not parquet_dir.exists():
        parquet_dir = raw_path
    files = sorted(parquet_dir.glob("*.parquet"))
    if not files:
        raise SystemExit(f"No parquet files under {parquet_dir}")
    return pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)


def _row_to_example(row: pd.Series) -> InputExample | None:
    text = row.get("text")
    ents = row.get("entities")
    if not text or ents is None:
        return None

    if isinstance(ents, str):
        try:
            ents = json.loads(ents)
        except Exception:
            return None

    # Drop empty labels and any drift past the validator.
    cleaned: dict[str, list[str]] = {}
    for label in LABELS:
        mentions = ents.get(label, []) or []
        kept = [m for m in mentions if m and m in text]
        if kept:
            cleaned[label] = kept

    if not cleaned:
        return None

    return InputExample(
        text=text,
        entities=cleaned,
        entity_descriptions={k: LABEL_DESCRIPTIONS[k] for k in cleaned},
    )


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument(
        "--raw-path",
        type=Path,
        required=True,
        help="Path to the NDD output dataset dir (or its parquet-files/ dir).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
    )
    parser.add_argument("--train-ratio", type=float, default=0.9)
    parser.add_argument("--val-ratio", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = _load_parquets(args.raw_path)
    print(f"Loaded {len(df)} raw rows from {args.raw_path}")

    if "entities_validated" in df.columns:
        before = len(df)
        df = df[df["entities_validated"] == True].reset_index(drop=True)  # noqa: E712
        print(f"  Kept {len(df)} / {before} rows after entity validation.")

    examples = [ex for ex in (_row_to_example(r) for _, r in df.iterrows()) if ex is not None]
    print(f"  Converted to {len(examples)} gliner2 InputExamples.")

    dataset = TrainingDataset(examples)
    dataset.validate(raise_on_error=False)  # report, don't crash
    dataset.print_stats()

    test_ratio = 1.0 - args.train_ratio - args.val_ratio
    train, val, test = dataset.split(
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=test_ratio,
        shuffle=True,
        seed=args.seed,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    train.save(args.out_dir / "train.jsonl")
    val.save(args.out_dir / "val.jsonl")
    test.save(args.out_dir / "test.jsonl")
    print(f"\nWrote {args.out_dir}/{{train,val,test}}.jsonl")


if __name__ == "__main__":
    main()
