import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { motion, AnimatePresence } from 'framer-motion';
import { Droplet, Thermometer, Wind, CheckCircle2, AlertTriangle, CloudRain, Loader2, MapPin, Sparkles, Navigation } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAppStore } from '@/store/useAppStore';
import { weatherApi, chatApi, type WeatherData } from '@/services/api';
import { cn } from '@/lib/utils';

export default function Irrigation() {
  const { activeLocation, setActiveLocation } = useAppStore();
  const [location, setLocation] = useState(activeLocation);
  const [inputLocation, setInputLocation] = useState(activeLocation);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [advisory, setAdvisory] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [advisoryLoading, setAdvisoryLoading] = useState(false);

  const fetchData = async (loc: string, force = false) => {
    setLoading(true);
    setAdvisory('');
    try {
      const data = await weatherApi.get(loc, 5, 'en', force);
      setWeather(data);
      // Now get AI irrigation advisory via chat
      setAdvisoryLoading(true);
      const chat = await chatApi.send(
        `Give me irrigation advisory for my farm. Location: ${loc}. Current weather: ${data.current.condition}, temperature ${data.current.temperature_c}°C, humidity ${data.current.humidity_pct}%, rainfall ${data.current.rainfall_mm}mm.`,
        loc,
        undefined,
      );
      setAdvisory(chat.reply);
    } catch (err: any) {
      setWeather(null);
      setAdvisory(`Could not fetch data: ${err.message}`);
    } finally {
      setLoading(false);
      setAdvisoryLoading(false);
    }
  };

  useEffect(() => { fetchData(location, true); }, []);

  const syncLocation = () => {
    if (!navigator.geolocation) return;
    setLoading(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        try {
          const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
          const data = await res.json();
          const placeName = data.address.city || data.address.town || data.address.village || data.address.county || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          const stateName = data.address.state || '';
          const fullLoc = stateName ? `${placeName}, ${stateName}` : placeName;
          setActiveLocation(fullLoc); // persist to store
          setLocation(fullLoc);
          setInputLocation(fullLoc);
          fetchData(fullLoc, true);
        } catch {
          const locStr = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          setActiveLocation(locStr);
          setLocation(locStr);
          setInputLocation(locStr);
          fetchData(locStr, true);
        }
      },
      () => setLoading(false)
    );
  };

  const shouldIrrigate = weather
    ? weather.current.rainfall_mm < 5 && weather.current.humidity_pct < 70
    : false;

  return (
    <div className="flex flex-col gap-10 w-full max-w-7xl mx-auto pb-20">
      <motion.div 
        initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 pt-6"
      >
        <div className="flex items-center gap-4">
          <div className="bg-blue-100/80 p-4 rounded-full">
            <Droplet className="h-8 w-8 text-blue-700" strokeWidth={1.5} />
          </div>
          <div>
            <h1 className="text-4xl font-semibold tracking-tight text-foreground">Smart Irrigation</h1>
            <p className="text-muted-foreground text-lg font-light mt-2">Live MeteoData paired with AI-driven hydration models.</p>
          </div>
        </div>

        {/* Location input */}
        <div className="flex flex-col sm:flex-row gap-4 w-full md:w-auto">
          <div className="relative">
            <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" strokeWidth={1.5} />
            <Input
              value={inputLocation}
              onChange={e => setInputLocation(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { setLocation(inputLocation); fetchData(inputLocation); } }}
              placeholder="Search location..."
              className="pl-12 h-14 w-full sm:w-72 bg-white border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] rounded-full focus-visible:ring-primary text-base"
            />
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline" title="Sync GPS Location"
              onClick={syncLocation}
              className="h-14 px-6 border-transparent bg-white hover:bg-muted text-foreground rounded-full shadow-[0_2px_10px_rgba(0,0,0,0.02)] font-medium text-base"
            >
              <Navigation className="h-5 w-5 mr-2 text-primary" strokeWidth={1.5} /> GPS
            </Button>
            <Button 
              className="h-14 px-8 bg-foreground hover:bg-foreground/90 text-background rounded-full font-medium text-base shadow-[0_8px_30px_rgba(0,0,0,0.12)] active:scale-[0.98] transition-transform"
              onClick={() => { setLocation(inputLocation); fetchData(inputLocation, true); }}
            >
              Update
            </Button>
          </div>
        </div>
      </motion.div>

      <div className="grid lg:grid-cols-2 gap-10">
        {/* Live Weather Card */}
        <Card className="glass-card h-full flex flex-col relative overflow-hidden">
          <CardHeader className="pb-6 relative z-10 px-8 pt-8">
            <CardTitle className="text-xl font-semibold flex items-center justify-between text-foreground">
              <span className="flex items-center gap-3">
                <CloudRain className="h-6 w-6 text-blue-500" strokeWidth={1.5} />
                Live MeteoData
              </span>
              <span className="text-sm font-medium text-muted-foreground uppercase tracking-widest">{location}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-2 relative z-10 px-8 pb-8 flex-1">
            <AnimatePresence mode="wait">
              {loading ? (
                <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
                  {[1, 2, 3].map(i => (
                    <div key={i} className="h-20 bg-muted/30 animate-pulse rounded-[24px]" />
                  ))}
                </motion.div>
              ) : weather ? (
                <motion.div key="data" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-8 h-full flex flex-col">
                  {/* Primary Stats Grid */}
                  <div className="grid grid-cols-2 gap-6">
                    <div className="bg-muted/30 p-6 rounded-[24px] flex items-center gap-5 transition-colors">
                      <div className="p-4 bg-orange-100 rounded-full">
                        <Thermometer className="h-6 w-6 text-orange-600" strokeWidth={1.5} />
                      </div>
                      <div>
                        <div className="text-3xl font-light text-foreground">{weather.current.temperature_c}°C</div>
                        <div className="text-xs font-medium text-muted-foreground uppercase tracking-widest mt-1">Temp</div>
                      </div>
                    </div>

                    <div className="bg-muted/30 p-6 rounded-[24px] flex items-center gap-5 transition-colors">
                      <div className="p-4 bg-blue-100 rounded-full">
                        <Droplet className="h-6 w-6 text-blue-600" strokeWidth={1.5} />
                      </div>
                      <div>
                        <div className="text-3xl font-light text-foreground">{weather.current.humidity_pct}%</div>
                        <div className="text-xs font-medium text-muted-foreground uppercase tracking-widest mt-1">Humidity</div>
                      </div>
                    </div>

                    <div className="bg-muted/30 p-6 rounded-[24px] flex items-center gap-5 transition-colors">
                      <div className="p-4 bg-sky-100 rounded-full">
                        <Wind className="h-6 w-6 text-sky-600" strokeWidth={1.5} />
                      </div>
                      <div>
                        <div className="text-3xl font-light text-foreground flex items-baseline gap-1">
                          {weather.current.wind_kmh} <span className="text-sm font-medium text-muted-foreground">km/h</span>
                        </div>
                        <div className="text-xs font-medium text-muted-foreground uppercase tracking-widest mt-1">Wind</div>
                      </div>
                    </div>

                    <div className="bg-muted/30 p-6 rounded-[24px] flex items-center gap-5 transition-colors">
                      <div className="p-4 bg-indigo-100 rounded-full">
                        <CloudRain className="h-6 w-6 text-indigo-600" strokeWidth={1.5} />
                      </div>
                      <div>
                        <div className="text-3xl font-light text-foreground flex items-baseline gap-1">
                          {weather.current.rainfall_mm} <span className="text-sm font-medium text-muted-foreground">mm</span>
                        </div>
                        <div className="text-xs font-medium text-muted-foreground uppercase tracking-widest mt-1">Rain</div>
                      </div>
                    </div>
                  </div>

                  {/* 5-day forecast */}
                  {weather.forecast?.length > 0 && (
                    <div className="pt-4 flex-1">
                      <div className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">5-Day Trajectory</div>
                      <div className="space-y-4">
                        {weather.forecast.slice(0, 5).map((day, i) => (
                          <div key={i} className="flex justify-between items-center py-2 border-b border-border/50 last:border-0 text-base">
                            <span className="font-medium text-foreground w-28">
                              {new Date(day.date).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}
                            </span>
                            <span className="flex-1 text-muted-foreground truncate px-2 font-light">{day.condition}</span>
                            <span className="text-foreground font-light w-24 text-right">{day.temp_min_c}° <span className="text-muted-foreground">/</span> {day.temp_max_c}°</span>
                            <span className="text-blue-500 font-medium w-16 text-right">{day.rainfall_mm}mm</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </motion.div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-center py-12">
                  <AlertTriangle className="h-12 w-12 text-muted-foreground mx-auto mb-4" strokeWidth={1} />
                  <p className="text-muted-foreground text-lg font-light">MeteoData unavailable for this location.</p>
                </div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>

        {/* AI Advisory Card */}
        <Card className={cn(
          "glass-card flex flex-col h-full transition-colors duration-500",
          !loading && shouldIrrigate ? 'bg-blue-50/50' : '',
          !loading && !shouldIrrigate ? 'bg-green-50/50' : ''
        )}>
          <CardHeader className="pb-6 relative z-10 px-8 pt-8">
            <CardTitle className="text-2xl font-semibold flex items-center gap-3 text-foreground">
              <Sparkles className="h-6 w-6 text-accent-foreground" strokeWidth={1.5} />
              AI Agronomist
            </CardTitle>
            <CardDescription className="text-base font-light mt-2">Real-time interpretation powered by AI.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-8 relative z-10 flex-1 flex flex-col px-8 pb-8">
            <AnimatePresence mode="wait">
              {loading ? (
                <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
                  <div className="h-32 bg-muted/30 animate-pulse rounded-[24px]" />
                  <div className="h-64 bg-muted/30 animate-pulse rounded-[24px]" />
                </motion.div>
              ) : (
                <motion.div key="content" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex-1 flex flex-col space-y-8">
                  {/* Irrigation decision badge */}
                  <div className={cn(
                    "p-8 rounded-[32px] flex flex-col gap-4",
                    shouldIrrigate
                      ? 'bg-blue-100 text-blue-900'
                      : 'bg-green-100 text-green-900'
                  )}>
                    <div className="flex items-center gap-4">
                      {shouldIrrigate
                        ? <Droplet className="h-10 w-10 animate-bounce" strokeWidth={1.5} />
                        : <CheckCircle2 className="h-10 w-10" strokeWidth={1.5} />
                      }
                      <h3 className="font-semibold text-3xl tracking-tight">
                        {shouldIrrigate ? 'Irrigate Now' : 'Optimal Hydration'}
                      </h3>
                    </div>
                    <p className="text-base font-light opacity-90 leading-relaxed">
                      {shouldIrrigate
                        ? `Low rainfall (${weather?.current.rainfall_mm}mm) and humidity (${weather?.current.humidity_pct}%). Immediate watering suggested to prevent crop stress.`
                        : `Moisture conditions are adequate (${weather?.current.humidity_pct}% humidity, ${weather?.current.rainfall_mm}mm rain). No action required.`
                      }
                    </p>
                  </div>

                  {/* AI advisory text */}
                  <div className="flex-1 bg-white rounded-[32px] p-8 border border-transparent shadow-[0_2px_10px_rgba(0,0,0,0.02)] flex flex-col">
                    <div className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-6 flex items-center gap-2">
                      <Sparkles className="h-4 w-4" strokeWidth={1.5} /> Detailed AI Strategy
                    </div>
                    
                    <div className="flex-1 overflow-y-auto max-h-[300px] pr-4 custom-scrollbar">
                      {advisoryLoading ? (
                        <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-4">
                          <Loader2 className="h-8 w-8 animate-spin" strokeWidth={1.5} />
                          <span className="text-base font-light">Synthesizing meteorological data...</span>
                        </div>
                      ) : advisory ? (
                        <div className="prose prose-base dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:font-light text-foreground">
                          <ReactMarkdown>{advisory}</ReactMarkdown>
                        </div>
                      ) : (
                        <p className="text-base font-light text-muted-foreground">No advisory generated.</p>
                      )}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
