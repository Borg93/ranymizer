# Dependencies — canonical packages & versions

The package set every SvelteKit + Tauri app built with this skill should
share, with the **gotchas that matter when upgrading** (major bumps in this
stack frequently change public APIs or peer requirements).

## How to look up the latest stable yourself

The single source of truth is the npm registry. **Always verify live** —
don't trust a snapshot below if its `Last verified` date is months old.

```bash
# One package
curl -s https://registry.npmjs.org/<pkg>/latest | jq -r .version

# A whole set, in parallel (bun, jq required)
for p in @sveltejs/kit svelte vite @tauri-apps/cli @tauri-apps/api bits-ui; do
  printf '%-30s %s\n' "$p" "$(curl -s https://registry.npmjs.org/$p/latest | jq -r .version)"
done

# In an existing project
cd frontend && bun outdated
```

`bunx npm-check-updates -u` rewrites `package.json` to the latest majors —
useful, but pair it with the major-bump caveats below.

## Canonical package set

These are the packages this skill installs (across Bootstrap, shadcn, Tray,
Updater, Command, Bun-server). Versions are caret-ranged so patches roll
forward automatically; majors require a deliberate bump.

| Package | Role | Major to target |
|---|---|---|
| `@sveltejs/kit` | SvelteKit framework | 2.x |
| `svelte` | Svelte runtime | 5.x (runes) |
| `@sveltejs/vite-plugin-svelte` | Vite ↔ Svelte glue | matches Vite major (see below) |
| `@sveltejs/adapter-static` | Static SPA adapter (Tauri target) | 3.x |
| `vite` | Bundler | 8.x (or the latest Vite that the plugin supports) |
| `svelte-check` | Type-check Svelte files | 4.x |
| `typescript` | Type checker | 6.x |
| `@tailwindcss/vite` | Tailwind 4 Vite plugin | 4.x |
| `tailwindcss` | Tailwind CSS | 4.x |
| `tw-animate-css` | shadcn-svelte animation tokens | 1.x |
| `clsx` | classname joiner (used by `cn()`) | 2.x |
| `tailwind-merge` | dedupe Tailwind classes | 3.x |
| `tailwind-variants` | variant helper for component libs | 3.x |
| `bits-ui` | shadcn-svelte primitive layer | 2.x |
| `mode-watcher` | dark/light mode tracker | 1.x |
| `lucide-svelte` | icon set | 1.x |
| `svelte-sonner` | toast notifications | 1.x |
| `@tauri-apps/api` | Tauri JS API (`invoke`, `event`, etc.) | 2.x |
| `@tauri-apps/cli` | Tauri CLI (`bun run tauri ...`) | 2.x |
| `svelte-adapter-bun` | Bun-server adapter (optional, non-Tauri target) | 1.x — see [adapter-bun.md](adapter-bun.md) |

## Verified snapshot

**Last verified:** 2026-05-20 (via `https://registry.npmjs.org/<pkg>/latest`).

| Package | Latest |
|---|---|
| `@sveltejs/kit` | 2.60.1 |
| `svelte` | 5.55.8 |
| `@sveltejs/vite-plugin-svelte` | 7.1.2 |
| `@sveltejs/adapter-static` | 3.0.10 |
| `vite` | 8.0.13 |
| `svelte-check` | 4.4.8 |
| `typescript` | 6.0.3 |
| `@tailwindcss/vite` | 4.3.0 |
| `tailwindcss` | 4.3.0 |
| `tw-animate-css` | 1.4.0 |
| `clsx` | 2.1.1 |
| `tailwind-merge` | 3.6.0 |
| `tailwind-variants` | 3.2.2 |
| `bits-ui` | 2.18.1 |
| `mode-watcher` | 1.1.0 |
| `lucide-svelte` | 1.0.1 |
| `svelte-sonner` | 1.1.1 |
| `@tauri-apps/api` | 2.11.0 |
| `@tauri-apps/cli` | 2.11.2 |
| `svelte-adapter-bun` | 1.0.1 |

