import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sidecarRequest } from '../api/sidecar';

export interface Handoff {
  handoff_id: string;
  patient_id: string;
  ambulance_id: string;
  clinic_id: string;
  chief_complaint: string;
  eta_minutes: number | null;
  status: 'pending' | 'acknowledged' | 'rejected';
  vital_signs: Record<string, unknown>;
  medications: string[];
  created_at: string;
  acknowledged_at: string | null;
}

const CLINIC_TOKEN = 'clinic-token'; // load from secure storage in later task

export function useHandoffs() {
  return useQuery<Handoff[]>({
    queryKey: ['handoffs'],
    queryFn: async () => {
      const text = await sidecarRequest(
        'GET',
        `/clinic/handoffs?status=pending`,
        undefined,
        { Authorization: `Bearer ${CLINIC_TOKEN}` },
      );
      return JSON.parse(text);
    },
  });
}

export function useAcknowledgeHandoff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (handoffId: string) => {
      const text = await sidecarRequest(
        'POST',
        `/clinic/handoffs/${handoffId}/ack`,
        undefined,
        { Authorization: `Bearer ${CLINIC_TOKEN}` },
      );
      return JSON.parse(text);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['handoffs'] }),
  });
}
