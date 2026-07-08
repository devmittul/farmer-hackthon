import { useEffect, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import {
  Sprout, LayoutDashboard, Leaf, Droplet,
  Stethoscope, FileText, Settings, LogOut, Menu, UserCircle, Bell, Search,
  Map, Globe, Activity, Clock, RefreshCw
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Toaster } from '@/components/ui/toaster';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { weatherApi } from '@/services/api';

/** How long (ms) cached weather stays fresh before re-fetching (15 min) */
const WEATHER_TTL_MS = 15 * 60 * 1000;

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Field Mapping', href: '/dashboard/field-mapping', icon: Map },
  { name: 'Satellite Analysis', href: '/dashboard/satellite-analysis', icon: Globe },
  { name: 'Crop Health', href: '/dashboard/crop-health', icon: Activity },
  { name: 'Crop Recommendation', href: '/dashboard/crop', icon: Leaf },
  { name: 'Irrigation Advisory', href: '/dashboard/irrigation', icon: Droplet },
  { name: 'Disease Diagnosis', href: '/dashboard/disease', icon: Stethoscope },
  { name: 'Reports', href: '/dashboard/reports', icon: FileText },
  { name: 'History', href: '/dashboard/field-history', icon: Clock },
];

function Sidebar({ pathname }: { pathname: string }) {
  const { logout } = useAppStore();

  return (
    <div className="flex h-full flex-col gap-6 py-8 bg-white shadow-[0_8px_30px_rgba(0,0,0,0.04)] border border-border/50 rounded-[40px]">
      <div className="flex items-center px-8 mb-6">
        <Link to="/" className="flex items-center gap-3 font-semibold group">
          <div className="bg-green-100 p-2.5 rounded-full shadow-[0_2px_10px_rgba(0,0,0,0.02)] group-hover:scale-105 transition-transform">
            <Sprout className="h-6 w-6 text-green-700" strokeWidth={1.5} />
          </div>
          <span className="text-2xl font-semibold tracking-tight text-foreground">KrishiMitra</span>
        </Link>
      </div>
      <div className="flex-1 overflow-auto px-6">
        <nav className="grid items-start gap-3 text-sm font-medium">
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className="relative flex items-center gap-4 rounded-full px-5 py-3.5 transition-all group"
              >
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active-bg"
                    className="absolute inset-0 rounded-full bg-green-50 border border-green-100/50"
                    initial={false}
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
                <div className="relative flex items-center gap-4 w-full">
                  <item.icon className={cn("h-5 w-5 transition-colors", isActive ? "text-green-700" : "text-muted-foreground group-hover:text-green-600")} strokeWidth={1.5} />
                  <span className={cn("transition-colors text-base", isActive ? "text-green-800 font-semibold" : "text-muted-foreground group-hover:text-foreground font-light")}>
                    {item.name}
                  </span>
                </div>
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="mt-auto p-6">
        <nav className="grid gap-3 text-sm font-medium">
          <Link
            to="/dashboard/profile"
            className="flex items-center gap-4 rounded-full px-5 py-3.5 text-muted-foreground transition-all hover:bg-muted hover:text-foreground font-light text-base"
          >
            <Settings className="h-5 w-5" strokeWidth={1.5} />
            Settings
          </Link>
          <button
            onClick={() => logout()}
            className="flex w-full items-center gap-4 rounded-full px-5 py-3.5 text-red-500 transition-all hover:bg-red-50 hover:text-red-600 font-light text-base text-left"
          >
            <LogOut className="h-5 w-5" strokeWidth={1.5} />
            Logout
          </button>
        </nav>
      </div>
    </div>
  );
}

