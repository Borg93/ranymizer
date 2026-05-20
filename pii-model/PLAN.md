# pii-model — plan

Train **Ranymizer's** Swedish PII detector. The model produced here is the
GLiNER2 checkpoint that `backend/app.py` already loads (currently
`fastino/gliner2-privacy-filter-PII-multi`) — once we have our own, we swap
it in, then ONNX-export it for the Tauri target (see `../TODO.md`).

Two pipelines feed each other:

1. **NeMo Data Designer (NDD)** generates synthetic, label-conditioned
   Swedish PII training data (one JSONL row = one `InputExample`).
2. **GLiNER2 trainer** (`fastino-ai-gliner2`) fine-tunes
   `fastino/gliner2-base-v1` on that data, with an optional LoRA adapter
   per locale.

Everything lives in `pii-model/` and is independent of the desktop / showcase
frontends; only the final checkpoint crosses the boundary.

---

## 0. Why this exists

The categories Ranymizer redacts (see
`frontend/src/lib/components/Landing.svelte` and
`frontend/src/lib/engine/models.ts`):

| label                 | description                                  |
|-----------------------|----------------------------------------------|
| `person`              | Names of people                              |
| `email`               | Email addresses                              |
| `phone`               | Phone numbers (Swedish + international)      |
| `address`             | Street addresses, postal codes               |
| `personnummer`        | Swedish personal ID (YYYYMMDD-XXXX)          |
| `organisationsnummer` | Swedish org. number (XXXXXX-XXXX)            |
| `bank`                | Bankgiro / Plusgiro / IBAN / account numbers |
| `date`                | Calendar dates                               |
| `url`                 | URLs                                         |

The off-the-shelf GLiNER2-PII model is multilingual but generic. Swedish
identifiers (`personnummer`, `organisationsnummer`, `bankgiro`) are
underrepresented in its training set. We fix that with targeted synthetic
data + light fine-tuning.

---

## 1. Folder layout (already scaffolded)

```
pii-model/
├── PLAN.md              # this file
├── pyproject.toml       # uv-managed; gliner2[local] + data-designer
├── configs/
│   └── ndd_swedish_pii.py          # ✅ NeMo Data Designer recipe (REAL)
├── scripts/
│   ├── 01_generate_synthetic.py    # ✅ NDD driver → data/raw/*.parquet
│   ├── 02_to_gliner2_jsonl.py      # ✅ parquet → gliner2 InputExample jsonl
│   ├── 03_train.py                 # ✅ GLiNER2Trainer wrapper (LoRA or full FT)
│   ├── 04_evaluate.py              # 🔲 TODO — held-out + real-screenshot eval
│   └── 05_export_onnx.py           # 🔲 TODO — checkpoint → ONNX (see ../TODO.md §2)
├── data/
│   ├── raw/                        # NDD output (gitignored)
│   ├── train.jsonl                 # converted training set (gitignored)
│   ├── val.jsonl
│   └── real_eval/                  # hand-labelled real screenshots (S3, NOT git)
└── outputs/
    ├── checkpoints/                # GLiNER2Trainer output_dir (gitignored)
    └── onnx/                       # final artefacts to ship (gitignored)
```

The `pyproject.toml` pins `gliner2[local]>=1.3.1` (gives us the `GLiNER2`
class, the `Extractor` model, `apply_lora`, `GLiNER2Trainer`, `TrainingConfig`,
`InputExample`, `TrainingDataset`) and `data-designer>=0.5.6` (gives us
`DataDesignerConfigBuilder`, `SamplerColumnConfig`, `LLMStructuredColumnConfig`,
`CustomColumnConfig`, etc — same surface as the NDD recipes upstream uses).

---

## 2. Synthetic data with NeMo Data Designer

Reference: `nvidia/NeMo-Data-Designer` v0.5+, recipes in this skill's docs.

### 2.1 Schema (what each record looks like)

Each NDD record produces ONE realistic Swedish text fragment + a
**ground-truth** dict of `{label: [mentions...]}` that maps onto the
categories above.

NDD columns (sketch — full version in `configs/ndd_swedish_pii.py`):

