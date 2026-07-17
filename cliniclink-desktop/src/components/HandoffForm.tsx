import { useState } from 'react';
import { sidecarRequest } from '../api/sidecar';

// TODO(Task 15): move to secure storage
const ADMIN_TOKEN = import.meta.env.VITE_CLINICLINK_ADMIN_TOKEN || 'admin-token';

interface Props {
  clinicId: string;
  onSent: () => void;
}

export default function HandoffForm({ clinicId, onSent }: Props) {
  const [patientId, setPatientId] = useState('');
  const [complaint, setComplaint] = useState('');
  const [eta, setEta] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [etaError, setEtaError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setEtaError(null);

    let etaMinutes: number | null = null;
    if (eta.trim() !== '') {
      const parsed = parseInt(eta, 10);
      if (!(Number.isInteger(parsed) && parsed >= 0)) {
        setEtaError('ETA must be a non-negative whole number.');
        return;
      }
      etaMinutes = parsed;
    }

    const payload = {
      handoff_id: `ho-${Date.now()}`,
      patient_id: patientId,
      clinic_id: clinicId,
      chief_complaint: complaint,
      eta_minutes: etaMinutes,
      vital_signs: {},
      medications: [],
    };

    setSubmitting(true);
    try {
      await sidecarRequest(
        'POST',
        '/ambulance/handoffs',
        payload,
        { Authorization: `Bearer ${ADMIN_TOKEN}` },
      );
      onSent();
      setPatientId('');
      setComplaint('');
      setEta('');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to send handoff.';
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <input value={patientId} onChange={(e) => setPatientId(e.target.value)} placeholder="Patient ID" className="w-full p-2 border rounded" required />
      <input value={complaint} onChange={(e) => setComplaint(e.target.value)} placeholder="Chief complaint" className="w-full p-2 border rounded" required />
      <input value={eta} onChange={(e) => { setEta(e.target.value); setEtaError(null); }} placeholder="ETA minutes" type="number" className="w-full p-2 border rounded" />
      {etaError && <p className="text-sm text-red-600">{etaError}</p>}
      <button
        type="submit"
        disabled={submitting}
        className={`px-4 py-2 rounded text-white ${submitting ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'}`}
      >
        {submitting ? 'Sending…' : 'Send Handoff'}
      </button>
      {submitError && <p className="text-sm text-red-600">{submitError}</p>}
    </form>
  );
}
