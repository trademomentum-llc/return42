import { useEffect } from 'react';
import { listen } from '@tauri-apps/api/event';

export type SidecarEvent = {
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

export function useSidecarEvent(callback: (event: SidecarEvent) => void) {
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    listen<string>('cliniclink:event', (e) => {
      try {
        callback(JSON.parse(e.payload));
      } catch {
        // ignore malformed events
      }
    }).then((fn) => {
      unlisten = fn;
    });
    return () => unlisten?.();
  }, [callback]);
}
