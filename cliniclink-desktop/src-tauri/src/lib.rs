mod sidecar;

use sidecar::{kill_sidecar, spawn_sidecar, SidecarState};
use tauri::{Manager, State};

#[tauri::command]
async fn get_sidecar_port(state: State<'_, SidecarState>) -> Result<u16, String> {
    let child_guard = state
        .child
        .lock()
        .map_err(|e| format!("sidecar child lock poisoned: {}", e))?;
    if child_guard.is_none() {
        return Err("sidecar is not running".to_string());
    }
    drop(child_guard);

    let port_guard = state
        .port
        .lock()
        .map_err(|e| format!("sidecar port lock poisoned: {}", e))?;
    Ok(*port_guard)
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
