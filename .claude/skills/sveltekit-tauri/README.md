# sveltekit-tauri

A Claude skill for scaffolding and extending **SvelteKit 2 + Tauri 2** desktop applications using a modern stack: Bun, Vite 7 with Rolldown, Tailwind CSS 4, shadcn-svelte, and Biome 2.

## Capabilities

| Capability        | What it does                                                                                |
|-------------------|---------------------------------------------------------------------------------------------|
| **Bootstrap**     | Scaffold a new SvelteKit + Tauri project end-to-end, with a working `invoke` example.       |
| **Icon**          | Replace the default app icon with a custom 1024×1024 PNG across all platforms.              |
| **Tray**          | Add a system tray / menu bar icon with a context menu and click handlers.                   |
| **Updater**       | Configure the auto-updater plugin for signed over-the-air updates.                          |
| **shadcn**        | Add shadcn-svelte components to an existing project.                                        |
| **Tauri command** | Expose a Rust function to the Svelte frontend via `invoke`.                                 |

## Structure

```
sveltekit-tauri/
├── SKILL.md              # Router — maps user requests to capabilities
├── references/           # Detailed workflows for each capability
│   ├── bootstrap.md
│   ├── icon.md
│   ├── tray.md
│   ├── updater.md
│   ├── shadcn.md
│   └── command.md
└── assets/               # Files copied into the user's project
    ├── app.css           # Tailwind 4 + shadcn-svelte design tokens
    ├── biome.json        # Biome config
    ├── components.json   # shadcn-svelte CLI config
    ├── utils.ts          # cn() helper that shadcn components import
    ├── lib.rs            # Sample Tauri entry with a greet command
    ├── +page.svelte      # Sample home page calling invoke('greet')
    ├── tray.rs           # System tray module
    └── updater.ts        # Svelte store + helpers for the updater
```

## Design choices

- **English-only**: keywords, code comments, button labels, and trigger phrases are all in English.
- **Bun-first**: `bun` is the assumed package manager. The skill never falls back to `npm` or `pnpm` unless the user asks.
- **SPA, not SSG**: bootstrap configures `adapter-static` with `fallback: 'index.html'` so `load` functions run in the WebView and can call Tauri APIs without prerender workarounds.
- **Rolldown by default**: bootstrap installs `rolldown-vite` as a Vite alias for faster builds, with `esbuild: false` since the two don't mix.
- **Servo is out of scope**: the experimental `tauri-runtime-verso` runtime is intentionally not included — it's still rough around the edges. Users who want it can add it themselves following the Nopsled template.
- **One working example end-to-end**: bootstrap leaves the user with a `greet` command they can actually call, so the next time they want a new command they have a working pattern to copy.

## License

MIT
