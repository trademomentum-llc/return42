import { useCallback, useMemo, useState } from 'react';
import { getMode, setMode, sidecarRequest } from '../api/sidecar';

export type SidecarHook = {
  loading: boolean;
  error: string | null;
  requestText: (
    method: string,
    path: string,
    body?: object,
    headers?: Record<string, string>,
  ) => Promise<string | null>;
  request: <T>(method: string, path: string, body?: object, headers?: Record<string, string>) => Promise<T | null>;
  get: <T>(path: string, headers?: Record<string, string>) => Promise<T | null>;
  post: <T>(path: string, body?: object, headers?: Record<string, string>) => Promise<T | null>;
  put: <T>(path: string, body?: object, headers?: Record<string, string>) => Promise<T | null>;
  del: <T>(path: string, headers?: Record<string, string>) => Promise<T | null>;
  setMode: (mode: 'clinic' | 'ambulance') => Promise<string | null>;
  getMode: () => Promise<{ mode: string | null } | null>;
  clearError: () => void;
};

function looksLikeJson(text: string): boolean {
  const trimmed = text.trim();
  if (trimmed.length === 0) return false;
  const first = trimmed[0];
  const last = trimmed[trimmed.length - 1];
  if (first === '{' && last === '}') return true;
  if (first === '[' && last === ']') return true;
  if (first === '"') return true;
  if (/^(true|false|null|-?\d+(\.\d+)?([eE][+-]?\d+)?)$/.test(trimmed)) return true;
  return false;
}

export function useSidecar(): SidecarHook {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requestText = useCallback(async (
    method: string,
    path: string,
    body?: object,
    headers?: Record<string, string>,
  ): Promise<string | null> => {
    setLoading(true);
    setError(null);
    try {
      return await sidecarRequest(method, path, body, headers);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const request = useCallback(async <T,>(
    method: string,
    path: string,
    body?: object,
    headers?: Record<string, string>,
  ): Promise<T | null> => {
    const text = await requestText(method, path, body, headers);
    if (text === null || text === '') return null;
    if (!looksLikeJson(text)) return null;
    try {
      return JSON.parse(text) as T;
    } catch {
      return null;
    }
  }, [requestText]);

  const get = useCallback(
    <T,>(path: string, headers?: Record<string, string>): Promise<T | null> =>
      request<T>('GET', path, undefined, headers),
    [request],
  );

  const post = useCallback(
    <T,>(path: string, body?: object, headers?: Record<string, string>): Promise<T | null> =>
      request<T>('POST', path, body, headers),
    [request],
  );

  const put = useCallback(
    <T,>(path: string, body?: object, headers?: Record<string, string>): Promise<T | null> =>
      request<T>('PUT', path, body, headers),
    [request],
  );

  const del = useCallback(
    <T,>(path: string, headers?: Record<string, string>): Promise<T | null> =>
      request<T>('DELETE', path, undefined, headers),
    [request],
  );

  const setModeCallback = useCallback(async (mode: 'clinic' | 'ambulance'): Promise<string | null> => {
    setLoading(true);
    setError(null);
    try {
      return await setMode(mode);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const getModeCallback = useCallback(async (): Promise<{ mode: string | null } | null> => {
    setLoading(true);
    setError(null);
    try {
      return await getMode();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return useMemo(
    () => ({
      loading,
      error,
      requestText,
      request,
      get,
      post,
      put,
      del,
      setMode: setModeCallback,
      getMode: getModeCallback,
      clearError,
    }),
    [loading, error, requestText, request, get, post, put, del, setModeCallback, getModeCallback, clearError],
  );
}