| column                  | type                | notes                                                        |
|-------------------------|---------------------|--------------------------------------------------------------|
| `text_type`             | `CategorySampler`   | `chat`, `support_ticket`, `invoice_line`, `email_body`, `form_screenshot`, `kontoutdrag`, `kvitto`, `id_kort_preview` — weighted to mirror real Ranymizer inputs |
| `register`              | `CategorySampler`   | `formal`, `informal`, `bureaucratic`, `mobile_chat`          |
| `seed_person`           | `PersonSampler`     | NDD's built-in; locale=`sv_SE`                               |
| `seed_company`          | `LLMStructured`     | small JSON: `{name, org_nr (XXXXXX-XXXX), bg, pg}`           |
| `seed_address`          | `LLMStructured`     | `{street, postnr (NNN NN), ort}`                             |
| `seed_personnummer`     | `Expression`        | generated with valid Luhn check digit (helper fn)            |
| `seed_pii_pool`         | `LLMStructured`     | grab-bag: `{email, phone, iban, date, url}`                  |
| `text`                  | `LLMText`           | the actual training sentence — references seed values        |
| `entities`              | `LLMStructured`     | `{label: [exact strings copied from `text`]}` — the labels   |
| `entities_validated`    | `CustomColumn`      | substring-check every mention; drop rows with any miss       |

The key trick: **we feed seeds (real PII values) to the LLM, then ask it
to produce both the text AND the label dict in the same call.** That way
mentions in `entities` are guaranteed to be substrings of `text` (and
the validator drops any drift).

### 2.2 NDD prompt for `text` (excerpt)

```
You write realistic Swedish {text_type} text in a {register} register.
You will be given seed values (person, company, addresses, PII). Use SOME
of them naturally in 1-3 sentences. Do not invent PII not in the seeds.
After writing the text, list every PII mention in `entities` keyed by:
person, email, phone, address, personnummer, organisationsnummer, bank,
date, url.

Seeds:
- person:        {seed_person}
- company:       {seed_company}
- address:       {seed_address}
- personnummer:  {seed_personnummer}
- other pii:     {seed_pii_pool}
```

### 2.3 Volumes

- Smoke: 1k rows (debug recipe / format).
- Pilot: 25k rows → train a LoRA adapter, sanity-check on
  `data/real_eval/`.
- Production: 200k rows, evenly weighted across `text_type`. Split
  90/5/5 train/val/test (NDD handles this with a sampling strategy).

### 2.4 Cost / runtime estimate

NDD with `openai-text` (default alias) at ~0.4s/record → ~22 hours for
200k. With `nvidia-super` on NIM, ~1.5h on 4×H100. Local vLLM
(`Qwen3-235B`) is the fallback when API credits run out.

---

## 3. Convert NDD output → GLiNER2 `InputExample` JSONL

`scripts/02_to_gliner2_jsonl.py`:

```python
from gliner2.training.data import InputExample, TrainingDataset
import pandas as pd, json

LABELS = ["person", "email", "phone", "address", "personnummer",
          "organisationsnummer", "bank", "date", "url"]

LABEL_DESCRIPTIONS = {
    "person": "Names of individuals, including given names, surnames, ...",
    "email": "Email addresses.",
    "phone": "Phone numbers (Swedish or international).",
    "address": "Street address, postal code, city.",
    "personnummer": "Swedish personal identity number (YYYYMMDD-XXXX).",
    "organisationsnummer": "Swedish organisation number (XXXXXX-XXXX).",
    "bank": "Bank account information: bankgiro, plusgiro, IBAN, BIC.",
    "date": "Calendar dates.",
    "url": "Web URLs.",
}

df = pd.read_parquet("data/raw/run.parquet")
examples = []
for _, row in df.iterrows():
    ents = row["entities"]  # {label: [mention, ...]}
    if not any(ents.values()):
        continue
    examples.append(InputExample(
        text=row["text"],
        entities={k: v for k, v in ents.items() if v},
        entity_descriptions=LABEL_DESCRIPTIONS,
    ))

ds = TrainingDataset(examples)
ds.validate(strict=True)             # span-in-text check
ds.print_stats()
train, val, test = ds.split(0.9, 0.05, 0.05, seed=42)
train.save("data/train.jsonl")
val.save("data/val.jsonl")
test.save("data/test.jsonl")
```

---

## 4. Training (using `fastino-ai-gliner2`)

Two paths — pick based on data volume:

### 4.1 LoRA (pilot, fast)

`scripts/03_train.py --config configs/train_lora_se.yaml`:

```python
from gliner2 import GLiNER2
from gliner2.training.trainer import GLiNER2Trainer, TrainingConfig

model = GLiNER2.from_pretrained("fastino/gliner2-base-v1")
config = TrainingConfig(
    output_dir="outputs/checkpoints/lora_se",
    num_epochs=10,
    batch_size=8,
    encoder_lr=1e-5, task_lr=5e-4,
    use_lora=True,
    lora_r=16, lora_alpha=32, lora_dropout=0.05,
    lora_target_modules=["encoder"],
    save_adapter_only=True,
    fp16=True,
    eval_strategy="epoch",
    early_stopping=True, early_stopping_patience=3,
)
trainer = GLiNER2Trainer(model, config)
trainer.train(train_data="data/train.jsonl", eval_data="data/val.jsonl")
```

