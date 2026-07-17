import { useEffect } from 'react';
import { listen } from '@tauri-apps/api/event';

export type SidecarEvent = {
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

export function useSidecarEvent(callback: (event: SidecarEvent) => void) {
  useEffect(() => {
    let active = true;
    let unlisten: (() => void) | undefined;

    listen<string>('cliniclink:event', (e) => {
      if (!active) return;
      try {
        callback(JSON.parse(e.payload));
      } catch {
        // ignore malformed events
      }
    }).then((fn) => {
      if (active) {
        unlisten = fn;
      } else {
        fn();
      }
    });

    return () => {
      active = false;
      unlisten?.();
    };
  }, [callback]);
}
