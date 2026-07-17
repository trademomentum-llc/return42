import { useState } from 'react';
import { sidecarRequest } from '../api/sidecar';

const ADMIN_TOKEN = 'admin-token'; // load from secure storage in later task

interface Props {
  clinicId: string;
  onSent: () => void;
}

export default function HandoffForm({ clinicId, onSent }: Props) {
  const [patientId, setPatientId] = useState('');
  const [complaint, setComplaint] = useState('');
  const [eta, setEta] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      handoff_id: `ho-${Date.now()}`,
      patient_id: patientId,
      clinic_id: clinicId,
      chief_complaint: complaint,
      eta_minutes: eta ? parseInt(eta, 10) : null,
      vital_signs: {},
      medications: [],
    };
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
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <input value={patientId} onChange={(e) => setPatientId(e.target.value)} placeholder="Patient ID" className="w-full p-2 border rounded" required />
      <input value={complaint} onChange={(e) => setComplaint(e.target.value)} placeholder="Chief complaint" className="w-full p-2 border rounded" required />
      <input value={eta} onChange={(e) => setEta(e.target.value)} placeholder="ETA minutes" type="number" className="w-full p-2 border rounded" />
      <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Send Handoff</button>
    </form>
  );
}
