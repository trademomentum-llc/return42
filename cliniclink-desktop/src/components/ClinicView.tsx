import { useHandoffs, useAcknowledgeHandoff } from '../hooks/useHandoffs';
import { useSidecarEvent } from '../hooks/useEvents';
import HandoffCard from './HandoffCard';

function playAlert() {
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  osc.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.2);
}

export default function ClinicView() {
  const { data: handoffs, isLoading, refetch } = useHandoffs();
  const ack = useAcknowledgeHandoff();

  useSidecarEvent((event) => {
    if (event.type === 'handoff.received') {
      playAlert();
      refetch();
    }
  });

  if (isLoading) return <p>Loading handoffs...</p>;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Incoming Handoffs</h2>
      {handoffs?.length === 0 && <p className="text-gray-500">No pending handoffs.</p>}
      {handoffs?.map((h) => (
        <HandoffCard key={h.handoff_id} handoff={h} onAck={(id) => ack.mutate(id)} />
      ))}
    </div>
  );
}
