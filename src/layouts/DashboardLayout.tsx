import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { 
  Sprout, LayoutDashboard, Leaf, Droplet, 
  Stethoscope, FileText, Settings, LogOut, Menu, UserCircle, Bell
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Toaster } from '@/components/ui/toaster';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Crop Recommendation', href: '/dashboard/crop', icon: Leaf },
  { name: 'Irrigation Advisory', href: '/dashboard/irrigation', icon: Droplet },
  { name: 'Disease Diagnosis', href: '/dashboard/disease', icon: Stethoscope },
  { name: 'Reports', href: '/dashboard/reports', icon: FileText },
];

function Sidebar({ pathname }: { pathname: string }) {
  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex h-14 items-center border-b px-4 lg:h-[60px] lg:px-6">
        <Link to="/" className="flex items-center gap-2 font-semibold">
          <div className="bg-primary/10 p-1.5 rounded-lg">
            <Sprout className="h-5 w-5 text-primary" />
          </div>
          <span className="text-lg">KrishiMitra AI</span>
        </Link>
      </div>
      <div className="flex-1 overflow-auto py-2">
        <nav className="grid items-start px-2 text-sm font-medium lg:px-4 gap-1">
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all hover:bg-muted",
                  isActive ? "bg-muted text-primary" : "text-muted-foreground"
                )}
              >
                <item.icon className={cn("h-4 w-4", isActive ? "text-primary" : "")} />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="mt-auto p-4 border-t">
        <nav className="grid gap-1 text-sm font-medium">
          <Link
            to="/dashboard/profile"
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-muted-foreground transition-all hover:bg-muted"
          >
            <Settings className="h-4 w-4" />
            Settings
          </Link>
          <Link
            to="/"
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-destructive transition-all hover:bg-muted"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </Link>
        </nav>
      </div>
    </div>
  );
}

export function DashboardLayout() {
  const { user } = useAppStore();
  const location = useLocation();

  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <div className="hidden border-r bg-muted/20 md:block">
        <Sidebar pathname={location.pathname} />
      </div>
      <div className="flex flex-col">
        <header className="flex h-14 items-center gap-4 border-b bg-muted/20 px-4 lg:h-[60px] lg:px-6">
          <Sheet>
            <SheetTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                className="shrink-0 md:hidden"
              >
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle navigation menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[280px] p-0">
              <Sidebar pathname={location.pathname} />
            </SheetContent>
          </Sheet>
          
          <div className="w-full flex-1">
            {/* Can add search here if needed */}
          </div>
          <div className="flex items-center gap-4">
            <Button variant="outline" size="icon" className="relative">
              <Bell className="h-4 w-4" />
              <Badge className="absolute -right-1 -top-1 h-4 w-4 p-0 flex justify-center items-center rounded-full bg-destructive text-[10px]">3</Badge>
              <span className="sr-only">Toggle notifications</span>
            </Button>
            <Link to="/dashboard/profile" className="flex items-center gap-2">
              <UserCircle className="h-8 w-8 text-muted-foreground" />
              <span className="text-sm font-medium hidden sm:inline-block">
                {user?.name || 'Farmer'}
              </span>
            </Link>
          </div>
        </header>
        <main className="flex-1 flex flex-col gap-4 p-4 lg:gap-6 lg:p-8 bg-muted/10">
          <Outlet />
        </main>
      </div>
      <Toaster />
    </div>
  );
}
