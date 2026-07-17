import { useHandoffs, useAcknowledgeHandoff } from '../hooks/useHandoffs';
import { useSidecarEvent } from '../hooks/useEvents';
import HandoffCard from './HandoffCard';

let alertCtx: AudioContext | null = null;

function playAlert() {
  if (!alertCtx) {
    alertCtx = new AudioContext();
  }
  if (alertCtx.state === 'suspended') {
    alertCtx.resume();
  }
  const osc = alertCtx.createOscillator();
  osc.connect(alertCtx.destination);
  osc.start();
  osc.stop(alertCtx.currentTime + 0.2);
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
