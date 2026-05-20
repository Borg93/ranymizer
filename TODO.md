# TODO — make the desktop target use the real models

The Tauri build currently runs **placeholder** ML in `frontend/src/lib/engine/worker.ts`
(`Xenova/trocr-small-printed` + a multilingual NER) instead of the real
PaddleOCR 3.5 + GLiNER2-PII the Python backend uses. The pipeline plumbing
is right; the models are wrong. Until this list is done, redaction-box
placement on the desktop won't match the showcase quality.

The end state is documented in `frontend/src/lib/engine/models.ts` as
`PADDLE_OCR` and `GLINER2`. `onnxModelsAvailable()` switches the worker
over once the artefacts exist at the documented URLs.

---

## 1. Convert PaddleOCR 3.5 → ONNX

Source: <https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version2.x/deployment/paddle2onnx.md>

```bash
# one-time tools
python3 -m pip install paddleocr==3.5.0 paddle2onnx onnxruntime

# download the same checkpoints app.py loads (PP-OCRv5_server)
mkdir -p /tmp/inference && cd /tmp/inference
wget -nc https://paddleocr.bj.bcebos.com/.../PP-OCRv5_server_det_infer.tar && tar xf *_det_infer.tar
wget -nc https://paddleocr.bj.bcebos.com/.../PP-OCRv5_server_rec_infer.tar && tar xf *_rec_infer.tar
wget -nc https://paddleocr.bj.bcebos.com/.../ch_ppocr_mobile_v2.0_cls_infer.tar && tar xf *_cls_infer.tar

# convert each stage (dynamic shapes are the default in paddle2onnx ≥1.2.3)
for stage in det rec cls; do
  paddle2onnx \
    --model_dir ./PP-OCRv5_server_${stage}_infer \
    --model_filename inference.pdmodel \
    --params_filename inference.pdiparams \
    --save_file ./${stage}_onnx/model.onnx \
    --opset_version 11 \
    --enable_onnx_checker True
done

# normalise detector input shape (some browsers refuse fully-dynamic inputs)
python3 -m paddle2onnx.optimize \
  --input_model det_onnx/model.onnx \
  --output_model det_onnx/model.onnx \
  --input_shape_dict "{'x': [-1,3,-1,-1]}"
```

Drop the resulting files in:

```
frontend/public/models/paddleocr/
├── det.onnx
├── cls.onnx
├── rec.onnx
└── dict.txt        # ppocr/utils/ppocr_keys_v1.txt (or lang-specific)
```

### Smoke test (Python ONNXRuntime — proves the conversion before browser)

```bash
python3 PaddleOCR/tools/infer/predict_system.py \
  --use_gpu=False --use_onnx=True \
  --det_model_dir=./det_onnx/model.onnx \
  --rec_model_dir=./rec_onnx/model.onnx \
  --cls_model_dir=./cls_onnx/model.onnx \
  --image_dir=PaddleOCR/doc/imgs_en/img_12.jpg \
  --rec_char_dict_path=PaddleOCR/ppocr/utils/en_dict.txt
```

Expect the same per-line boxes + recognised text that `backend/app.py`
produces. If they match, the ONNX models are good.

## 2. Convert GLiNER2-PII → ONNX

Source: `fastino/gliner2-privacy-filter-PII-multi` (label-conditioned, multilingual).

```python
# rough sketch — refine once the GLiNER2 ONNX export tooling is settled
from gliner2 import GLiNER2  # the [local] extra used by backend/app.py
import torch

model = GLiNER2.from_pretrained("fastino/gliner2-privacy-filter-PII-multi")
dummy = model.tokenize(["dummy text"], ["person", "email", "phone"])
torch.onnx.export(
    model,
    args=(dummy.input_ids, dummy.attention_mask, dummy.label_input_ids),
    f="model.onnx",
    input_names=["input_ids", "attention_mask", "label_input_ids"],
    output_names=["span_scores"],
    dynamic_axes={
        "input_ids":        {0: "batch", 1: "seq"},
        "attention_mask":   {0: "batch", 1: "seq"},
        "label_input_ids":  {0: "batch", 1: "labels"},
        "span_scores":      {0: "batch", 1: "seq", 2: "seq", 3: "labels"},
    },
    opset_version=17,
)
```

Pair with `tokenizer.json` (from `AutoTokenizer.save_pretrained`) and a
`labels.json` mirroring `backend/app.py`'s `PII_LABELS` (label name +
description, since GLiNER2 conditions on descriptions).

Drop everything in `frontend/public/models/gliner2/`.

## 3. Wire the worker to the ONNX models

When the artefacts above exist (probed via `onnxModelsAvailable()`),
`worker.ts` should switch from transformers.js to direct
`onnxruntime-web` `InferenceSession`s:

- Detector: input image → text-line polygons (port `db_postprocess`).
- Classifier: orientation guard per crop.
- Recogniser: CTC decode per crop → text + per-line geometry.
- GLiNER2: tokenise OCR text → span scores → decode to `PiiSpan[]`.
- Then `spansToBoxes(spans, lines)` (already a stub in worker.ts) becomes
  real: it maps char spans to OCR line polygons exactly like
  `app.py:map_spans_to_boxes`.

