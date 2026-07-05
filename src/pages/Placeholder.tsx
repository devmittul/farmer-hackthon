import { Link, useLocation } from 'react-router-dom';
import { ArrowLeft, Construction } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function Placeholder() {
  const location = useLocation();
  const pageName = location.pathname.split('/').filter(Boolean).pop() || 'Page';
  const capitalizedName = pageName.charAt(0).toUpperCase() + pageName.slice(1);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="bg-primary/10 p-4 rounded-full mb-6">
        <Construction className="h-12 w-12 text-primary" />
      </div>
      <h1 className="text-3xl font-bold mb-4">{capitalizedName} Page</h1>
      <p className="text-muted-foreground max-w-md mb-8">
        This section is currently under construction for the hackathon demo. Please check back later.
      </p>
      <Button asChild>
        <Link to="/">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Home
        </Link>
      </Button>
    </div>
  );
}
