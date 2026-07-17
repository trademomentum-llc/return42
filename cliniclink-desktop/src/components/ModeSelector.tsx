import { setMode } from '../api/sidecar';
import { useAppStore } from '../store/appStore';

export default function ModeSelector() {
  const setAppMode = useAppStore((s) => s.setMode);

  const choose = async (mode: 'clinic' | 'ambulance') => {
    await setMode(mode);
    setAppMode(mode);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-6">
      <h1 className="text-3xl font-bold text-teal-700">ClinicLink Desktop</h1>
      <p className="text-gray-600">Select your role to continue</p>
      <div className="flex gap-4">
        <button
          onClick={() => choose('clinic')}
          className="px-8 py-4 bg-teal-600 text-white rounded-lg hover:bg-teal-700"
        >
          Clinic
        </button>
        <button
          onClick={() => choose('ambulance')}
          className="px-8 py-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Ambulance
        </button>
      </div>
    </div>
  );
}
