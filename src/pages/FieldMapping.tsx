import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Map as MapIcon, Globe, MapPin, Navigation, Trash2, Save, 
  Search, Plus, Sparkles, ChevronRight, Check, X, ShieldAlert, HelpCircle,
  Download, Star, Edit, ShieldCheck
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { farmApi } from '@/services/api';
import { useAppStore } from '@/store/useAppStore';
import { useToast } from '@/hooks/use-toast';
import { Link } from 'react-router-dom';

import Map, { Source, Layer, NavigationControl, GeolocateControl, Marker } from 'react-map-gl/mapbox';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import * as turf from '@turf/turf';
import type { Farm } from '@/types/farm';

import 'mapbox-gl/dist/mapbox-gl.css';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';

// Default Map center: center of India agricultural hub (Nagpur region)
const DEFAULT_CENTER = { lat: 21.1458, lng: 79.0882 };

export default function FieldMapping() {
  const { toast } = useToast();
  const { 
    farms, 
    activeFarm, 
    farmsLoading, 
    loadFarms, 
    activateFarm,
    activeLocation,
    setActiveLocation
  } = useAppStore();

  const [selectedFarmId, setSelectedFarmId] = useState<string | null>(null);
  const [selectedFarm, setSelectedFarm] = useState<Farm | null>(null);

  // Mapbox Token configuration
  const mapboxToken = import.meta.env.VITE_MAPBOX_TOKEN || '';

  // Map Views & Controls
  const [mapStyle, setMapStyle] = useState<'satellite' | 'streets'>('satellite');
  const [drawMode, setDrawMode] = useState<'idle' | 'drawing' | 'editing'>('idle');
  const [drawnPolygon, setDrawnPolygon] = useState<any>(null);
  const [calculatedArea, setCalculatedArea] = useState<{
    sqMeter: number;
    hectare: number;
    acres: number;
  } | null>(null);

  // Dialog State
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [farmName, setFarmName] = useState('');
  const [savingFarm, setSavingFarm] = useState(false);

  // Search autocomplete state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [searching, setSearching] = useState(false);

  // Map and Draw Refs
  const mapRef = useRef<any>(null);
  const drawRef = useRef<MapboxDraw | null>(null);
  const searchContainerRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<any>(null);

  // Click outside search suggestions handler
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(event.target as Node)) {
        setShowSearchResults(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // Load farms on mount
  useEffect(() => {
    loadFarms();
  }, []);

  // Update selected farm details when list or active changes
  useEffect(() => {
    if (selectedFarmId) {
      const found = farms.find(f => f.farm_id === selectedFarmId);
      setSelectedFarm(found || null);
    } else if (activeFarm) {
      setSelectedFarmId(activeFarm.farm_id);
      setSelectedFarm(activeFarm);
    }
  }, [farms, selectedFarmId, activeFarm]);

  // Sync Map viewport to active location or active farm on load
  useEffect(() => {
    if (mapRef.current) {
      // If we have an active farm with boundary, zoom to it
      if (activeFarm?.boundary) {
        try {
          const bbox = turf.bbox(activeFarm.boundary);
          mapRef.current.fitBounds(
            [[bbox[0], bbox[1]], [bbox[2], bbox[3]]],
            { padding: 80, duration: 1500 }
          );
          return;
        } catch (e) {
          console.error("Failed to fit active farm bounds:", e);
        }
      }

      // Fallback: parse activeLocation
      if (activeLocation) {
        const parts = activeLocation.split(',');
        if (parts.length === 2) {
          const lat = parseFloat(parts[0]);
          const lon = parseFloat(parts[1]);
          if (!isNaN(lat) && !isNaN(lon)) {
            mapRef.current.flyTo({
              center: [lon, lat],
              zoom: 14,
              duration: 1500
            });
            return;
          }
        }

        // If activeLocation is a text string (like "Nagpur, Maharashtra"), geocode it to fly the map to it
        fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(activeLocation)}&limit=1`)
          .then(res => res.json())
          .then(data => {
            if (data && data.length > 0 && mapRef.current) {
              const lat = parseFloat(data[0].lat);
              const lon = parseFloat(data[0].lon);
              if (!isNaN(lat) && !isNaN(lon)) {
                mapRef.current.flyTo({
                  center: [lon, lat],
                  zoom: 14,
                  duration: 1500
                });
              }
            }
          })
          .catch(err => console.error("Failed to geocode activeLocation on map load:", err));
      }
    }
  }, [activeFarm, activeLocation]);

  // Handle Search Input Change (OSM Nominatim API)
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchQuery(val);
    
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (val.length < 3) {
      setSearchResults([]);
      setShowSearchResults(false);
      return;
    }

    setSearching(true);
    debounceTimerRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(val)}&countrycodes=in&limit=5`
        );
        const data = await res.json();
        setSearchResults(data || []);
        setShowSearchResults(true);
      } catch (err) {
        console.error("OSM Search failed:", err);
      } finally {
        setSearching(false);
      }
    }, 500);
  };

  const handleSelectSearchResult = (result: any) => {
    const lat = parseFloat(result.lat);
    const lon = parseFloat(result.lon);
    if (mapRef.current) {
      mapRef.current.flyTo({
        center: [lon, lat],
        zoom: 15,
        essential: true,
        duration: 1500
      });
    }
    setSearchQuery(result.display_name);
    setShowSearchResults(false);
  };

  // Map Initialization & Event Listeners
  const onMapLoad = (evt: any) => {
    const map = evt.target;
    
    // Instantiate MapboxDraw without default UI buttons to keep custom premium UI controls
    const draw = new MapboxDraw({
      displayControlsDefault: false,
      controls: {
        polygon: true,
        trash: true
      },
      defaultMode: 'simple_select'
    });
    
    map.addControl(draw);
    drawRef.current = draw;

    // Attach Mapbox Draw Event Handlers
    map.on('draw.create', handleDrawCreate);
    map.on('draw.update', handleDrawUpdate);
    map.on('draw.delete', handleDrawDelete);
  };

  // Mapbox Draw events
  const handleDrawCreate = (e: any) => {
    const feature = e.features[0];
    if (feature && feature.geometry.type === 'Polygon') {
      const area = turf.area(feature);
      setCalculatedArea({
        sqMeter: Math.round(area),
        hectare: parseFloat((area / 10000).toFixed(4)),
        acres: parseFloat((area * 0.000247105).toFixed(3))
      });
      setDrawnPolygon(feature.geometry);
      setDrawMode('editing');
      setShowSaveDialog(true);
    }
  };

  const handleDrawUpdate = (e: any) => {
    const feature = e.features[0];
    if (feature && feature.geometry.type === 'Polygon') {
      const area = turf.area(feature);
      setCalculatedArea({
        sqMeter: Math.round(area),
        hectare: parseFloat((area / 10000).toFixed(4)),
        acres: parseFloat((area * 0.000247105).toFixed(3))
      });
      setDrawnPolygon(feature.geometry);
    }
  };

  const handleDrawDelete = () => {
    setDrawnPolygon(null);
    setCalculatedArea(null);
    setDrawMode('idle');
  };

  // Programmatic drawing control triggers
  const startDrawing = () => {
    if (drawRef.current) {
      drawRef.current.deleteAll();
      drawRef.current.changeMode('draw_polygon');
      setDrawMode('drawing');
      toast({
        title: "Drawing Mode Active",
        description: "Click on the map to define the boundary vertices. Close the polygon to finish."
      });
    }
  };

  const cancelDrawing = () => {
    if (drawRef.current) {
      drawRef.current.deleteAll();
    }
    setDrawnPolygon(null);
    setCalculatedArea(null);
    setDrawMode('idle');
    setShowSaveDialog(false);
  };

  // Save the drawn farm to FastAPI
  const handleSaveFarm = async () => {
    if (!farmName.trim()) {
      toast({
        variant: "destructive",
        title: "Validation error",
        description: "Please enter a farm name to save."
      });
      return;
    }
    if (!drawnPolygon) return;

    setSavingFarm(true);
    try {
      const res = await farmApi.create({
        name: farmName,
        boundary: drawnPolygon
      });
      
      toast({
        title: "Farm registered",
        description: `Farm "${res.name}" has been mapped and geocoded successfully.`
      });

      // Reset local state
      setFarmName('');
      setShowSaveDialog(false);
      setDrawnPolygon(null);
      setCalculatedArea(null);
      setDrawMode('idle');

      if (drawRef.current) {
        drawRef.current.deleteAll();
      }

      // Reload list and select new farm
      await loadFarms();
      if (res) {
        setSelectedFarmId(res.farm_id);
        activateFarm(res.farm_id).catch(() => {});
      }
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Failed to save farm",
        description: err.message || "An error occurred."
      });
    } finally {
      setSavingFarm(false);
    }
  };

  // Delete a farm boundary
  const handleDeleteFarm = async (farmId: string) => {
    if (!confirm("Are you sure you want to permanently delete this farm mapping?")) return;
    
    try {
      await farmApi.delete(farmId);
      toast({
        title: "Farm deleted",
        description: "The farm registry has been deleted."
      });
      
      if (selectedFarmId === farmId) {
        setSelectedFarmId(null);
        setSelectedFarm(null);
      }
      
      await loadFarms();
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Failed to delete farm",
        description: err.message || "Something went wrong."
      });
    }
  };

  // Activate farm globally
  const handleActivateFarm = async (farmId: string) => {
    try {
      await activateFarm(farmId);
      toast({
        title: "Farm activated!",
        description: "This farm has been set as your primary active location context."
      });
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Activation failed",
        description: err.message || "Could not set active farm."
      });
    }
  };

  // Select card and pan map
  const selectFarm = (farm: Farm) => {
    setSelectedFarmId(farm.farm_id);
    setSelectedFarm(farm);
    activateFarm(farm.farm_id).catch(() => {});

    if (mapRef.current) {
      if (farm.boundary) {
        try {
          const bbox = turf.bbox(farm.boundary);
          mapRef.current.fitBounds(
            [[bbox[0], bbox[1]], [bbox[2], bbox[3]]],
            { padding: 80, duration: 1200 }
          );
        } catch (e) {
          console.error("Bbox calculation failed, flying to center", e);
          if (farm.center_coordinate) {
            mapRef.current.flyTo({
              center: [farm.center_coordinate.longitude, farm.center_coordinate.latitude],
              zoom: 15,
              duration: 1200
            });
          }
        }
      } else if (farm.center_coordinate) {
        mapRef.current.flyTo({
          center: [farm.center_coordinate.longitude, farm.center_coordinate.latitude],
          zoom: 15,
          duration: 1200
        });
      }
    }
  };

  // Export boundary to GeoJSON file download
  const handleExportGeoJson = (farm: Farm) => {
    if (!farm.boundary) return;
    const fileContent = {
      type: "Feature",
      geometry: farm.boundary,
      properties: {
        name: farm.name,
        area_acres: farm.area_acres,
        area_hectares: farm.area_hectares,
        village: farm.village,
        district: farm.district,
        state: farm.state,
        country: farm.country,
        created_at: farm.created_at
      }
    };
    const blob = new Blob([JSON.stringify(fileContent, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${farm.name.toLowerCase().replace(/\s+/g, '_')}_boundary.geojson`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast({
      title: "Export complete",
      description: "Boundary GeoJSON file downloaded."
    });
  };



  // Sync with browser's high-accuracy GPS coordinates
  const syncExactLocation = () => {
    if (!navigator.geolocation) {
      toast({
        variant: "destructive",
        title: "Not supported",
        description: "Browser geolocation is not supported on this device."
      });
      return;
    }

    toast({
      title: "Locating...",
      description: "Requesting your exact GPS coordinates..."
    });

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        if (mapRef.current) {
          mapRef.current.flyTo({
            center: [lon, lat],
            zoom: 15,
            duration: 1500
          });
        }

        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`
          );
          const data = await res.json();
          const place = data.address.city || data.address.town || data.address.village || data.address.county || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          const state = data.address.state || '';
          const fullLoc = state ? `${place}, ${state}` : place;
          setActiveLocation(fullLoc);
          toast({
            title: "Location Synced",
            description: `Map centered and location updated to: ${fullLoc}`
          });
        } catch {
          const fallback = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          setActiveLocation(fallback);
          toast({
            title: "Location Synced (Coords only)",
            description: `Map centered at: ${fallback}`
          });
        }
      },
      (err) => {
        console.error("GPS fetch failed:", err);
        toast({
          variant: "destructive",
          title: "GPS Access Denied",
          description: "Please check your browser location permissions."
        });
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  };

  // Map Click handler (selects farm if clicked on it)
  const handleMapClick = (event: any) => {
    if (drawMode !== 'idle') return;
    const features = mapRef.current?.queryRenderedFeatures(event.point, {
      layers: ['farms-fill-layer']
    });
    if (features && features.length > 0) {
      const fId = features[0].properties.farm_id;
      const found = farms.find(f => f.farm_id === fId);
      if (found) {
        selectFarm(found);
      }
    }
  };

  // Format saved farms list as a FeatureCollection for Mapbox Source
  const savedFarmsGeoJson: any = {
    type: 'FeatureCollection',
    features: farms
      .filter(f => f.boundary && f.boundary.type === 'Polygon')
      .map(f => ({
        type: 'Feature',
        geometry: f.boundary,
        properties: {
          farm_id: f.farm_id,
          name: f.name,
          is_active: f.is_active,
          area_acres: f.area_acres
        }
      }))
  };

  // Retrieve Mapbox Map Style URL
  const mapStyleUrl = mapStyle === 'satellite' 
    ? 'mapbox://styles/mapbox/satellite-streets-v12'
    : 'mapbox://styles/mapbox/outdoors-v12';

  return (
    <div className="flex flex-col gap-8 w-full max-w-[1600px] mx-auto pb-20">
      
      {/* Header Panel */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6">
        <div>
          <h1 className="text-4xl font-semibold tracking-tight text-foreground flex items-center gap-3">
            <MapIcon className="h-10 w-10 text-green-600" strokeWidth={1.5} />
            Farm Boundary Registry
          </h1>
          <p className="text-muted-foreground text-lg font-light mt-1">
            Define farm borders using Mapbox Draw, geocode addresses, and synchronize active fields with GEE.
          </p>
        </div>

        {/* Mapbox Token and Search Controls */}
        <div className="flex flex-wrap items-center gap-4 w-full lg:w-auto">
          {/* Nominatim Search box */}
          <div ref={searchContainerRef} className="relative flex-1 sm:max-w-xs">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
              <Input
                value={searchQuery}
                onChange={handleSearchChange}
                placeholder="Search village, city, region..."
                className="w-full pl-10 pr-4 h-11 bg-white border-border rounded-full shadow-sm"
              />
              {searching && (
                <div className="absolute right-4 top-1/2 -translate-y-1/2">
                  <div className="h-4 w-4 border-2 border-green-600 border-t-transparent animate-spin rounded-full" />
                </div>
              )}
            </div>

            {/* Nominatim Search results dropdown */}
            <AnimatePresence>
              {showSearchResults && searchResults.length > 0 && (
                <motion.ul
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="absolute left-0 right-0 mt-2 bg-white/95 backdrop-blur-md border border-slate-200 rounded-2xl shadow-xl z-50 overflow-hidden divide-y divide-slate-100 max-h-60 overflow-y-auto"
                >
                  {searchResults.map((r, idx) => (
                    <li
                      key={idx}
                      onClick={() => handleSelectSearchResult(r)}
                      className="p-3.5 text-xs text-slate-700 hover:bg-slate-50 cursor-pointer font-light transition-colors"
                    >
                      {r.display_name}
                    </li>
                  ))}
                </motion.ul>
              )}
            </AnimatePresence>
          </div>

          {/* Sync GPS Button */}
          <Button
            onClick={syncExactLocation}
            variant="outline"
            className="rounded-full h-11 px-5 border-border bg-white shadow-sm font-medium text-green-700 hover:text-green-800 hover:bg-green-50"
          >
            <Navigation className="mr-2 h-4 w-4 text-green-600" />
            Sync GPS
          </Button>

        </div>
      </div>

      {/* Main Content Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
        
        {/* LEFT COLUMN: Map Canvas & Toolbar */}
        <div className="xl:col-span-8 flex flex-col gap-6">
          <Card className="border-0 shadow-lg bg-white rounded-[32px] overflow-hidden relative">
            
            {/* Map Canvas */}
            <div className="relative h-[600px] w-full bg-slate-100">
              <Map
                ref={mapRef}
                initialViewState={{
                  longitude: DEFAULT_CENTER.lng,
                  latitude: DEFAULT_CENTER.lat,
                  zoom: 5
                }}
                mapStyle={mapStyleUrl}
                mapboxAccessToken={mapboxToken}
                onLoad={onMapLoad}
                onClick={handleMapClick}
                interactiveLayerIds={['farms-fill-layer']}
              >
                {/* Navigation and Geolocate Controls */}
                <NavigationControl position="bottom-right" />
                <GeolocateControl 
                  position="bottom-right" 
                  trackUserLocation={true} 
                  showUserLocation={true}
                  positionOptions={{ enableHighAccuracy: true }}
                  onGeolocate={async (e: any) => {
                    const lat = e.coords.latitude;
                    const lon = e.coords.longitude;
                    try {
                      const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
                      const data = await res.json();
                      const place = data.address.city || data.address.town || data.address.village || data.address.county || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
                      const state = data.address.state || '';
                      const fullLoc = state ? `${place}, ${state}` : place;
                      setActiveLocation(fullLoc);
                      toast({
                        title: "Location Synced",
                        description: `Updated your live location context to: ${fullLoc}`,
                      });
                    } catch {
                      setActiveLocation(`${lat.toFixed(4)}, ${lon.toFixed(4)}`);
                    }
                  }}
                />

                {/* Render All Saved Farms Boundaries */}
                {farms.length > 0 && (
                  <Source id="saved-farms-source" type="geojson" data={savedFarmsGeoJson}>
                    {/* Fill layer */}
                    <Layer
                      id="farms-fill-layer"
                      type="fill"
                      paint={{
                        'fill-color': [
                          'case',
                          ['boolean', ['get', 'is_active'], false],
                          '#10b981', // active farm is vivid green
                          '#3b82f6'  // inactive is blue
                        ],
                        'fill-opacity': [
                          'case',
                          ['==', ['get', 'farm_id'], selectedFarmId],
                          0.35,
                          0.15
                        ]
                      }}
                    />
                    {/* Stroke layer */}
                    <Layer
                      id="farms-stroke-layer"
                      type="line"
                      paint={{
                        'line-color': [
                          'case',
                          ['boolean', ['get', 'is_active'], false],
                          '#047857',
                          '#2563eb'
                        ],
                        'line-width': [
                          'case',
                          ['==', ['get', 'farm_id'], selectedFarmId],
                          4,
                          1.5
                        ]
                      }}
                    />
                  </Source>
                )}

                {/* Markers for Farms that do not have polygons, but have centroids */}
                {farms
                  .filter(f => !f.boundary && f.center_coordinate)
                  .map(f => (
                    <Marker
                      key={f.farm_id}
                      longitude={f.center_coordinate!.longitude}
                      latitude={f.center_coordinate!.latitude}
                      anchor="bottom"
                      onClick={(e: any) => {
                        e.originalEvent?.stopPropagation();
                        selectFarm(f);
                      }}
                    >
                      <div className="cursor-pointer group flex flex-col items-center">
                        <div className={`p-1.5 rounded-full shadow-md border-2 border-white ${f.is_active ? 'bg-emerald-600' : 'bg-blue-600'} transition-transform group-hover:scale-110`}>
                          <MapPin className="h-5 w-5 text-white" />
                        </div>
                        <span className="bg-white/90 backdrop-blur px-2 py-0.5 rounded text-[10px] border border-slate-200 mt-1 font-semibold text-slate-700 shadow-sm max-w-[80px] truncate">
                          {f.name}
                        </span>
                      </div>
                    </Marker>
                  ))}
              </Map>

              {/* Floating Map Custom Toolbar */}
              <div className="absolute top-4 left-4 z-10 flex flex-col gap-3">
                
                {/* View Style Switcher */}
                <div className="bg-white/90 backdrop-blur border border-slate-200/80 p-1.5 rounded-full shadow-lg flex gap-1 items-center">
                  <button
                    onClick={() => setMapStyle('satellite')}
                    className={`text-xs font-semibold px-4 py-2 rounded-full transition-colors flex items-center gap-1.5 ${mapStyle === 'satellite' ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-500 hover:text-slate-900'}`}
                  >
                    <Globe className="h-3.5 w-3.5" />
                    Satellite
                  </button>
                  <button
                    onClick={() => setMapStyle('streets')}
                    className={`text-xs font-semibold px-4 py-2 rounded-full transition-colors flex items-center gap-1.5 ${mapStyle === 'streets' ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-500 hover:text-slate-900'}`}
                  >
                    <MapIcon className="h-3.5 w-3.5" />
                    Terrain/Outdoors
                  </button>
                </div>

                {/* Drawing Actions */}
                <div className="bg-white/90 backdrop-blur border border-slate-200/80 p-2.5 rounded-3xl shadow-lg flex flex-col gap-2 max-w-fit">
                  {drawMode === 'idle' ? (
                    <Button
                      onClick={startDrawing}
                      className="bg-green-600 hover:bg-green-700 text-white font-semibold rounded-full h-11 px-6 shadow-md transition-all active:scale-[0.98] w-full"
                    >
                      <Plus className="h-4.5 w-4.5 mr-2" />
                      Map Farm Boundary
                    </Button>
                  ) : (
                    <div className="flex flex-col gap-2">
                      <span className="text-[10px] text-green-700 font-mono uppercase bg-green-50 px-2.5 py-1 rounded-full text-center font-bold">
                        {drawMode === 'drawing' ? 'Drawing Mode' : 'Editing Mode'}
                      </span>
                      <div className="flex gap-2">
                        <Button
                          onClick={cancelDrawing}
                          variant="outline"
                          size="sm"
                          className="rounded-full border-slate-200 text-slate-500 hover:bg-slate-50 h-9 font-medium"
                        >
                          <X className="h-3.5 w-3.5 mr-1" />
                          Cancel
                        </Button>
                        {drawnPolygon && (
                          <Button
                            onClick={() => setShowSaveDialog(true)}
                            size="sm"
                            className="rounded-full bg-green-600 hover:bg-green-700 text-white h-9 font-semibold"
                          >
                            <Save className="h-3.5 w-3.5 mr-1" />
                            Save
                          </Button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </Card>

          {/* Real-time Turf calculated Area Stats Card */}
          <AnimatePresence>
            {calculatedArea && (
              <motion.div 
                initial={{ opacity: 0, y: 15 }} 
                animate={{ opacity: 1, y: 0 }} 
                exit={{ opacity: 0, y: 15 }}
              >
                <Card className="border-0 shadow-md bg-white rounded-[24px]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold uppercase tracking-widest text-green-700 flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-green-600" />
                      Live Polygon Geometry Analytics (Turf.js)
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-2">
                    <div className="grid grid-cols-3 gap-6 text-center">
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100">
                        <div className="text-xs text-muted-foreground font-light mb-1">Square Meters</div>
                        <div className="text-xl font-bold text-slate-800">{calculatedArea.sqMeter.toLocaleString()} m²</div>
                      </div>
                      <div className="bg-green-50/50 p-4 rounded-2xl border border-green-100/50">
                        <div className="text-xs text-green-700 font-medium mb-1">Hectares</div>
                        <div className="text-xl font-extrabold text-green-700">{calculatedArea.hectare} ha</div>
                      </div>
                      <div className="bg-orange-50/50 p-4 rounded-2xl border border-orange-100/50">
                        <div className="text-xs text-orange-700 font-medium mb-1">Acres</div>
                        <div className="text-xl font-extrabold text-orange-700">{calculatedArea.acres} acres</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* RIGHT COLUMN: Farm Registry Details Panel */}
        <div className="xl:col-span-4 flex flex-col gap-6">
          
          {/* Selected Farm Details */}
          {selectedFarm ? (
            <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
              <Card className="border-0 shadow-lg bg-white rounded-[32px] relative overflow-hidden">
                <div className="absolute top-0 right-0 p-24 bg-green-50/30 blur-2xl rounded-full translate-x-1/2 -translate-y-1/2" />
                <CardHeader className="pb-4 relative z-10 flex flex-row items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-mono uppercase px-3 py-1 rounded-full font-bold flex items-center gap-1 ${selectedFarm.is_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                        {selectedFarm.is_active ? (
                          <>
                            <Star className="h-3 w-3 fill-green-600" /> Active Farm
                          </>
                        ) : (
                          'Inactive'
                        )}
                      </span>
                      {selectedFarm.village && (
                        <span className="text-[10px] font-mono uppercase bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full">
                          📍 {selectedFarm.village}
                        </span>
                      )}
                    </div>
                    <CardTitle className="text-2xl font-semibold text-slate-800 mt-3">{selectedFarm.name}</CardTitle>
                    {selectedFarm.center_coordinate && (
                      <CardDescription className="font-light text-slate-500 mt-1">
                        GPS Lock: {selectedFarm.center_coordinate.latitude.toFixed(5)}°, {selectedFarm.center_coordinate.longitude.toFixed(5)}°
                      </CardDescription>
                    )}
                  </div>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => {
                      setSelectedFarmId(null);
                      setSelectedFarm(null);
                    }} 
                    className="rounded-full h-8 w-8 hover:bg-slate-100"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </CardHeader>
                <CardContent className="space-y-6 relative z-10">
                  
                  {/* Address Meta Card */}
                  {(selectedFarm.district || selectedFarm.state) && (
                    <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100/80 text-xs text-slate-600 font-light space-y-1.5">
                      <div className="flex justify-between">
                        <span className="text-slate-400">District:</span>
                        <span className="font-semibold text-slate-800">{selectedFarm.district || '—'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">State:</span>
                        <span className="font-semibold text-slate-800">{selectedFarm.state || '—'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Country:</span>
                        <span className="font-semibold text-slate-800">{selectedFarm.country || 'India'}</span>
                      </div>
                    </div>
                  )}

                  {/* Area geometry breakdown */}
                  <div className="grid grid-cols-2 gap-4 bg-slate-50 p-5 rounded-[24px] border border-slate-100">
                    <div>
                      <span className="text-xs text-muted-foreground font-light">Acres</span>
                      <div className="text-xl font-bold text-slate-800 mt-0.5">{selectedFarm.area_acres?.toFixed(3) || '—'} ac</div>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground font-light">Hectares</span>
                      <div className="text-xl font-bold text-slate-800 mt-0.5">{selectedFarm.area_hectares?.toFixed(3) || '—'} ha</div>
                    </div>
                    <div className="col-span-2 pt-3 border-t border-slate-200/60 mt-1">
                      <span className="text-xs text-muted-foreground font-light">Total Area</span>
                      <div className="text-lg font-semibold text-slate-800 mt-0.5">
                        {selectedFarm.area_m2 ? `${Math.round(selectedFarm.area_m2).toLocaleString()} m²` : '—'}
                      </div>
                    </div>
                  </div>

                  {/* Satellite Summary if present */}
                  {selectedFarm.latest_satellite && (
                    <div className="bg-green-50/40 border border-green-100/50 p-4 rounded-2xl space-y-2 text-xs">
                      <h4 className="font-bold text-green-800 uppercase tracking-widest text-[10px] flex items-center gap-1.5">
                        <ShieldCheck className="h-4.5 w-4.5 text-green-700" />
                        Latest GEE Crop Diagnostic
                      </h4>
                      <div className="flex justify-between">
                        <span className="text-green-700">Mean NDVI Index:</span>
                        <span className="font-bold text-green-800">{selectedFarm.latest_satellite.ndvi?.toFixed(3)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-green-700">Canopy Health:</span>
                        <span className="font-bold text-green-800">{selectedFarm.latest_satellite.crop_health}</span>
                      </div>
                    </div>
                  )}

                  {/* Actions toolbar */}
                  <div className="flex flex-col gap-3">

                    
                    {selectedFarm.boundary && (
                      <div className="grid grid-cols-2 gap-3">
                        <Button 
                          asChild 
                          className="bg-slate-900 hover:bg-slate-800 text-white rounded-full h-12 font-semibold"
                        >
                          <Link to={`/dashboard/satellite-analysis?field_id=${selectedFarm.farm_id}`}>
                            GEE Analytics <Sparkles className="ml-2 h-4 w-4 text-green-400" />
                          </Link>
                        </Button>
                        <Button 
                          variant="outline"
                          onClick={() => handleExportGeoJson(selectedFarm)}
                          className="rounded-full border-slate-200 text-slate-700 hover:bg-slate-50 h-12 font-semibold"
                        >
                          <Download className="mr-2 h-4.5 w-4.5" /> Export GeoJSON
                        </Button>
                      </div>
                    )}

                    <Button 
                      variant="outline" 
                      onClick={() => handleDeleteFarm(selectedFarm.farm_id)}
                      className="w-full rounded-full border-rose-200 text-rose-600 hover:bg-rose-50 hover:text-rose-700 h-12 font-semibold"
                    >
                      <Trash2 className="mr-2 h-4.5 w-4.5" /> Delete Farm Borders
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ) : (
            <Card className="border-0 shadow-md bg-slate-50/50 rounded-[32px] border-dashed border-2 border-slate-200 p-8 text-center flex flex-col items-center justify-center min-h-[220px]">
              <HelpCircle className="h-12 w-12 text-slate-300 mb-3" strokeWidth={1.5} />
              <h3 className="text-base font-semibold text-slate-500">No Farm Selected</h3>
              <p className="text-xs text-slate-400 max-w-[240px] font-light mt-1">
                Click on a saved boundary polygon on the map or select from the registry below to display coordinates, geocoding and download files.
              </p>
            </Card>
          )}

          {/* Farms List Registry */}
          <Card className="border-0 shadow-lg bg-white rounded-[32px] flex-1">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-semibold text-slate-800 flex items-center justify-between">
                <span>My Registered Farms</span>
                <span className="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full font-mono">{farms.length} Registry</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-y-auto max-h-[350px] divide-y divide-slate-100">
                {farmsLoading ? (
                  <div className="py-12 flex justify-center items-center">
                    <div className="h-6 w-6 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : farms.length === 0 ? (
                  <div className="py-16 text-center text-muted-foreground font-light text-sm px-6">
                    No farm boundaries registered yet.<br/>Click <strong>Map Farm Boundary</strong> to define your first border.
                  </div>
                ) : (
                  farms.map(f => {
                    const isSelected = selectedFarmId === f.farm_id;
                    return (
                      <div 
                        key={f.farm_id} 
                        onClick={() => selectFarm(f)}
                        className={`flex items-center justify-between p-5 cursor-pointer transition-all hover:bg-slate-50/80 ${isSelected ? 'bg-green-50/40 border-l-4 border-green-600' : ''}`}
                      >
                        <div className="flex flex-col gap-1 min-w-0 pr-4">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-800 truncate text-base">{f.name}</span>
                            {f.is_active && (
                              <span className="bg-green-100 text-green-700 text-[9px] font-bold px-2 py-0.5 rounded-full uppercase">
                                Active
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-muted-foreground font-light flex items-center gap-1.5">
                            {f.boundary ? `📍 ${f.area_acres?.toFixed(2) || 0} acres` : '⚠️ No polygon drawn'}
                            {f.village && ` • ${f.village}`}
                          </span>
                        </div>
                        <ChevronRight className="h-5 w-5 text-slate-300 flex-shrink-0" />
                      </div>
                    );
                  })
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Save Dialog Overlay */}
      <AnimatePresence>
        {showSaveDialog && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }} 
              animate={{ scale: 1, opacity: 1 }} 
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white rounded-[32px] shadow-xl w-full max-w-md overflow-hidden"
            >
              <div className="p-8 space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                    <Save className="h-5 w-5 text-green-600" /> Save Mapped Farm
                  </h3>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={cancelDrawing} 
                    className="rounded-full h-8 w-8 hover:bg-slate-100"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="farm-name">Farm Registry Name</Label>
                    <Input 
                      id="farm-name" 
                      value={farmName} 
                      onChange={(e) => setFarmName(e.target.value)} 
                      placeholder="e.g. Western Harvest Acres" 
                      className="rounded-xl border-slate-200 focus-visible:ring-green-500"
                    />
                    <p className="text-[10px] text-muted-foreground font-light">
                      Address layers (village, district, state, country) will be geocoded automatically.
                    </p>
                  </div>
                </div>

                {calculatedArea && (
                  <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100 flex justify-between items-center text-sm">
                    <span className="text-slate-500 font-light">Calculated Area:</span>
                    <span className="font-semibold text-slate-800">{calculatedArea.acres} Acres ({calculatedArea.hectare} ha)</span>
                  </div>
                )}

                <div className="flex gap-4">
                  <Button 
                    onClick={cancelDrawing} 
                    variant="ghost" 
                    className="flex-1 rounded-full border border-slate-200 h-12 font-semibold"
                  >
                    Cancel
                  </Button>
                  <Button 
                    onClick={handleSaveFarm} 
                    disabled={savingFarm || !farmName.trim()}
                    className="flex-1 bg-green-600 hover:bg-green-700 text-white rounded-full h-12 font-semibold"
                  >
                    {savingFarm ? "Saving..." : "Save Farm border"}
                  </Button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
}
