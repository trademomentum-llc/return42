import { useQuery } from '@tanstack/react-query';
import { sidecarRequest } from '../api/sidecar';

export interface Clinic {
  node_id: string;
  verify_key_b64: string;
}

export function useClinics() {
  return useQuery<Clinic[]>({
    queryKey: ['clinics'],
    queryFn: async () => {
      const text = await sidecarRequest('GET', '/ambulance/clinics');
      return JSON.parse(text);
    },
  });
}
