# pii-model

Train Ranymizer's Swedish PII GLiNER2 model. Synthetic data via
[NeMo Data Designer](https://github.com/NVIDIA-NeMo/DataDesigner)
(`data-designer` on PyPI), training via
[fastino-ai/GLiNER2](https://github.com/fastino-ai/GLiNER2) (`gliner2[local]`
on PyPI).

See [`PLAN.md`](./PLAN.md) for the full plan and milestones.

## Dependencies

Pinned in `pyproject.toml`:

| package              | role                                                  |
|----------------------|-------------------------------------------------------|
| `gliner2[local]>=1.3.1` | `GLiNER2` model class, `GLiNER2Trainer`, `TrainingConfig`, `InputExample`, `TrainingDataset`, LoRA via PEFT. The `[local]` extra pulls torch + transformers + peft. |
| `data-designer>=0.5.6` | `DataDesignerConfigBuilder`, sampler/expression/LLM/custom column configs — same API the upstream NDD recipes use. |
| `torch`, `peft`, `pandas`, `pyarrow` | runtime deps for training + parquet I/O. |
| `onnx`, `onnxruntime`, `safetensors` | only used by `05_export_onnx.py`. |

`gliner2` is the package name; the GitHub repo (`fastino-ai/GLiNER2`) is the
same project — there is no separate `fastino-ai-gliner2` PyPI package.

## Quick start

```bash
cd pii-model
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e .

# 1. Smoke-test the NDD recipe (5 rows, debug)
python scripts/01_generate_synthetic.py --preview

# 2. Generate 1k smoke set
python scripts/01_generate_synthetic.py --num-records 1000

# 3. Convert to GLiNER2 InputExample JSONL (drops invalid rows, splits 90/5/5)
python scripts/02_to_gliner2_jsonl.py \
    --raw-path data/raw/swedish_pii_synthetic

# 4. Train a LoRA adapter (pilot)
python scripts/03_train.py --mode lora --num-epochs 10

# After it works → bump --num-records up to 200k, switch --mode full.
```

Pick your NDD model provider via `--model-alias`:
- `openai-text` (default, set `OPENAI_API_KEY`)
- `nvidia-text` / `nvidia-super` (set `NVIDIA_API_KEY`)
- `vllm` (point `data-designer` at a local vLLM endpoint via env)

## Output

`outputs/onnx/` gets copied to `../frontend/public/models/gliner2/` for the
desktop build (see `../TODO.md` §3), and the HF checkpoint in
`outputs/checkpoints/full_se/final/` replaces `MODEL_ID` in
`../backend/app.py` for the showcase.
