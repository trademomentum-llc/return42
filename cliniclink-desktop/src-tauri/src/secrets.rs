const KEYRING_SERVICE: &str = "com.trademomentum.cliniclink-desktop";

/// Keys the frontend is permitted to store. Service-controlled keys such as
/// `NODE_SIGNING_KEY` must never be written by the frontend.
pub const ALLOWED_STORE_KEYS: &[&str] = &["CLINIC_TOKEN", "CLINICLINK_ADMIN_TOKEN"];

pub async fn store_secret(key: &str, value: &str) -> Result<(), String> {
    if !ALLOWED_STORE_KEYS.contains(&key) {
        return Err("key is not allowed".to_string());
    }
    let entry = keyring::Entry::new(KEYRING_SERVICE, key).map_err(|e| e.to_string())?;
    entry.set_password(value).map_err(|e| e.to_string())
}

pub async fn read_secret(key: &str) -> Result<Option<String>, String> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, key).map_err(|e| e.to_string())?;
    match entry.get_password() {
        Ok(value) => Ok(Some(value)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}
