import { invoke } from '@tauri-apps/api/core';

/** Keys the frontend is permitted to store or query. */
export type StoredSecretKey = 'CLINIC_TOKEN' | 'CLINICLINK_ADMIN_TOKEN';

export async function sidecarRequest(
  method: string,
  path: string,
  body?: object,
  headers?: Record<string, string>,
): Promise<string> {
  return invoke('sidecar_request', {
    method,
    path,
    body: body ? JSON.stringify(body) : undefined,
    headers: headers ? JSON.stringify(headers) : undefined,
  });
}

export async function setMode(mode: 'clinic' | 'ambulance'): Promise<string> {
  return invoke('set_mode', { mode });
}

export async function getMode(): Promise<{ mode: string | null }> {
  const text = await sidecarRequest('GET', '/mode');
  return JSON.parse(text);
}

/** Store a token in the OS keychain. Service keys such as NODE_SIGNING_KEY cannot be written. */
export async function storeSecret(
  key: StoredSecretKey,
  value: string,
): Promise<void> {
  return invoke('store_secret', { key, value });
}

/** Check whether a token exists in secure storage without reading its value. */
export async function hasSecret(key: StoredSecretKey): Promise<boolean> {
  return invoke('has_secret', { key });
}
