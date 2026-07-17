import { useEffect } from 'react';
import ModeSelector from './components/ModeSelector';
import ClinicView from './components/ClinicView';
import AmbulanceView from './components/AmbulanceView';
import ConnectionStatus from './components/ConnectionStatus';
import { useAppStore } from './store/appStore';
import { getMode } from './api/sidecar';
import { useConnection } from './hooks/useConnection';

export default function App() {
  const mode = useAppStore((s) => s.mode);
  const setMode = useAppStore((s) => s.setMode);
  const connectionStatus = useConnection();

  useEffect(() => {
    getMode()
      .then((m) => {
        if (m.mode === 'clinic' || m.mode === 'ambulance') setMode(m.mode);
      })
      .catch((error) => {
        console.error('Failed to load current mode:', error);
      });
  }, [setMode]);

  if (!mode) return <ModeSelector />;

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <header className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold text-teal-700">ClinicLink Desktop</h1>
        <div className="flex items-center gap-4">
          <ConnectionStatus status={connectionStatus} />
          <span className="text-sm uppercase tracking-wide text-gray-500">{mode} mode</span>
        </div>
      </header>
      {mode === 'clinic' ? <ClinicView /> : mode === 'ambulance' ? <AmbulanceView /> : <p>Mode: {mode}</p>}
    </div>
  );
}
