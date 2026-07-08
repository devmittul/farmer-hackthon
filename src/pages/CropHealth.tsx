import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { 
  Activity, Heart, AlertTriangle, ShieldCheck, Info, MapPin, 
  Droplets, Flame, Sparkles, ChevronRight, HelpCircle
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { farmApi } from '@/services/api';
import { useToast } from '@/hooks/use-toast';
import { Link } from 'react-router-dom';

import type { Farm } from '@/types/farm';

export default function CropHealth() {
  const { toast } = useToast();
  const [farms, setFarms] = useState<Farm[]>([]);
  const [selectedFarmId, setSelectedFarmId] = useState<string>('');
  const [loading, setLoading] = useState(true);

  const loadFarms = async () => {
    try {
      const data = await farmApi.list();
      setFarms(data || []);
      if (data && data.length > 0) {
        setSelectedFarmId(data[0].farm_id);
      }
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Error loading crop health",
        description: err.message || "Failed to fetch farms."
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFarms();
  }, []);

  const selectedFarm = farms.find(f => f.farm_id === selectedFarmId);
  const satellite = selectedFarm?.latest_satellite;

  // Generate dynamic insights based on NDVI
  const getInsights = (ndvi: number | undefined) => {
    if (ndvi === undefined) return null;
    
    if (ndvi < 0.15) {
      return {
        status: "Critical Stress",
        color: "text-rose-500 bg-rose-50 border-rose-100",
        progressBar: "bg-rose-500",
        percentage: 15,
        pestRisk: "High (Weeds / Soil Pathogens)",
        waterIndex: "Dry / Severe Under-irrigation",
        actions: [
          "Check field for soil moisture starvation immediately.",
          "Verify if weeds are overtaking the bare soil layers.",
          "Prepare fertilizer schedule to restore nutrient levels."
        ]
      };
    } else if (ndvi < 0.35) {
      return {
        status: "Moderate Stress / Early Growth",
        color: "text-orange-500 bg-orange-50 border-orange-100",
        progressBar: "bg-orange-500",
        percentage: 45,
        pestRisk: "Medium (Opportunistic fungi / aphids)",
        waterIndex: "Slightly dry - needs irrigation attention",
        actions: [
          "Verify sprinkler schedules for balanced watering.",
          "Apply light nitrogen feed if crop is in seedling phase.",
          "Monitor leaves for discoloration indicating root rot."
        ]
      };
    } else if (ndvi < 0.55) {
      return {
        status: "Healthy / Vegetative Growth",
        color: "text-yellow-600 bg-yellow-50/50 border-yellow-100/50",
        progressBar: "bg-yellow-500",
        percentage: 72,
        pestRisk: "Low (Pest vectors monitored)",
        waterIndex: "Optimal moisture balance",
        actions: [
          "Maintain standard watering cycles.",
          "Scout boundaries for initial insect larvae signs.",
          "Record crop height and density logs."
        ]
      };
    } else {
      return {
        status: "Peak Vigour / Optimal Health",
        color: "text-green-600 bg-green-50 border-green-100",
        progressBar: "bg-green-600",
        percentage: 95,
        pestRisk: "Very Low",
        waterIndex: "Perfect moisture retention",
        actions: [
          "Evaluate harvest timelines in crop logs.",
          "No immediate actions needed. Canopy health is fully stabilized."
        ]
      };
    }
  };

  const insights = getInsights(satellite?.ndvi);

  return (
    <div className="flex flex-col gap-8 w-full max-w-[1600px] mx-auto pb-20">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-4xl font-semibold tracking-tight text-foreground flex items-center gap-3">
            <Activity className="h-10 w-10 text-green-600" strokeWidth={1.5} />
            Crop Health Diagnostics
          </h1>
          <p className="text-muted-foreground text-lg font-light mt-1">
            Visualise anomalies, plant water stress, and crop protection advisories.
          </p>
        </div>

        {/* Dropdown selector */}
        {farms.length > 0 && (
          <div className="flex items-center gap-3 bg-white border border-border px-5 py-3 rounded-full shadow-sm w-full md:w-80">
            <span className="text-sm font-medium text-slate-500 flex-shrink-0">Select Farm:</span>
            <Select value={selectedFarmId} onValueChange={(id) => setSelectedFarmId(id)}>
              <SelectTrigger className="border-0 bg-transparent focus:ring-0 focus:ring-offset-0 font-semibold text-slate-700 h-6 p-0 text-sm">
                <SelectValue placeholder="Choose a farm" />
              </SelectTrigger>
              <SelectContent className="rounded-2xl border-slate-200">
                {farms.map(f => (
                  <SelectItem key={f.farm_id} value={f.farm_id} className="rounded-xl">
                    {f.name} ({f.area_acres?.toFixed(1) || 0} ac)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {loading ? (
        <div className="h-64 flex flex-col items-center justify-center gap-4 text-slate-500">
          <motion.div 
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
            className="h-6 w-6 border-2 border-green-500 border-t-transparent rounded-full"
          />
        </div>
      ) : farms.length === 0 ? (
        <Card className="border-0 shadow-md bg-white rounded-[32px] p-12 text-center max-w-md mx-auto mt-10">
          <HelpCircle className="h-16 w-16 text-slate-300 mx-auto mb-4" strokeWidth={1.5} />
          <h3 className="text-xl font-bold mb-2">No Farms Saved</h3>
          <p className="text-sm text-muted-foreground font-light mb-6">
            You must register and map your farm boundaries before loading diagnostic recommendations.
          </p>
          <Button asChild className="rounded-full bg-green-600 hover:bg-green-700 text-white font-semibold">
            <Link to="/dashboard/field-mapping">Map a Farm</Link>
          </Button>
        </Card>
      ) : satellite ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* LEFT DIAGNOSTICS CARD */}
          <div className="lg:col-span-8 space-y-6">
            
            {/* Status card */}
            <Card className={`border-0 shadow-lg rounded-[32px] overflow-hidden ${insights?.color} border`}>
              <CardHeader className="pb-4">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-mono uppercase bg-white/80 border border-current px-3 py-1 rounded-full font-bold">
                    Diagnostic Summary
                  </span>
                  <span className="text-xs text-muted-foreground">Reading Date: {satellite.captured_at}</span>
                </div>
                <CardTitle className="text-3xl font-bold mt-4 flex items-center gap-3">
                  <Heart className="h-8 w-8 text-current fill-current animate-pulse" />
                  {insights?.status}
                </CardTitle>
                <CardDescription className="text-slate-600 font-light mt-1">
                  NDVI reading of <strong>{(satellite.ndvi || 0).toFixed(3)}</strong> represents a vegetation rating of <strong>{satellite.vegetation_index}%</strong> of peak capability.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-2">
                <div className="space-y-2">
                  <div className="flex justify-between text-xs font-medium text-slate-700">
                    <span>Index Rating</span>
                    <span>{satellite.vegetation_index}%</span>
                  </div>
                  <Progress value={Math.min(Math.max(satellite.vegetation_index || 0, 0), 100)} className={`h-3 rounded-full bg-slate-100 ${insights?.progressBar}`} />
                </div>
              </CardContent>
            </Card>

            {/* Health parameters */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              <Card className="border-0 shadow-md bg-white rounded-[24px] p-6">
                <CardHeader className="p-0 pb-4">
                  <CardTitle className="text-sm font-semibold uppercase tracking-widest text-slate-400 flex items-center gap-2">
                    <Droplets className="h-4.5 w-4.5 text-blue-500" /> Plant Water Index
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <p className="text-lg font-bold text-slate-800">{insights?.waterIndex}</p>
                  <p className="text-xs text-muted-foreground font-light mt-1.5 leading-relaxed">
                    Evaluates leaf water thickness and irrigation sufficiency computed from Sentinel reflection parameters.
                  </p>
                </CardContent>
              </Card>

              <Card className="border-0 shadow-md bg-white rounded-[24px] p-6">
                <CardHeader className="p-0 pb-4">
                  <CardTitle className="text-sm font-semibold uppercase tracking-widest text-slate-400 flex items-center gap-2">
                    <Flame className="h-4.5 w-4.5 text-orange-500" /> Pest & Disease Vulnerability
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <p className="text-lg font-bold text-slate-800">{insights?.pestRisk}</p>
                  <p className="text-xs text-muted-foreground font-light mt-1.5 leading-relaxed">
                    Under-vegetated or stressed patches present higher vulnerability profiles for pathogen proliferation.
                  </p>
                </CardContent>
              </Card>

            </div>

            {/* Advisory actions card */}
            <Card className="border-0 shadow-lg bg-white rounded-[32px] p-8">
              <h3 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-green-600" strokeWidth={1.5} />
                Actionable AI Agronomist Advisor
              </h3>
              <div className="space-y-4">
                {insights?.actions.map((act, idx) => (
                  <div key={idx} className="flex gap-4 p-4 bg-slate-50/50 rounded-2xl border border-slate-100">
                    <div className="h-7 w-7 rounded-full bg-green-100 flex items-center justify-center text-green-700 font-bold font-mono text-xs flex-shrink-0">
                      {idx + 1}
                    </div>
                    <p className="text-sm font-light text-slate-700 leading-relaxed">{act}</p>
                  </div>
                ))}
              </div>
            </Card>

          </div>

          {/* RIGHT COL: Guidelines & Farm Stats */}
          <div className="lg:col-span-4 space-y-6">
            <Card className="border-0 shadow-lg bg-white rounded-[32px] p-6">
              <CardHeader className="p-0 pb-4">
                <CardTitle className="text-lg font-semibold text-slate-800">Diagnostic Details</CardTitle>
              </CardHeader>
              <CardContent className="p-0 space-y-5">
                <div className="flex justify-between items-center text-sm py-2.5 border-b border-slate-100">
                  <span className="text-slate-400 font-light">Farm Name</span>
                  <span className="font-semibold text-slate-800">{selectedFarm.name}</span>
                </div>
                <div className="flex justify-between items-center text-sm py-2.5 border-b border-slate-100">
                  <span className="text-slate-400 font-light">Area Size</span>
                  <span className="font-semibold text-slate-800">{selectedFarm.area_acres?.toFixed(1) || 0} Acres</span>
                </div>
                <div className="flex justify-between items-center text-sm py-2.5 border-b border-slate-100">
                  <span className="text-slate-400 font-light">Satellite Sensor</span>
                  <span className="font-semibold text-slate-800">Sentinel-2 SR</span>
                </div>
                <div className="flex justify-between items-center text-sm py-2.5">
                  <span className="text-slate-400 font-light">Last Check</span>
                  <span className="font-semibold text-slate-800">{satellite.captured_at}</span>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-md bg-white rounded-[24px] p-6 space-y-4">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                <AlertTriangle className="h-4.5 w-4.5 text-yellow-500" /> Disclaimer
              </h4>
              <p className="text-xs text-slate-500 font-light leading-relaxed">
                Satellite data serves as an estimation tool based on optical spectral wavelengths. It should be cross-verified in person with direct soil/leaf inspection before enacting chemical weed or pest applications.
              </p>
            </Card>
          </div>

        </div>
      ) : (
        <Card className="border-0 shadow-md bg-white rounded-[32px] p-12 text-center max-w-md mx-auto mt-10">
          <Info className="h-16 w-16 text-slate-300 mx-auto mb-4" strokeWidth={1.5} />
          <h3 className="text-xl font-bold mb-2">No Diagnostic Data</h3>
          <p className="text-sm text-muted-foreground font-light mb-6">
            This farm hasn't been analyzed on the satellite server yet.
          </p>
          <Button asChild className="rounded-full bg-green-600 hover:bg-green-700 text-white font-semibold">
            <Link to={`/dashboard/satellite-analysis?field_id=${selectedFarmId}`}>Run Satellite Scan</Link>
          </Button>
        </Card>
      )}

    </div>
  );
}
