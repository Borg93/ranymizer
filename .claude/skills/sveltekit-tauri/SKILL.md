---
name: sveltekit-tauri
description: Toolkit for SvelteKit 2 + Tauri 2 desktop apps using Bun, Rolldown (rolldown-vite), Tailwind CSS 4, shadcn-svelte, and Biome. Scaffolds new projects and adds production features (custom app icon, system tray, auto-updater, shadcn components, Rust commands). Use whenever the user wants to create, scaffold, bootstrap, or initialize a SvelteKit + Tauri desktop app — and whenever they want to add a tray / menu bar icon, replace the app icon, configure the auto-updater, install shadcn-svelte components, or wire up a new Tauri command. Trigger this skill even when the user only mentions one piece of the stack (e.g. "add a tray icon to my Tauri app") rather than the full combination.
---

# SvelteKit + Tauri Skill

A toolkit for building **SvelteKit 2 + Tauri 2** desktop applications with a modern, fast stack:

- **Svelte 5 + SvelteKit 2** with runes and `adapter-static`
- **Bun** as the package manager and runtime
- **Vite 8** with **Rolldown** (`rolldown-vite`) for ultra-fast bundling
- **Tauri 2** for the native shell (Rust backend, WebView frontend)
- **Tailwind CSS 4** with the new `@tailwindcss/vite` plugin
- **shadcn-svelte** for accessible UI components
- **Biome 2** as the formatter and linter (replaces ESLint + Prettier)

The skill covers the full lifecycle: scaffold a new project, then layer features on as you need them.

## Capabilities

| Capability        | Trigger phrases                                                                                       | Reference                                       |
|-------------------|-------------------------------------------------------------------------------------------------------|-------------------------------------------------|
| **Bootstrap**     | "create project", "new app", "bootstrap", "scaffold", "set up SvelteKit + Tauri", "initialize"        | [references/bootstrap.md](references/bootstrap.md) |
| **Icon**          | "replace app icon", "change icon", "set app logo", "custom icon"                                      | [references/icon.md](references/icon.md)        |
| **Tray**          | "tray icon", "system tray", "menu bar icon", "menubar icon", "status bar icon"                        | [references/tray.md](references/tray.md)        |
| **Updater**       | "auto-updater", "auto update", "over-the-air updates", "ship updates"                                 | [references/updater.md](references/updater.md)  |
| **shadcn**        | "add shadcn component", "install button/dialog/card", "shadcn-svelte"                                 | [references/shadcn.md](references/shadcn.md)    |
| **Tauri command** | "add a Tauri command", "call Rust from frontend", "invoke", "frontend ↔ backend"                      | [references/command.md](references/command.md)  |
| **Bun server**    | "svelte-adapter-bun", "Bun server", "Bun production server", "Bun deployment", "WebSocket SvelteKit"  | [references/adapter-bun.md](references/adapter-bun.md) |
| **Dependencies**  | "latest stable", "update dependencies", "bump deps", "newest versions", "package.json versions", "what version of …" | [references/dependencies.md](references/dependencies.md) |

## When to Use

- The user wants to **create a new** SvelteKit + Tauri desktop app → **Bootstrap**
- The user wants to **replace the app icon** with a custom PNG → **Icon**
- The user wants to **add a system tray / menu bar / menubar icon** with a context menu → **Tray**
- The user wants to **enable over-the-air auto-updates** → **Updater**
- The user wants to **add a shadcn-svelte UI component** (button, dialog, card, etc.) → **shadcn**
- The user wants to **expose a Rust function** to the Svelte frontend → **Tauri command**
- The user asks about **`svelte-adapter-bun`** / running SvelteKit as a Bun HTTP server (or wants both Tauri *and* a Bun-server build from the same repo) → **Bun server**. ⚠ The Tauri target always stays on `@sveltejs/adapter-static` — never swap it for `svelte-adapter-bun`.
- The user wants to **update `package.json` to the newest stable versions** (or asks which versions of the canonical packages to pin) → **Dependencies**. Always re-verify versions live from the npm registry; the doc carries a dated snapshot + major-bump caveats (Vite ↔ vite-plugin-svelte lockstep, bits-ui major ↔ shadcn re-install, `@tauri-apps/api` ↔ `@tauri-apps/cli` lockstep, etc.).

## How to Use

1. Identify which capability matches the request using the trigger phrases above.
2. Read the corresponding reference file in `references/` — it contains the step-by-step workflow.
3. Follow that workflow exactly. Each reference is self-contained.

If the request spans multiple capabilities (e.g. "bootstrap a new app and add a tray icon"), handle them sequentially in logical order: bootstrap first, then layer features on top.

## Conventions used across this skill

- **Package manager**: `bun` (use `bun add`, `bun install`, `bun run`, `bunx`). Never use `npm` or `pnpm` unless the user explicitly asks.
- **Tauri CLI**: invoke via `bunx tauri <command>` or `bun run tauri <command>` once it's wired into `package.json`.
- **Paths**:
  - Frontend code: `src/`
  - Rust code: `src-tauri/src/`
  - Tauri config: `src-tauri/tauri.conf.json`
  - Tauri capabilities (permissions): `src-tauri/capabilities/default.json`
- **`SKILL_DIR`** in workflows refers to the directory containing this `SKILL.md`. When a workflow says "copy `SKILL_DIR/assets/foo.rs`", substitute the actual path.
