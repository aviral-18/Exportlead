import { create } from "zustand";
import { persist } from "zustand/middleware";
import Cookies from "js-cookie";
import { authApi } from "@/lib/api";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email, password) => {
        set({ isLoading: true });
        try {
          const tokens = await authApi.login(email, password);
          Cookies.set("access_token", tokens.access_token, { secure: true, sameSite: "strict" });
          Cookies.set("refresh_token", tokens.refresh_token, { secure: true, sameSite: "strict" });
          set({ user: tokens.user, isAuthenticated: true, isLoading: false });
        } catch (err) {
          set({ isLoading: false });
          throw err;
        }
      },

      logout: async () => {
        const refreshToken = Cookies.get("refresh_token");
        if (refreshToken) {
          try { await authApi.logout(refreshToken); } catch { /* ignore */ }
        }
        Cookies.remove("access_token");
        Cookies.remove("refresh_token");
        set({ user: null, isAuthenticated: false });
      },

      setUser: (user) => set({ user, isAuthenticated: true }),

      checkAuth: async () => {
        const token = Cookies.get("access_token");
        if (!token) { set({ isAuthenticated: false }); return; }
        try {
          const user = await authApi.me();
          set({ user, isAuthenticated: true });
        } catch {
          set({ isAuthenticated: false, user: null });
        }
      },
    }),
    {
      name: "brass-auth",
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);
