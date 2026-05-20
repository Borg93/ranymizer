# Bootstrap: New SvelteKit + Tauri Project

Create a new desktop application using the modern SvelteKit + Tauri stack: Svelte 5, SvelteKit 2, Bun, Vite 7 with Rolldown, Tauri 2, Tailwind CSS 4, shadcn-svelte, and Biome 2.

The end result is a project with:

- **Frontend**: SvelteKit 2 + Svelte 5 (runes mode) + Tailwind 4 + shadcn-svelte
- **Build**: Vite 7 with the `rolldown-vite` drop-in for Rust-powered bundling
- **Backend**: Tauri 2 + Rust, with the frontend in SPA mode (no SSR)
- **Tooling**: Biome 2 for formatting and linting, TypeScript everywhere
- **Working example**: an `invoke`-based greeting command wiring Svelte → Rust

## Prerequisites

Before starting, confirm the user has these installed. If anything is missing, point them at the install instructions and stop until they confirm.

| Tool | Install |
|------|---------|
| **Bun** ≥ 1.2 | https://bun.sh |
| **Rust** (stable, ≥ 1.77) | https://rustup.rs |
| **Platform deps** | Windows: MSVC C++ build tools · macOS: `xcode-select --install` · Linux: `libwebkit2gtk-4.1-dev`, `librsvg2-dev`, `libayatana-appindicator3-dev`, `libxdo-dev`, `build-essential`, `curl`, `wget`, `file`, `libssl-dev` |

## Workflow

### Step 1: Collect project info

Use `AskUserQuestion` (or equivalent) to collect three values in one round:

- **project-name**: kebab-case identifier, e.g. `my-awesome-app`. Used as the npm package name and Cargo crate name.
- **display-name**: human-readable window title, may include spaces and Unicode, e.g. `My Awesome App`.
- **package-id**: reverse-DNS bundle identifier, e.g. `com.example.myawesomeapp`. Must be unique per app.

### Step 2: Scaffold the SvelteKit project

Run inside the directory where the project should live. This creates a `<project-name>/` subfolder:

```bash
bunx sv create <project-name> \
  --template minimal \
  --types ts \
  --no-add-ons \
  --install bun
cd <project-name>
```

If `sv create` isn't yet available in the user's environment, fall back to:
```bash
bunx create-svelte@latest <project-name>
```
and pick **Skeleton project**, **TypeScript**, **None** for add-ons.

### Step 3: Add `@sveltejs/adapter-static`

SvelteKit defaults to `adapter-auto`, which targets servers. Tauri serves the frontend statically, so swap it out:

```bash
bun add -D @sveltejs/adapter-static
```

Edit `svelte.config.js`:

```js
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
export default {
  preprocess: vitePreprocess(),
  compilerOptions: { runes: true },
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: 'index.html', // SPA mode
    }),
    alias: { $lib: 'src/lib' },
  },
};
```

Create `src/routes/+layout.ts` with:

```ts
export const prerender = true;
export const ssr = false;
```

This puts the app in SPA mode so `load` functions run in the WebView and can call Tauri APIs.

### Step 4: Switch to Rolldown-powered Vite

Replace plain Vite with the Rolldown drop-in. Edit `package.json` `devDependencies`:

```json
"vite": "npm:rolldown-vite@^7.1.2"
```

Then re-install:

```bash
bun install
```

Update `vite.config.ts` to enable the native plugin and skip esbuild (it conflicts with Rolldown):

```ts
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host ? { protocol: 'ws', host, port: 1421 } : undefined,
    watch: { ignored: ['**/src-tauri/**'] },
  },
  envPrefix: ['VITE_', 'TAURI_ENV_*'],
  build: {
    target: process.env.TAURI_ENV_PLATFORM === 'windows' ? 'chrome105' : 'safari13',
    minify: !process.env.TAURI_ENV_DEBUG ? 'oxc' : false,
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
  },
  experimental: { enableNativePlugin: true },
  esbuild: false,
});
```

### Step 5: Add Tailwind CSS 4

```bash
bun add tailwindcss @tailwindcss/vite
bun add -D tw-animate-css
```

Replace `src/app.css` with the contents of `SKILL_DIR/assets/app.css` — it sets up Tailwind 4 and the shadcn-svelte design tokens (light + dark) using `@theme inline`.

Import the CSS in `src/routes/+layout.svelte`:

```svelte
<script lang="ts">
  import '../app.css';
  let { children } = $props();
</script>

{@render children?.()}
```

### Step 6: Wire up shadcn-svelte

Create `components.json` at the project root with the contents of `SKILL_DIR/assets/components.json`. Then add the support utilities and one component to verify everything wires up:

```bash
bun add clsx tailwind-merge tailwind-variants
mkdir -p src/lib
```

Copy `SKILL_DIR/assets/utils.ts` to `src/lib/utils.ts`. Then install the Button component via the shadcn CLI to confirm the config is correct:

