import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Cloud, Droplets, Wind, Leaf, Stethoscope, ArrowRight, MessageSquare, Thermometer, Send, Loader2, CheckCircle2, XCircle, Server } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAppStore } from '@/store/useAppStore';
import { weatherApi, chatApi, systemApi, type WeatherData, type ChatMessage } from '@/services/api';

export default function Dashboard() {
  const { user } = useAppStore();
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(true);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'ai'; text: string; intent?: string }>>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();

  const location = user?.location || 'Mumbai, India';
  const [currentLocation, setCurrentLocation] = useState(location);

  const [systemStatus, setSystemStatus] = useState<Record<string, { status: string; message: string }> | null>(null);
  const [systemLoading, setSystemLoading] = useState(true);

  const fetchWeather = (loc: string, force = false) => {
    setWeatherLoading(true);
    weatherApi.get(loc, 3, 'en', force)
      .then(setWeather)
      .catch(() => setWeather(null))
      .finally(() => setWeatherLoading(false));
  };

  useEffect(() => {
    fetchWeather(currentLocation);
    
    // Fetch System Status
    setSystemLoading(true);
    systemApi.getStatus()
      .then(setSystemStatus)
      .catch(() => setSystemStatus(null))
      .finally(() => setSystemLoading(false));
  }, [currentLocation]);

  const syncLocation = () => {
    if (!navigator.geolocation) return;
    setWeatherLoading(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        try {
          const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
          const data = await res.json();
          const placeName = data.address.city || data.address.town || data.address.village || data.address.county || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          const stateName = data.address.state || '';
          const fullLocation = stateName ? `${placeName}, ${stateName}` : placeName;
          setCurrentLocation(fullLocation);
          fetchWeather(fullLocation, true);
        } catch (e) {
          const locStr = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          setCurrentLocation(locStr);
          fetchWeather(locStr, true);
        }
      },
      () => setWeatherLoading(false)
    );
  };

  const sendChat = async () => {
    const msg = chatInput.trim();
    if (!msg || chatLoading) return;
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: msg }]);
    setChatLoading(true);
    try {
      const res: ChatMessage = await chatApi.send(msg, currentLocation, sessionId);
      if (res.session_id) setSessionId(res.session_id);
      setChatMessages(prev => [...prev, { role: 'ai', text: res.reply, intent: res.intent }]);
    } catch (err: any) {
      setChatMessages(prev => [...prev, { role: 'ai', text: `Error: ${err.message}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight">
          Welcome back, {user?.name ?? 'Farmer'}
        </h1>
        <p className="text-muted-foreground">
          Live overview for your farm in <span className="font-medium text-foreground">{currentLocation}</span>.
        </p>
      </div>

      {/* Top Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Weather Card */}
        <Card className="col-span-2 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 border-blue-100 dark:border-blue-900">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Cloud className="h-5 w-5 text-blue-500" />
              Live Weather — {currentLocation}
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={syncLocation} disabled={weatherLoading} title="Sync GPS Location">
                Sync Location
              </Button>
              <Button variant="outline" size="sm" onClick={() => fetchWeather(currentLocation, true)} disabled={weatherLoading} title="Force Refresh">
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {weatherLoading ? (
              <div className="h-20 animate-pulse bg-blue-100/50 dark:bg-blue-900/20 rounded-md" />
            ) : weather ? (
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-4xl font-bold">{weather.current.temperature_c}°C</div>
                  <div className="text-sm font-medium text-muted-foreground mt-1">{weather.current.condition}</div>
                </div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <Droplets className="h-4 w-4 text-blue-500" />
                    <span>{weather.current.humidity_pct}% Humidity</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Wind className="h-4 w-4 text-blue-500" />
                    <span>{weather.current.wind_kmh} km/h</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Thermometer className="h-4 w-4 text-orange-400" />
                    <span>{weather.current.rainfall_mm}mm Rain</span>
                  </div>
                  <div className="flex items-center gap-2 text-muted-foreground text-xs">
                    {weather.forecast?.[0]?.date && `Forecast: ${weather.forecast[0].condition}`}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">Weather data unavailable. Check API connection.</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Farm Size</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{user?.farm_size_acres ?? '—'} Acres</div>
            <p className="text-xs text-muted-foreground mt-1">Registered profile</p>
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center justify-between">
              Core Services
              {systemLoading && <Loader2 className="h-3 w-3 animate-spin" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1">
            {systemStatus ? (
              <div className="space-y-2 mt-1">
                {[
                  { key: 'claude_api', name: 'Claude AI' },
                  { key: 'weather', name: 'Weather API' },
                  { key: 'earth_engine', name: 'Earth Engine' },
                  { key: 'mongodb', name: 'Database' },
                  { key: 'location', name: 'Location' }
                ].map(({ key, name }) => {
                  const s = systemStatus[key];
                  const isLive = s?.status === 'Live';
                  return (
                    <div key={key} className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">{name}</span>
                      <div className={`flex items-center gap-1 font-medium ${isLive ? 'text-green-600 dark:text-green-400' : 'text-red-500'}`}>
                        {isLive ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                        {s?.status || 'Offline'}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground h-full flex items-center justify-center">
                {!systemLoading && "Status unavailable"}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* AI Chat Widget */}
      <Card className="border-t-4 border-t-primary">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <MessageSquare className="h-5 w-5 text-primary" />
            Ask KrishiMitra AI
          </CardTitle>
          <CardDescription>Ask about weather, crops, routes, emergencies — in any language.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {chatMessages.length > 0 && (
            <div className="max-h-60 overflow-y-auto space-y-2 p-3 bg-muted/30 rounded-lg">
              {chatMessages.map((m, i) => (
                <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] px-3 py-2 rounded-lg text-sm ${
                    m.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-background border shadow-sm'
                  }`}>
                    {m.role === 'ai' && m.intent && (
                      <div className="text-xs text-muted-foreground mb-1 font-mono">
                        [{m.intent}]
                      </div>
                    )}
                    {m.role === 'ai' ? (
                      <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-pre:p-0">
                        <ReactMarkdown>{m.text}</ReactMarkdown>
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap">{m.text}</div>
                    )}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-background border shadow-sm px-3 py-2 rounded-lg">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  </div>
                </div>
              )}
            </div>
          )}
          <div className="flex gap-2">
            <Input
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendChat()}
              placeholder="e.g. What should I grow this season? / Aaj ka mausam kaisa hai?"
              disabled={chatLoading}
            />
            <Button onClick={sendChat} disabled={chatLoading || !chatInput.trim()} size="icon">
              {chatLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
          <div className="flex gap-2 flex-wrap">
            {['What crop to grow?', 'Will it rain today?', 'Route to mandi'].map(q => (
              <button
                key={q}
                onClick={() => { setChatInput(q); }}
                className="text-xs px-2 py-1 rounded-full bg-muted hover:bg-muted/80 text-muted-foreground transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* AI Services Grid */}
      <h2 className="text-xl font-bold tracking-tight mt-2">AI Services</h2>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          { title: 'Crop Recommendation', desc: 'ML-powered crop prediction for your soil.', icon: Leaf, href: '/dashboard/crop', color: 'text-green-500' },
          { title: 'Irrigation Advisory', desc: 'Smart watering with live weather data.', icon: Droplets, href: '/dashboard/irrigation', color: 'text-blue-500' },
          { title: 'Disease Diagnosis', desc: 'Describe symptoms, get AI diagnosis.', icon: Stethoscope, href: '/dashboard/disease', color: 'text-red-500' },
        ].map((service, i) => (
          <motion.div key={i} whileHover={{ y: -5 }} transition={{ type: 'spring', stiffness: 300 }}>
            <Card className="h-full flex flex-col hover:border-primary/50 transition-colors">
              <CardHeader>
                <div className="mb-4">
                  <div className={`p-3 rounded-xl bg-background shadow-sm inline-block ${service.color}`}>
                    <service.icon className="h-6 w-6" />
                  </div>
                </div>
                <CardTitle className="text-xl">{service.title}</CardTitle>
                <CardDescription>{service.desc}</CardDescription>
              </CardHeader>
              <CardContent className="mt-auto">
                <Button asChild className="w-full" variant="outline">
                  <Link to={service.href}>
                    Open Module <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
