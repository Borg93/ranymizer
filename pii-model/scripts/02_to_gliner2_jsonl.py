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

import hashlib
import json
import platform
import subprocess
import sys
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from configs.ndd_swedish_pii import (  # noqa: E402
    LABELS,
    LABEL_DESCRIPTIONS,
    _SWEDISH_FIRST_NAMES,
    _SWEDISH_SURNAMES,
    _SWEDISH_STREETS,
    _SWEDISH_CITIES,
)
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

    examples = [
        ex for ex in (_row_to_example(r) for _, r in df.iterrows()) if ex is not None
    ]
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

    card_path = args.out_dir / "dataset_card.md"
    card_path.write_text(
        _dataset_card(
            raw_path=args.raw_path,
            n_train=len(train),
            n_val=len(val),
            n_test=len(test),
            seed=args.seed,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=test_ratio,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {card_path}")


# =============================================================================
# Provenance / dataset card
# =============================================================================


def _hash_pool(values) -> str:
    """Stable short hash of a seed pool (so kommun DPIA can cite it)."""
    blob = json.dumps(list(values), ensure_ascii=False, sort_keys=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _git_rev() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _dataset_card(
    *,
    raw_path: Path,
    n_train: int,
    n_val: int,
    n_test: int,
    seed: int,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
) -> str:
    """Generate a dataset card mirroring the IMY/DPIA-relevant facts.

    Kept inline (not a Jinja template) so downstream kommuner can copy this
    file verbatim into their konsekvensbedömning (Art. 35 GDPR).
    """
    cities = [c[0] for c in _SWEDISH_CITIES]
    pools = {
        "first_names": (_SWEDISH_FIRST_NAMES, len(_SWEDISH_FIRST_NAMES)),
        "surnames": (_SWEDISH_SURNAMES, len(_SWEDISH_SURNAMES)),
        "streets": (_SWEDISH_STREETS, len(_SWEDISH_STREETS)),
        "cities": (cities, len(cities)),
    }
    pool_lines = [
        f"  - `{name}` — {n} entries — sha256[:16] = `{_hash_pool(vals)}`"
        for name, (vals, n) in pools.items()
    ]
    label_lines = [f"  - `{lab}` — {LABEL_DESCRIPTIONS[lab]}" for lab in LABELS]
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"""\
# Ranymizer Swedish-PII synthetic dataset

Generated: {timestamp}
Source parquet: `{raw_path}`
Recipe revision (git): `{_git_rev()}`
Python: {platform.python_version()}  ({platform.platform()})

## Provenance

100 % synthetic. **No real Swedish citizen data is used at any point.**
Every personally-identifying span (names, addresses, personnummer,
organisationsnummer, bankgiro, phone, email, health condition, religious /
ethnic indicator) is drawn from a hand-curated seed pool or computed by a
deterministic generator (Luhn-valid personnummer, random org-nr / bankgiro).
Sensitive Art. 9 GDPR labels (`health`, `religion_ethnicity`) come from short
clinical / membership phrases — no real medical records, no real congregational
lists.

This matches the practice followed by Atea/Lidingö stad in IMY's regulatory
sandbox project IMY-2024-5156, §2.4: *"Deltagarna har uppgett att man endast
har använt fabricerade uppgifter inom ramen för detta projekt för att utvärdera
olika modellers prestanda."*

## Generator

- Recipe: `pii-model/configs/ndd_swedish_pii.py`
- Framework: NeMo Data Designer (`data-designer` PyPI package).
- LLM: configured per run (see the NDD `model_alias` in
  `scripts/01_generate_synthetic.py` / `scripts/run_hf_preview.py`).
- Quality filters applied before this split:
  - Substring validator (`entities_validated == True`): every labelled
    mention must appear verbatim in the generated text.
  - LLM-as-judge rubrics (`swedish_naturalness`, `seed_grounding`,
    `label_completeness`) — see `PII_JUDGE_SCORES` in the recipe.

## Seed pools (sha256[:16] for DPIA citation)

{chr(10).join(pool_lines)}

## Labels

{chr(10).join(label_lines)}

## Splits

- train: {n_train} rows
- val:   {n_val} rows
- test:  {n_test} rows
- Split ratios: {train_ratio:.2f} / {val_ratio:.2f} / {test_ratio:.2f}
  (`TrainingDataset.split` with seed = {seed}).

## Suggested DPIA references

When a kommun deploys a model trained on this dataset, the relevant Art. 35
GDPR konsekvensbedömning criteria from IMY's förteckning that typically apply
are:

- 4) Behandling av känsliga personuppgifter (labels `health`,
  `religion_ethnicity` are Art. 9 categories).
- 5) Behandling av personuppgifter i stor omfattning.
- 7) Behandling av personuppgifter om personer i underläge eller
  beroendeställning (text genres `socialtjänstanteckning`, `LSS-utredning`,
  `skolärende`, `biståndsbeslut`, `journalanteckning`).
- 8) Användning av ny teknik / nya organisatoriska lösningar.

Two or more = DPIA required (IMY-2024-5156, §6.3).

## Constraints honoured by the recipe

- 3 kap. 3 § andra stycket dataskyddslagen — `TEXT_GEN_SYSTEM_PROMPT`
  explicitly forbids grouping multiple individuals by a sensitive attribute.
- Art. 5(1)(b) ändamålsprincipen — the dataset is generated solely for the
  purpose of training a PII-detection (masking) model and contains no real
  personal data that could be re-purposed.
"""


if __name__ == "__main__":
    main()
