import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Leaf, Eye, EyeOff, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAppStore } from '@/store/useAppStore';

export default function Register() {
  const navigate = useNavigate();
  const { register, authLoading, authError, clearError } = useAppStore();
  const [showPass, setShowPass] = useState(false);
  const [form, setForm] = useState({
    name: '', email: '', phone: '', password: '',
    location: '', farm_size_acres: '', language: 'en',
  });

  const set = (key: string, val: string) => setForm(f => ({ ...f, [key]: val }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    try {
      await register({
        name: form.name,
        email: form.email,
        phone: form.phone,
        password: form.password,
        location: form.location || undefined,
        farm_size_acres: form.farm_size_acres ? Number(form.farm_size_acres) : undefined,
      });
      navigate('/dashboard');
    } catch {
      // Error shown from store
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-emerald-100 dark:from-green-950 dark:to-emerald-950 p-4">
      <Card className="w-full max-w-lg shadow-xl">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="bg-green-600 p-3 rounded-2xl">
              <Leaf className="h-8 w-8 text-white" />
            </div>
          </div>
          <CardTitle className="text-2xl">Create Account</CardTitle>
          <CardDescription>Join KrishiMitra AI — free for all farmers</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 space-y-2">
                <Label htmlFor="name">Full Name</Label>
                <Input id="name" required value={form.name} onChange={e => set('name', e.target.value)} placeholder="Ramesh Kumar" />
              </div>

              <div className="space-y-2">
                <Label htmlFor="reg-email">Email</Label>
                <Input id="reg-email" type="email" required value={form.email} onChange={e => set('email', e.target.value)} placeholder="farmer@example.com" />
              </div>

              <div className="space-y-2">
                <Label htmlFor="phone">Phone</Label>
                <Input id="phone" required value={form.phone} onChange={e => set('phone', e.target.value)} placeholder="+919876543210" />
              </div>

              <div className="col-span-2 space-y-2">
                <Label htmlFor="reg-password">Password</Label>
                <div className="relative">
                  <Input
                    id="reg-password" type={showPass ? 'text' : 'password'} required
                    value={form.password} onChange={e => set('password', e.target.value)}
                    placeholder="Min 8 chars, 1 uppercase, 1 number"
                  />
                  <Button type="button" variant="ghost" size="icon" className="absolute right-0 top-0 h-full" onClick={() => setShowPass(s => !s)}>
                    {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="location">Location (optional)</Label>
                <div className="flex gap-2">
                  <Input id="location" value={form.location} onChange={e => set('location', e.target.value)} placeholder="Punjab, India" />
                  <Button type="button" variant="outline" size="sm" onClick={() => {
                    if (navigator.geolocation) {
                      navigator.geolocation.getCurrentPosition(async (pos) => {
                        const lat = pos.coords.latitude;
                        const lon = pos.coords.longitude;
                        try {
                          const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
                          const data = await res.json();
                          const placeName = data.address.city || data.address.town || data.address.village || data.address.county || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
                          const stateName = data.address.state || '';
                          set('location', stateName ? `${placeName}, ${stateName}` : placeName);
                        } catch (e) {
                          set('location', `${lat.toFixed(4)}, ${lon.toFixed(4)}`);
                        }
                      });
                    }
                  }}>
                    Sync Location
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="farm_size">Farm Size in Acres (optional)</Label>
                <Input id="farm_size" type="number" step="0.1" value={form.farm_size_acres} onChange={e => set('farm_size_acres', e.target.value)} placeholder="e.g. 2.5" />
              </div>

              <div className="col-span-2 space-y-2">
                <Label>Preferred Language</Label>
                <Select value={form.language} onValueChange={v => set('language', v)}>
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

            {authError && (
              <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-lg">
                {authError}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={authLoading}>
              {authLoading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Creating account...</> : 'Create Account'}
            </Button>

            <p className="text-center text-sm text-muted-foreground">
              Already have an account?{' '}
              <Link to="/login" className="text-primary font-medium hover:underline">Sign in</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