```bash
bunx shadcn-svelte@latest add button
```

If the CLI prompts for confirmation, accept the defaults — `components.json` already supplies the paths and base color. Adding further components later is covered in [references/shadcn.md](shadcn.md).

### Step 7: Add Biome

```bash
bun add -D --exact @biomejs/biome
```

Copy `SKILL_DIR/assets/biome.json` to the project root. Add these scripts to `package.json`:

```json
"format": "biome format --write ./src",
"lint": "biome lint --write ./src",
"check": "biome check --write ./src"
```

Delete any `.prettierrc`, `.prettierignore`, `eslint.config.js` files that `sv create` may have generated — Biome replaces both tools.

### Step 8: Add Tauri

Initialize the Rust backend. Answer the prompts using the values from Step 1:

```bash
bunx @tauri-apps/cli@latest init
```

Prompts:

| Prompt | Answer |
|--------|--------|
| App name | `display-name` |
| Window title | `display-name` |
| Where are your web assets located? | `../build` |
| What is the URL of your dev server? | `http://localhost:1420` |
| What is your frontend dev command? | `bun run dev` |
| What is your frontend build command? | `bun run build` |

Then edit `src-tauri/tauri.conf.json` to set the `identifier` to your `package-id`:

```json
{
  "identifier": "com.example.myawesomeapp",
  "build": {
    "frontendDist": "../build",
    "devUrl": "http://localhost:1420",
    "beforeDevCommand": "bun run dev",
    "beforeBuildCommand": "bun run build"
  }
}
```

Install the JS API and add the Tauri scripts to `package.json`:

```bash
bun add @tauri-apps/api
bun add -D @tauri-apps/cli
```

Add to `package.json` `scripts`:

```json
"tauri": "tauri"
```

### Step 9: Add a working example command

Copy `SKILL_DIR/assets/lib.rs` to `src-tauri/src/lib.rs` (replaces the generated stub). It defines a `greet(name: &str) -> String` command and registers it.

Copy `SKILL_DIR/assets/+page.svelte` to `src/routes/+page.svelte` (replaces the generated home page). It uses the Button component and `invoke('greet', { name })` to demonstrate frontend ↔ backend communication end-to-end.

### Step 10: Verify everything builds

Run these in order. Fix any failures before moving on.

```bash
bun install
bun run check
bun run tauri dev
```

For `bun run tauri dev`:

- Run it and watch the log for `ready in` or `Local: http://localhost:1420` — that means the dev server is up.
- Wait at most **120 seconds** for the desktop window to appear. Don't poll indefinitely.
- If an error like `error[E`, `FAILED`, `cannot find`, or `panicked at` appears in the log, stop and fix it.
- To stop the dev server cleanly:

  ```bash
  kill $(lsof -ti tcp:1420) 2>/dev/null; pkill -f "tauri dev" 2>/dev/null
  ```

### Step 11: Initialize Git

```bash
git init
git add .
git commit -m "Initial commit"
```

### Step 12: Tell the user what they got

Summarize what was created:

- The dev workflow: `bun run tauri dev` for a hot-reloading desktop app, `bun run tauri build` for a release bundle.
- The directory layout: `src/` for Svelte code, `src-tauri/src/` for Rust code, `src-tauri/tauri.conf.json` for app metadata, `src-tauri/capabilities/default.json` for permissions.
- The example command in `src-tauri/src/lib.rs` and the matching `invoke` call in `src/routes/+page.svelte` — that pattern is the entry point for all frontend ↔ backend communication.
- Where to go next: this skill also covers adding a [tray icon](tray.md), [custom app icon](icon.md), [auto-updater](updater.md), [more shadcn components](shadcn.md), and [more Rust commands](command.md).

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `cargo: command not found` | Install Rust via https://rustup.rs and restart the shell |
| `bun: command not found` | Install Bun via https://bun.sh |
| Linux: `libwebkit2gtk` not found | Install the platform deps listed above |
| `bun install` fails with peer dep warnings | Bun is stricter than npm; pass `--no-strict-peer-dependencies` or accept the warnings — usually harmless |
| Tauri dev window is blank | Confirm `frontendDist` is `../build` and `devUrl` is `http://localhost:1420`; ensure `+layout.ts` sets `ssr = false` |
| Port 1420 already in use | Kill the stale process: `kill $(lsof -ti tcp:1420)` |
| Tailwind classes don't apply | Confirm `tailwindcss()` is in `vite.config.ts` plugins and `app.css` is imported from `+layout.svelte` |
| Rolldown breaks a plugin | Some Vite plugins assume esbuild — fall back to standard `vite` by removing the `npm:rolldown-vite@...` alias |
| `bun run tauri dev` errors with "missing identifier" | Set `identifier` in `tauri.conf.json` to a valid reverse-DNS string |
