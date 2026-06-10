# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""`pii-model` — the CLI. Thin typer wrappers, one command per pipeline stage.

Each command builds a config + endpoint and delegates to a workspace package.
Heavy stage dependencies (data-designer, gliner2/torch, deepeval) are imported
lazily *inside* each command, so `--help` and unrelated commands stay instant.
"""

import logging
from pathlib import Path

import typer
from ranymizer_trainer.modes import TrainMode
from rich.console import Console
from rich.markup import escape

from ranymizer_pii.settings import settings

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    help="Ranymizer Swedish-PII pipeline: generate -> convert -> train -> evaluate.",
)
console = Console()
err_console = Console(stderr=True)


@app.command()
def generate(
    num: int = typer.Option(1000, help="Number of synthetic rows to generate."),
    dataset_name: str = typer.Option("swedish_pii_synthetic", help="NDD dataset name."),
    out: Path = typer.Option(Path("data/raw"), help="Where parquet artifacts land."),
    base_url: str | None = typer.Option(None, help="Override the LLM base URL."),
    model: str | None = typer.Option(None, help="Override the served model id."),
    faker_seed: int | None = typer.Option(
        None, help="Seed Faker for reproducible PII seeds."
    ),
    concurrency: int | None = typer.Option(
        None,
        "--concurrency",
        min=1,
        help="In-flight LLM requests (overrides the endpoint default of 32). "
        "Throughput scales to ~48-96 on the local vLLM; the server's "
        "--max-num-seqs must allow at least this many.",
    ),
    config_file: Path | None = typer.Option(
        None,
        "--config",
        help="Path to a JSON file with SynthesisConfig overrides "
        "(genres, layouts, subject_counts, no_pii_fraction, "
        "foreign_locale_fraction, ...).",
    ),
    preview: bool = typer.Option(
        False, help="Preview a few rows without writing a dataset."
    ),
) -> None:
    """Generate synthetic Swedish PII rows with the LLM (NeMo Data Designer).

    OUTPUT format is fixed to GLiNER2; --config tunes WHAT is synthesized.
    """
    from ranymizer_synthesizer import SynthesisConfig
    from ranymizer_synthesizer import create as run_create
    from ranymizer_synthesizer import preview as run_preview

    if config_file is not None:
        try:
            config = SynthesisConfig.model_validate_json(config_file.read_text())
        except (OSError, ValueError) as exc:
            err_console.print(
                f"[bold red]error:[/bold red] could not load config "
                f"'{config_file}': {escape(str(exc))}"
            )
            raise SystemExit(1) from exc
        if faker_seed is not None:
            config = config.model_copy(update={"faker_seed": faker_seed})
    else:
        config = SynthesisConfig(faker_seed=faker_seed)
    endpoint = settings.endpoint(base_url=base_url, model=model)
    if concurrency is not None:
        endpoint = endpoint.model_copy(update={"max_parallel_requests": concurrency})
    if preview:
        result = run_preview(config, endpoint, num_records=num, artifact_path=out)
        dataset = result.dataset
        if dataset is None:
            err_console.print("[bold red]error:[/bold red] preview returned no dataset")
            raise SystemExit(1)
        for _, row in dataset.iterrows():
            console.print(
                f"\n[bold cyan]{row.get('text_type')} / {row.get('text_layout')}[/bold cyan]"
            )
            console.print(str(row.get("text")), markup=False)
            console.print(f"entities: {row.get('entities')}", markup=False)
        return
    run_create(
        config,
        endpoint,
        num_records=num,
        dataset_name=dataset_name,
        artifact_path=out,
    )
    console.print(
        f"[green]✓[/green] wrote dataset '{dataset_name}' ({num} rows) under {out}"
    )


@app.command()
def convert(
    raw: Path = typer.Option(
        Path("data/raw"), help="Parquet dir produced by `generate`."
    ),
    out: Path = typer.Option(
        Path("data"), help="Where JSONL splits + dataset card land."
    ),
    train_ratio: float = typer.Option(0.9),
    val_ratio: float = typer.Option(0.05),
    seed: int = typer.Option(42),
    ocr_augment: bool = typer.Option(
        False, help="Append span-preserving OCR-noised variants."
    ),
    ocr_rate: float = typer.Option(0.06),
    ocr_seed: int = typer.Option(1234),
    dedup_threshold: float | None = typer.Option(
        None,
        "--dedup-threshold",
        min=0.5,
        max=1.0,
        help="If set (e.g. 0.97), drop semantic near-duplicate texts via the local "
        "embedding endpoint (:8001) before splitting. Off by default. "
        "Range [0.5, 1.0] — lower cosine thresholds match nearly everything.",
    ),
) -> None:
    """Convert generated parquet into GLiNER2 train/val/test JSONL + dataset card."""
    from ranymizer_trainer.convert import convert as run_convert

    run_convert(
        raw_path=raw,
        out_dir=out,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        seed=seed,
        ocr_augment=ocr_augment,
        ocr_rate=ocr_rate,
        ocr_seed=ocr_seed,
        dedup_threshold=dedup_threshold,
    )


@app.command()
def train(
    mode: TrainMode = typer.Option(
        TrainMode.LORA, help="LoRA pilot (default) or full fine-tune."
    ),
    base_model: str = typer.Option("fastino/gliner2-base-v1"),
    data: Path = typer.Option(Path("data"), help="Dir holding train/val/test JSONL."),
    out: Path | None = typer.Option(None, help="Checkpoint output dir."),
    num_epochs: int = typer.Option(10),
    batch_size: int = typer.Option(8),
) -> None:
    """Train a GLiNER2 model (LoRA pilot or full fine-tune) on the JSONL splits."""
    from ranymizer_trainer.train import train as run_train

    run_train(
        mode=mode,
        base_model=base_model,
        data_dir=data,
        output_dir=out,
        num_epochs=num_epochs,
        batch_size=batch_size,
    )


@app.command()
def evaluate(
    data: Path = typer.Option(Path("data/raw"), help="Parquet/JSONL rows to judge."),
    num: int | None = typer.Option(None, help="Cap rows judged (None = all)."),
    gate_only: bool = typer.Option(
        False, help="Cheap binary gate instead of the full rubric."
    ),
    out: Path = typer.Option(
        Path("outputs"), help="Directory for JSON/Markdown reports."
    ),
    base_url: str | None = typer.Option(None, help="Override the judge LLM base URL."),
    model: str | None = typer.Option(None, help="Override the judge model id."),
) -> None:
    """LLM-as-judge data-quality evaluation (DeepEval) of generated rows."""
    from ranymizer_evaluation.run import evaluate_data

    endpoint = settings.endpoint(base_url=base_url, model=model)
    evaluate_data(
        endpoint=endpoint, data=data, num=num, gate_only=gate_only, out_dir=out
    )


@app.command(name="eval-model")
def eval_model(
    checkpoint: str = typer.Option(
        "fastino/gliner2-privacy-filter-PII-multi",
        help="GLiNER2 checkpoint to score (HF id or local dir).",
    ),
    data: Path = typer.Option(
        Path("data"), help="Dir holding the gold test.jsonl (from `convert`)."
    ),
    adapter: Path | None = typer.Option(
        None, help="Optional LoRA adapter dir, e.g. outputs/checkpoints/lora_se/final."
    ),
    threshold: float = typer.Option(0.5, help="Span confidence threshold."),
    out: Path = typer.Option(Path("outputs"), help="Where to write the JSON report."),
) -> None:
    """Score a GLiNER2 model: span-level NER precision/recall/F1 on the test split.

    Measures the MODEL (vs `evaluate`, which judges the DATA). Run it on the
    off-the-shelf checkpoint and again with --adapter to compare before/after.
    """
    from ranymizer_trainer.eval import evaluate_checkpoint

    report = evaluate_checkpoint(
        checkpoint,
        data / "test.jsonl",
        adapter=str(adapter) if adapter else None,
        threshold=threshold,
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "model_ner_eval.json").write_text(report.model_dump_json(indent=2))
    console.print(
        f"[bold]{report.checkpoint}[/bold]  ({report.num_examples} test rows)\n"
        f"micro P/R/F1 = {report.micro_precision:.3f} / {report.micro_recall:.3f} / "
        f"{report.micro_f1:.3f}   macro F1 = {report.macro_f1:.3f}"
    )
    for s in report.per_label[:12]:
        console.print(
            f"  {s.label:20s} P={s.precision:.2f} R={s.recall:.2f} "
            f"F1={s.f1:.2f}  (support={s.support})"
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        app()
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"[bold red]error:[/bold red] {escape(str(exc))}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
