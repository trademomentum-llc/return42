import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { readSecret, sidecarRequest } from '../api/sidecar';

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

function useClinicToken() {
  return useQuery<string | null>({
    queryKey: ['secrets', 'CLINIC_TOKEN'],
    queryFn: () => readSecret('CLINIC_TOKEN'),
    staleTime: Infinity,
  });
}

export function useHandoffs() {
  const { data: token, isLoading: tokenLoading } = useClinicToken();
  return useQuery<Handoff[]>({
    queryKey: ['handoffs', token],
    queryFn: async () => {
      if (!token) {
        throw new Error('CLINIC_TOKEN is not configured in secure storage.');
      }
      const text = await sidecarRequest(
        'GET',
        `/clinic/handoffs?status=pending`,
        undefined,
        { Authorization: `Bearer ${token}` },
      );
      return JSON.parse(text);
    },
    enabled: !tokenLoading,
  });
}

export function useAcknowledgeHandoff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (handoffId: string) => {
      const token = await readSecret('CLINIC_TOKEN');
      if (!token) {
        throw new Error('CLINIC_TOKEN is not configured in secure storage.');
      }
      const text = await sidecarRequest(
        'POST',
        `/clinic/handoffs/${handoffId}/ack`,
        undefined,
        { Authorization: `Bearer ${token}` },
      );
      return JSON.parse(text);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['handoffs'] }),
  });
}
