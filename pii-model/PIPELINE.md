# Ranymizer PII pipeline — how it fits together

Goal: train **our own** Swedish-PII GLiNER2 model on **synthetic** data we generate,
and measure it. Everything below runs locally; the only "AI" used for *generation*
and *data-judging* is your own **Gemma on the vLLM server** (`localhost:8003`).

---

## 1. The straight-line pipeline (what exists today)

```
                         your vLLM Gemma (localhost:8003)
                                   │  (used by generate + evaluate)
                                   ▼
┌───────────┐   ┌───────────┐   ┌───────────┐   ┌─────────────┐   ┌─────────────┐
│ 1 generate│──▶│ 2 convert │──▶│  3 train  │──▶│4 evaluate    │   │5 eval-model │
│  (synth)  │   │ (to JSONL)│   │ (GLiNER2) │   │  (DATA QC)  │   │ (MODEL P/R/F1)
└───────────┘   └───────────┘   └───────────┘   └─────────────┘   └─────────────┘
 parquet         train/val/test   checkpoint      quality report    F1 report
                 .jsonl           (LoRA/full)     (report.md)        (report.md)

CLI:  pii-model generate → convert → train → evaluate → eval-model
```

What each stage **means**, concretely:

| stage | command | what it does | needs |
|---|---|---|---|
| **1 generate** | `pii-model generate` | Gemma writes 1000s of realistic Swedish docs (invoices, ID cards, journals…) **and labels every PII span**. Faker supplies the fake names/personnummer (no real people). | vLLM Gemma |
| **2 convert** | `pii-model convert` | Turns the parquet into **GLiNER2 training JSONL** (`{input, output}`), drops hallucinated/duplicate rows, and splits **train/val/test with no person leaking across splits**. | — |
| **3 train** | `pii-model train` | Fine-tunes a GLiNER2 checkpoint on our JSONL. **LoRA** (tiny adapter) or **full**. | GPU |
| **4 evaluate** | `pii-model evaluate` | **Judges the DATA**: is it natural Swedish, grounded in the seeds, fully labelled, GDPR-safe? (LLM-as-judge = your Gemma.) | vLLM Gemma |
| **5 eval-model** | `pii-model eval-model` | **Scores the MODEL**: span-level precision/recall/F1 on the held-out test set. Run on the off-the-shelf checkpoint and again `--adapter` to compare before/after. | GPU |

> **The two evals are different things.**
> `evaluate` (4) = "is my **training data** good?"  →  judges DATA, uses Gemma.
> `eval-model` (5) = "is my **trained model** good?"  →  scores MODEL, no Gemma.

---

## 2. Loop A — data-quality feedback (deepeval → filter)

**What it means:** use the data-judge (stage 4) to **throw away or regenerate the
bad synthetic rows before training**, so the model only ever learns from clean data.

```
        ┌──────────────────────────────────────────────┐
        │                                                │
        ▼                                                │ (drop / regenerate
   ┌──────────┐    ┌──────────────┐    ┌──────────┐      │  the rows that fail)
   │ generate │───▶│ evaluate     │───▶│  GATE    │──────┘
   │  (Gemma) │    │ (judge each  │    │ keep if  │
   └──────────┘    │  row: Swedish│    │ scores ≥ │────▶ clean rows ──▶ convert ──▶ train
                   │  grounded,   │    │ threshold│
                   │  complete,   │    └──────────┘
                   │  safe)       │
                   └──────────────┘
```

