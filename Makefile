.PHONY: help install \
        showcase-backend showcase-frontend showcase-build \
        local-dev local-build tauri-dev tauri-build \
        check format lint \
        docker-build docker-run clean

# Default — list every target with its docstring.
help:
	@grep -E '^[a-zA-Z][a-zA-Z_-]*:.*?##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?##"}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

install: ## Install bun + rust + uv, then frontend deps + backend venv
	@command -v bun  >/dev/null || curl -fsSL https://bun.sh/install | bash
	@command -v cargo >/dev/null || curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
	@command -v uv   >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
	cd frontend && bun install
	cd backend  && uv sync

# ── Showcase target (Python gr.Server + Gradio engine in the SPA) ──────
showcase-backend:   ## Run the Python Gradio backend on :7860
	cd backend && uv run python server.py

showcase-frontend:  ## Run the SvelteKit dev server (Gradio engine) on :5173
	cd frontend && bun run dev

showcase-build:     ## Build the SvelteKit SPA against the Gradio engine
	cd frontend && bun run build

# ── Local-engine target (browser dev with the local worker, no backend) ─
local-dev:          ## Dev server with VITE_ENGINE=local (browser, no backend)
	cd frontend && bun run dev:local

local-build:        ## Production build with VITE_ENGINE=local
	cd frontend && bun run build:local

# ── Tauri desktop ──────────────────────────────────────────────────────
tauri-dev:          ## Run the Tauri 2.0 desktop app in dev mode
	cd frontend && bun run tauri dev

tauri-build:        ## Bundle the Tauri 2.0 desktop release
	cd frontend && bun run tauri build

# ── Quality ────────────────────────────────────────────────────────────
check:              ## Type-check the frontend (svelte-kit sync + svelte-check)
	cd frontend && bun run check

format:             ## Format .ts/.js/.json with Biome
	cd frontend && bun run format

lint:               ## Lint + autofix .ts/.js/.json with Biome
	cd frontend && bun run lint

# ── Docker (showcase only) ─────────────────────────────────────────────
docker-build:       ## Build the all-in-one showcase Docker image
	docker build -t ranymizer .

docker-run:         ## Run the showcase container on :7860
	docker run --rm -p 7860:7860 ranymizer

# ── Cleanup ────────────────────────────────────────────────────────────
clean:              ## Remove generated artefacts (node_modules, build, .venv, cargo target)
	rm -rf frontend/node_modules frontend/.svelte-kit frontend/build
	rm -rf backend/.venv
	cd frontend/src-tauri && cargo clean 2>/dev/null || true
