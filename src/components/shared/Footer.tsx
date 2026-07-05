import { Link } from 'react-router-dom';
import { Sprout, Share2, Globe, Mail, Phone, MapPin } from 'lucide-react';

export function Footer() {
  return (
    <footer className="bg-foreground text-background py-12">
      <div className="container mx-auto px-4 grid grid-cols-1 md:grid-cols-4 gap-8">
        <div className="space-y-4">
          <Link to="/" className="flex items-center space-x-2">
            <Sprout className="h-6 w-6 text-primary" />
            <span className="font-bold text-xl">KrishiMitra AI</span>
          </Link>
          <p className="text-muted-foreground text-sm">
            Empowering small and marginal farmers with AI-driven intelligence, localized insights, and modern agricultural solutions.
          </p>
          <div className="flex gap-4 pt-2">
            <Globe className="h-5 w-5 text-muted-foreground hover:text-primary cursor-pointer transition-colors" />
            <Share2 className="h-5 w-5 text-muted-foreground hover:text-primary cursor-pointer transition-colors" />
          </div>
        </div>

        <div>
          <h3 className="font-semibold text-lg mb-4">Quick Links</h3>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li><Link to="/about" className="hover:text-primary transition-colors">About Us</Link></li>
            <li><Link to="/features" className="hover:text-primary transition-colors">Features</Link></li>
            <li><Link to="/impact" className="hover:text-primary transition-colors">Our Impact</Link></li>
            <li><Link to="/contact" className="hover:text-primary transition-colors">Contact</Link></li>
          </ul>
        </div>

        <div>
          <h3 className="font-semibold text-lg mb-4">Services</h3>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li><Link to="/crop-recommendation" className="hover:text-primary transition-colors">Crop Recommendation</Link></li>
            <li><Link to="/irrigation" className="hover:text-primary transition-colors">Smart Irrigation</Link></li>
            <li><Link to="/disease-diagnosis" className="hover:text-primary transition-colors">Disease Diagnosis</Link></li>
            <li><Link to="/market-prices" className="hover:text-primary transition-colors">Market Prices</Link></li>
          </ul>
        </div>

        <div>
          <h3 className="font-semibold text-lg mb-4">Contact Us</h3>
          <ul className="space-y-3 text-sm text-muted-foreground">
            <li className="flex items-start gap-3">
              <MapPin className="h-5 w-5 text-primary shrink-0" />
              <span>Agri-Tech Park, Sector 42, New Delhi, India 110001</span>
            </li>
            <li className="flex items-center gap-3">
              <Phone className="h-5 w-5 text-primary shrink-0" />
              <span>+91 1800 123 4567 (Toll Free)</span>
            </li>
            <li className="flex items-center gap-3">
              <Mail className="h-5 w-5 text-primary shrink-0" />
              <span>support@krishimitra.ai</span>
            </li>
          </ul>
        </div>
      </div>
      <div className="container mx-auto px-4 mt-12 pt-8 border-t border-muted-foreground/20 text-center text-sm text-muted-foreground flex flex-col md:flex-row justify-between items-center gap-4">
        <p>© {new Date().getFullYear()} KrishiMitra AI. All rights reserved.</p>
        <div className="flex gap-4">
          <Link to="/privacy" className="hover:text-primary transition-colors">Privacy Policy</Link>
          <Link to="/terms" className="hover:text-primary transition-colors">Terms of Service</Link>
        </div>
      </div>
    </footer>
  );
}
