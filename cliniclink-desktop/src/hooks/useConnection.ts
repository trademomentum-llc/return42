import { useState } from 'react';
import { useSidecarEvent } from './useEvents';

export function useConnection() {
  const [status, setStatus] = useState<'healthy' | 'degraded' | 'offline'>('healthy');

  useSidecarEvent((event) => {
    if (event.type === 'connection.degraded') setStatus('degraded');
    if (event.type === 'connection.restored') setStatus('healthy');
    if (event.type === 'mesh.peer.lost') setStatus('degraded');
  });

  return status;
}
