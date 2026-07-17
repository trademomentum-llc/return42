mod sidecar;

use sidecar::{kill_sidecar, spawn_sidecar, SidecarState};
use tauri::{Manager, State};

#[tauri::command]
async fn get_sidecar_port(state: State<'_, SidecarState>) -> Result<u16, String> {
    Ok(*state.port.lock().unwrap())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(SidecarState::new())
        .setup(|app| {
            spawn_sidecar(app.handle())?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let _ = kill_sidecar(window.app_handle());
            }
        })
        .invoke_handler(tauri::generate_handler![get_sidecar_port])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
