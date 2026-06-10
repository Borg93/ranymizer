# 10k Swedish-PII run — results (2026-06-10)

End-to-end: generate 10k (Gemma 4 / local :8003 for 5k + ra.se cluster for 5k) →
convert (entity-validation + semantic dedup) → leakage-safe split → train
LoRA + full FT → span-level NER eval on a held-out test split.

## Dataset (reusable)

`data/se_10k/` — leakage-safe splits + `dataset_card.md`.

| | rows |
|---|---|
| generated | 10,000 |
| after entity-validation | 9,990 (99.9%) |
| after exact + **semantic dedup** (cos≥0.97, dropped 98) | 9,889 |
| **train / val / test** | **8,854 / 522 / 513** |

## Model NER — span-level, 513 held-out test rows

| metric | base (off-the-shelf) | **+ LoRA** | + full FT |
|---|---|---|---|
| micro precision | 0.717 | 0.720 | 0.488 |
| micro recall | 0.802 | **0.978** | 0.971 |
| **micro F1** | 0.757 | **0.830** | 0.650 |
| macro F1 | 0.466 | **0.559** | 0.460 |
| TP / FP / FN | 2208 / 870 / 544 | 2692 / 1046 / 60 | 2672 / **2798** / 80 |

**Ship the LoRA adapter** (`outputs/checkpoints/lora_se_10k/final/`, ~10 MB):
micro F1 **+0.073**, macro **+0.093**, recall **0.80 → 0.98** over the base
checkpoint. Big per-label gains: person 0.89→0.99, personnummer 0.77→0.97,
health 0.45→0.92, address 0.83→0.95, phone 0.59→0.74.

## Is the synthetic data working, or just overfitting?

**Working — it generalizes.** The eval is on a **held-out test split the model
never trained on**, and LoRA lifts held-out micro-F1 0.757 → 0.830. Memorization
would not transfer to unseen rows.

**No data leakage** (verified): **0** train↔test exact-text overlaps and **0 / 598**
test personnummers present in train — the group-by-seed-identity split + distinct
Faker seeds across the two halves keep every subject in a single split.

**Honest caveat:** "held-out" is the *same synthetic distribution* (same recipe /
Faker / Gemma). This proves in-distribution generalization, **not** transfer to
real Swedish documents — that needs a real gold benchmark (e.g. SPY), which we
don't have yet.

## Why full FT lost (it over-tags, not classic memorization)

Full fine-tune kept high recall (0.971) but **precision collapsed to 0.488** —
FP exploded to **2798** (vs LoRA's 1046). It sprays rare-label predictions:

| label | support | TP | **FP** | precision |
|---|---|---|---|---|
| bank | 10 | 10 | **457** | 0.02 |
| card_number | 36 | 33 | **411** | 0.07 |
| iban | 11 | 11 | **411** | 0.03 |
| ip_address | 26 | 26 | **401** | 0.06 |
| religion_ethnicity | 1 | 1 | **291** | 0.00 |

Full FT (10 epochs, all encoder weights) overfit the *label distribution* and
lost the base model's calibration. LoRA's low-rank update preserved it. Same
lesson as the earlier 2k run.

## DeepEval data-quality

**Did not complete** — the 200-row sampled judge stage hit a `TimeoutError`
(rc=1). No LLM quality scores for this run. Re-runnable with
`pii-model evaluate --data <parquet> --num 200`. Note the data already passed the
**deterministic** checks (99.9% entity-validated, deduped).

## Reuse

```bash
# retrain from the saved splits
pii-model train --mode lora --data data/se_10k --out outputs/checkpoints/lora_se_10k

# score any checkpoint on the held-out test set
pii-model eval-model --checkpoint fastino/gliner2-base-v1 \
  --adapter outputs/checkpoints/lora_se_10k/final --data data/se_10k
```

Eval JSONs: `outputs/eval_10k/eval_{before,lora,full}.json` (git-ignored, local).
Full-FT checkpoint discarded (degraded, 804 MB).
