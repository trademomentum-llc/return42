use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};

pub struct SidecarState {
    pub child: Mutex<Option<Child>>,
    pub port: Mutex<u16>,
}

impl SidecarState {
    pub fn new() -> Self {
        Self {
            child: Mutex::new(None),
            port: Mutex::new(2842),
        }
    }
}

pub fn spawn_sidecar(app: &AppHandle) -> Result<u16, String> {
    let sidecar_path = app
        .path()
        .resolve("r42-cliniclink", tauri::path::BaseDirectory::Resource)
        .map_err(|e| e.to_string())?;

    let child = Command::new(sidecar_path)
        .arg("sidecar")
        .arg("--port")
        .arg("2842")
        .arg("--host")
        .arg("127.0.0.1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {}", e))?;

    // In a real implementation, parse stdout for SIDECAR_PORT=...
    // For this plan, assume port 2842 and verify health.
    let port = 2842u16;
    {
        let state: State<SidecarState> = app.state();
        *state.child.lock().unwrap() = Some(child);
        *state.port.lock().unwrap() = port;
    }

    Ok(port)
}

pub fn kill_sidecar(app: &AppHandle) -> Result<(), String> {
    let state: State<SidecarState> = app.state();
    if let Some(mut child) = state.child.lock().unwrap().take() {
        let _ = child.kill();
        let _ = child.wait();
    }
    Ok(())
}
