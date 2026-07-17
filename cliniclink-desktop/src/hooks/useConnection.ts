import { useEffect, useRef, useState } from 'react';
import { sidecarRequest } from '../api/sidecar';
import { useSidecarEvent } from './useEvents';

const HEALTH_INTERVAL_MS = 5000;
const OFFLINE_FAILURE_THRESHOLD = 2;

export function useConnection() {
  const [status, setStatus] = useState<'healthy' | 'degraded' | 'offline'>('healthy');
  const consecutiveFailuresRef = useRef(0);
  const degradedByEventRef = useRef(false);

  useEffect(() => {
    let active = true;

    async function pollHealth() {
      try {
        await sidecarRequest('GET', '/health');
        if (!active) return;
        consecutiveFailuresRef.current = 0;
        setStatus(degradedByEventRef.current ? 'degraded' : 'healthy');
      } catch {
        if (!active) return;
        consecutiveFailuresRef.current += 1;
        if (consecutiveFailuresRef.current >= OFFLINE_FAILURE_THRESHOLD) {
          setStatus('offline');
        }
      }
    }

    pollHealth();
    const interval = setInterval(pollHealth, HEALTH_INTERVAL_MS);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  useSidecarEvent((event) => {
    if (event.type === 'connection.degraded' || event.type === 'mesh.peer.lost') {
      degradedByEventRef.current = true;
      setStatus('degraded');
    }
    if (event.type === 'connection.restored') {
      degradedByEventRef.current = false;
      setStatus('healthy');
    }
    if (event.type === 'connection.lost') {
      setStatus('offline');
    }
  });

  return status;
}