**Status: the judge exists, but its scores are NOT yet enforced.** Today `convert`
only drops rows on the *deterministic* check (`entities_validated`, i.e. "is every
mention literally in the text") + exact-duplicate text. The LLM-judge scores
(swedish_naturalness, seed_grounding, …) are **reported but never used to filter**.

**How we "fix Loop A" — concretely (small change):**
1. Generate **with the judge on** (`config.judge = true`) so each row carries the
   judge score columns (`*_score`, `pii_quality_judge_result`). *(The recipe already
   adds these when judge is on.)*
2. In `convert.py`, where it currently does
   `df = df[df["entities_validated"] == True]`, **also** drop rows whose judge gate
   failed — e.g. add a `--min-judge-score` option and keep only
   `min(swedish_naturalness_score, seed_grounding_score, label_completeness_score) ≥ N`.
3. (Optional) instead of dropping, **regenerate** failed rows — a second `generate`
   pass for the shortfall.

That's it: Loop A = wire the gate that already exists into `convert`. ~1 file.

---

## 3. Loop B — model-weakness feedback (eval-model → targeted generation)

**What it means:** after training, find **what the MODEL is bad at**, then **generate
more data of exactly those cases** and retrain. Classic active-learning / hard-example
mining — cheap here because the data is synthetic and our generator is config-driven.

```
        ┌───────────────────────────────────────────────────────────────┐
        │                                                                 │
        ▼                                                                 │
   ┌──────────┐   ┌────────┐   ┌────────────┐   ┌──────────────┐   ┌──────────────┐
   │ generate │──▶│ train  │──▶│ eval-model │──▶│ find WEAK     │──▶│ re-weight    │
   │ (config) │   │        │   │ per label  │   │ slices        │   │ SynthesisCfg │
   └──────────┘   └────────┘   │ + per slice│   │ e.g. iban F1  │   │ ↑ those      │
        ▲                      └────────────┘   │ =0.4, table   │   │ genres/      │
        │                                       │ layout weak,  │   │ layouts/     │
        └───────────────────────────────────────│ 3-subject weak│◀──│ subjects     │
                       (loop back with biased config)            └──────────────┘
```

Example one turn of the loop:
```
eval-model says:   iban F1 = 0.40   |   table_row layout weak   |   3-subject rows weak
                          │
                          ▼   (re-weight the generator — just config numbers)
SynthesisConfig:   genres["kortbetalning"] ↑ , layouts["table_row"] ↑ , subject_counts["3"] ↑
                          │
                          ▼
generate v2  →  merge with v1  →  retrain  →  eval-model again  →  iban F1 climbs
```

**Why it fits us:** the synthesizer is **config-driven** (`SynthesisConfig`: `genres`,
`layouts`, `subject_counts`, label weights), so "make more of X" = change a number.

**What's missing to build Loop B:**
1. **Per-slice eval** — `eval-model` gives per-**label** F1 but not per-**genre/layout/
   subject-count** (the JSONL doesn't carry that metadata yet). Need to thread
   `text_type` / `text_layout` / `num_subjects` into the test rows and score per slice.
2. **A config-bias step** — turn a weak-slice report into a re-weighted `SynthesisConfig`.
3. **A small orchestrator** — the generate→train→eval→re-weight loop.

---

## 4. Loop A vs Loop B — which, and when

| | Loop A (data quality) | Loop B (model weakness) |
|---|---|---|
| Driven by | **data** judge (deepeval / Gemma) | **model** eval (P/R/F1) |
| Improves | cleanliness of training data | model accuracy where it's weak |
| Size | ~1-file change (wire gate into convert) | real feature (~per-slice eval + bias + loop) |
| Needs first | nothing | **a trained model + its eval** (to know weaknesses) |

**Sequencing:** Loop B is the higher-value one, but it **depends on a measured weakness**
— so we must run **train → eval-model once** before we can target anything. Loop A is
independent and can be wired anytime. Recommended order:

```
   run the (gated) experiment → read eval-model weak labels
        → THEN build Loop B against real data    (Loop A whenever — it's cheap)
```

---

## 5. File map

```
src/ranymizer_pii/cli.py            generate · convert · train · evaluate · eval-model
packages/synthesizer/               the config-driven DD recipe (SynthesisConfig, prompts)
packages/trainer/convert.py         parquet → GLiNER2 JSONL, leakage-safe split, filtering
packages/trainer/train.py           GLiNER2Trainer (LoRA / full)
packages/trainer/eval.py            MODEL eval — span P/R/F1   (Loop B signal)
packages/evaluation/                DATA eval — deepeval judge (Loop A signal)
```
