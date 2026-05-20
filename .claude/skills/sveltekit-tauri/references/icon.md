# Icon: Replace the App Icon

Replace the default Tauri icon with a custom one. Tauri's CLI generates all the platform-specific sizes and formats (macOS `.icns`, Windows `.ico`, Linux PNGs) from a single 1024×1024 source PNG.

## Workflow

### Step 1: Have the user prepare a source icon

Ask the user to drop a **1024×1024 PNG** named `app-icon.png` at the project root (next to `package.json`).

If the source is smaller or in a different format, ask them to resize/convert it first — quality-wise, you can only downsample, not upsample. RGBA is recommended so transparency is preserved.

Wait for confirmation, then verify:

```bash
test -f app-icon.png && echo "found" || echo "missing"
```

If it's missing, ask again and don't proceed.

### Step 2: Generate platform icons

From the project root:

```bash
bun run tauri icon app-icon.png
```

This writes the full icon set into `src-tauri/icons/`, overwriting anything that was there:

- `32x32.png`, `128x128.png`, `128x128@2x.png` (Linux)
- `icon.icns` (macOS)
- `icon.ico` (Windows)
- `Square*Logo.png` and `StoreLogo.png` (Windows Store)

If the command fails, read the error. Common causes:

- `app-icon.png` is not exactly 1024×1024 → resize it
- `app-icon.png` is not actually a PNG (e.g. a renamed JPG) → re-export from an image editor
- `@tauri-apps/cli` isn't installed → run `bun install`

### Step 3: Verify

Restart the dev app to confirm:

```bash
bun run tauri dev
```

The Dock (macOS) and taskbar (Windows / Linux) should show the new icon.

### Step 4: Tell the user what changed

- All platform icons in `src-tauri/icons/` were regenerated from `app-icon.png`.
- Keep `app-icon.png` in the project root — when they want to change the icon again, replace that file and re-run `bun run tauri icon app-icon.png`.
- macOS Dock and Windows Explorer cache icons aggressively. If the old icon still shows after rebuild:
  - **macOS**: `rm -rf src-tauri/target` and rebuild, or run `killall Dock` to clear the Dock cache.
  - **Windows**: log out and back in, or restart Explorer.

## Requirements

| Property | Value |
|----------|-------|
| Filename | `app-icon.png` |
| Location | Project root (next to `package.json`) |
| Size     | 1024×1024 pixels |
| Format   | PNG, RGBA recommended |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `app-icon.png` not found | Confirm it's at the project root, not inside `src/` or `src-tauri/` |
| "icon dimensions must be 1024x1024" | Resize with an image editor or `magick app-icon.png -resize 1024x1024 app-icon.png` |
| Old icon still showing after rebuild | Clear OS-level icon caches (see Step 4) |
| `tauri icon` command not recognized | Install `@tauri-apps/cli`: `bun add -D @tauri-apps/cli` |
