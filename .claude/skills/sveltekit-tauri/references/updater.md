# Updater: Auto-Updater Configuration

Add over-the-air updates to a SvelteKit + Tauri app using `@tauri-apps/plugin-updater`. The app will periodically check a JSON endpoint for new versions, download the signed bundle, install it, and relaunch.

The flow is:

1. Build a release bundle with a private signing key.
2. Upload the bundle + a `latest.json` manifest to a public URL.
3. The installed app checks `latest.json` on startup (or on user demand), verifies the signature, and applies the update.

## Workflow

### Step 1: Generate a signing key pair

Tauri uses a public/private keypair to sign updates. The **public** key is baked into the app at build time; the **private** key signs each release.

```bash
bunx @tauri-apps/cli@latest signer generate -w ~/.tauri/myapp.key
```

This writes two files:

- `~/.tauri/myapp.key` — **private** key. Never commit. Treat like a credential.
- `~/.tauri/myapp.key.pub` — **public** key. Copy the contents (a base64 string) into `tauri.conf.json` in Step 3.

If the user already has a key (e.g. from a previous setup), skip generation and just locate the existing files.

### Step 2: Install the updater plugin

```bash
bun add @tauri-apps/plugin-updater @tauri-apps/plugin-process
```

Add the Rust crates to `src-tauri/Cargo.toml` `[dependencies]`:

```toml
tauri-plugin-updater = "2"
tauri-plugin-process = "2"
```

### Step 3: Configure `tauri.conf.json`

Read `src-tauri/tauri.conf.json` and add a `plugins.updater` block. Use the **contents** of `~/.tauri/myapp.key.pub` (not the path) as `pubkey`:

```json
{
  "plugins": {
    "updater": {
      "active": true,
      "endpoints": [
        "https://example.com/releases/{{target}}/{{current_version}}"
      ],
      "dialog": false,
      "pubkey": "PASTE_CONTENTS_OF_myapp.key.pub_HERE"
    }
  }
}
```

About the fields:

- **endpoints**: a list of URLs the app polls. Tauri substitutes `{{target}}` (e.g. `darwin-aarch64`, `windows-x86_64`) and `{{current_version}}`. Use a CDN-backed static endpoint or a GitHub Releases URL.
- **dialog**: `false` means the app controls the update UI in JavaScript (recommended for a polished UX). `true` shows Tauri's built-in dialog.
- **pubkey**: the public key that verifies update signatures.

### Step 4: Register the plugins in Rust

Read `src-tauri/src/lib.rs`. Add the plugin registrations before `.run(`:

```rust
tauri::Builder::default()
    .plugin(tauri_plugin_updater::Builder::new().build())
    .plugin(tauri_plugin_process::init())
    // ...existing plugins and setup
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
```

### Step 5: Add the updater permissions

Read `src-tauri/capabilities/default.json`. Add to the `permissions` array:

```json
"updater:default",
"process:default",
"process:allow-restart"
```

### Step 6: Copy the JS helper

Copy `SKILL_DIR/assets/updater.ts` to `src/lib/updater.ts`. It exports a small Svelte store and two functions:

- **`updaterState`** — a writable store with `{ checked, checking, installing, hasUpdate, latestVersion, error }`.
- **`ensureUpdateChecked(force?)`** — checks for an update once per session (or always, if `force = true`). Safe to call from multiple places; concurrent calls share one in-flight request.
- **`installAvailableUpdate(onProgress?)`** — downloads, installs, and relaunches. Pass an optional callback to receive download progress events.

### Step 7: Wire it into the UI

Add a minimal "check for updates" UI somewhere in the app — typically a button in Settings or a banner at the top of the main view:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureUpdateChecked, installAvailableUpdate, updaterState } from '$lib/updater';

  onMount(() => {
    // Check silently on app launch.
    ensureUpdateChecked().catch(console.error);
  });
</script>

{#if $updaterState.hasUpdate}
  <div class="banner">
    Update available: v{$updaterState.latestVersion}
    <button
      onclick={() => installAvailableUpdate()}
      disabled={$updaterState.installing}
    >
      {$updaterState.installing ? 'Installing…' : 'Install and restart'}
    </button>
  </div>
{/if}
```

### Step 8: Build and sign a release

When the user is ready to ship, build with the private key in env:

```bash
TAURI_SIGNING_PRIVATE_KEY="$(cat ~/.tauri/myapp.key)" \
TAURI_SIGNING_PRIVATE_KEY_PASSWORD="" \
bun run tauri build
```

The build produces installers in `src-tauri/target/release/bundle/` plus `.sig` files containing the signature for each bundle.

### Step 9: Publish a `latest.json` manifest

Upload each platform's installer + signature to the endpoint, plus a `latest.json` manifest in this shape:

```json
{
  "version": "1.2.3",
  "notes": "What's new in this release",
  "pub_date": "2026-01-15T12:00:00Z",
  "platforms": {
    "darwin-aarch64": {
      "signature": "CONTENTS_OF_THE_.sig_FILE",
      "url": "https://example.com/releases/myapp_1.2.3_aarch64.app.tar.gz"
    },
    "windows-x86_64": {
      "signature": "CONTENTS_OF_THE_.sig_FILE",
      "url": "https://example.com/releases/myapp_1.2.3_x64-setup.nsis.zip"
    },
    "linux-x86_64": {
      "signature": "CONTENTS_OF_THE_.sig_FILE",
      "url": "https://example.com/releases/myapp_1.2.3_amd64.AppImage.tar.gz"
    }
  }
}
```

If hosting on GitHub Releases, the simplest pattern is the [`tauri-action`](https://github.com/tauri-apps/tauri-action) workflow — it builds for each platform and publishes the manifest automatically.

### Step 10: Tell the user what they got

- A signing keypair at `~/.tauri/myapp.key` (private — never commit) and `~/.tauri/myapp.key.pub` (public — embedded in the app via `tauri.conf.json`).
- The updater plugin enabled, polling `endpoints[0]` for new versions.
- A `$lib/updater.ts` helper with `ensureUpdateChecked()` and `installAvailableUpdate()` — call these from any Svelte component.
- A release workflow: `bun run tauri build` with the signing key in env, then upload the bundle + `.sig` file + a `latest.json` manifest to the endpoint.
- For ongoing releases: bump `version` in `package.json` and `src-tauri/tauri.conf.json`, build, sign, and update `latest.json`. Existing installs will pick up the new version on their next check.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `signature verification failed` on install | Confirm the `pubkey` in `tauri.conf.json` matches the one used to sign the bundle |
| `endpoint returned 404` | Confirm the endpoint URL templating (`{{target}}`, `{{current_version}}`) resolves correctly — Tauri logs the resolved URL at the `info` level |
| `no update available` even after publishing | The manifest's `version` must be strictly greater than the installed version (semver comparison) |
| App doesn't relaunch after install | Check that `process:allow-restart` is in `capabilities/default.json` and `tauri_plugin_process::init()` is registered |
| Build fails: "missing TAURI_SIGNING_PRIVATE_KEY" | Pass the env var as in Step 8; the password env var is also required even if empty |
