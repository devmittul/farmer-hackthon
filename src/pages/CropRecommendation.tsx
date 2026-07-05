import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';
import { Leaf, MapPin, Search, Loader2, AlertTriangle, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cropApi, type CropResult } from '@/services/api';

export default function CropRecommendation() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CropResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    location: 'Punjab, India',
    nitrogen: 90,
    phosphorus: 42,
    potassium: 43,
    temperature: 22,
    humidity: 75,
    ph: 6.5,
    rainfall: 200,
    language: 'en',
  });

  const setField = (key: string, value: string | number) =>
    setForm(f => ({ ...f, [key]: value }));

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setError(null);
    try {
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
      });
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Prediction failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-2">
        <div className="bg-green-100 p-2 rounded-lg dark:bg-green-900/30">
          <Leaf className="h-6 w-6 text-green-600 dark:text-green-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Smart Crop Recommendation</h1>
          <p className="text-muted-foreground">AI-powered ML prediction with Gemini explanation.</p>
        </div>
      </div>

      {!result ? (
        <Card className="border-t-4 border-t-primary shadow-md">
          <CardHeader>
            <CardTitle>Soil & Climate Inputs</CardTitle>
            <CardDescription>
              Enter your soil test values and climate data for precise ML-based recommendations.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAnalyze} className="space-y-6">
              <div className="grid md:grid-cols-2 gap-6">
                {/* Location */}
                <div className="space-y-2">
                  <Label>Location</Label>
                  <div className="flex gap-2">
                    <Input
                      value={form.location}
                      onChange={e => setField('location', e.target.value)}
                      placeholder="Enter Village/District"
                    />
                    <Button
                      type="button" variant="outline" size="sm"
                      title="Sync Location"
                      onClick={() => {
                        if (navigator.geolocation) {
                          navigator.geolocation.getCurrentPosition(async pos => {
                            const lat = pos.coords.latitude;
                            const lon = pos.coords.longitude;
                            try {
                              const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
                              const data = await res.json();
                              const placeName = data.address.city || data.address.town || data.address.village || data.address.county || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
                              const stateName = data.address.state || '';
                              setField('location', stateName ? `${placeName}, ${stateName}` : placeName);
                            } catch (e) {
                              setField('location', `${lat.toFixed(4)}, ${lon.toFixed(4)}`);
                            }
                          });
                        }
                      }}
                    >
                      Sync Location
                    </Button>
                  </div>
                </div>

                {/* Language */}
                <div className="space-y-2">
                  <Label>Response Language</Label>
                  <Select value={form.language} onValueChange={v => setField('language', v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
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

              {/* NPK */}
              <div>
                <Label className="text-base font-semibold mb-3 block">Soil Test Values (kg/ha)</Label>
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { key: 'nitrogen', label: 'Nitrogen (N)', color: 'text-blue-500', min: 0, max: 200 },
                    { key: 'phosphorus', label: 'Phosphorus (P)', color: 'text-red-500', min: 0, max: 200 },
                    { key: 'potassium', label: 'Potassium (K)', color: 'text-orange-500', min: 0, max: 200 },
                  ].map(({ key, label, color, min, max }) => (
                    <div key={key} className="space-y-1">
                      <Label className={`text-xs font-medium ${color}`}>{label}</Label>
                      <Input
                        type="number" min={min} max={max} step="1"
                        value={form[key as keyof typeof form]}
                        onChange={e => setField(key, e.target.value)}
                        className="font-mono"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Climate */}
              <div>
                <Label className="text-base font-semibold mb-3 block">Climate Parameters</Label>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { key: 'temperature', label: 'Temp (°C)', min: 0, max: 50, step: '0.1' },
                    { key: 'humidity', label: 'Humidity (%)', min: 0, max: 100, step: '1' },
                    { key: 'ph', label: 'Soil pH', min: 0, max: 14, step: '0.1' },
                    { key: 'rainfall', label: 'Rainfall (mm)', min: 0, max: 3000, step: '1' },
                  ].map(({ key, label, min, max, step }) => (
                    <div key={key} className="space-y-1">
                      <Label className="text-xs font-medium">{label}</Label>
                      <Input
                        type="number" min={min} max={max} step={step}
                        value={form[key as keyof typeof form]}
                        onChange={e => setField(key, e.target.value)}
                        className="font-mono"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {error && (
                <div className="flex items-center gap-2 text-destructive text-sm bg-destructive/10 p-3 rounded-lg">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}

              <div className="pt-2 flex justify-end">
                <Button type="submit" size="lg" disabled={loading} className="w-full md:w-auto">
                  {loading ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Running ML Model...</>
                  ) : (
                    <><Search className="mr-2 h-4 w-4" />Predict Best Crop</>
                  )}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold">ML Prediction Results</h2>
            <Button variant="outline" onClick={() => setResult(null)}>Edit Inputs</Button>
          </div>

          {/* Primary Result */}
          <Card className="border-t-4 border-t-green-500 overflow-hidden">
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-xs font-mono text-muted-foreground mb-1">TOP RECOMMENDATION</div>
                  <CardTitle className="text-4xl capitalize">{result.recommended_crop}</CardTitle>
                </div>
                <div className="text-right">
                  <div className="text-5xl font-bold text-green-600">{result.confidence.toFixed(1)}%</div>
                  <div className="text-xs text-muted-foreground">ML Confidence</div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Confidence bar */}
              <div className="w-full bg-muted rounded-full h-3">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${result.confidence}%` }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                  className="bg-green-500 h-3 rounded-full"
                />
              </div>

              {/* AI Explanation */}
              {result.explanation && (
                <div className="bg-muted/50 p-4 rounded-lg">
                  <div className="flex items-center gap-2 text-sm font-semibold mb-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    Gemini AI Explanation
                  </div>
                  <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-pre:p-0 text-muted-foreground">
                    <ReactMarkdown>{result.explanation}</ReactMarkdown>
                  </div>
                </div>
              )}

              {/* Alternatives */}
              {result.alternatives?.length > 0 && (
                <div>
                  <div className="text-sm font-semibold mb-2">Alternative Crops</div>
                  <div className="flex gap-2 flex-wrap">
                    {result.alternatives.map((alt, i) => (
                      <span key={i} className="capitalize px-3 py-1 bg-muted rounded-full text-sm">
                        {alt}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Tips */}
              {result.tips?.length > 0 && (
                <div>
                  <div className="text-sm font-semibold mb-2">Farming Tips</div>
                  <ul className="space-y-1">
                    {result.tips.map((tip, i) => (
                      <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                        <span className="text-green-500 mt-0.5">•</span>{tip}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Soil inputs used */}
              <div className="pt-2 border-t">
                <div className="text-xs text-muted-foreground mb-2">Inputs used for prediction</div>
                <div className="grid grid-cols-4 gap-2 text-xs font-mono">
                  {Object.entries(result.soil_inputs || {}).map(([k, v]) => (
                    <div key={k} className="bg-muted px-2 py-1 rounded">
                      <span className="text-muted-foreground">{k}: </span>
                      <span className="font-medium">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-center pt-2">
            <Button variant="outline" onClick={() => setResult(null)} className="w-full md:w-auto">
              Run Another Prediction
            </Button>
          </div>
        </motion.div>
      )}
    </div>
  );
}
