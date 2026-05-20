# Ranymizer — Swedish screenshot redactor

OCR → PII detection → canvas editor for redacting Swedish screenshots
before sharing. **Two build targets** from one codebase:

- **Showcase** (Python `gr.Server` backend, ZeroGPU on HF Space): PaddleOCR 3.5 → GLiNER2-PII → JSON.
- **Desktop** (Tauri 2.0, fully local): transformers.js → ONNX Runtime Web → WebGPU/WASM, no backend.

Stack: SvelteKit 2 · Svelte 5 (runes) · Tailwind 4 · shadcn-svelte · Bun · Tauri 2 · Biome.

```
.
├── README.md
├── Dockerfile                # showcase: Python + static SPA, EXPOSE 7860
├── Makefile                  # `make install`, `make showcase-backend`, `make tauri-dev`, …
├── example-images/           # (you create) drop test screenshots here for the showcase landing page
├── backend/                  # Python — showcase target only
│   ├── pyproject.toml        # uv project (name = "ranymizer")
│   ├── .python-version       # 3.11
│   ├── requirements.txt      # fallback for hosts that need pip
│   ├── app.py                # PaddleOCR + GLiNER2 pipeline
│   ├── server.py             # gr.Server: API routes + SvelteKit static mount
│   └── README.md             # uv setup + run instructions
└── frontend/                 # SvelteKit 2 SPA — both targets
    ├── package.json          # bun-managed
    ├── biome.json            # formatter + linter (.ts / .json only — Svelte handled by svelte-check)
    ├── svelte.config.js      # adapter-static (right for BOTH targets)
    ├── vite.config.ts        # engine selected by VITE_ENGINE at build time
    ├── src-tauri/            # Tauri 2.0 shell (locked-down CSP, core:default capability only)
    └── src/
        ├── app.html / app.css
        ├── routes/           # +layout.ts has ssr=false + prerender=true (SPA)
        └── lib/
            ├── state.svelte.ts   # EditorState (depends on engine, not on Gradio)
            ├── api.ts            # @gradio/client wrapper (showcase only)
            ├── utils.ts          # cn() + shadcn-svelte type helpers
            ├── types.ts
            ├── engine/           # ← the seam between UI and inference
            │   ├── types.ts      #   AnonymizerEngine interface
            │   ├── index.ts      #   picks engine from import.meta.env.VITE_ENGINE
            │   ├── gradio.ts     #   showcase: wraps @gradio/client
            │   ├── local.ts      #   desktop: drives the worker
            │   ├── worker.ts     #   transformers.js OCR + PII (ES module worker)
            │   ├── webgpu.ts     #   auto → webgpu → wasm backend detection
            │   └── models.ts     #   model registry + offline category meta
            └── components/
                ├── ui/       # shadcn-svelte primitives (button, card, toggle-group, badge, separator, toggle)
                ├── Landing.svelte / Editor.svelte / Canvas.svelte / Sidebar.svelte / Loading.svelte
```

## Setup (one-time)

```bash
make install     # installs bun + rust + uv if missing, then frontend deps + backend venv
```

Manual install:

```bash
# bun (frontend), rust (Tauri), uv (backend Python)
curl -fsSL https://bun.sh/install | bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
curl -LsSf https://astral.sh/uv/install.sh | sh

cd frontend && bun install
cd backend  && uv sync
```

## Run

The `Makefile` has every target — `make` (with no args) lists them. The
common ones:

```bash
# ── Showcase (Python backend + SPA over network) ──────────────
make showcase-backend      # Python gr.Server on :7860
make showcase-frontend     # SvelteKit dev on :5173 (Gradio engine)

# ── Desktop (Tauri 2.0, fully local, no Python) ──────────────
make tauri-dev             # opens a native window, hot-reload
make tauri-build           # release bundle (.dmg/.app/.deb/.msi)

# ── Local engine in a browser (no Python, no native shell) ───
make local-dev             # http://localhost:5173 with VITE_ENGINE=local
make local-build           # static build with VITE_ENGINE=local

# ── Showcase in one Docker image ─────────────────────────────
make docker-build && make docker-run    # http://localhost:7860
```

CORS is open on the Python side for `:5173` so the dev frontend can hit the
backend on `:7860`. Edits to `.svelte` / `.ts` hot-reload. Edits to `app.py`
or `server.py` require a Python restart.

## Data flow

Same pattern as the BiRefNet demo: `FileData` in, JSON out. The source
image is **never round-tripped through the server** — the SvelteKit client
already has the `File`, so `state.upload(file)` calls
`URL.createObjectURL(file)` and feeds it straight to `<img>`. The Python
side returns only `{filename, width, height, boxes, text, spans}`.
`/api/meta` is a separate plain GET for the static category colors/labels;
it's cached in-memory on the client.

```
   ┌──── File (kept on client) ──────────────► <img src=blob:…>
   │                                            (canvas + redaction)
   │
   │            ┌─── @gradio/client.predict("/anonymize_screenshot")
   File ────────┤   FileData (multipart)
                │   ────────────────────────►   PaddleOCR ► GLiNER2
                │                              ◄──────────────
                └── JSON: {boxes, spans, text, width, height}
```

## Theme mapping

The carefully tuned colors from the original Ranymizer are
preserved as CSS variables in `:root` and mapped to shadcn's semantic
names via `@theme inline` in `app.css`:

