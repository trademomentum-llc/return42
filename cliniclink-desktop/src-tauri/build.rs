fn main() {
    tauri_build::try_build(
        tauri_build::Attributes::new().app_manifest(
            tauri_build::AppManifest::new().commands(&[
                "get_sidecar_port",
                "sidecar_request",
                "set_mode",
                "store_secret",
                "has_secret",
            ]),
        ),
    )
    .expect("failed to run tauri-build");
}
