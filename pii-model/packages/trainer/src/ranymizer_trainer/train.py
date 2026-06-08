# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Train a GLiNER2 model (LoRA pilot or full fine-tune) on the converted JSONL.

Mirrors the pattern from `fastino-ai-gliner2` tutorials 9-10:
  - LoRA pilot:   `--mode lora`  (default)  -- ~5MB adapter, fast.
  - Full FT:      `--mode full`             -- ~450MB checkpoint, slower.

Run:
    pii-model train --mode lora --num-epochs 10
    pii-model train --mode full --num-epochs 15 --batch-size 16
"""

from __future__ import annotations

import logging
from pathlib import Path

from gliner2 import GLiNER2
from gliner2.training.trainer import GLiNER2Trainer, TrainingConfig

from ranymizer_trainer.modes import TrainMode

log = logging.getLogger(__name__)


def train(
    *,
    mode: TrainMode = TrainMode.LORA,
    base_model: str = "fastino/gliner2-base-v1",
    data_dir: Path,
    output_dir: Path | None = None,
    num_epochs: int = 10,
    batch_size: int = 8,
    encoder_lr: float = 1e-5,
    task_lr: float = 5e-4,
    lora_r: int = 16,
    lora_alpha: float = 32.0,
    lora_dropout: float = 0.05,
    fp16: bool = True,
    wandb: bool = False,
    wandb_project: str = "ranymizer-pii",
) -> None:
    """Train a GLiNER2 model (LoRA pilot or full fine-tune) on the JSONL splits."""
    output_dir = output_dir or (
        Path.cwd() / "outputs" / "checkpoints" / f"{mode.value}_se"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    train_path = data_dir / "train.jsonl"
    val_path = data_dir / "val.jsonl"
    if not train_path.exists():
        raise FileNotFoundError(f"Missing {train_path}. Run `pii-model convert` first.")

    use_lora = mode is TrainMode.LORA
    config = TrainingConfig(
        output_dir=str(output_dir),
        experiment_name=f"ranymizer_pii_{mode.value}",
        num_epochs=num_epochs,
        batch_size=batch_size,
        encoder_lr=encoder_lr,
        task_lr=task_lr,
        warmup_ratio=0.1,
        scheduler_type="cosine",
        fp16=fp16,
        eval_strategy="epoch",
        save_best=True,
        early_stopping=True,
        early_stopping_patience=3,
        report_to_wandb=wandb,
        wandb_project=wandb_project,
        use_lora=use_lora,
        lora_r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        lora_target_modules=["encoder"] if use_lora else [],
        save_adapter_only=use_lora,
    )

    log.info("Loading base model: %s", base_model)
    model = GLiNER2.from_pretrained(base_model)

    trainer = GLiNER2Trainer(model, config)
    results = trainer.train(
        train_data=str(train_path),
        eval_data=str(val_path) if val_path.exists() else None,
    )

    log.info("Training complete.")
    if results.get("best_metric") is not None:
        log.info("  Best val loss: %.4f", results["best_metric"])
    log.info("  Total steps:   %s", results.get("total_steps"))
    log.info("  Wall time:     %.1f min", results.get("total_time_seconds", 0) / 60)
    artefact_kind = "adapter only" if use_lora else "full model"
    log.info("Artefact: %s/final/  (%s)", output_dir, artefact_kind)
    log.info("Next step: pii-model evaluate")