| original token | shadcn name (Tailwind class)      |
| -------------- | --------------------------------- |
| `--bg`         | `--background` (`bg-background`)  |
| `--surface`    | `--card` (`bg-card`)              |
| `--surface2`   | `--muted`, `--secondary`          |
| `--text`       | `--foreground`                    |
| `--text2`      | `--muted-foreground`              |
| `--accent`     | `--primary` (`bg-primary`)        |
| `--accent-dim` | `--accent` (the shadcn one)       |
| `--border-c`   | `--border`                        |
| `--danger`     | `--destructive`                   |

Fonts (`Inter`, `Lora`, `ui-monospace`) are bound to `--font-sans`,
`--font-serif`, `--font-mono` and exposed as `font-sans`, `font-serif`,
`font-mono` Tailwind utilities.

Both dark (default) and the original light-mode media query are wired
up; toggle via `mode-watcher` if you want a manual switch.

## Environment knobs (Python)

| var                      | default                                       | meaning                                          |
| ------------------------ | --------------------------------------------- | ------------------------------------------------ |
| `USE_GPU`                | `1`                                           | flip to `0` to force CPU                         |
| `GLINER_MODEL`           | `fastino/gliner2-privacy-filter-PII-multi`    | override to test other GLiNER2 checkpoints       |
| `GLINER_COMPILE`         | `1`                                           | `torch.compile` on the GLiNER2 encoder (GPU only) |
| `INFERENCE_DTYPE`        | `float32`                                     | passed to PaddleOCR's `engine_config.dtype`      |
| `LOAD_MODELS_ON_STARTUP` | `1`                                           | preload both models so the first request is fast |

## Known limits

1. **Personnummer / orgnr recall will be soft out of the box.** The
   GLiNER2-PII encoder was trained on English + Dutch / German /
   French / Italian / Spanish / Portuguese, never on Swedish national-ID
   formats. Description hints in `PII_LABELS` help but don't replace
   fine-tuning. Run an eval on real docs and expect to LoRA-tune.

2. **PaddleOCR returns line polygons, not per-word boxes.** Each PII
   span is mapped to the OCR line(s) it overlaps; single-line spans
   are narrowed by character ratio within the line.

3. **Dependency interaction (Python side).** PaddleOCR 3.5's
   transformers backend pins `transformers >= 5.4.0`. GLiNER2 has its
   own transformers requirement via `gliner2[local]`. If pip can't
   resolve, install `gliner2[local]` first then `paddleocr==3.5.0`
   last in a fresh venv.

## Architecture — one codebase, two build targets

This is **not** two apps. The redaction editor (`state.svelte.ts` +
components) depends only on an `AnonymizerEngine` interface
(`src/lib/engine/`). Two implementations, selected at build time by
`VITE_ENGINE`:

| Target | `VITE_ENGINE` | Inference | Privacy | Ships as |
| ------ | ------------- | --------- | ------- | -------- |
| **Showcase** | `gradio` (default) | Python `gr.Server` (ZeroGPU) | image uploaded | HF Space (static SPA) |
| **Desktop** | `local` | transformers.js + ONNX Runtime Web + WebGPU, in a Web Worker | nothing leaves the device | Tauri 2.0 app |

```
src/lib/engine/
├── types.ts     # AnonymizerEngine interface — the only seam
├── index.ts     # picks engine from import.meta.env.VITE_ENGINE
├── gradio.ts    # showcase: wraps @gradio/client (api.ts)
├── local.ts     # desktop: drives the worker
├── worker.ts    # transformers.js OCR + PII (ES module worker)
├── webgpu.ts    # auto → webgpu → wasm backend detection
└── models.ts    # model registry + offline category meta
src-tauri/        # Tauri 2.0 shell (per the sveltekit-tauri skill)
```

### Run

```bash
# Showcase (unchanged): Python + Gradio engine
python server.py
cd frontend && bun run dev            # http://localhost:5173

# Secure local desktop (Tauri 2.0, local engine)
cd frontend
bun install
bunx tauri icon path/to/logo.png      # one-time: generate app icons
bun run tauri dev                     # hot-reloading desktop window
bun run tauri build                   # release bundle
```

`bun run dev:local` / `bun run build:local` build the SPA with the local
engine without the Tauri shell (browser testing).

### Security (desktop)

- **No Rust commands** — the whole pipeline is in the WebView; zero native
  attack surface. `capabilities/default.json` grants `core:default` only
  (no fs/shell/http/dialog).
- **Strict CSP** in `tauri.conf.json`: `connect-src` is the only outbound
  allowance and only reaches the HF Hub — for the *first-run model
  download*, cached in the WebView thereafter. The image/text are never in
  an outbound request. Bundle weights as resources + drop `connect-src` to
  go fully air-gapped.
- The source image still never round-trips a server in any mode
  (`createObjectURL`); the showcase only uploads to ZeroGPU for inference.

### ⚠️ Open item — model parity (the real R&D)

`src/lib/engine/models.ts` ships **placeholder** model ids. The Python
side is PaddleOCR (full-page OCR *with line polygons*) + GLiNER2
(label-conditioned PII). Neither runs in transformers.js as-is: in-browser
OCR that returns box geometry, and a GLiNER2-equivalent ONNX (Swedish
`personnummer`/`orgnr`), are unresolved — `worker.ts` wires the pipeline
correctly but box placement depends on this. Tracked alongside "Known
limits" above.

Tooling note: the existing project's Vite/Tailwind/shadcn setup was kept
as-is; only the **Tauri** parts of the local `sveltekit-tauri` skill were
applied (it otherwise bootstraps a greenfield rolldown/Biome stack).
