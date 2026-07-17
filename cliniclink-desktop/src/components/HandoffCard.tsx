import type { Handoff } from '../hooks/useHandoffs';

interface Props {
  handoff: Handoff;
  onAck: (id: string) => void;
}

export default function HandoffCard({ handoff, onAck }: Props) {
  return (
    <div className="bg-white rounded-lg shadow p-4 mb-4 border-l-4 border-teal-500">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="font-bold text-lg">{handoff.patient_id}</h3>
          <p className="text-gray-700">{handoff.chief_complaint || 'No complaint recorded'}</p>
          <p className="text-sm text-gray-500">Ambulance: {handoff.ambulance_id} | ETA: {handoff.eta_minutes ?? '?'} min</p>
        </div>
        <button
          onClick={() => onAck(handoff.handoff_id)}
          className="px-4 py-2 bg-teal-600 text-white rounded hover:bg-teal-700"
        >
          Acknowledge
        </button>
      </div>
      {handoff.vital_signs && Object.keys(handoff.vital_signs).length > 0 && (
        <pre className="mt-2 text-xs bg-gray-100 p-2 rounded">{JSON.stringify(handoff.vital_signs, null, 2)}</pre>
      )}
      {handoff.medications && handoff.medications.length > 0 && (
        <p className="mt-2 text-sm text-gray-600">Meds: {handoff.medications.join(', ')}</p>
      )}
    </div>
  );
}
