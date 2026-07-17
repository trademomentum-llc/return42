import { useState } from 'react';
import ClinicList from './ClinicList';
import HandoffForm from './HandoffForm';
import { useOutbox } from '../hooks/useOutbox';

export default function AmbulanceView() {
  const [selectedClinic, setSelectedClinic] = useState<string | null>(null);
  const { data: outbox, refetch } = useOutbox();

  return (
    <div className="grid grid-cols-2 gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-4">Target Clinic</h2>
        <ClinicList selected={selectedClinic} onSelect={setSelectedClinic} />
        {selectedClinic && (
          <>
            <h3 className="font-semibold mt-6 mb-2">New Handoff</h3>
            <HandoffForm clinicId={selectedClinic} onSent={() => refetch()} />
          </>
        )}
      </div>
      <div>
        <h2 className="text-xl font-semibold mb-4">Outbox</h2>
        {outbox?.length === 0 && <p className="text-gray-500">No queued handoffs.</p>}
        {outbox?.map((item) => (
          <div key={item.id} className="p-3 bg-white rounded shadow mb-2">
            <p className="font-medium">{item.payload.handoff_id}</p>
            <p className="text-sm text-gray-500">{item.payload.patient_id}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
