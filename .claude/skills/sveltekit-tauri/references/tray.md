# Tray: System Tray / Menu Bar Icon

Add a system tray icon (also called menu bar icon on macOS or status bar icon on Linux) with a context menu and left-click handler.

The user gets:

- An icon in the OS status area, template-styled so it adapts to light/dark menu bars on macOS.
- A right-click menu with **Show**, a placeholder action, and **Quit**.
- A left-click handler that shows/focuses the main window.

## Workflow

### Step 1: Have the user prepare a tray icon

Ask the user to provide a **32×32 transparent PNG** (or 64×64 for HiDPI) and place it at `src-tauri/icons/tray-icon.png`.

For best results on macOS, the icon should be **monochrome with transparency** — Tauri renders it as a template image, meaning the OS tints it appropriately for the menu bar's current appearance.

If the user doesn't have a custom icon yet, they can reuse `src-tauri/icons/32x32.png` (the app icon Tauri generates from `app-icon.png`). It'll look fine on Windows and Linux but may look bad on the macOS menu bar because it isn't monochrome.

Verify the file exists:

```bash
test -f src-tauri/icons/tray-icon.png && echo "found" || echo "missing"
```

If it's missing, copy the app icon as a fallback:

```bash
cp src-tauri/icons/32x32.png src-tauri/icons/tray-icon.png
```

### Step 2: Enable the `tray-icon` feature

Read `src-tauri/Cargo.toml`. Add `"tray-icon"` to the `tauri` feature list. If `tauri` has no `features` array yet:

```toml
tauri = { version = "2", features = ["tray-icon"] }
```

If it already has features, append `"tray-icon"` to them. Also add the `image` crate (used to load the PNG into a Tauri `Image`):

```toml
image = "0.25"
```

### Step 3: Copy the tray module

Copy `SKILL_DIR/assets/tray.rs` to `src-tauri/src/tray.rs`. The file defines:

- `setup_tray(app: &AppHandle)` — public entry point you call from `lib.rs`.
- `load_tray_icon()` — loads the PNG via `include_bytes!` and converts it to RGBA.
- `build_tray_menu(app)` — wires the menu items and click handlers.
- `show_main_window(app)` — unminimizes, shows, and focuses the main window.

If the user wants additional menu items, this is the file to extend.

### Step 4: Register the tray in `lib.rs`

Read `src-tauri/src/lib.rs`. Make two changes:

1. Add `mod tray;` near the top, after any existing `mod` declarations.
2. Inside the `.setup` closure, add a call to `setup_tray`:

```rust
.setup(|app| {
    if let Err(e) = tray::setup_tray(app.handle()) {
        eprintln!("Failed to set up tray: {e}");
    }
    Ok(())
})
```

If `.setup` already exists, add the `if let Err(e) = ...` block at the end of its body (before `Ok(())`).

### Step 5: Verify

```bash
bun run check
bun run tauri dev
```

A tray icon should appear in the OS status area. Right-click it to see the menu; left-click it to focus the main window.

### Step 6: Tell the user what they got

- A tray icon at `src-tauri/icons/tray-icon.png` (replace this file to change the icon — no code changes needed).
- A context menu with **Show**, a placeholder **Do something…** item, and **Quit**.
- All click handlers live in `src-tauri/src/tray.rs`. To add a new menu item, follow the pattern: build a `MenuItem`, add it to `Menu::with_items`, then handle its `id` in `.on_menu_event`.
- To trigger a frontend action from a menu item (e.g. "open Settings"), emit a window event from Rust and listen for it in Svelte. There's a commented example at the bottom of `tray.rs` showing the pattern.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Tray icon doesn't appear on Linux | Install `libayatana-appindicator3-dev` and a tray-supporting desktop environment (GNOME requires the AppIndicator extension) |
| Tray icon is blurry on macOS HiDPI | Use a 64×64 PNG; macOS will downscale for standard displays |
| Tray icon looks wrong color on macOS | Make it monochrome with transparency; `icon_as_template(true)` is already set |
| Menu doesn't open on left-click on Windows | This is normal — left-click shows the window; right-click shows the menu. To open the menu on left-click too, set `.show_menu_on_left_click(true)` in `tray.rs` (already enabled) |
| "feature `tray-icon` not found" | Confirm `"tray-icon"` is in the `tauri` feature list in `Cargo.toml` |
