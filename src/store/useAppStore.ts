/**
 * KrishiMitra – Global App Store (Zustand)
 * Persists auth + location + weather cache + active farm to localStorage.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi, farmApi, refreshApi, tokenStore, type UserProfile, type WeatherData, type RefreshResult } from '@/services/api';
import type { Farm } from '@/types/farm';

interface AppState {
  // Auth
  user: UserProfile | null;
  isAuthenticated: boolean;
  authLoading: boolean;
  authError: string | null;

  // App settings
  language: string;

  // ── Global location & weather cache ───────────────────────────────────────
  /** GPS-synced or manually set location — shared across all pages. */
  activeLocation: string;
  /** Cached weather for activeLocation — avoids redundant re-fetching. */
  weatherCache: WeatherData | null;
  /** Epoch ms of last successful weather fetch — controls TTL. */
  weatherCachedAt: number | null;

  // ── Farm Management ────────────────────────────────────────────────────────
  /** All farms belonging to the logged-in user. */
  farms: Farm[];
  /** The currently selected/active farm. */
  activeFarm: Farm | null;
  /** Whether farms are currently being loaded. */
  farmsLoading: boolean;

  // ── Refresh State (Provider Architecture v2) ──────────────────────────────
  /** Whether a full refresh is in progress. */
  refreshing: boolean;
  /** Result of the last full refresh. */
  lastRefresh: RefreshResult | null;
  /** Epoch ms of last completed refresh. */
  lastRefreshedAt: number | null;
  /** Error message from last failed refresh. */
  refreshError: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    name: string; email: string; phone: string; password: string;
    location?: string; farm_size_acres?: number;
  }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  updateProfile: (data: {
    name?: string; email?: string; phone?: string;
    location?: string; farm_size_acres?: number;
  }) => Promise<void>;
  setLanguage: (lang: string) => void;
  clearError: () => void;
  setUser: (user: UserProfile | null) => void;
  setActiveLocation: (location: string) => void;
  setWeatherCache: (weather: WeatherData) => void;

  // Farm actions
  loadFarms: () => Promise<void>;
  setActiveFarm: (farm: Farm | null) => Promise<void>;
  setFarms: (farms: Farm[]) => void;
  activateFarm: (farmId: string) => Promise<void>;

  // Refresh actions
  refreshFarmData: (farmId?: string, fieldId?: string) => Promise<void>;
}

const getFarmLocationString = async (farm: Farm): Promise<string> => {
  const parts = [farm.village, farm.district, farm.state].filter(Boolean);
  if (parts.length > 0) {
    return parts.join(', ');
  }
  if (farm.center_coordinate) {
    const { latitude, longitude } = farm.center_coordinate;
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`);
      const data = await res.json();
      const place = data.address.city || data.address.town || data.address.village || data.address.county;
      const state = data.address.state || '';
      if (place) {
        return state ? `${place}, ${state}` : place;
      }
      return `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
    } catch {
      return `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
    }
  }
  return 'Unknown Location';
};

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      authLoading: false,
      authError: null,
      language: 'en',
      activeLocation: 'Mumbai, India',
      weatherCache: null,
      weatherCachedAt: null,
      farms: [],
      activeFarm: null,
      farmsLoading: false,
      refreshing: false,
      lastRefresh: null,
      lastRefreshedAt: null,
      refreshError: null,

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
            activeLocation: res.user.location || get().activeLocation,
          });
          // Load farms after login
          get().loadFarms();
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
            activeLocation: res.user.location || get().activeLocation,
          });
        } catch (err: any) {
          set({ authError: err.message, authLoading: false });
          throw err;
        }
      },

      logout: () => {
        tokenStore.clear();
        set({
          user: null,
          isAuthenticated: false,
          authError: null,
          farms: [],
          activeFarm: null,
        });
      },

      refreshUser: async () => {
        if (!tokenStore.get()) return;
        try {
          const user = await authApi.me();
          set({ user, isAuthenticated: true });
          // Load farms on session restore
          get().loadFarms();
        } catch {
          tokenStore.clear();
          set({ user: null, isAuthenticated: false });
        }
      },

      updateProfile: async (data) => {
        set({ authLoading: true, authError: null });
        try {
          const updatedUser = await authApi.updateProfile(data);
          set({ user: updatedUser, isAuthenticated: true, authLoading: false });
          
          // Also sync active location if updated
          if (updatedUser.location) {
            set({ activeLocation: updatedUser.location });
          }
        } catch (err: any) {
          set({ authError: err.message, authLoading: false });
          throw err;
        }
      },

      loadFarms: async () => {
        if (!tokenStore.get()) return;
        set({ farmsLoading: true });
        try {
          const farms = await farmApi.list();
          const activeFarm = farms.find(f => f.is_active) || farms[0] || null;
          set({ farms, activeFarm, farmsLoading: false });

          // Sync activeLocation from farm center if available
          if (activeFarm) {
            const locStr = await getFarmLocationString(activeFarm);
            set({ activeLocation: locStr });
          }
        } catch {
          set({ farmsLoading: false });
        }
      },

      setActiveFarm: async (farm) => {
        set({ activeFarm: farm });
        if (farm) {
          const locStr = await getFarmLocationString(farm);
          set({ activeLocation: locStr });
        }
      },

      setFarms: (farms) => set({ farms }),

      activateFarm: async (farmId) => {
        try {
          const farm = await farmApi.activate(farmId);
          set(state => ({
            activeFarm: farm,
            farms: state.farms.map(f => ({
              ...f,
              is_active: f.farm_id === farmId,
            })),
          }));
          if (farm) {
            const locStr = await getFarmLocationString(farm);
            set({ activeLocation: locStr });
          }
        } catch (err: any) {
          console.error('Failed to activate farm:', err);
          throw err;
        }
      },

      setLanguage: (language) => set({ language }),
      clearError: () => set({ authError: null }),
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setActiveLocation: (location) => set({ activeLocation: location }),
      setWeatherCache: (weather) => set({ weatherCache: weather, weatherCachedAt: Date.now() }),

      refreshFarmData: async (farmId, fieldId) => {
        if (!tokenStore.get()) return;
        set({ refreshing: true, refreshError: null });
        try {
          const fId = farmId || get().activeFarm?.farm_id;
          const result = await refreshApi.fullRefresh(fId, fieldId);
          set({
            refreshing: false,
            lastRefresh: result,
            lastRefreshedAt: Date.now(),
            refreshError: null,
            // Invalidate weather cache so dashboard re-fetches
            weatherCache: null,
            weatherCachedAt: null,
          });
          // Reload farms to pick up any updated satellite data
          get().loadFarms();
        } catch (err: any) {
          set({ refreshing: false, refreshError: err.message });
        }
      },
    }),
    {
      name: 'krishimitra-store',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        language: state.language,
        activeLocation: state.activeLocation,
        weatherCache: state.weatherCache,
        weatherCachedAt: state.weatherCachedAt,
        activeFarm: state.activeFarm,
        lastRefreshedAt: state.lastRefreshedAt,
      }),
    },
  ),
);
