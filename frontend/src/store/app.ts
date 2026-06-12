import { create } from "zustand";
import type { WsEvent } from "@/types";

interface Notification {
  id: string;
  title: string;
  message: string;
  level: "info" | "success" | "warning" | "error";
  ts: string;
  read: boolean;
}

interface LiveFeedItem {
  id: string;
  event: string;
  data: unknown;
  ts: string;
}

interface AppState {
  // Real-time feed
  liveFeed: LiveFeedItem[];
  unreadNotifications: number;
  notifications: Notification[];
  wsConnected: boolean;

  // UI state
  sidebarCollapsed: boolean;
  commandPaletteOpen: boolean;
  activeTheme: "light" | "dark" | "system";

  // Actions
  addLiveFeedItem: (event: WsEvent) => void;
  addNotification: (n: Omit<Notification, "id" | "ts" | "read">) => void;
  markAllRead: () => void;
  setWsConnected: (connected: boolean) => void;
  toggleSidebar: () => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setTheme: (theme: "light" | "dark" | "system") => void;
}

export const useAppStore = create<AppState>()((set) => ({
  liveFeed: [],
  unreadNotifications: 0,
  notifications: [],
  wsConnected: false,
  sidebarCollapsed: false,
  commandPaletteOpen: false,
  activeTheme: "system",

  addLiveFeedItem: (event) =>
    set((state) => ({
      liveFeed: [
        { id: `${event.ts}-${Math.random()}`, event: event.event, data: event.data, ts: event.ts },
        ...state.liveFeed.slice(0, 49),
      ],
    })),

  addNotification: (n) =>
    set((state) => ({
      notifications: [
        { ...n, id: crypto.randomUUID(), ts: new Date().toISOString(), read: false },
        ...state.notifications.slice(0, 99),
      ],
      unreadNotifications: state.unreadNotifications + 1,
    })),

  markAllRead: () =>
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadNotifications: 0,
    })),

  setWsConnected: (connected) => set({ wsConnected: connected }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  setTheme: (theme) => set({ activeTheme: theme }),
}));
