import { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Stethoscope, UploadCloud, Camera, Mic, CheckCircle2, AlertTriangle, AlertOctagon } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { api } from '@/services/api';

export default function DiseaseDiagnosis() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setPreviewUrl(URL.createObjectURL(selectedFile));
      setResult(null);
    }
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setAnalyzing(true);
    setProgress(0);
    
    // Simulate progress
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 95) {
          clearInterval(interval);
          return 95;
        }
        return prev + 5;
      });
    }, 100);

    const data = await api.diagnoseDisease(file, null);
    
    clearInterval(interval);
    setProgress(100);
    setTimeout(() => {
      setResult(data);
      setAnalyzing(false);
    }, 500);
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'low': return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case 'medium': return <AlertTriangle className="h-5 w-5 text-orange-500" />;
      case 'high': return <AlertOctagon className="h-5 w-5 text-red-500" />;
      default: return null;
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-2">
        <div className="bg-red-100 p-2 rounded-lg dark:bg-red-900/30">
          <Stethoscope className="h-6 w-6 text-red-600 dark:text-red-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Crop Disease Diagnosis</h1>
          <p className="text-muted-foreground">Upload a photo of your crop to instantly identify diseases.</p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Provide Input</CardTitle>
            <CardDescription>Upload an image or record a voice description.</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="image" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="image">Upload Image</TabsTrigger>
                <TabsTrigger value="voice">Voice Assist</TabsTrigger>
              </TabsList>
              
              <TabsContent value="image" className="space-y-4 pt-4">
                <div 
                  className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center transition-colors ${previewUrl ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}`}
                  onClick={() => fileInputRef.current?.click()}
                  style={{ cursor: 'pointer' }}
                >
                  <input 
                    type="file" 
                    className="hidden" 
                    ref={fileInputRef} 
                    accept="image/*"
                    onChange={handleFileChange}
                  />
                  
                  {previewUrl ? (
                    <div className="relative w-full aspect-video rounded-lg overflow-hidden mb-4">
                      <img src={previewUrl} alt="Preview" className="object-cover w-full h-full" />
                    </div>
                  ) : (
                    <>
                      <div className="bg-muted p-4 rounded-full mb-4">
                        <UploadCloud className="h-8 w-8 text-muted-foreground" />
                      </div>
                      <h3 className="font-semibold mb-1">Click to upload or drag and drop</h3>
                      <p className="text-sm text-muted-foreground">JPG, PNG or WEBP (max. 5MB)</p>
                    </>
                  )}
                  
                  <div className="flex gap-2 mt-4">
                    <Button variant="outline" type="button" onClick={(e: React.MouseEvent) => { e.stopPropagation(); fileInputRef.current?.click(); }}>
                      <UploadCloud className="mr-2 h-4 w-4" /> Browse
                    </Button>
                    <Button variant="outline" type="button" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
                      <Camera className="mr-2 h-4 w-4" /> Camera
                    </Button>
                  </div>
                </div>

                <Button 
                  className="w-full" 
                  size="lg" 
                  disabled={!file || analyzing}
                  onClick={handleAnalyze}
                >
                  {analyzing ? 'Analyzing Image...' : 'Diagnose Disease'}
                </Button>
                
                {analyzing && (
                  <div className="space-y-2 mt-4">
                    <div className="flex justify-between text-sm">
                      <span>Processing image with AI...</span>
                      <span>{progress}%</span>
                    </div>
                    <Progress value={progress} className="h-2" />
                  </div>
                )}
              </TabsContent>
              
              <TabsContent value="voice" className="pt-4">
                <div className="border rounded-xl p-8 flex flex-col items-center justify-center text-center bg-muted/30">
                  <div className="w-24 h-24 rounded-full bg-primary/10 flex items-center justify-center mb-6 cursor-pointer hover:bg-primary/20 transition-colors group">
                    <Mic className="h-10 w-10 text-primary group-hover:scale-110 transition-transform" />
                  </div>
                  <h3 className="font-semibold text-lg mb-2">Tap to Speak</h3>
                  <p className="text-muted-foreground max-w-sm">
                    Describe the symptoms you are seeing on your crops in your local language.
                  </p>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <div>
          {!result ? (
            <Card className="h-full flex flex-col items-center justify-center text-center p-6 bg-muted/30 border-dashed">
              <Stethoscope className="h-12 w-12 text-muted-foreground mb-4 opacity-50" />
              <h3 className="text-xl font-medium text-muted-foreground mb-2">No Analysis Yet</h3>
              <p className="text-sm text-muted-foreground max-w-xs">
                Upload an image or record a voice description to get AI-powered diagnosis.
              </p>
            </Card>
          ) : (
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
              <Card className="border-t-4 border-t-red-500 overflow-hidden relative shadow-md">
                <div className="absolute top-4 right-4 bg-muted px-2 py-1 rounded text-xs font-medium flex items-center gap-1">
                  Confidence: <span className="text-primary font-bold">{result.confidence}%</span>
                </div>
                <CardHeader>
                  <CardTitle className="text-2xl">{result.disease}</CardTitle>
                  <CardDescription className="flex items-center gap-2 mt-1">
                    Severity: 
                    <span className="flex items-center gap-1 font-medium text-foreground">
                      {getSeverityIcon(result.severity)} {result.severity}
                    </span>
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div>
                    <h4 className="font-semibold mb-2 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-orange-500" /> Symptoms Detected
                    </h4>
                    <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                      {result.symptoms.map((s: string, i: number) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>
                  
                  <div className="bg-green-50 dark:bg-green-950/30 p-4 rounded-lg border border-green-200 dark:border-green-900">
                    <h4 className="font-semibold mb-2 flex items-center gap-2 text-green-800 dark:text-green-400">
                      <CheckCircle2 className="h-4 w-4" /> Recommended Treatment
                    </h4>
                    <ul className="list-disc list-inside text-sm text-green-700 dark:text-green-500 space-y-1">
                      {result.treatment.map((t: string, i: number) => <li key={i}>{t}</li>)}
                    </ul>
                  </div>

                  <div>
                    <h4 className="font-semibold mb-2 text-sm">Prevention</h4>
                    <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                      {result.prevention.map((p: string, i: number) => <li key={i}>{p}</li>)}
                    </ul>
                  </div>

                  {result.severity.toLowerCase() === 'high' && (
                    <Button variant="destructive" className="w-full">
                      Contact Agriculture Expert Now
                    </Button>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