Adapter: ~5–10MB. Swap on top of base model at inference time. Easy to
iterate per locale (LoRA per dialect / country down the road).

### 4.2 Full fine-tune (production, after pilot looks good)

Same trainer, `use_lora=False`, `num_epochs=15`, `batch_size=16`,
`fp16=True`. Final checkpoint is ~450MB; this is what ONNX-exports
cleanly.

### 4.3 Hardware

- LoRA pilot: 1×A100/H100 ~2h for 25k rows.
- Full FT: 4×H100 ~6–8h for 200k rows.
- CPU is not realistic.

---

## 5. Evaluation

`scripts/04_evaluate.py` runs on three sets:

1. **Held-out test** (`data/test.jsonl`) — span-level precision / recall
   per label.
2. **Real screenshots** (`data/real_eval/`) — hand-OCR'd ground truth
   from anonymised real Ranymizer inputs. This is the only metric that
   matters; synthetic numbers are reproductively-self-referential.
3. **Adversarial set** — handwritten edge cases:
   - personnummer with century prefix (`19850515-1234` vs `850515-1234`)
   - org. numbers with vs without dash
   - Swedish addresses with `c/o` / `lgh`
   - Phone numbers `+46 70 ...` vs `070-...`

Metric: F1 per label + macro-F1. Target before shipping: macro-F1 ≥
0.92 on real screenshots; ≥0.97 on `personnummer` and
`organisationsnummer` (regex-y, so should be near-perfect).

---

## 6. ONNX export → desktop

`scripts/05_export_onnx.py`. See `../TODO.md §2` for the export sketch
(the recipe from the gliner2 README). Output:

```
outputs/onnx/
├── model.onnx
├── tokenizer.json
└── labels.json   # mirrors LABEL_DESCRIPTIONS above
```

These three files become the contents of
`frontend/public/models/gliner2/` (see `models.ts`). Once they're in
place, `onnxModelsAvailable()` flips true and `worker.ts` switches off
the transformers.js fallback.

---

## 7. Showcase backend swap

When the new checkpoint is good:

1. Push it to a private HF repo (e.g. `ranymizer/gliner2-pii-sv-v1`).
2. In `backend/app.py`, change `MODEL_ID = "fastino/..."` to
   `"ranymizer/gliner2-pii-sv-v1"`.
3. Update `LABEL_DESCRIPTIONS` if labels changed.

Local devs use `HUGGINGFACE_HUB_TOKEN` to pull the private repo until
we open-source it.

---

## 8. Milestones

| # | task                                             | output                       | depends on   |
|---|--------------------------------------------------|------------------------------|--------------|
| 1 | scaffold `pii-model/` + `pyproject.toml`         | this folder                  | —            |
| 2 | NDD recipe smoke (1k rows)                       | `data/raw/smoke.parquet`     | 1            |
| 3 | `02_to_gliner2_jsonl.py` works on smoke          | `data/{train,val,test}.jsonl`| 2            |
| 4 | LoRA pilot training run (25k rows)               | `outputs/checkpoints/lora_se`| 3            |
| 5 | Hand-label 50 real screenshots → `real_eval/`    | gold set                     | —            |
| 6 | Evaluate LoRA on `real_eval/` → numbers          | report                       | 4, 5         |
| 7 | NDD production run (200k)                        | `data/raw/prod.parquet`      | 6 (if good)  |
| 8 | Full fine-tune                                   | `outputs/checkpoints/full`   | 7            |
| 9 | ONNX export                                      | `outputs/onnx/*`             | 8            |
| 10| Wire into `frontend/public/models/gliner2/`      | desktop parity               | 9, TODO.md §3|
| 11| Swap `MODEL_ID` in `backend/app.py`              | showcase parity              | 8            |

Items 1–3 are "today"; items 5–6 unblock everything because they tell
us whether synthetic-only training is sufficient or if we need real
data augmentation.

---

## 9. Open questions

- **Privacy of `real_eval/`**: real Swedish PII can't live in the
  repo. Plan: store hashes + offset spans in git, keep the actual
  pixels in a private S3 bucket; `04_evaluate.py` pulls them when an
  env var is set.
- **Per-locale adapters**: do we ship one model or one base + N LoRA
  adapters (sv, no, da)? Probably one base + adapters; matches Tauri
  multi-locale story without re-shipping 300MB.
- **NIM vs OpenAI for NDD**: cheaper to use NIM (`nvidia-super`) on
  internal infra; OpenAI is the dev-time fallback. Both are wired by
  default in NDD.
- **GLiNER2 ONNX export status**: the export path in `../TODO.md` is
  best-effort — confirm with `fastino-ai-gliner2` upstream whether
  there's a blessed exporter before relying on a hand-rolled
  `torch.onnx.export`.
