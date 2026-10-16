import { create } from 'zustand';

export interface NoticeItem {
  id: string;
  type: 'success' | 'info' | 'warning' | 'error';
  content: string;
  createdAt: number;
}

interface NoticeState {
  items: NoticeItem[];
  push: (type: NoticeItem['type'], content: string) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}

export const useNoticeStore = create<NoticeState>((set) => ({
  items: [],
  push: (type, content) => {
    const id = `n_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    set((state) => ({ items: [...state.items, { id, type, content, createdAt: Date.now() }] }));
    return id;
  },
  dismiss: (id) => set((state) => ({ items: state.items.filter((item) => item.id !== id) })),
  clear: () => set({ items: [] }),
}));
