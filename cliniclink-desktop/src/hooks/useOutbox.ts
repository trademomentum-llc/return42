import { useQuery } from '@tanstack/react-query';
import { sidecarRequest } from '../api/sidecar';

export interface OutboxItem {
  id: number;
  payload: {
    handoff_id?: string;
    patient_id?: string;
    [key: string]: unknown;
  };
}

export function useOutbox() {
  return useQuery<OutboxItem[]>({
    queryKey: ['outbox'],
    queryFn: async () => {
      const text = await sidecarRequest('GET', '/ambulance/outbox');
      return JSON.parse(text);
    },
  });
}
