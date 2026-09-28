import { create } from 'zustand';

export interface Notification {
  id: string;
  kind: 'info' | 'success' | 'warning' | 'error';
  title: string;
  detail?: string;
  ts: number;
}

type UIState = {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  currentProject: string;
  setCurrentProject: (p: string) => void;
  notifications: Notification[];
  pushNotification: (n: Omit<Notification, 'id' | 'ts'>) => void;
  dismissNotification: (id: string) => void;
  clearNotifications: () => void;
};

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  // Empty by default; TopBar populates from /projects on first load.
  currentProject: '',
  setCurrentProject: (p) => set({ currentProject: p }),
  notifications: [],
  pushNotification: (n) =>
    set((s) => ({
      notifications: [
        {
          ...n,
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          ts: Date.now(),
        },
        ...s.notifications,
      ].slice(0, 20),
    })),
  dismissNotification: (id) =>
    set((s) => ({ notifications: s.notifications.filter((n) => n.id !== id) })),
  clearNotifications: () => set({ notifications: [] }),
}));
