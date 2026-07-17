use crate::secrets;
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

pub async fn spawn_sidecar(app: &AppHandle) -> Result<u16, String> {
    let sidecar_path = app
        .path()
        .resolve("r42-cliniclink", tauri::path::BaseDirectory::Resource)
        .map_err(|e| e.to_string())?;

    let mut cmd = Command::new(sidecar_path);
    cmd.arg("sidecar")
        .arg("--port")
        .arg("2842")
        .arg("--host")
        .arg("127.0.0.1")
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());

    if let Ok(Some(key)) = secrets::read_secret("NODE_SIGNING_KEY").await {
        cmd.env("NODE_SIGNING_KEY", key);
    }
    if let Ok(Some(token)) = secrets::read_secret("CLINIC_TOKEN").await {
        cmd.env("CLINIC_TOKEN", token);
    }
    if let Ok(Some(token)) = secrets::read_secret("CLINICLINK_ADMIN_TOKEN").await {
        cmd.env("CLINICLINK_ADMIN_TOKEN", token);
    }

    let child = cmd
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {}", e))?;

    // In a real implementation, parse stdout for SIDECAR_PORT=...
    // For this plan, assume port 2842.
    let port = 2842u16;
    {
        let state: State<SidecarState> = app.state();
        *state
            .child
            .lock()
            .map_err(|e| format!("sidecar child lock poisoned: {}", e))? = Some(child);
        *state
            .port
            .lock()
            .map_err(|e| format!("sidecar port lock poisoned: {}", e))? = port;
    }

    Ok(port)
}

pub fn kill_sidecar(app: &AppHandle) -> Result<(), String> {
    let state: State<SidecarState> = app.state();
    let mut child_guard = state
        .child
        .lock()
        .map_err(|e| format!("sidecar child lock poisoned: {}", e))?;
    if let Some(mut child) = child_guard.take() {
        child
            .kill()
            .map_err(|e| format!("failed to kill sidecar: {}", e))?;
        child
            .wait()
            .map_err(|e| format!("failed to wait for sidecar: {}", e))?;
    }
    Ok(())
}
