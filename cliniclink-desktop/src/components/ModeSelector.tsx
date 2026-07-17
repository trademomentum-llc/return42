import { useState } from 'react';
import { setMode } from '../api/sidecar';
import { useAppStore } from '../store/appStore';

export default function ModeSelector() {
  const setAppMode = useAppStore((s) => s.setMode);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const choose = async (mode: 'clinic' | 'ambulance') => {
    setIsSaving(true);
    setSaveError(null);
    try {
      await setMode(mode);
      setAppMode(mode);
    } catch (error) {
      console.error(`Failed to set mode to ${mode}:`, error);
      setSaveError(error instanceof Error ? error.message : 'Failed to set mode');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-6">
      <h1 className="text-3xl font-bold text-teal-700">ClinicLink Desktop</h1>
      <p className="text-gray-600">Select your role to continue</p>
      {saveError && (
        <p className="text-red-600 text-sm" role="alert">
          {saveError}
        </p>
      )}
      <div className="flex gap-4">
        <button
          onClick={() => choose('clinic')}
          disabled={isSaving}
          className="px-8 py-4 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSaving ? 'Saving…' : 'Clinic'}
        </button>
        <button
          onClick={() => choose('ambulance')}
          disabled={isSaving}
          className="px-8 py-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSaving ? 'Saving…' : 'Ambulance'}
        </button>
      </div>
    </div>
  );
}
