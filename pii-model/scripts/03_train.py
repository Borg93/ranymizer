# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""
Train a GLiNER2 model (LoRA pilot or full fine-tune) on the converted JSONL.

Mirrors the pattern from `fastino-ai-gliner2` tutorials 9–10:
  - LoRA pilot:   `--mode lora`  (default)  — ~5MB adapter, fast.
  - Full FT:      `--mode full`             — ~450MB checkpoint, slower.

Run:
    uv run scripts/03_train.py --mode lora --num-epochs 10
    uv run scripts/03_train.py --mode full --num-epochs 15 --batch-size 16
"""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from gliner2 import GLiNER2
from gliner2.training.trainer import GLiNER2Trainer, TrainingConfig


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--mode", choices=["lora", "full"], default="lora")
    parser.add_argument(
        "--base-model",
        type=str,
        default="fastino/gliner2-base-v1",
        help="HF base checkpoint to start from.",
    )
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to outputs/checkpoints/<mode>_se",
    )
    parser.add_argument("--num-epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--encoder-lr", type=float, default=1e-5)
    parser.add_argument("--task-lr", type=float, default=5e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=float, default=32.0)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--fp16", action="store_true", default=True)
    parser.add_argument("--no-fp16", dest="fp16", action="store_false")
    parser.add_argument(
        "--wandb",
        action="store_true",
        help="Log to Weights & Biases (set WANDB_API_KEY).",
    )
    parser.add_argument("--wandb-project", type=str, default="ranymizer-pii")
    args = parser.parse_args()

    output_dir = args.output_dir or (
        Path(__file__).resolve().parent.parent
        / "outputs"
        / "checkpoints"
        / f"{args.mode}_se"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    train_path = args.data_dir / "train.jsonl"
    val_path = args.data_dir / "val.jsonl"
    if not train_path.exists():
        raise SystemExit(f"Missing {train_path}. Run 02_to_gliner2_jsonl.py first.")

    common = dict(
        output_dir=str(output_dir),
        experiment_name=f"ranymizer_pii_{args.mode}",
        num_epochs=args.num_epochs,
        batch_size=args.batch_size,
        encoder_lr=args.encoder_lr,
        task_lr=args.task_lr,
        warmup_ratio=0.1,
        scheduler_type="cosine",
        fp16=args.fp16,
        eval_strategy="epoch",
        save_best=True,
        early_stopping=True,
        early_stopping_patience=3,
        report_to_wandb=args.wandb,
        wandb_project=args.wandb_project,
    )

    if args.mode == "lora":
        config = TrainingConfig(
            **common,
            use_lora=True,
            lora_r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            lora_target_modules=["encoder"],  # query/key/value/dense — see tutorial 10
            save_adapter_only=True,
        )
    else:
        config = TrainingConfig(**common)

    print(f"Loading base model: {args.base_model}")
    model = GLiNER2.from_pretrained(args.base_model)

    trainer = GLiNER2Trainer(model, config)
    results = trainer.train(
        train_data=str(train_path),
        eval_data=str(val_path) if val_path.exists() else None,
    )

    print("\nTraining complete.")
    if results.get("best_metric") is not None:
        print(f"  Best val loss: {results['best_metric']:.4f}")
    print(f"  Total steps:   {results.get('total_steps')}")
    print(f"  Wall time:     {results.get('total_time_seconds', 0) / 60:.1f} min")
    print(f"\nArtefact: {output_dir}/final/  ({'adapter only' if args.mode == 'lora' else 'full model'})")
    print("Next step: scripts/04_evaluate.py (TBD)")


if __name__ == "__main__":
    main()
