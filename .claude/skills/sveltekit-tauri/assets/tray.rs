// System tray icon with a context menu.
//
// Loads `src-tauri/icons/tray-icon.png` and wires up a menu with
// Show / Do something… / Quit. Call `setup_tray(app.handle())` from
// inside the .setup closure in lib.rs.

use image::ImageDecoder;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager,
};

pub fn setup_tray(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    build_tray_menu(app)?;
    Ok(())
}

fn load_tray_icon() -> tauri::image::Image<'static> {
    // Decode the embedded PNG into raw RGBA bytes so Tauri can render it.
    let png_bytes = include_bytes!("../icons/tray-icon.png");
    let decoder = image::codecs::png::PngDecoder::new(std::io::Cursor::new(png_bytes))
        .expect("tray-icon.png is not a valid PNG");
    let (width, height) = decoder.dimensions();
    let mut rgba = vec![0u8; (width * height * 4) as usize];

    let decoder = image::codecs::png::PngDecoder::new(std::io::Cursor::new(png_bytes))
        .expect("tray-icon.png is not a valid PNG");
    ImageDecoder::read_image(decoder, rgba.as_mut_slice())
        .expect("failed to decode tray-icon.png");

    tauri::image::Image::new_owned(rgba, width, height)
}

fn build_tray_menu(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    // Menu items. The first arg of MenuItem::with_id is the id used in
    // the .on_menu_event handler below.
    let show_item = MenuItem::with_id(app, "show", "Show", true, None::<&str>)?;
    let action_item = MenuItem::with_id(app, "do_something", "Do something…", true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&show_item, &action_item, &separator, &quit_item])?;

    let icon = load_tray_icon();

    let _tray = TrayIconBuilder::new()
        .icon(icon)
        // template = true makes the icon adapt to light/dark menu bars on macOS.
        // Set to false if you ship a full-color icon.
        .icon_as_template(true)
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => show_main_window(app),
            "do_something" => {
                // Placeholder. Replace with your own action, or emit an event
                // to the frontend (see the example function at the bottom).
                eprintln!("tray: 'do_something' clicked");
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            // Left-click on the tray icon brings the main window forward.
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main_window(tray.app_handle());
            }
        })
        .build(app)?;

    Ok(())
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

// Example: trigger a frontend action from a tray menu item by emitting an event.
// Uncomment and adapt when you need a menu item to open a route, modal, etc.
//
// use tauri::Emitter;
//
// fn show_main_window_with_event(app: &AppHandle, event_name: &str) {
//     if let Some(window) = app.get_webview_window("main") {
//         let _ = window.unminimize();
//         let _ = window.show();
//         let _ = window.set_focus();
//         let _ = window.emit(event_name, ());
//     }
// }
//
// On the Svelte side:
//   import { listen } from '@tauri-apps/api/event';
//   const unlisten = await listen('open-settings', () => { /* ... */ });
