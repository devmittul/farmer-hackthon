import { Outlet } from 'react-router-dom';
import { Navbar } from '@/components/shared/Navbar';
import { Footer } from '@/components/shared/Footer';
import { Toaster } from '@/components/ui/toaster';

export function MainLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1 bg-farm-pattern">
        <Outlet />
      </main>
      <Footer />
      <Toaster />
    </div>
  );
}
