# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""LLM-as-judge data-quality evaluation of generated Swedish PII rows.

Loads recipe output rows (a parquet directory such as ``data/raw`` or a JSONL
file), builds DeepEval ``LLMTestCase``s, and judges them with the user's own
local Gemma via an OpenAI-compatible endpoint (``LocalOpenAIJudge``) — never
OpenAI. Writes a JSON + Markdown report to ``outputs/``.

The judge endpoint is an injected :class:`ranymizer_pii_core.ModelEndpoint` (the
same value object that drives generation), so the caller decides which server
does the judging.

Modes:
    (default)    Run all four GEval metrics + the data_quality_gate DAG across
                 all rows via ``deepeval.evaluate`` and aggregate.
    gate_only    Per-row ``measure`` of only the ``data_quality_gate`` DAG
                 metric (cheaper: one judging chain per row).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from ranymizer_pii_core import ModelEndpoint

from ranymizer_evaluation.judge import LocalOpenAIJudge
from ranymizer_evaluation.metrics import build_metrics, row_to_test_case

__all__ = ["evaluate_data"]

log = logging.getLogger(__name__)


def _load_rows(data_path: Path, limit: int | None) -> list[dict]:
    """Load rows from a parquet directory/file or a JSONL file."""
    if data_path.is_dir():
        frames = [pd.read_parquet(p) for p in sorted(data_path.glob("*.parquet"))]
        if not frames:
            raise FileNotFoundError(f"No .parquet files under {data_path}")
        df = pd.concat(frames, ignore_index=True)
        rows = df.to_dict(orient="records")
    elif data_path.suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in data_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    elif data_path.suffix == ".parquet":
        rows = pd.read_parquet(data_path).to_dict(orient="records")
    else:
        raise ValueError(
            f"Unsupported data path: {data_path} "
            "(expected a parquet dir/file or a .jsonl file)"
        )
    if limit is not None:
        rows = rows[:limit]
    return rows


def _gate_only(rows: list[dict], judge: LocalOpenAIJudge) -> dict:
    """Per-row measure of just the data_quality_gate DAG metric."""
    metrics = build_metrics(judge)
    gate = metrics.data_quality_gate
    results: list[dict] = []
    for i, row in enumerate(rows):
        test_case = row_to_test_case(row)
        score = gate.measure(test_case)
        results.append(
            {
                "index": i,
                "score": score,
                "success": bool(gate.success),
                "reason": gate.reason,
            }
        )
        log.info(
            f"  row {i:>4}  gate={score:.3f}  "
            f"{'PASS' if gate.success else 'FAIL'}  {gate.reason or ''}"
        )
    passed = sum(1 for r in results if r["success"])
    return {
        "mode": "gate-only",
        "metric": "data_quality_gate",
        "rows": len(results),
        "passed": passed,
        "pass_rate": (passed / len(results)) if results else 0.0,
        "results": results,
    }


def _full(rows: list[dict], judge: LocalOpenAIJudge) -> dict:
    """Run all metrics across all rows via deepeval.evaluate and aggregate."""
    from deepeval import evaluate
    from deepeval.evaluate.configs import DisplayConfig

    metrics = build_metrics(judge)
    test_cases = [row_to_test_case(row) for row in rows]
    result = evaluate(
        test_cases=test_cases,
        metrics=metrics.all_metrics,
        display_config=DisplayConfig(print_results=False, show_indicator=True),
    )

    per_metric: dict[str, dict] = {}
    per_row: list[dict] = []
    for tr in result.test_results:
        row_metrics: dict[str, float | None] = {}
        for md in tr.metrics_data or []:
            row_metrics[md.name] = md.score
            agg = per_metric.setdefault(
                md.name, {"scores": [], "passed": 0, "count": 0}
            )
            if md.score is not None:
                agg["scores"].append(md.score)
            agg["count"] += 1
            if md.success:
                agg["passed"] += 1
        per_row.append({"index": tr.index, "metrics": row_metrics})

    summary: dict[str, dict] = {}
    for name, agg in per_metric.items():
        scores = agg["scores"]
        summary[name] = {
            "mean_score": (sum(scores) / len(scores)) if scores else None,
            "passed": agg["passed"],
            "count": agg["count"],
            "pass_rate": (agg["passed"] / agg["count"]) if agg["count"] else 0.0,
        }
    return {
        "mode": "full",
        "rows": len(rows),
        "summary": summary,
        "results": per_row,
    }


def _write_report(
    report: dict, base_url: str, model: str, out_dir: Path
) -> tuple[Path, Path]:
    """Write JSON + Markdown reports to ``out_dir`` and return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = {
        **report,
        "generated_at": stamp,
        "judge_base_url": base_url,
        "judge_model": model,
    }
    json_path = out_dir / f"data_quality_{stamp}.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Swedish PII data-quality evaluation",
        "",
        f"- Generated: `{stamp}`",
        f"- Judge: `{model}` @ `{base_url}`",
        f"- Mode: `{report['mode']}`",
        f"- Rows judged: {report['rows']}",
        "",
    ]
    if report["mode"] == "gate-only":
        lines += [
            f"- data_quality_gate pass rate: "
            f"**{report['pass_rate']:.1%}** "
            f"({report['passed']}/{report['rows']})",
        ]
    else:
        lines += [
            "## Metric summary",
            "",
            "| metric | mean score | pass rate |",
            "| --- | --- | --- |",
        ]
        for name, agg in report["summary"].items():
            mean = "-" if agg["mean_score"] is None else f"{agg['mean_score']:.3f}"
            lines.append(f"| {name} | {mean} | {agg['pass_rate']:.1%} |")
    md_path = out_dir / f"data_quality_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def evaluate_data(
    *,
    endpoint: ModelEndpoint,
    data: Path,
    num: int | None,
    gate_only: bool,
    out_dir: Path,
) -> None:
    """LLM-as-judge data-quality evaluation of generated Swedish PII rows.

    The judge LLM is the injected ``endpoint`` (a shared-kernel
    :class:`ranymizer_pii_core.ModelEndpoint`) — never OpenAI.
    """
    data_path = data
    if not data_path.is_absolute():
        data_path = Path.cwd() / data_path
    rows = _load_rows(data_path, num)
    if not rows:
        raise ValueError(f"No rows loaded from {data_path}")

    judge = LocalOpenAIJudge(endpoint)
    log.info(
        f"Judge: {endpoint.model} @ {endpoint.base_url}   "
        f"rows: {len(rows)}   mode: {'gate-only' if gate_only else 'full'}"
    )

    start = time.perf_counter()
    report = _gate_only(rows, judge) if gate_only else _full(rows, judge)
    elapsed = time.perf_counter() - start

    json_path, md_path = _write_report(
        report, endpoint.base_url, endpoint.model, out_dir
    )
    log.info(f"\nJudged {len(rows)} rows in {elapsed:.1f}s.")
    log.info(f"  JSON report:     {json_path}")
    log.info(f"  Markdown report: {md_path}")
