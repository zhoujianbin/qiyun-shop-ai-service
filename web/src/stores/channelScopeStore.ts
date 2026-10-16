import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { ChannelAccount } from '@/types/domain';

interface ChannelScopeState {
  available: ChannelAccount[];
  activeIds: number[];
  loaded: boolean;
  setAvailable: (channels: ChannelAccount[]) => void;
  setActive: (ids: number[]) => void;
  setLoaded: (loaded: boolean) => void;
  reset: () => void;
  /** 当前生效的单一渠道账号（后台列表请求参数） */
  activeChannelId: () => number | null;
}

export const useChannelScopeStore = create<ChannelScopeState>()(
  persist(
    (set, get) => ({
      available: [],
      activeIds: [],
      loaded: false,
      setAvailable: (channels) =>
        set((state) => {
          const valid = new Set(channels.map((c) => c.id));
          const kept = state.activeIds.filter((id) => valid.has(id));
          const nextActive = kept.length > 0 ? kept : channels.slice(0, 1).map((c) => c.id);
          return { available: channels, activeIds: nextActive, loaded: true };
        }),
      setActive: (ids) => set({ activeIds: ids }),
      setLoaded: (loaded) => set({ loaded }),
      reset: () => set({ available: [], activeIds: [], loaded: false }),
      activeChannelId: () => {
        const { activeIds } = get();
        return activeIds.length === 1 ? activeIds[0] ?? null : null;
      },
    }),
    {
      name: 'qy.channelScope',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({ activeIds: state.activeIds }),
    },
  ),
);
