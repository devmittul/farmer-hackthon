import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { motion, AnimatePresence } from 'framer-motion';
import { Leaf, Search, Loader2, AlertTriangle, Sparkles, Sprout, CloudRain, Droplets, Thermometer, Wind, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cropApi, weatherApi, twinApi, type CropResult } from '@/services/api';
import { useAppStore } from '@/store/useAppStore';

export default function CropRecommendation() {
  const { 
    activeLocation, 
    weatherCache, 
    weatherCachedAt, 
    setActiveLocation, 
    setWeatherCache,
    farms,
    activeFarm,
    activateFarm
  } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CropResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [weatherFilling, setWeatherFilling] = useState(false);
  const [fields, setFields] = useState<any[]>([]);
  const [selectedFarmId, setSelectedFarmId] = useState<string>(activeFarm?.farm_id || '');
  const [selectedFieldId, setSelectedFieldId] = useState<string>('');

  const [form, setForm] = useState({
    location: activeLocation,
    nitrogen: 90,
    phosphorus: 42,
    potassium: 43,
    temperature: 22,
    humidity: 75,
    ph: 6.5,
    rainfall: 200,
    language: 'en',
    user_question: '',       // filled from the "What do you want to know?" input
    crop_concern: '',        // filled from the concern selector
  });

  const setField = (key: string, value: string | number) =>
    setForm(f => ({ ...f, [key]: value }));

  /** Fill temperature, humidity, rainfall from a WeatherData object */
  const applyWeatherToForm = (w: typeof weatherCache) => {
    if (!w) return;
    const rain = w.forecast?.reduce((sum, d) => sum + (d.rainfall_mm ?? 0), 0) ?? 0;
    setForm(f => ({
      ...f,
      temperature: parseFloat(w.current.temperature_c.toFixed(1)),
      humidity: Math.round(w.current.humidity_pct),
      rainfall: parseFloat(rain.toFixed(1)),
    }));
  };

  // Load fields on mount
  useEffect(() => {
    twinApi.getFields()
      .then((data: any) => setFields(data || []))
      .catch((err) => console.error("Failed to load fields:", err));
  }, []);

  // Sync selected farm state when activeFarm changes globally
  useEffect(() => {
    if (activeFarm) {
      setSelectedFarmId(activeFarm.farm_id);
    }
  }, [activeFarm]);

  const handleFarmChange = async (farmId: string) => {
    setSelectedFarmId(farmId);
    setSelectedFieldId('');
    if (farmId) {
      try {
        await activateFarm(farmId);
        const farm = farms.find(f => f.farm_id === farmId);
        if (farm) {
          const locName = farm.village || farm.district || farm.name || activeLocation;
          setField('location', locName);
          setActiveLocation(locName);
        }
      } catch (err) {
        console.error("Failed to activate farm:", err);
      }
    }
  };

  const handleFieldChange = (fieldId: string) => {
    setSelectedFieldId(fieldId);
    if (fieldId) {
      const field = fields.find(f => f.field_id === fieldId);
      if (field) {
        setForm(f => ({
          ...f,
          nitrogen: field.nitrogen_kg_ha !== undefined && field.nitrogen_kg_ha !== null ? field.nitrogen_kg_ha : f.nitrogen,
          phosphorus: field.phosphorus_kg_ha !== undefined && field.phosphorus_kg_ha !== null ? field.phosphorus_kg_ha : f.phosphorus,
          potassium: field.potassium_kg_ha !== undefined && field.potassium_kg_ha !== null ? field.potassium_kg_ha : f.potassium,
          ph: field.soil_profile?.ph_h2o ?? field.soil_ph ?? f.ph,
        }));
      }
    }
  };

  // Auto-fill from global cache on mount & when cache/location changes
  useEffect(() => {
    setField('location', activeLocation);
    const WEATHER_TTL_MS = 15 * 60 * 1000;
    const cacheAge = weatherCachedAt ? Date.now() - weatherCachedAt : Infinity;

    // Only use cache if the location is loosely matching (to avoid using old cache for new farm)
    const isSameLocation = weatherCache?.location?.toLowerCase().includes(activeLocation.split(',')[0].toLowerCase().trim());
    
    if (weatherCache && cacheAge < WEATHER_TTL_MS && isSameLocation) {
      applyWeatherToForm(weatherCache);
    } else {
      setWeatherFilling(true);
      weatherApi.get(activeLocation, 5, 'en', true)
        .then(data => {
          setWeatherCache(data);
          applyWeatherToForm(data);
        })
        .catch(() => { /* keep defaults */ })
        .finally(() => setWeatherFilling(false));
    }

    // Auto-fetch soil pH based on location if not using a specific field
    if (!selectedFieldId && activeLocation) {
      cropApi.getSoil(activeLocation)
        .then((data: any) => {
          if (data && data.ph_h2o) {
            setForm(f => ({ ...f, ph: parseFloat(data.ph_h2o.toFixed(1)) }));
          }
        })
        .catch(() => { /* ignore */ });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLocation, weatherCachedAt]);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      // Build a rich contextual question if the user didn't type one
      const userQ = form.user_question.trim() ||
        `Based on my soil and climate conditions in ${form.location}, what crop should I grow` +
        (form.crop_concern ? ` considering my concern about ${form.crop_concern}` : '') +
        '? Please include practical farming tips.';

      const data = await cropApi.predict({
        nitrogen: Number(form.nitrogen),
        phosphorus: Number(form.phosphorus),
        potassium: Number(form.potassium),
        temperature: Number(form.temperature),
        humidity: Number(form.humidity),
        ph: Number(form.ph),
        rainfall: Number(form.rainfall),
        language: form.language,
        location: form.location,
        user_question: userQ,
        crop_concern: form.crop_concern || undefined,
      });
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Prediction failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-10 w-full max-w-7xl mx-auto pb-20">
      {/* Header */}
      <motion.div 
        initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-5 mb-4 pt-6"
      >
        <div className="bg-green-100/80 p-4 rounded-full">
          <Leaf className="h-8 w-8 text-green-700" strokeWidth={1.5} />
        </div>
        <div>
          <h1 className="text-4xl font-semibold tracking-tight text-foreground">Smart Crop Recommendation</h1>
          <p className="text-muted-foreground text-lg font-light mt-2">Machine Learning yield prediction powered by Gemini AI.</p>
        </div>
      </motion.div>

      <AnimatePresence mode="wait">
        {!result ? (
          <motion.div 
            key="form"
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
          >
            <Card className="glass-card flex flex-col relative overflow-hidden">
              <CardHeader className="pb-6 border-b border-border/50 bg-muted/30 px-8 pt-8">
                <CardTitle className="text-2xl font-semibold text-foreground">Soil & Climate Parameters</CardTitle>
                <CardDescription className="text-base font-light mt-2">
                  Enter your local soil test values and climate data for hyper-accurate ML recommendations.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-10 px-8 pb-10">
                <form onSubmit={handleAnalyze} className="space-y-12">
                  {/* Farm & Field Selection Context */}
                  <div className="grid md:grid-cols-2 gap-10 p-8 bg-green-50/50 border border-green-100/50 rounded-[32px] mb-8">
                    <div className="space-y-4">
                      <Label className="text-sm font-semibold text-green-800 uppercase tracking-widest">Select Farm Context</Label>
                      <Select value={selectedFarmId} onValueChange={handleFarmChange}>
                        <SelectTrigger className="h-14 bg-white border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] rounded-full text-base px-6">
                          <SelectValue placeholder="Select a Farm" />
                        </SelectTrigger>
                        <SelectContent className="rounded-[20px] border-border">
                          {farms.map(f => (
                            <SelectItem key={f.farm_id} value={f.farm_id}>
                              {f.name || 'Unnamed Farm'} ({f.village || f.district || 'No Location'})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-4">
                      <Label className="text-sm font-semibold text-green-800 uppercase tracking-widest">Select Field Context <span className="text-green-600/70 font-normal normal-case">(Auto-fills Soil Parameters)</span></Label>
                      <Select 
                        value={selectedFieldId} 
                        onValueChange={handleFieldChange}
                        disabled={!selectedFarmId}
                      >
                        <SelectTrigger className="h-14 bg-white border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] rounded-full text-base px-6">
                          <SelectValue placeholder={selectedFarmId ? "Select a Field to Auto-fill" : "Select a Farm first"} />
                        </SelectTrigger>
                        <SelectContent className="rounded-[20px] border-border">
                          <SelectItem value="">None (Manual entry)</SelectItem>
                          {fields.filter(field => field.farm_id === selectedFarmId).map(f => (
                            <SelectItem key={f.field_id} value={f.field_id}>
                              {f.name || f.fieldName || 'Unnamed Field'} ({f.current_crop || 'No crop'})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* Location & Lang */}
                  <div className="grid md:grid-cols-2 gap-10">
                    <div className="space-y-4">
                      <Label className="text-sm font-semibold text-muted-foreground uppercase tracking-widest">Target Location</Label>
                      <div className="flex gap-4">
                        <Input
                          value={form.location}
                          onChange={e => setField('location', e.target.value)}
                          placeholder="Enter Village/District"
                          className="h-14 bg-white border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] rounded-full text-base focus-visible:ring-primary px-6"
                        />
                        <Button
                          type="button" variant="outline"
                          title="Sync Location"
                          className="h-14 px-6 border-transparent bg-white hover:bg-muted text-foreground rounded-full shadow-[0_2px_10px_rgba(0,0,0,0.02)] font-medium text-base"
                          onClick={() => {
                            if (!navigator.geolocation) return;
                            navigator.geolocation.getCurrentPosition(async pos => {
                              const { latitude: lat, longitude: lon } = pos.coords;
                              try {
                                const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
                                const data = await res.json();
                                const place = data.address.city || data.address.town || data.address.village || data.address.county || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
                                const state = data.address.state || '';
                                setActiveLocation(state ? `${place}, ${state}` : place); // → triggers useEffect
                              } catch {
                                setActiveLocation(`${lat.toFixed(4)}, ${lon.toFixed(4)}`);
                              }
                            });
                          }}
                        >
                          <RefreshCw className="h-4 w-4 mr-2" strokeWidth={1.5} />
                          Sync GPS
                        </Button>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <Label className="text-sm font-semibold text-muted-foreground uppercase tracking-widest">Response Language</Label>
                      <Select value={form.language} onValueChange={v => setField('language', v)}>
                        <SelectTrigger className="h-14 bg-white border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] rounded-full text-base px-6">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="rounded-[20px] border-border">
                          <SelectItem value="en">English</SelectItem>
                          <SelectItem value="hi">Hindi</SelectItem>
                          <SelectItem value="pa">Punjabi</SelectItem>
                          <SelectItem value="mr">Marathi</SelectItem>
                          <SelectItem value="te">Telugu</SelectItem>
                          <SelectItem value="ta">Tamil</SelectItem>
                          <SelectItem value="gu">Gujarati</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* Crop Concern + Custom Question */}
                  <div className="grid md:grid-cols-2 gap-10">
                    <div className="space-y-4">
                      <Label className="text-sm font-semibold text-muted-foreground uppercase tracking-widest">Primary Concern</Label>
                      <Select value={form.crop_concern} onValueChange={v => setField('crop_concern', v)}>
                        <SelectTrigger className="h-14 bg-white border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] rounded-full text-base px-6">
                          <SelectValue placeholder="Select your main concern (optional)" />
                        </SelectTrigger>
                        <SelectContent className="rounded-[20px] border-border">
                          <SelectItem value="">None — general recommendation</SelectItem>
                          <SelectItem value="water scarcity">💧 Water Scarcity / Drought</SelectItem>
                          <SelectItem value="export market">📦 Export Market Quality</SelectItem>
                          <SelectItem value="late season planting">🌾 Late Season Planting</SelectItem>
                          <SelectItem value="pest and disease resistance">🐛 Pest & Disease Resistance</SelectItem>
                          <SelectItem value="organic farming">🌿 Organic Farming</SelectItem>
                          <SelectItem value="maximum yield">📈 Maximum Yield</SelectItem>
                          <SelectItem value="minimum cost">💰 Minimum Input Cost</SelectItem>
                          <SelectItem value="intercropping">🌱 Intercropping Compatibility</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-4">
                      <Label className="text-sm font-semibold text-muted-foreground uppercase tracking-widest">Your Question <span className="text-muted-foreground/50 font-normal normal-case">(optional)</span></Label>
                      <Input
                        value={form.user_question}
                        onChange={e => setField('user_question', e.target.value)}
                        placeholder="e.g. Which crop needs least water for winter planting?"
                        className="h-14 bg-white border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] rounded-full text-base focus-visible:ring-primary px-6"
                      />
                    </div>
                  </div>

                  <div className="grid lg:grid-cols-2 gap-10">
                    {/* NPK */}
                    <div className="space-y-8 bg-muted/20 p-8 rounded-[32px] border border-transparent">
                      <div className="flex items-center gap-3 mb-2">
                        <Sprout className="h-6 w-6 text-green-600" strokeWidth={1.5} />
                        <Label className="text-lg font-semibold text-foreground">Macronutrients (NPK)</Label>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                        {[
                          { key: 'nitrogen', label: 'Nitrogen (N)', color: 'text-blue-600', min: 0, max: 200, unit: 'kg/ha' },
                          { key: 'phosphorus', label: 'Phosphorus (P)', color: 'text-orange-600', min: 0, max: 200, unit: 'kg/ha' },
                          { key: 'potassium', label: 'Potassium (K)', color: 'text-yellow-600', min: 0, max: 200, unit: 'kg/ha' },
                        ].map(({ key, label, color, min, max }) => (
                          <div key={key} className="space-y-3 relative">
                            <Label className={`text-xs font-semibold uppercase tracking-widest ${color}`}>{label}</Label>
                            <div className="relative">
                              <Input
                                type="number" min={min} max={max} step="1"
                                value={form[key as keyof typeof form]}
                                onChange={e => setField(key, e.target.value)}
                                className="font-mono text-xl h-14 bg-white border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] rounded-[20px] px-5"
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Climate */}
                    <div className="space-y-8 bg-muted/20 p-8 rounded-[32px] border border-transparent">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <CloudRain className="h-6 w-6 text-blue-500" strokeWidth={1.5} />
                          <Label className="text-lg font-semibold text-foreground">Environmental Data</Label>
                        </div>
                        {weatherFilling && (
                          <span className="text-xs text-blue-600 font-medium flex items-center gap-1.5 bg-blue-50 px-3 py-1 rounded-full">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            Auto-filling from live weather…
                          </span>
                        )}
                        {!weatherFilling && weatherCache && (
                          <span className="text-xs text-green-700 font-medium flex items-center gap-1.5 bg-green-50 px-3 py-1 rounded-full">
                            <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                            Live weather applied
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-6">
                        {[
                          { key: 'temperature', label: 'Temp (°C)', min: 0, max: 50, step: '0.1', icon: Thermometer, color: 'text-orange-500' },
                          { key: 'humidity', label: 'Humidity (%)', min: 0, max: 100, step: '1', icon: Droplets, color: 'text-blue-500' },
                          { key: 'ph', label: 'Soil pH', min: 0, max: 14, step: '0.1', icon: Wind, color: 'text-purple-500' },
                          { key: 'rainfall', label: 'Rainfall (mm)', min: 0, max: 3000, step: '0.1', icon: CloudRain, color: 'text-cyan-500' },
                        ].map(({ key, label, min, max, step, icon: Icon, color }) => (
                          <div key={key} className="space-y-3">
                            <Label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                              <Icon className={`h-4 w-4 ${color}`} strokeWidth={1.5} /> {label}
                            </Label>
                            <Input
                              type="number" min={min} max={max} step={step}
                              value={form[key as keyof typeof form]}
                              onChange={e => setField(key, e.target.value)}
                              className="font-mono text-xl h-14 bg-white border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] rounded-[20px] px-5"
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {error && (
                    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="flex items-center gap-4 text-red-700 bg-red-50 border border-transparent p-6 rounded-[24px]">
                      <AlertTriangle className="h-6 w-6 shrink-0" strokeWidth={1.5} />
                      <span className="text-base font-medium">{error}</span>
                    </motion.div>
                  )}

                  <div className="pt-6 flex justify-end">
                    <Button type="submit" size="lg" disabled={loading} className="w-full md:w-auto h-16 px-10 text-lg bg-foreground hover:bg-foreground/90 text-background shadow-[0_8px_30px_rgba(0,0,0,0.12)] rounded-full transition-transform active:scale-[0.98] font-medium">
                      {loading ? (
                        <><Loader2 className="mr-3 h-5 w-5 animate-spin" strokeWidth={1.5} />Processing ML Model...</>
                      ) : (
                        <><Search className="mr-3 h-5 w-5" strokeWidth={1.5} />Generate Prediction</>
                      )}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </motion.div>
        ) : (
          <motion.div 
            key="result"
            initial={{ opacity: 0, scale: 0.98, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }}
            className="space-y-10"
          >
            <div className="flex justify-between items-center px-4">
              <h2 className="text-3xl font-semibold text-foreground">Analysis Complete</h2>
              <Button variant="outline" onClick={() => setResult(null)} className="rounded-full bg-white shadow-sm h-12 px-6 font-medium text-base border-transparent hover:bg-muted">
                <RefreshCw className="h-4 w-4 mr-2" strokeWidth={1.5} /> Modify Parameters
              </Button>
            </div>

            {/* Primary Result */}
            <Card className="glass-card overflow-hidden relative flex flex-col">
              <CardHeader className="relative z-10 pb-0 px-10 pt-10">
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-8">
                  <div>
                    <div className="inline-flex items-center rounded-full bg-green-100 px-4 py-1.5 text-xs font-semibold text-green-700 mb-6 uppercase tracking-widest">
                      Top Recommendation
                    </div>
                    <CardTitle className="text-6xl md:text-8xl font-semibold capitalize text-foreground py-2">
                      {result.recommended_crop}
                    </CardTitle>
                  </div>
                  <div className="md:text-right bg-white p-6 rounded-[32px] shadow-[0_2px_10px_rgba(0,0,0,0.02)] min-w-[160px]">
                    <div className="text-6xl md:text-7xl font-light text-foreground">
                      {result.confidence_score?.toFixed(1) || '0.0'}<span className="text-3xl text-muted-foreground font-light">%</span>
                    </div>
                    <div className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mt-2">Model Confidence</div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-12 relative z-10 pt-10 pb-12 px-10">
                {/* Confidence bar */}
                <div className="w-full bg-muted rounded-full h-4 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${result.confidence_score || 0}%` }}
                    transition={{ duration: 1.5, ease: 'easeOut', delay: 0.2 }}
                    className="bg-green-400 h-full rounded-full"
                  />
                </div>

                <div className="grid lg:grid-cols-3 gap-10">
                  <div className="lg:col-span-2 space-y-10">
                    {/* AI Explanation */}
                    {result.explanation && (
                      <div className="bg-white p-8 rounded-[32px] border border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
                        <div className="flex items-center gap-3 text-lg font-semibold mb-6 text-foreground">
                          <div className="p-3 bg-purple-100 rounded-full">
                            <Sparkles className="h-6 w-6 text-purple-600" strokeWidth={1.5} />
                          </div>
                          AI Analysis & Reasoning
                        </div>
                        <div className="prose prose-base dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:font-light text-foreground">
                          <ReactMarkdown>{result.explanation}</ReactMarkdown>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="space-y-8">
                    {/* Alternatives */}
                    {result.alternatives?.length > 0 && (
                      <div className="bg-white p-8 rounded-[32px] border border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
                        <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-6">Viable Alternatives</div>
                        <div className="flex gap-3 flex-wrap">
                          {result.alternatives.map((alt, i) => (
                            <span key={i} className="capitalize px-5 py-2.5 bg-muted/50 rounded-full text-base font-medium text-foreground">
                              {alt}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Tips */}
                    {result.tips && result.tips.length > 0 && (
                      <div className="bg-green-50/50 p-8 rounded-[32px] border border-transparent">
                        <div className="text-xs font-semibold uppercase tracking-widest text-green-700 mb-6">Agronomy Tips</div>
                        <ul className="space-y-5">
                          {result.tips.map((tip, i) => (
                            <li key={i} className="text-base font-light text-foreground flex items-start gap-4 leading-relaxed">
                              <span className="text-green-600 mt-1 shrink-0 bg-green-100 p-1.5 rounded-full"><Leaf className="h-4 w-4" strokeWidth={1.5} /></span>
                              <span>{tip}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>

                {/* Soil inputs used */}
                <div className="pt-10 border-t border-border/50">
                  <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-6">Dataset Used for Inference</div>
                  <div className="flex flex-wrap gap-4 text-sm font-mono">
                    {Object.entries(result.input_params || {}).map(([k, v]) => (
                      <div key={k} className="bg-white border border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] px-4 py-2 rounded-xl flex gap-3 items-center">
                        <span className="text-muted-foreground uppercase tracking-widest text-xs font-sans font-semibold">{k}</span>
                        <span className="font-medium text-foreground">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
