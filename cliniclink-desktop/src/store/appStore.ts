import { create } from 'zustand';

interface AppState {
  mode: 'clinic' | 'ambulance' | null;
  setMode: (mode: 'clinic' | 'ambulance') => void;
}

export const useAppStore = create<AppState>((set) => ({
  mode: null,
  setMode: (mode) => set({ mode }),
}));
