# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Model-level NER evaluation for a GLiNER2 checkpoint.

Distinct from ``ranymizer_evaluation`` (LLM-as-judge *data* quality): this scores
the trained *model*. It runs ``extract_entities`` over the held-out gold test
split and computes span-level precision/recall/F1 per label — exact
``(label, mention)`` match, the protocol the fastino model card reports on the
SPY benchmark. Because GLiNER2 conditions on the label set at inference time, the
same held-out split can score any checkpoint (off-the-shelf or fine-tuned) on our
own taxonomy, which is exactly what a before/after-training comparison needs.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from gliner2 import GLiNER2
from pydantic import BaseModel
from ranymizer_pii_core import LABEL_NAMES


class LabelScore(BaseModel):
    """Per-label span-level confusion counts and P/R/F1."""

    label: str
    support: int
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


class NerReport(BaseModel):
    """Span-level NER scores for one checkpoint over one test split."""

    checkpoint: str
    num_examples: int
    threshold: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    macro_f1: float
    per_label: list[LabelScore]


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _gold_from_jsonl(test_path: Path) -> list[tuple[str, dict[str, set[str]]]]:
    """Read ``test.jsonl`` into ``(text, {label: {casefolded mentions}})`` rows."""
    rows: list[tuple[str, dict[str, set[str]]]] = []
    for line in test_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        entities = obj.get("output", {}).get("entities") or {}
        gold = {
            str(label): {str(m).casefold() for m in mentions if str(m)}
            for label, mentions in entities.items()
            if mentions
        }
        rows.append((obj["input"], gold))
    return rows


def evaluate_model(
    model: GLiNER2,
    test_path: Path,
    *,
    checkpoint_name: str,
    labels: Sequence[str] = LABEL_NAMES,
    threshold: float = 0.5,
    batch_size: int = 16,
) -> NerReport:
    """Score a loaded GLiNER2 ``model`` against gold ``test.jsonl`` at span level."""
    gold_rows = _gold_from_jsonl(test_path)
    texts = [text for text, _ in gold_rows]
    preds = model.batch_extract_entities(
        texts, list(labels), threshold=threshold, batch_size=batch_size
    )

    tp: dict[str, int] = dict.fromkeys(labels, 0)
    fp: dict[str, int] = dict.fromkeys(labels, 0)
    fn: dict[str, int] = dict.fromkeys(labels, 0)
    for (_, gold), pred in zip(gold_rows, preds, strict=True):
        pred_entities = pred.get("entities", {}) if isinstance(pred, dict) else {}
        for label in labels:
            gold_set = gold.get(label, set())
            pred_set = {str(m).casefold() for m in pred_entities.get(label, []) if m}
            tp[label] += len(gold_set & pred_set)
            fp[label] += len(pred_set - gold_set)
            fn[label] += len(gold_set - pred_set)

    per_label: list[LabelScore] = []
    gold_f1s: list[float] = []
    for label in labels:
        t, f_pos, f_neg = tp[label], fp[label], fn[label]
        if t + f_pos + f_neg == 0:
            continue  # label absent from both gold and predictions — skip
        precision, recall, f1 = _prf(t, f_pos, f_neg)
        per_label.append(
            LabelScore(
                label=label,
                support=t + f_neg,
                tp=t,
                fp=f_pos,
                fn=f_neg,
                precision=round(precision, 3),
                recall=round(recall, 3),
                f1=round(f1, 3),
            )
        )
        if t + f_neg > 0:  # macro averages over labels that occur in gold
            gold_f1s.append(f1)

    micro_p, micro_r, micro_f1 = _prf(sum(tp.values()), sum(fp.values()), sum(fn.values()))
    macro_f1 = sum(gold_f1s) / len(gold_f1s) if gold_f1s else 0.0
    return NerReport(
        checkpoint=checkpoint_name,
        num_examples=len(gold_rows),
        threshold=threshold,
        micro_precision=round(micro_p, 3),
        micro_recall=round(micro_r, 3),
        micro_f1=round(micro_f1, 3),
        macro_f1=round(macro_f1, 3),
        per_label=sorted(per_label, key=lambda s: -s.support),
    )


def evaluate_checkpoint(
    checkpoint: str,
    test_path: Path,
    *,
    adapter: str | None = None,
    labels: Sequence[str] = LABEL_NAMES,
    threshold: float = 0.5,
) -> NerReport:
    """Load a GLiNER2 ``checkpoint`` (optionally + a LoRA ``adapter`` dir) and score it."""
    model = GLiNER2.from_pretrained(checkpoint)
    name = checkpoint
    if adapter is not None:
        model.load_adapter(adapter)
        name = f"{checkpoint} + {adapter}"
    return evaluate_model(
        model, test_path, checkpoint_name=name, labels=labels, threshold=threshold
    )