If the date above is older than ~3 months when you read this, re-run the
lookup script and refresh the table; the rest of this doc stays useful.

## Major-bump caveats

Don't skip these when bumping a major version — each has historically
broken consumers.

### `vite` ↔ `@sveltejs/vite-plugin-svelte`
**Bump together.** The plugin tracks Vite majors:
- Vite 5 ↔ vite-plugin-svelte 3
- Vite 6 ↔ vite-plugin-svelte 5
- Vite 7 ↔ vite-plugin-svelte 6
- Vite 8 ↔ vite-plugin-svelte 7+

Mismatched majors give cryptic build-time errors. Always update both in the
same commit and re-run `bun install`.

### `@sveltejs/kit`
Within 2.x: roll forward freely. Read the SvelteKit changelog before
crossing a *minor* boundary if your app uses load functions or
`$app/state` (the demo's `import { page } from '$app/state'` was added in
2.12; older 2.x exposed `page` from `$app/stores`).

### `svelte` (5.x)
Runes API stabilised in 5.0. Newer minors regularly add APIs (e.g.
`{@attach}` in 5.29). Verify with the autofixer after a minor bump.

### `bits-ui` (1 → 2)
**shadcn-svelte components target a specific bits-ui major.** If you
upgrade across this boundary, the components installed with
`bunx shadcn-svelte add ...` need to be **re-installed** so they match the
new bits-ui API surface. Same for the inverse downgrade.

### `tailwind-merge` (2 → 3) / `tailwind-variants` (0.x → 3)
The `cn()` helper from `utils.ts` keeps working unchanged. But
`tailwind-variants`'s public types shifted across the 0.x→1.x line; any
explicit `tv()` factories you wrote may need their generic args re-checked.

### `tailwindcss` (4.x)
Tailwind 4 uses `@tailwindcss/vite` + `@import 'tailwindcss';` in CSS, **not**
the old `tailwind.config.js`. If you see a config file or `npx tailwindcss
init`, the project was upgraded mid-flight and needs `app.css` rewritten
(use `SKILL_DIR/assets/app.css`).

### `mode-watcher` (0.5 → 1)
v1 changed the import surface: `mode` is now a *function*/store object
(`mode.current`) rather than a raw store. The asset `ThemeToggle.svelte`
already uses the 1.x form.

### `svelte-sonner` (0.3 → 1)
v1 is API-compatible for `toast.success` / `toast.error`, but the
`<Toaster ... />` props were tightened — re-check `toastOptions` typings.

### `lucide-svelte` (0.x → 1)
Icons are now imported per-icon (`import Mic from 'lucide-svelte/icons/mic'`)
which the demo's components already do. Some older barrel imports
(`import { Mic } from 'lucide-svelte'`) still work but cost more bundle size.

### `typescript` (5 → 6)
TS 6 is stricter about some inference patterns and dropped a few deprecated
flags. Run `bun run check` after upgrading; expect zero-to-few errors in a
well-typed Svelte 5 codebase.

### `@tauri-apps/api` ↔ `@tauri-apps/cli`
**Same major required.** Tauri 2 JS API and CLI ship in lockstep; mixing
1.x ↔ 2.x silently fails the bundle. Keep both pinned to `^2.x`.

## Standard upgrade recipe

```bash
# 1. Bump (interactive: pick what you want)
bunx npm-check-updates --interactive

# 2. Install + type-check + build
bun install
bun run check
bun --bun run build

# 3. Smoke-test the Tauri target
bun run tauri dev
```

If `bun run check` surfaces type errors, validate the changed Svelte files
with `npx @sveltejs/mcp svelte-autofixer <path>` before fixing manually —
the autofixer often flags the actual API shift.

## Adding a new dep

1. Look up its latest with the curl/jq one-liner above.
2. `bun add <pkg>@latest` (or `bun add -D <pkg>@latest` for devDeps).
3. Update the **Canonical package set** table in this file if it's
   stack-defining for the skill (i.e. another agent should know about it).

---

**Last verified:** 2026-05-20