ONNX Runtime Web supports WebGPU (`executionProviders: ['webgpu', 'wasm']`)
— wire it through `webgpu.ts`'s `resolveBackend`.

## 4. Bundle vs first-run download

Both `paddleocr/` and `gliner2/` are big (~500 MB combined). Choices:

- **First-run download** (current direction): keep them under
  `frontend/public/models/` and ship in the Tauri bundle. ~+500 MB on
  `tauri build` artefact size.
- **Lazy fetch**: don't ship them in the bundle; download on first
  analyse and cache in the WebView (Cache API). Smaller installer,
  needs network on first use. Update `tauri.conf.json` `csp.connect-src`
  to allow the model host.

Decide before the first real release.

## 5. Delete the transformers.js fallback

Once steps 1–3 are done and `onnxModelsAvailable()` returns true on a
clean install, remove the bottom half of `frontend/src/lib/engine/models.ts`
(`OCR_MODEL`, `PII_MODEL` placeholders) and the matching code path in
`worker.ts`. Also drop the `@huggingface/transformers` dep if nothing
else needs it.

## 6. Update the README architecture section

Once parity is reached, edit the "Open item — model parity" warning in
the root `README.md` to "Resolved" and link to this file (`TODO.md`) for
the conversion record.

---

## 7. Backend: wire the Settings drawer config into `app.py`

The Settings drawer in the frontend already collects every output-level
knob a user can tweak. Right now only `pipelineConfig.gliner.threshold`
and `enabledLabels` reach the mock engine; the real Python backend
ignores everything else. To finish parity:

### 7.1 Pass `PipelineConfig` through the Gradio API

- `frontend/src/lib/api.ts::anonymizeScreenshot` — add a second argument
  `config` and forward it as JSON in the
  `client.predict('/anonymize_screenshot', { image, config })` call.
- `backend/server.py::anonymize_screenshot_api(image, config_json: str)`
  — parse the JSON, pass to `app.run_pii_analysis` + `ocr_image`.

### 7.2 PaddleOCR knobs from `pipelineConfig.paddleocr`

`backend/app.py::get_ocr` is a singleton, so flags can't change after
boot. Refactor to either:

- Re-instantiate `PaddleOCR(...)` when the relevant flags change, or
- Pass overrides to `pipeline.predict(arr, use_doc_orientation_classify=…,
  use_doc_unwarping=…, use_textline_orientation=…, layout_threshold=…)`
  per request (PaddleOCR 3.5 accepts per-call overrides).

Fields to wire:

- `layoutThreshold`
- `useDocOrientationClassify`
- `useDocUnwarping`
- `useTextlineOrientation`
- `useChartRecognition`
- `useSealRecognition`
- `useOcrForImageBlock`

### 7.3 GLiNER2 knobs from `pipelineConfig.gliner`

In `backend/app.py::run_pii_analysis` (today hard-codes `threshold=0.5`
and the global `PII_LABELS` dict):

```python
def run_pii_analysis(text, config):
    labels = config["enabledLabels"] or DEFAULT_PII_LABELS
    descriptions = {
        k: config["descriptions"].get(k, DEFAULT_DESC[k]) for k in labels
    }
    result = model.extract_entities(
        text,
        descriptions,                       # was the global PII_LABELS
        threshold=config["threshold"],      # was 0.5
        include_spans=True,
        include_confidence=True,
    )
    return _apply_label_rules(text, result, config["rules"])
```

### 7.4 `_apply_label_rules` — the post-filter ladder

The drawer's four per-label knobs (see `LabelRule` in
`frontend/src/lib/types.ts`) all run *after* GLiNER2 returns candidates:

1. **Per-label threshold** — drop `span.confidence < rule.threshold`
   when `rule.threshold > 0`.
2. **Regex** — `re.fullmatch` / `re.search` / `not re.search` depending
   on `rule.regexMode`. Catch `re.error` so a bad pattern doesn't crash
   the request; log + skip the rule on parse failure.
3. **Luhn** — only when `rule.validateLuhn` is true *and* the matched
   text is digit-only after stripping `[-+ ]`. Standard right-to-left:

   ```python
   def luhn_ok(digits: str) -> bool:
       total = 0
       for i, ch in enumerate(reversed(digits)):
           d = int(ch)
           if i % 2 == 1:
               d *= 2
               if d > 9: d -= 9
           total += d
       return total % 10 == 0
   ```

   Personnummer needs the separator stripped first
   (`850315-2389` → `8503152389`).

### 7.5 VLM sampling knobs from `pipelineConfig.vlm`

Today the backend uses PaddleOCR-VL defaults. Forward `temperature`,
`topP`, `repetitionPenalty`, `maxNewTokens`, `minPixels`, `maxPixels`
to `pipeline.predict(...)`. PaddleOCR-VL 1.5 accepts all of them per
call (see the official PaddleOCR-VL usage tutorial).

### 7.6 Migrate the local engine too (later)

When the Tauri build finally uses on-device transformers.js / GLiNER2
WASM, the same `PipelineConfig` shape needs to reach
`frontend/src/lib/engine/worker.ts`. The seam already exists
(`AnalyzeOptions.config`); the worker just ignores the field today.
