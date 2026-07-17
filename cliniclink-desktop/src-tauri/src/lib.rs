mod secrets;
mod sidecar;

use sidecar::{kill_sidecar, spawn_sidecar, SidecarState};
use tauri::{Emitter, Manager, State};

#[tauri::command]
async fn store_secret(key: String, value: String) -> Result<(), String> {
    secrets::store_secret(&key, &value).await
}

/// Returns whether a secret exists without exposing its value to the frontend.
/// Only keys the frontend is allowed to store may be queried.
#[tauri::command]
async fn has_secret(key: String) -> Result<bool, String> {
    if !secrets::ALLOWED_STORE_KEYS.contains(&key.as_str()) {
        return Err(format!(
            "key '{}' is not allowed; only {:?} may be queried",
            key,
            secrets::ALLOWED_STORE_KEYS
        ));
    }
    match secrets::read_secret(&key).await {
        Ok(Some(_)) => Ok(true),
        Ok(None) => Ok(false),
        Err(e) => Err(e),
    }
}

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

#[tauri::command]
async fn sidecar_request(
    state: State<'_, SidecarState>,
    method: String,
    path: String,
    body: Option<String>,
    headers: Option<String>,
) -> Result<String, String> {
    let port = *state
        .port
        .lock()
        .map_err(|e| format!("sidecar port lock poisoned: {}", e))?;
    let url = format!("http://127.0.0.1:{}{}", port, path);
    let client = reqwest::Client::new();
    let mut req = match method.to_uppercase().as_str() {
        "GET" => client.get(&url),
        "POST" => client.post(&url),
        "PUT" => client.put(&url),
        "DELETE" => client.delete(&url),
        _ => return Err("unsupported method".to_string()),
    };
    if let Some(h) = headers {
        let parsed: std::collections::HashMap<String, String> =
            serde_json::from_str(&h).map_err(|e| e.to_string())?;
        for (k, v) in parsed {
            req = req.header(k, v);
        }
    }
    if let Some(b) = body {
        req = req.body(b).header("Content-Type", "application/json");
    }
    let resp = req.send().await.map_err(|e| e.to_string())?;
    let text = resp.text().await.map_err(|e| e.to_string())?;
    Ok(text)
}

#[tauri::command]
async fn set_mode(state: State<'_, SidecarState>, mode: String) -> Result<String, String> {
    sidecar_request(
        state,
        "POST".to_string(),
        "/mode".to_string(),
        Some(format!("{{\"mode\":\"{}\"}}", mode)),
        None,
    )
    .await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(SidecarState::new())
        .setup(|app| {
            tokio::runtime::Handle::current()
                .block_on(spawn_sidecar(app.handle()))?;
            let handle = app.handle().clone();
            let port: u16 = *handle
                .state::<SidecarState>()
                .port
                .lock()
                .map_err(|e| format!("sidecar port lock poisoned: {}", e))?;
            tauri::async_runtime::spawn(async move {
                use futures_util::StreamExt;
                use tokio_tungstenite::tungstenite::Message;

                let url = format!("ws://127.0.0.1:{}/events", port);
                if let Ok((mut ws, _)) = tokio_tungstenite::connect_async(&url).await {
                    while let Some(Ok(Message::Text(text))) = ws.next().await {
                        let _ = handle.emit("cliniclink:event", text);
                    }
                }
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let _ = kill_sidecar(window.app_handle());
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_sidecar_port,
            sidecar_request,
            set_mode,
            store_secret,
            has_secret
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
