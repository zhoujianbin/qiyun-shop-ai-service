import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export type Density = 'comfortable' | 'middle' | 'compact';
export type ThemeMode = 'light' | 'dark' | 'system';

interface UiState {
  siderCollapsed: boolean;
  density: Density;
  theme: ThemeMode;
  toggleSider: () => void;
  setSiderCollapsed: (collapsed: boolean) => void;
  setDensity: (density: Density) => void;
  setTheme: (theme: ThemeMode) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      siderCollapsed: false,
      density: 'comfortable',
      theme: 'light',
      toggleSider: () => set((state) => ({ siderCollapsed: !state.siderCollapsed })),
      setSiderCollapsed: (siderCollapsed) => set({ siderCollapsed }),
      setDensity: (density) => set({ density }),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: 'qy.ui',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ siderCollapsed: state.siderCollapsed, density: state.density, theme: state.theme }),
    },
  ),
);
