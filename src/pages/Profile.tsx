import { Globe, Settings, Bell } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAppStore } from '@/store/useAppStore';

export default function Profile() {
  const { user, language, setLanguage } = useAppStore();

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-2">
        <div className="bg-primary/10 p-2 rounded-lg">
          <Settings className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Account Settings</h1>
          <p className="text-muted-foreground">Manage your profile and platform preferences.</p>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Farmer Profile</CardTitle>
              <CardDescription>Update your personal and farm information.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Full Name</Label>
                  <Input defaultValue={user?.name} />
                </div>
                <div className="space-y-2">
                  <Label>Phone Number</Label>
                  <Input defaultValue="+91 9876543210" />
                </div>
                <div className="space-y-2">
                  <Label>Farm Size (Acres)</Label>
                  <Input type="number" defaultValue={user?.farmSize} />
                </div>
                <div className="space-y-2">
                  <Label>Village/District</Label>
                  <Input defaultValue={user?.location} />
                </div>
              </div>
              <Button className="mt-4">Save Changes</Button>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Preferences</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Globe className="h-4 w-4 text-muted-foreground" />
                  Language
                </Label>
                <Select value={language} onValueChange={setLanguage}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select Language" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="hi">Hindi (हिंदी)</SelectItem>
                    <SelectItem value="te">Telugu (తెలుగు)</SelectItem>
                    <SelectItem value="ta">Tamil (தமிழ்)</SelectItem>
                    <SelectItem value="mr">Marathi (मराठी)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2 pt-2">
                <Label className="flex items-center gap-2">
                  <Bell className="h-4 w-4 text-muted-foreground" />
                  Alerts
                </Label>
                <div className="flex flex-col gap-2 mt-2">
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" defaultChecked className="rounded border-gray-300 text-primary focus:ring-primary" />
                    SMS Weather Alerts
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" defaultChecked className="rounded border-gray-300 text-primary focus:ring-primary" />
                    Disease Warnings
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" className="rounded border-gray-300 text-primary focus:ring-primary" />
                    Market Price Updates
                  </label>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-destructive/20">
            <CardContent className="pt-6">
              <Button variant="destructive" className="w-full">
                Logout
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
