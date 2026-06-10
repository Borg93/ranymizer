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
    per_label_thresholds: dict[str, float] | None = None


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

    micro_p, micro_r, micro_f1 = _prf(
        sum(tp.values()), sum(fp.values()), sum(fn.values())
    )
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


# =============================================================================
# Per-label threshold calibration (GLiNER2-PII paper §6: "label-specific
# thresholds … calibration on a small validation set could improve precision
# without substantially reducing recall"). Extract candidates once at a low
# floor WITH confidences, pick the F-beta-maximising threshold per label on
# val, and apply it to test.
# =============================================================================

_GRID: tuple[float, ...] = tuple(round(0.05 * i, 2) for i in range(1, 20))  # 0.05..0.95


def _predict_candidates(
    model: GLiNER2,
    texts: Sequence[str],
    labels: Sequence[str],
    *,
    floor: float,
    batch_size: int,
) -> list[dict[str, list[tuple[str, float]]]]:
    """Per-row ``{label: [(casefolded_mention, confidence)]}`` at a low floor."""
    preds = model.batch_extract_entities(
        list(texts),
        list(labels),
        threshold=floor,
        include_confidence=True,
        batch_size=batch_size,
    )
    rows: list[dict[str, list[tuple[str, float]]]] = []
    for pred in preds:
        entities = pred.get("entities", {}) if isinstance(pred, dict) else {}
        row: dict[str, list[tuple[str, float]]] = {}
        for label, items in entities.items():
            cand = [
                (str(it["text"]).casefold(), float(it.get("confidence", 1.0)))
                for it in items
                if isinstance(it, dict) and it.get("text")
            ]
            if cand:
                row[str(label)] = cand
        rows.append(row)
    return rows


def _counts_at(
    candidates: list[dict[str, list[tuple[str, float]]]],
    gold_rows: list[tuple[str, dict[str, set[str]]]],
    label: str,
    threshold: float,
) -> tuple[int, int, int]:
    """Span-level (tp, fp, fn) for one label at one confidence threshold."""
    tp = fp = fn = 0
    for (_, gold), cand in zip(gold_rows, candidates, strict=True):
        pred = {m for m, conf in cand.get(label, []) if conf >= threshold}
        gold_set = gold.get(label, set())
        tp += len(gold_set & pred)
        fp += len(pred - gold_set)
        fn += len(gold_set - pred)
    return tp, fp, fn


def _fbeta(precision: float, recall: float, beta: float) -> float:
    b2 = beta * beta
    denom = b2 * precision + recall
    return (1 + b2) * precision * recall / denom if denom else 0.0


def tune_thresholds(
    candidates: list[dict[str, list[tuple[str, float]]]],
    gold_rows: list[tuple[str, dict[str, set[str]]]],
    *,
    labels: Sequence[str] = LABEL_NAMES,
    beta: float = 1.0,
) -> dict[str, float]:
    """Per-label threshold maximising F-beta on (val) candidates + gold.

    ``beta > 1`` favours recall — the redaction objective the paper argues for
    (a missed PII span costs more than an over-prediction).
    """
    best: dict[str, float] = {}
    for label in labels:
        best_thr, best_score = 0.5, -1.0
        for thr in _GRID:
            tp, fp, fn = _counts_at(candidates, gold_rows, label, thr)
            precision, recall, _ = _prf(tp, fp, fn)
            score = _fbeta(precision, recall, beta)
            if score > best_score:
                best_score, best_thr = score, thr
        best[label] = best_thr
    return best


def _report_from_candidates(
    candidates: list[dict[str, list[tuple[str, float]]]],
    gold_rows: list[tuple[str, dict[str, set[str]]]],
    *,
    checkpoint_name: str,
    labels: Sequence[str],
    thresholds: dict[str, float],
) -> NerReport:
    """Build a NerReport by applying a per-label threshold map to candidates."""
    per_label: list[LabelScore] = []
    gold_f1s: list[float] = []
    tot_tp = tot_fp = tot_fn = 0
    for label in labels:
        tp, fp, fn = _counts_at(candidates, gold_rows, label, thresholds[label])
        tot_tp += tp
        tot_fp += fp
        tot_fn += fn
        if tp + fp + fn == 0:
            continue
        precision, recall, f1 = _prf(tp, fp, fn)
        per_label.append(
            LabelScore(
                label=label,
                support=tp + fn,
                tp=tp,
                fp=fp,
                fn=fn,
                precision=round(precision, 3),
                recall=round(recall, 3),
                f1=round(f1, 3),
            )
        )
        if tp + fn > 0:
            gold_f1s.append(f1)
    micro_p, micro_r, micro_f1 = _prf(tot_tp, tot_fp, tot_fn)
    macro_f1 = sum(gold_f1s) / len(gold_f1s) if gold_f1s else 0.0
    return NerReport(
        checkpoint=checkpoint_name,
        num_examples=len(gold_rows),
        threshold=-1.0,
        micro_precision=round(micro_p, 3),
        micro_recall=round(micro_r, 3),
        micro_f1=round(micro_f1, 3),
        macro_f1=round(macro_f1, 3),
        per_label=sorted(per_label, key=lambda s: -s.support),
        per_label_thresholds=thresholds,
    )


def evaluate_checkpoint_tuned(
    checkpoint: str,
    val_path: Path,
    test_path: Path,
    *,
    adapter: str | None = None,
    labels: Sequence[str] = LABEL_NAMES,
    floor: float = 0.05,
    beta: float = 1.0,
    batch_size: int = 16,
) -> tuple[NerReport, NerReport]:
    """Tune per-label thresholds on ``val`` and score ``test`` both ways.

    Returns ``(fixed_0.5_report, tuned_report)`` so the calibration gain over a
    flat 0.5 threshold is explicit.
    """
    model = GLiNER2.from_pretrained(checkpoint)
    name = checkpoint
    if adapter is not None:
        model.load_adapter(adapter)
        name = f"{checkpoint} + {adapter}"

    val_gold = _gold_from_jsonl(val_path)
    val_cand = _predict_candidates(
        model, [t for t, _ in val_gold], labels, floor=floor, batch_size=batch_size
    )
    thresholds = tune_thresholds(val_cand, val_gold, labels=labels, beta=beta)

    test_gold = _gold_from_jsonl(test_path)
    test_cand = _predict_candidates(
        model, [t for t, _ in test_gold], labels, floor=floor, batch_size=batch_size
    )
    fixed = _report_from_candidates(
        test_cand,
        test_gold,
        checkpoint_name=name,
        labels=labels,
        thresholds=dict.fromkeys(labels, 0.5),
    )
    tuned = _report_from_candidates(
        test_cand,
        test_gold,
        checkpoint_name=name,
        labels=labels,
        thresholds=thresholds,
    )
    return fixed, tuned
