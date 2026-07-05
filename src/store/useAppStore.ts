/**
 * KrishiMitra – Global App Store (Zustand)
 * Persists auth state to localStorage.
 * All user data comes from the real backend.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi, tokenStore, type UserProfile } from '@/services/api';

interface AppState {
  // Auth
  user: UserProfile | null;
  isAuthenticated: boolean;
  authLoading: boolean;
  authError: string | null;

  // App settings
  language: string;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    name: string; email: string; phone: string; password: string;
    location?: string; farm_size_acres?: number;
  }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  setLanguage: (lang: string) => void;
  clearError: () => void;
  setUser: (user: UserProfile | null) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      authLoading: false,
      authError: null,
      language: 'en',

      login: async (email, password) => {
        set({ authLoading: true, authError: null });
        try {
          const res = await authApi.login(email, password);
          tokenStore.set(res.access_token);
          set({
            user: res.user,
            isAuthenticated: true,
            authLoading: false,
            authError: null,
          });
        } catch (err: any) {
          set({ authError: err.message, authLoading: false });
          throw err;
        }
      },

      register: async (data) => {
        set({ authLoading: true, authError: null });
        try {
          const res = await authApi.register({ ...data, language: get().language });
          tokenStore.set(res.access_token);
          set({
            user: res.user,
            isAuthenticated: true,
            authLoading: false,
            authError: null,
          });
        } catch (err: any) {
          set({ authError: err.message, authLoading: false });
          throw err;
        }
      },

      logout: () => {
        tokenStore.clear();
        set({ user: null, isAuthenticated: false, authError: null });
      },

      refreshUser: async () => {
        if (!tokenStore.get()) return;
        try {
          const user = await authApi.me();
          set({ user, isAuthenticated: true });
        } catch {
          // Token expired
          tokenStore.clear();
          set({ user: null, isAuthenticated: false });
        }
      },

      setLanguage: (language) => set({ language }),
      clearError: () => set({ authError: null }),
      setUser: (user) => set({ user, isAuthenticated: !!user }),
    }),
    {
      name: 'krishimitra-store',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        language: state.language,
      }),
    },
  ),
);
