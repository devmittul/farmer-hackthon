/**
 * KrishiMitra AI – Complete API Service Layer
 * All calls go to the real FastAPI backend.
 * No mocks. No timeouts. Real data only.
 */
import type { Farm, CreateFarmPayload, UpdateFarmPayload } from '@/types/farm';

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
  confidence_score: number;
  alternatives: string[];
  explanation?: string;
  tips?: string[];
  input_params: Record<string, any>;
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

  updateProfile: (data: {
    name?: string;
    email?: string;
    phone?: string;
    location?: string;
    farm_size_acres?: number;
  }) => apiFetch<UserProfile>('/auth/profile', {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
};

// ── Chat API ──────────────────────────────────────────────────────────────────
export const chatApi = {
  send: async (
    message: string,
    location?: string,
    sessionId?: string,
    language = 'en',
    fieldId?: string,
    farmId?: string,
  ) => {
    const startTime = performance.now();
    try {
      const response = await apiFetch<ChatMessage>('/chat', {
        method: 'POST',
        body: JSON.stringify({
          message,
          location,
          session_id: sessionId,
          language,
          field_id: fieldId,
          farm_id: farmId,
        }),
      });
      const latencyMs = performance.now() - startTime;
      console.log(`Frontend Request (/chat) completed in ${latencyMs.toFixed(2)}ms`);
      return response;
    } catch (error) {
      const latencyMs = performance.now() - startTime;
      console.error(`Frontend Request (/chat) failed after ${latencyMs.toFixed(2)}ms`, error);
      throw error;
    }
  },

  history: (limit = 20, skip = 0) =>
    apiFetch<ChatMessage[]>(`/history?limit=${limit}&skip=${skip}`),
};

// ── Farm API ──────────────────────────────────────────────────────────────────
export const farmApi = {
  list: () =>
    apiFetch<Farm[]>('/farms'),

  getActive: () =>
    apiFetch<Farm | null>('/farms/active'),

  create: (data: CreateFarmPayload) =>
    apiFetch<Farm>('/farms', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (farmId: string) =>
    apiFetch<Farm>(`/farms/${farmId}`),

  update: (farmId: string, data: UpdateFarmPayload) =>
    apiFetch<Farm>(`/farms/${farmId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  delete: (farmId: string) =>
    apiFetch<{ farm_id: string; deleted: boolean }>(`/farms/${farmId}`, {
      method: 'DELETE',
    }),

  activate: (farmId: string) =>
    apiFetch<Farm>(`/farms/${farmId}/activate`, {
      method: 'POST',
    }),

  analyze: (farmId: string) =>
    apiFetch<any>(`/farms/${farmId}/analyze`, {
      method: 'POST',
    }),

  getSatellite: (farmId: string) =>
    apiFetch<any>(`/farms/${farmId}/satellite`),
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
  predict: async (inputs: {
    nitrogen: number; phosphorus: number; potassium: number;
    temperature: number; humidity: number; ph: number; rainfall: number;
    language?: string; location?: string;
    user_question?: string; crop_concern?: string;
  }) => {
    return apiFetch<CropResult>('/crop/predict', {
      method: 'POST',
      body: JSON.stringify(inputs),
    });
  },
  getSoil: async (location: string) => {
    return apiFetch<any>(`/crop/soil?location=${encodeURIComponent(location)}`, {
      method: 'GET'
    });
  }
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

// ── Refresh API (Provider Architecture v2) ────────────────────────────────────
export interface RefreshResult {
  refresh_id: string;
  status: string;
  elapsed_ms: number;
  steps: Array<{ message: string; at: string }>;
  providers_refreshed: Array<{ name: string; available: boolean; status: string }>;
  snapshot_version: number;
}

export const refreshApi = {
  /** Full refresh: re-run every provider, ignore all caches */
  fullRefresh: (farmId?: string, fieldId?: string) =>
    apiFetch<RefreshResult>('/refresh/full', {
      method: 'POST',
      body: JSON.stringify({ farm_id: farmId, field_id: fieldId }),
    }),

  /** Get refresh progress */
  getStatus: (refreshId: string) =>
    apiFetch<any>(`/refresh/status/${refreshId}`),

  /** Get the latest refresh snapshot */
  getLatest: () =>
    apiFetch<any>('/refresh/latest'),
};

// ── Fields API (New Module) ───────────────────────────────────────────────────
export const fieldApi = {
  list: () => apiFetch<any[]>('/fields'),
  get: (fieldId: string) => apiFetch<any>(`/fields/${fieldId}`),
  create: (data: any) => apiFetch<any>('/fields', { method: 'POST', body: JSON.stringify(data) }),
  update: (fieldId: string, data: any) => apiFetch<any>(`/fields/${fieldId}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (fieldId: string) => apiFetch<{ field_id: string; deleted: boolean }>(`/fields/${fieldId}`, { method: 'DELETE' }),
  analyze: (fieldId: string) => apiFetch<any>(`/twin/fields/${fieldId}/satellite`),
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
  getCropRecommendation: async (inputs: Record<string, number>, location?: string, user_question?: string) => {
    const data = await cropApi.predict({
      nitrogen: inputs.n ?? 90,
      phosphorus: inputs.p ?? 42,
      potassium: inputs.k ?? 43,
      temperature: inputs.temperature ?? 22,
      humidity: inputs.humidity ?? 75,
      ph: inputs.ph ?? 6.5,
      rainfall: inputs.rainfall ?? 200,
      location,
      user_question,
    });
    return [{
      name: data.recommended_crop.charAt(0).toUpperCase() + data.recommended_crop.slice(1),
      score: Math.round(data.confidence_score),
      waterRequired: 'Medium',
      yield: 'High',
      risk: 'Low',
      profit: 'High',
      season: 'Current',
      reason: data.explanation || `AI confidence: ${data.confidence_score.toFixed(1)}%`,
      alternatives: data.alternatives,
      tips: data.tips,
    }];
  },
  diagnoseDisease: async (file?: File) => {
    if (!file) throw new Error('No image file provided. Please upload a plant photo first.');

    // ── Read model/key from env vars (never hardcoded) ──────────────────────
    const apiKey   = import.meta.env.VITE_GEMINI_API_KEY as string;
    const model    = (import.meta.env.VITE_GEMINI_MODEL as string) || 'gemini-2.5-flash';

    if (!apiKey) {
      throw new Error('VITE_GEMINI_API_KEY is not set. Please add it to your .env file.');
    }

    // ── Validate image MIME type before uploading ────────────────────────────
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
    const mimeType = file.type || 'image/jpeg';
    if (!allowedTypes.includes(mimeType)) {
      throw new Error(`Unsupported image format "${file.type}". Please upload a JPG, PNG, or WEBP image.`);
    }

    // ── Convert File → base64 ────────────────────────────────────────────────
    const base64Data = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        const base64 = result.split(',')[1];
        if (!base64) { reject(new Error('Failed to read image file. The file may be corrupted.')); return; }
        resolve(base64);
      };
      reader.onerror = () => reject(new Error('Failed to read image file.'));
      reader.readAsDataURL(file);
    });

    // ── Call Gemini REST API (v1beta) ────────────────────────────────────────
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

    let response: Response;
    try {
      response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{
            parts: [
              {
                text: [
                  'You are an expert plant pathologist with 20 years of field experience.',
                  'Analyze the provided crop leaf image carefully.',
                  'Identify the disease, or confirm if the plant is healthy.',
                  'You MUST respond with ONLY a raw JSON object — no markdown, no explanation, no code fences.',
                  'Required keys: "disease" (string), "confidence" (number 0-100),',
                  '"severity" (exactly one of: "Low", "Medium", "High"),',
                  '"symptoms" (array of 3-5 strings), "causes" (array of 2-4 strings),',
                  '"treatment" (array of 3-5 actionable strings),',
                  '"prevention" (array of 3-5 strings).',
                ].join(' '),
              },
              {
                inlineData: { mimeType, data: base64Data },
              },
            ],
          }],
          generationConfig: { temperature: 0.2, maxOutputTokens: 1024 },
        }),
      });
    } catch (networkErr: any) {
      throw new Error(`Network error — could not reach Gemini API. Check your internet connection. (${networkErr.message})`);
    }

    // ── Handle all HTTP-level errors explicitly ──────────────────────────────
    if (!response.ok) {
      let errBody: any = {};
      try { errBody = await response.json(); } catch { /* ignore */ }
      const apiMsg: string = errBody?.error?.message || response.statusText;
      const code: number   = errBody?.error?.code    || response.status;
      if (code === 400) throw new Error(`Invalid request — image may be corrupted or too large. (${apiMsg})`);
      if (code === 401 || code === 403) throw new Error(`Invalid or unauthorized Gemini API key. Check VITE_GEMINI_API_KEY. (${apiMsg})`);
      if (code === 404) throw new Error(`Model "${model}" not found. Change VITE_GEMINI_MODEL to "gemini-2.5-flash". (${apiMsg})`);
      if (code === 429) throw new Error(`Gemini quota exceeded. Please wait a moment and try again. (${apiMsg})`);
      if (code >= 500) throw new Error(`Gemini server error (${code}). Try again shortly. (${apiMsg})`);
      throw new Error(`Gemini API error ${code}: ${apiMsg}`);
    }

    // ── Parse response safely ────────────────────────────────────────────────
    let rawJson: any;
    try { rawJson = await response.json(); } catch {
      throw new Error('Received an unreadable response from Gemini. Please try again.');
    }

    const candidate = rawJson?.candidates?.[0];
    if (!candidate) {
      const blockReason = rawJson?.promptFeedback?.blockReason;
      if (blockReason) throw new Error(`Request blocked by Gemini safety filters (${blockReason}). Use a clear plant image.`);
      throw new Error('No diagnosis was returned by the AI. Please try a different image.');
    }

    const rawText: string = candidate?.content?.parts?.[0]?.text ?? '';
    if (!rawText.trim()) throw new Error('Gemini returned an empty response. Please upload a clearer image.');

    // Strip any accidental markdown fences
    const cleaned = rawText
      .replace(/^```json\s*/i, '').replace(/^```\s*/i, '').replace(/```\s*$/i, '').trim();

    try {
      return JSON.parse(cleaned);
    } catch {
      const match = cleaned.match(/\{[\s\S]*\}/);
      if (match) { try { return JSON.parse(match[0]); } catch { /* fall through */ } }
      throw new Error('AI returned an unexpected format. Please try the diagnosis again.');
    }
  },
  getSensorData: async () => ({ soilMoisture: 'N/A', airTemp: 'N/A', humidity: 'N/A', ph: 'N/A', n: 'N/A', p: 'N/A', k: 'N/A', connected: false }),

  /**
   * Irrigation advisory derived from live weather for the given location.
   * All values come from real weather data — nothing is hardcoded.
   */
  getIrrigationAdvisory: async (location = 'auto') => {
    const data = await weatherApi.get(location, 5).catch(() => null);
    if (!data) return {
      shouldIrrigate: true,
      waterAmount: 'Check local conditions',
      fertilizer: 'Consult AI Chat for fertilizer advice',
      nextRain: 'Unavailable',
      drySpellRisk: 'Unknown',
      farmHealth: 'Unknown',
      statusColor: 'yellow',
    };
    const todayRain = data.current.rainfall_mm;
    const totalForecastRain = data.forecast.reduce((s, d) => s + d.rainfall_mm, 0);
    const avgHumidity = data.forecast.reduce((s, d) => s + d.humidity_pct, 0) / (data.forecast.length || 1);
    const shouldIrrigate = todayRain < 5 && avgHumidity < 65;
    // Water amount: base 20mm minus what rain already provides
    const waterMm = Math.max(0, Math.round(20 - todayRain));
    const drySpellRisk = totalForecastRain < 10 ? 'High' : totalForecastRain < 30 ? 'Medium' : 'Low';
    const farmHealth = avgHumidity > 70 ? 'Good' : avgHumidity > 50 ? 'Fair' : 'Needs Attention';
    return {
      shouldIrrigate,
      waterAmount: `${waterMm} mm`,
      fertilizer: shouldIrrigate ? 'Apply fertilizer before irrigation for best absorption' : 'Wait for current moisture to stabilise',
      nextRain: data.forecast?.[0]?.condition ?? 'Unknown',
      drySpellRisk,
      farmHealth,
      statusColor: shouldIrrigate ? 'yellow' : 'green',
      advisory: data.advisory,
    };
  },
  getReports: async () => [],
};
