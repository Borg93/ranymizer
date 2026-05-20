// No #[tauri::command]s by design: the whole pipeline runs in the WebView,
// so the native surface stays minimal.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
