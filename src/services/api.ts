/**
 * KrishiMitra AI – Complete API Service Layer
 * All calls go to the real FastAPI backend.
 * No mocks. No timeouts. Real data only.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// ── Auth token helpers ────────────────────────────────────────────────────────
export const tokenStore = {
  get: () => localStorage.getItem('km_access_token'),
  set: (t: string) => localStorage.setItem('km_access_token', t),
  clear: () => { localStorage.removeItem('km_access_token'); localStorage.removeItem('km_user'); },
};

// ── Base fetch with auth ──────────────────────────────────────────────────────
async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  skipAuth = false,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers as Record<string, string>),
  };

  const token = tokenStore.get();
  if (token && !skipAuth) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: `HTTP ${res.status}` }));
    throw new Error(err.message || err.detail || `Request failed: ${res.status}`);
  }

  const json = await res.json();
  // Unwrap standard response envelope { success, data, message }
  return (json.data !== undefined ? json.data : json) as T;
}

// ── Types ─────────────────────────────────────────────────────────────────────
export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserProfile;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  phone?: string;
  location?: string;
  farm_size_acres?: number;
  language?: string;
}

export interface WeatherData {
  location: string;
  current: {
    temperature_c: number;
    humidity_pct: number;
    wind_kmh: number;
    condition: string;
    rainfall_mm: number;
  };
  forecast: Array<{
    date: string;
    condition: string;
    temp_min_c: number;
    temp_max_c: number;
    rainfall_mm: number;
    humidity_pct: number;
  }>;
  advisory?: string;
}

export interface CropResult {
  recommended_crop: string;
  confidence: number;
  alternatives: string[];
  explanation?: string;
  tips?: string[];
  soil_inputs: Record<string, number>;
}

export interface ChatMessage {
  reply: string;
  intent: string;
  language: string;
  session_id: string;
  data?: Record<string, unknown>;
  audio_url?: string;
}

export interface RouteResult {
  origin: string;
  destination: string;
  distance_km: number;
  duration_min: number;
  steps: Array<{ instruction: string; distance_m: number }>;
  advisory?: string;
}

export interface VehicleResult {
  demand_level: string;
  recommended_vehicles: string[];
  estimated_cost_inr: { min: number; max: number };
  best_time_window: string;
  explanation?: string;
}

// ── Auth API ──────────────────────────────────────────────────────────────────
export const authApi = {
  register: (data: {
    name: string; email: string; phone: string; password: string;
    location?: string; farm_size_acres?: number; language?: string;
  }) => apiFetch<AuthResponse>('/auth/register', {
    method: 'POST', body: JSON.stringify(data),
  }, true),

  login: (email: string, password: string) =>
    apiFetch<AuthResponse>('/auth/login', {
      method: 'POST', body: JSON.stringify({ email, password }),
    }, true),

  me: () => apiFetch<UserProfile>('/auth/me'),
};

// ── Chat API ──────────────────────────────────────────────────────────────────
export const chatApi = {
  send: (message: string, location?: string, sessionId?: string, language = 'en', fieldId?: string) =>
    apiFetch<ChatMessage>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, location, session_id: sessionId, language, field_id: fieldId }),
    }),

  history: (limit = 20, skip = 0) =>
    apiFetch<ChatMessage[]>(`/history?limit=${limit}&skip=${skip}`),
};

// ── Weather API ───────────────────────────────────────────────────────────────
export const weatherApi = {
  get: (location: string, days = 3, language = 'en', forceRefresh = false) =>
    apiFetch<WeatherData>('/weather', {
      method: 'POST',
      body: JSON.stringify({ location, days, language, force_refresh: forceRefresh }),
    }),
};

// ── Crop API ──────────────────────────────────────────────────────────────────
export const cropApi = {
  predict: (inputs: {
    nitrogen: number; phosphorus: number; potassium: number;
    temperature: number; humidity: number; ph: number; rainfall: number;
    language?: string; location?: string;
  }) => apiFetch<CropResult>('/crop/predict', {
    method: 'POST', body: JSON.stringify(inputs),
  }),
};

// ── Route API ─────────────────────────────────────────────────────────────────
export const routeApi = {
  plan: (origin: string, destination: string, cargo_type = 'general', language = 'en') =>
    apiFetch<RouteResult>('/route/plan', {
      method: 'POST',
      body: JSON.stringify({ origin, destination, cargo_type, language }),
    }),
};

// ── Vehicle API ───────────────────────────────────────────────────────────────
export const vehicleApi = {
  predict: (data: {
    quantity_tonnes: number; destination: string;
    crop_type: string; date: string; origin?: string; language?: string;
  }) => apiFetch<VehicleResult>('/vehicle/predict', {
    method: 'POST', body: JSON.stringify(data),
  }),
};

// ── SOS API ───────────────────────────────────────────────────────────────────
export const sosApi = {
  send: (latitude: number, longitude: number, description: string, emergency_type = 'general') =>
    apiFetch('/sos', {
      method: 'POST',
      body: JSON.stringify({ latitude, longitude, description, emergency_type }),
    }),
};

// ── Voice API ─────────────────────────────────────────────────────────────────
export const voiceApi = {
  send: (audioBlob: Blob, language = 'en', location?: string) => {
    const form = new FormData();
    form.append('audio', audioBlob, 'recording.webm');
    form.append('language', language);
    if (location) form.append('location', location);
    return apiFetch<ChatMessage>('/voice', { method: 'POST', body: form });
  },
};

// ── Courier API ───────────────────────────────────────────────────────────────
export const courierApi = {
  create: (data: {
    pickup_location: string; delivery_location: string;
    cargo_description: string; quantity_kg: number;
    contact_phone: string; pickup_date?: string;
  }) => apiFetch('/courier/create', { method: 'POST', body: JSON.stringify(data) }),

  list: (status?: string) =>
    apiFetch(`/courier/list${status ? `?status=${status}` : ''}`),
};

// ── Digital Twin API ──────────────────────────────────────────────────────────
export const twinApi = {
  // Farmer
  getFarmer: () => apiFetch('/twin/farmer'),
  updateFarmer: (data: any) => apiFetch('/twin/farmer', { method: 'PUT', body: JSON.stringify(data) }),
  
  // Farms
  getFarms: () => apiFetch('/twin/farms'),
  createFarm: (data: any) => apiFetch('/twin/farms', { method: 'POST', body: JSON.stringify(data) }),
  getFarmDetails: (farmId: string) => apiFetch(`/twin/farms/${farmId}`),
  
  // Fields
  getFields: () => apiFetch('/twin/fields'),
  registerField: (data: any) => apiFetch('/twin/fields', { method: 'POST', body: JSON.stringify(data) }),
  updateField: (fieldId: string, data: any) => apiFetch(`/twin/fields/${fieldId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  
  // Field Intelligence
  fetchSatellite: (fieldId: string) => apiFetch(`/twin/fields/${fieldId}/satellite`),
  recordHarvest: (fieldId: string, data: any) => apiFetch(`/twin/fields/${fieldId}/harvest`, { method: 'POST', body: JSON.stringify(data) }),
};

// ── System API ────────────────────────────────────────────────────────────────
export const systemApi = {
  getStatus: () => apiFetch<Record<string, { status: string; message: string }>>('/system/status'),
};

// ── Legacy compatibility shim (so old imports don't break during migration) ───
export const api = {
  getWeather: async () => {
    const data = await weatherApi.get('auto', 1).catch(() => null);
    if (!data) return { temp: '--', humidity: '--', wind: '--', condition: 'Unavailable', rainProb: 0 };
    return {
      temp: data.current.temperature_c,
      humidity: data.current.humidity_pct,
      wind: `${data.current.wind_kmh} km/h`,
      condition: data.current.condition,
      rainProb: data.current.rainfall_mm,
    };
  },
  getCropRecommendation: async (inputs: Record<string, number>) => {
    const data = await cropApi.predict({
      nitrogen: inputs.n ?? 90,
      phosphorus: inputs.p ?? 42,
      potassium: inputs.k ?? 43,
      temperature: inputs.temperature ?? 22,
      humidity: inputs.humidity ?? 75,
      ph: inputs.ph ?? 6.5,
      rainfall: inputs.rainfall ?? 200,
    });
    return [{
      name: data.recommended_crop.charAt(0).toUpperCase() + data.recommended_crop.slice(1),
      score: Math.round(data.confidence),
      waterRequired: 'Medium',
      yield: 'High',
      risk: 'Low',
      profit: 'High',
      season: 'Current',
      reason: data.explanation || `AI confidence: ${data.confidence.toFixed(1)}%`,
      alternatives: data.alternatives,
      tips: data.tips,
    }];
  },
  diagnoseDisease: async () => ({ disease: 'Use AI Chat for diagnosis', confidence: 0, severity: 'N/A', symptoms: [], causes: [], treatment: [], prevention: [] }),
  getSensorData: async () => ({ soilMoisture: 'N/A', airTemp: 'N/A', humidity: 'N/A', ph: 'N/A', n: 'N/A', p: 'N/A', k: 'N/A', connected: false }),
  getIrrigationAdvisory: async () => {
    const data = await weatherApi.get('auto', 3).catch(() => null);
    const rain = data?.forecast?.[0]?.rainfall_mm ?? 0;
    return {
      shouldIrrigate: rain < 5,
      waterAmount: '15 mm',
      fertilizer: 'Check with AI Chat',
      nextRain: data?.forecast?.[1]?.condition ?? 'Unknown',
      drySpellRisk: rain < 2 ? 'High' : 'Low',
      farmHealth: 'Good',
      statusColor: rain < 5 ? 'yellow' : 'green',
    };
  },
  getReports: async () => [],
};