export function DashboardLayout() {
  const {
    user,
    isAuthenticated,
    activeLocation,
    weatherCachedAt,
    setActiveLocation,
    setWeatherCache,
    farms,
    activateFarm,
    logout,
    refreshFarmData,
    refreshing,
    lastRefreshedAt,
  } = useAppStore();
  const location = useLocation();
  const navigate = useNavigate();

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
    }
  }, [isAuthenticated, navigate]);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // ── Auto-sync GPS on first load, then prefetch weather into global cache ──
  useEffect(() => {
    const prefetchWeather = async (loc: string, force = false) => {
      const cacheAge = weatherCachedAt ? Date.now() - weatherCachedAt : Infinity;
      if (!force && cacheAge < WEATHER_TTL_MS) return; // still fresh
      try {
        const data = await weatherApi.get(loc, 5, 'en', force);
        setWeatherCache(data);
      } catch { /* silent — pages handle their own error states */ }
    };

    if (!navigator.geolocation) {
      // No GPS support — just prefetch with stored location
      prefetchWeather(activeLocation);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`,
          );
          const data = await res.json();
          const place = data.address.city || data.address.town || data.address.village || data.address.county || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          const state = data.address.state || '';
          const fullLoc = state ? `${place}, ${state}` : place;
          setActiveLocation(fullLoc);
          prefetchWeather(fullLoc, true);
        } catch {
          const fallback = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          setActiveLocation(fallback);
          prefetchWeather(fallback, true);
        }
      },
      () => {
        // GPS denied — use stored location
        prefetchWeather(activeLocation);
      },
      { timeout: 8000, maximumAge: 5 * 60 * 1000 },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const searchResults: any[] = [];
  if (searchQuery.trim()) {
    const query = searchQuery.toLowerCase();

    // Filter Navigation Pages
    navigation.forEach(item => {
      if (item.name.toLowerCase().includes(query)) {
        searchResults.push({
          type: 'page',
          id: `page-${item.name}`,
          name: item.name,
          icon: item.icon,
          href: item.href,
        });
      }
    });

    // Filter Farms
    farms.forEach(farm => {
      if (farm.name.toLowerCase().includes(query) || (farm.village && farm.village.toLowerCase().includes(query))) {
        searchResults.push({
          type: 'farm',
          id: `farm-${farm.farm_id}`,
          name: farm.name,
          subName: farm.village || farm.district || 'Registered Farm',
          icon: Map,
          action: () => {
            activateFarm(farm.farm_id);
            navigate('/dashboard');
          }
        });
      }
    });

    // Commands/Other
    if ('settings'.includes(query) || 'profile'.includes(query)) {
      searchResults.push({
        type: 'action',
        id: 'action-settings',
        name: 'Settings & Profile',
        icon: Settings,
        href: '/dashboard/profile'
      });
    }
    if ('logout'.includes(query) || 'sign out'.includes(query)) {
      searchResults.push({
        type: 'action',
        id: 'action-logout',
        name: 'Logout',
        icon: LogOut,
        action: () => logout()
      });
    }
  }

  useEffect(() => {
    setSelectedIndex(0);
  }, [searchQuery]);

  const handleSelectResult = (result: any) => {
    setSearchQuery('');
    setIsSearchFocused(false);
    if (result.href) {
      navigate(result.href);
    } else if (result.action) {
      result.action();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (searchResults.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % searchResults.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + searchResults.length) % searchResults.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      handleSelectResult(searchResults[selectedIndex]);
    } else if (e.key === 'Escape') {
      setIsSearchFocused(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-background flex flex-col md:flex-row p-4 md:p-6 lg:p-8">
      {/* Floating Desktop Sidebar */}
      <div className="hidden md:block fixed h-[calc(100vh-32px)] md:h-[calc(100vh-48px)] lg:h-[calc(100vh-64px)] w-[280px] lg:w-[320px] z-20">
        <Sidebar pathname={location.pathname} />
      </div>

      <div className="flex flex-col flex-1 md:ml-[280px] lg:ml-[320px] md:pl-6 lg:pl-8">
        {/* Floating Top Navigation */}
        <header
          className="sticky top-4 md:top-6 lg:top-8 z-30 flex h-20 items-center gap-4 bg-white/70 border border-border/50 px-6 lg:px-8 rounded-[40px] shadow-[0_8px_30px_rgba(0,0,0,0.04)] mb-8 md:mb-10 lg:mb-12"
          style={{ backdropFilter: 'blur(30px)' }}
        >
          <Sheet>
            <SheetTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                className="shrink-0 md:hidden border-transparent bg-muted shadow-sm rounded-full h-10 w-10"
              >
                <Menu className="h-5 w-5 text-foreground" strokeWidth={1.5} />
                <span className="sr-only">Toggle navigation menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[320px] p-4 bg-transparent border-none">
              <Sidebar pathname={location.pathname} />
            </SheetContent>
          </Sheet>

          <div className="w-full flex-1 relative hidden sm:block">
            <div className="relative w-full max-w-md">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
              <Input
                placeholder="Search anything..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onFocus={() => setIsSearchFocused(true)}
                onBlur={() => {
                  setTimeout(() => setIsSearchFocused(false), 200);
                }}
                onKeyDown={handleKeyDown}
                className="w-full pl-10 h-10 bg-muted/50 border-transparent rounded-full shadow-none focus-visible:ring-1 focus-visible:ring-border"
              />

              {/* Search Dropdown */}
              {isSearchFocused && searchQuery.trim() && (
                <div 
                  className="absolute top-12 left-0 right-0 bg-white border border-border/60 rounded-[28px] shadow-[0_20px_40px_rgba(0,0,0,0.08)] overflow-hidden z-50 p-2 mt-2 max-h-[320px] overflow-y-auto"
                >
                  {searchResults.length > 0 ? (
                    searchResults.map((result, idx) => {
                      const Icon = result.icon;
                      const isSelected = idx === selectedIndex;
                      return (
                        <div
                          key={result.id}
                          onMouseDown={(e) => {
                            e.preventDefault();
                            handleSelectResult(result);
                          }}
                          onMouseEnter={() => setSelectedIndex(idx)}
                          className={cn(
                            "flex items-center gap-4 px-4 py-3 cursor-pointer rounded-2xl transition-all duration-200 border",
                            isSelected 
                              ? "bg-green-50/90 border-green-100/80 text-green-800 shadow-[0_4px_12px_rgba(34,197,94,0.04)]" 
                              : "border-transparent text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                          )}
                        >
                          <div className={cn(
                            "p-2.5 rounded-xl transition-colors",
                            isSelected ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground"
                          )}>
                            <Icon className="h-4 w-4" strokeWidth={1.5} />
                          </div>
                          <div className="flex flex-col flex-1 min-w-0">
                            <span className={cn(
                              "text-sm font-medium truncate",
                              isSelected ? "text-green-900" : "text-foreground"
                            )}>
                              {result.name}
                            </span>
                            {result.subName && (
                              <span className="text-[10px] text-muted-foreground font-light truncate mt-0.5">
                                {result.subName}
                              </span>
                            )}
                          </div>
                          <span className={cn(
                            "text-[9px] uppercase tracking-wider px-2 py-0.5 rounded-full font-mono font-semibold shrink-0",
                            isSelected ? "bg-green-100/80 text-green-800" : "bg-muted text-muted-foreground"
                          )}>
                            {result.type}
                          </span>
                        </div>
                      );
                    })
                  ) : (
                    <div className="px-6 py-8 text-center text-muted-foreground text-sm font-light">
                      No modules or farms found for <span className="font-semibold text-foreground">"{searchQuery}"</span>
                    </div>
                  )}
                </div>
              )}


            </div>
          </div>

          <div className="flex items-center gap-4 lg:gap-8 ml-auto">
            <button className="relative p-2.5 text-muted-foreground hover:text-foreground transition-colors rounded-full hover:bg-muted shadow-[0_2px_10px_rgba(0,0,0,0.02)] hidden sm:block">
              <Bell className="h-5 w-5" strokeWidth={1.5} />
              <Badge className="absolute top-2 right-2 h-2.5 w-2.5 p-0 flex justify-center items-center rounded-full bg-orange-400 text-[0px] border-2 border-white">3</Badge>
              <span className="sr-only">Toggle notifications</span>
            </button>
            <button
              onClick={() => refreshFarmData()}
              disabled={refreshing}
              title={lastRefreshedAt ? `Last refreshed: ${new Date(lastRefreshedAt).toLocaleTimeString()}` : 'Refresh all farm data'}
              className="relative p-2.5 text-muted-foreground hover:text-green-600 transition-colors rounded-full hover:bg-green-50 shadow-[0_2px_10px_rgba(0,0,0,0.02)] hidden sm:flex items-center gap-2 disabled:opacity-50"
            >
              <RefreshCw className={`h-5 w-5 ${refreshing ? 'animate-spin' : ''}`} strokeWidth={1.5} />
              {lastRefreshedAt && (
                <span className="text-[10px] font-light text-muted-foreground hidden lg:inline">
                  {new Date(lastRefreshedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
              <span className="sr-only">Refresh Farm Data</span>
            </button>
            <Link to="/dashboard/profile" className="flex items-center gap-4 pl-4 lg:pl-6 sm:border-l border-border/50 group">
              <div className="flex flex-col items-end hidden md:flex">
                <span className="text-sm font-medium text-foreground group-hover:text-green-700 transition-colors">
                  {user?.name || 'Farmer'}
                </span>
                <span className="text-xs font-light text-muted-foreground">Pro Member</span>
              </div>
              <div className="h-10 w-10 lg:h-12 lg:w-12 rounded-full bg-green-100 flex items-center justify-center border-2 border-white shadow-sm transition-transform group-hover:scale-105">
                <UserCircle className="h-6 w-6 lg:h-7 lg:w-7 text-green-700" strokeWidth={1.5} />
              </div>
            </Link>
          </div>
        </header>

        <main className="flex-1 flex flex-col relative w-full">
          <Outlet />
        </main>
      </div>
      <Toaster />
    </div>
  );
}
