import { invoke } from '@tauri-apps/api/core';

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
