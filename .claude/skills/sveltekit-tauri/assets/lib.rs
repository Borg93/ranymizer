// Tauri application entry point.
//
// Add new commands with #[tauri::command] and register them in
// invoke_handler! below. Call them from Svelte via:
//   import { invoke } from '@tauri-apps/api/core';
//   await invoke('greet', { name: 'world' });

#[tauri::command]
fn greet(name: &str) -> String {
    if name.trim().is_empty() {
        "Hello, world!".to_string()
    } else {
        format!("Hello, {name}!")
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|_app| {
            #[cfg(debug_assertions)]
            {
                // Plug in logging only in debug builds.
                // Add `tauri-plugin-log = "2"` to Cargo.toml to use this.
                // _app.handle().plugin(
                //     tauri_plugin_log::Builder::default()
                //         .level(log::LevelFilter::Info)
                //         .build(),
                // )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
