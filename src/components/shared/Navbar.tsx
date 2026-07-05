import { Link } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Menu, Sprout, Globe } from 'lucide-react';

export function Navbar() {
  const { user, language, setLanguage } = useAppStore();

  const toggleLanguage = () => {
    const langs = ['en', 'hi', 'te', 'ta'];
    const nextIdx = (langs.indexOf(language) + 1) % langs.length;
    setLanguage(langs[nextIdx]);
  };

  const NavLinks = () => (
    <>
      <Link to="/" className="text-sm font-medium transition-colors hover:text-primary">Home</Link>
      <Link to="/features" className="text-sm font-medium transition-colors hover:text-primary">Features</Link>
      {user && <Link to="/dashboard" className="text-sm font-medium transition-colors hover:text-primary">Dashboard</Link>}
      <Link to="/about" className="text-sm font-medium transition-colors hover:text-primary">About</Link>
      <Link to="/contact" className="text-sm font-medium transition-colors hover:text-primary">Contact</Link>
    </>
  );

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-2">
          <Link to="/" className="flex items-center space-x-2">
            <div className="bg-primary/10 p-2 rounded-lg">
              <Sprout className="h-6 w-6 text-primary" />
            </div>
            <span className="font-bold text-xl tracking-tight hidden sm:inline-block">
              KrishiMitra AI
            </span>
          </Link>
        </div>

        <nav className="hidden md:flex items-center gap-6">
          <NavLinks />
        </nav>

        <div className="flex items-center gap-2 sm:gap-4">
          <Button variant="ghost" size="icon" onClick={toggleLanguage} title="Change Language">
            <Globe className="h-5 w-5" />
            <span className="sr-only">Toggle language</span>
          </Button>

          {user ? (
            <div className="hidden sm:flex items-center gap-2">
              <span className="text-sm text-muted-foreground mr-2">Hello, {user.name}</span>
              <Button asChild variant="outline">
                <Link to="/dashboard">Dashboard</Link>
              </Button>
            </div>
          ) : (
            <div className="hidden sm:flex items-center gap-2">
              <Button variant="ghost" asChild>
                <Link to="/login">Login</Link>
              </Button>
              <Button asChild>
                <Link to="/register">Register</Link>
              </Button>
            </div>
          )}

          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle Menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="right">
              <div className="flex flex-col gap-6 mt-8">
                <NavLinks />
                <hr className="my-2" />
                {user ? (
                  <Button asChild className="w-full">
                    <Link to="/dashboard">Dashboard</Link>
                  </Button>
                ) : (
                  <div className="flex flex-col gap-2">
                    <Button variant="outline" asChild className="w-full">
                      <Link to="/login">Login</Link>
                    </Button>
                    <Button asChild className="w-full">
                      <Link to="/register">Register</Link>
                    </Button>
                  </div>
                )}
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
