import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Droplet, Thermometer, Wind, CheckCircle2, AlertTriangle, CloudRain, Loader2, RefreshCw, MapPin } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAppStore } from '@/store/useAppStore';
import { weatherApi, chatApi, type WeatherData } from '@/services/api';

export default function Irrigation() {
  const { user } = useAppStore();
  const [location, setLocation] = useState(user?.location || 'Mumbai, India');
  const [inputLocation, setInputLocation] = useState(location);
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

  useEffect(() => { fetchData(location); }, []);

  const syncLocation = () => {
    if (!navigator.geolocation) return;
    setLoading(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        try {
          const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
          const data = await res.json();
          const placeName = data.address.city || data.address.town || data.address.village || data.address.county || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          const stateName = data.address.state || '';
          const fullLoc = stateName ? `${placeName}, ${stateName}` : placeName;
          setLocation(fullLoc);
          setInputLocation(fullLoc);
          fetchData(fullLoc, true);
        } catch (e) {
          const locStr = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
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
    <div className="flex flex-col gap-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between mb-2 flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="bg-blue-100 p-2 rounded-lg dark:bg-blue-900/30">
            <Droplet className="h-6 w-6 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Irrigation & Advisory</h1>
            <p className="text-muted-foreground">Live weather + AI-powered irrigation guidance.</p>
          </div>
        </div>

        {/* Location input */}
        <div className="flex gap-2">
          <Input
            value={inputLocation}
            onChange={e => setInputLocation(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { setLocation(inputLocation); fetchData(inputLocation); } }}
            placeholder="Enter location..."
            className="w-48"
          />
          <Button
            variant="outline" size="icon" title="Sync Location"
            onClick={syncLocation}
          >
            <MapPin className="h-4 w-4 text-primary" />
          </Button>
          <Button variant="outline" size="icon" onClick={() => fetchData(location, true)} title="Refresh Data">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Live Weather Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-xl flex items-center gap-2">
              <CloudRain className="h-5 w-5 text-blue-500" />
              Live Weather — {location}
            </CardTitle>
            <CardDescription>Real-time data from Open-Meteo.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-4">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="h-12 bg-muted animate-pulse rounded-md" />
                ))}
              </div>
            ) : weather ? (
              <>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="bg-muted/50 p-4 rounded-lg flex items-start gap-3">
                    <Thermometer className="h-5 w-5 text-orange-500 mt-0.5" />
                    <div>
                      <div className="text-2xl font-bold">{weather.current.temperature_c}°C</div>
                      <div className="text-xs text-muted-foreground">Temperature</div>
                    </div>
                  </div>
                  <div className="bg-muted/50 p-4 rounded-lg flex items-start gap-3">
                    <Droplet className="h-5 w-5 text-blue-500 mt-0.5" />
                    <div>
                      <div className="text-2xl font-bold">{weather.current.humidity_pct}%</div>
                      <div className="text-xs text-muted-foreground">Humidity</div>
                    </div>
                  </div>
                  <div className="bg-muted/50 p-4 rounded-lg flex items-start gap-3">
                    <Wind className="h-5 w-5 text-sky-500 mt-0.5" />
                    <div>
                      <div className="text-2xl font-bold">{weather.current.wind_kmh}</div>
                      <div className="text-xs text-muted-foreground">Wind (km/h)</div>
                    </div>
                  </div>
                  <div className="bg-muted/50 p-4 rounded-lg flex items-start gap-3">
                    <CloudRain className="h-5 w-5 text-indigo-500 mt-0.5" />
                    <div>
                      <div className="text-2xl font-bold">{weather.current.rainfall_mm}mm</div>
                      <div className="text-xs text-muted-foreground">Rainfall</div>
                    </div>
                  </div>
                </div>

                {/* 5-day forecast */}
                {weather.forecast?.length > 0 && (
                  <div>
                    <div className="text-xs font-semibold text-muted-foreground mb-2">5-DAY FORECAST</div>
                    <div className="space-y-2">
                      {weather.forecast.slice(0, 5).map((day, i) => (
                        <div key={i} className="flex justify-between items-center text-sm py-1 border-b last:border-0">
                          <span className="text-muted-foreground">{new Date(day.date).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}</span>
                          <span>{day.condition}</span>
                          <span className="font-mono text-xs">{day.temp_min_c}° – {day.temp_max_c}°C</span>
                          <span className="text-blue-500 text-xs">{day.rainfall_mm}mm</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-sm text-muted-foreground">Weather unavailable for this location.</div>
            )}
          </CardContent>
        </Card>

        {/* AI Advisory Card */}
        <Card className="border-t-4 border-t-blue-500">
          <CardHeader>
            <CardTitle className="text-xl">AI Irrigation Advisory</CardTitle>
            <CardDescription>Generated by Gemini based on live weather.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loading ? (
              <div className="space-y-4">
                <div className="h-24 bg-muted animate-pulse rounded-md" />
                <div className="h-12 bg-muted animate-pulse rounded-md" />
              </div>
            ) : (
              <>
                {/* Irrigation decision badge */}
                <div className={`p-4 rounded-xl border ${shouldIrrigate
                  ? 'bg-blue-50 border-blue-200 text-blue-900 dark:bg-blue-950/40 dark:border-blue-800/50 dark:text-blue-100'
                  : 'bg-green-50 border-green-200 text-green-900 dark:bg-green-950/40 dark:border-green-800/50 dark:text-green-100'
                }`}>
                  <div className="flex items-center gap-3 mb-1">
                    {shouldIrrigate
                      ? <AlertTriangle className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                      : <CheckCircle2 className="h-6 w-6 text-green-600 dark:text-green-400" />
                    }
                    <h3 className="font-bold text-lg">
                      {shouldIrrigate ? 'Irrigation Recommended' : 'No Irrigation Needed'}
                    </h3>
                  </div>
                  <p className="text-sm">
                    {shouldIrrigate
                      ? `Low rainfall (${weather?.current.rainfall_mm}mm) and humidity (${weather?.current.humidity_pct}%). Irrigate your crops.`
                      : `Moisture conditions are adequate (${weather?.current.humidity_pct}% humidity, ${weather?.current.rainfall_mm}mm rain).`
                    }
                  </p>
                </div>

                {/* Gemini advisory text */}
                <div className="bg-muted/50 rounded-lg p-4">
                  {advisoryLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Generating AI advisory...
                    </div>
                  ) : advisory ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-pre:p-0">
                      <ReactMarkdown>{advisory}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No advisory available.</p>
                  )}
                </div>

                <Button
                  className="w-full" variant="outline"
                  onClick={() => fetchData(location, true)}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Refresh Advisory
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
