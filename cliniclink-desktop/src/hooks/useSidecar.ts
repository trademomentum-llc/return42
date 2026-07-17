import { useCallback, useState } from 'react';
import { getMode, setMode, sidecarRequest } from '../api/sidecar';

export type SidecarHook = {
  loading: boolean;
  error: string | null;
  request: <T>(method: string, path: string, body?: object, headers?: Record<string, string>) => Promise<T | null>;
  get: <T>(path: string, headers?: Record<string, string>) => Promise<T | null>;
  post: <T>(path: string, body?: object, headers?: Record<string, string>) => Promise<T | null>;
  put: <T>(path: string, body?: object, headers?: Record<string, string>) => Promise<T | null>;
  del: <T>(path: string, headers?: Record<string, string>) => Promise<T | null>;
  setMode: (mode: 'clinic' | 'ambulance') => Promise<string | null>;
  getMode: () => Promise<{ mode: string | null } | null>;
  clearError: () => void;
};

export function useSidecar(): SidecarHook {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const request = useCallback(async <T,>(
    method: string,
    path: string,
    body?: object,
    headers?: Record<string, string>,
  ): Promise<T | null> => {
    setLoading(true);
    setError(null);
    try {
      const text = await sidecarRequest(method, path, body, headers);
      return JSON.parse(text) as T;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

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

  return {
    loading,
    error,
    request,
    get,
    post,
    put,
    del,
    setMode: setModeCallback,
    getMode: getModeCallback,
    clearError,
  };
}
