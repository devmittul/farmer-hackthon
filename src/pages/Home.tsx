import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  ArrowRight, Sprout, Droplets, Stethoscope, 
  TrendingUp, ShieldCheck, Languages, Zap
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';

export default function Home() {
  return (
    <div className="flex flex-col">
      {/* Hero Section */}
      <section className="relative pt-24 pb-32 overflow-hidden flex items-center justify-center min-h-[80vh]">
        <div className="absolute inset-0 z-0 opacity-10 bg-[url('https://images.unsplash.com/photo-1625246333195-78d9c38ad449?q=80&w=2070')] bg-cover bg-center" />
        <div className="absolute inset-0 bg-gradient-to-b from-background/50 to-background/95 z-0" />
        
        <div className="container relative z-10 px-4 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="inline-flex items-center rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-sm font-medium text-primary mb-6">
              <Sprout className="mr-2 h-4 w-4" />
              Smart Farming for Everyone
            </div>
            <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight text-foreground max-w-4xl mx-auto mb-6">
              AI-Powered <span className="text-primary">Smart Farming</span> for Every Farmer
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
              Leverage satellite intelligence, weather forecasting, and AI diagnosis to increase your yield and reduce risks, all in your local language.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" asChild className="rounded-full px-8 h-12 text-md">
                <Link to="/register">
                  Start Now <ArrowRight className="ml-2 h-5 w-5" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" className="rounded-full px-8 h-12 text-md bg-background/50 backdrop-blur">
                Watch Demo
              </Button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Statistics Section */}
      <section className="py-12 bg-primary/5">
        <div className="container px-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
            {[
              { value: "50,000+", label: "Farmers Supported" },
              { value: "1.2M", label: "Acres Monitored" },
              { value: "85%", label: "Disease Accuracy" },
              { value: "30%", label: "Water Saved" },
            ].map((stat, i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="p-6 rounded-2xl bg-background shadow-sm border border-border/50"
              >
                <div className="text-3xl md:text-4xl font-bold text-primary mb-2">{stat.value}</div>
                <div className="text-sm font-medium text-muted-foreground">{stat.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Overview */}
      <section className="py-24 container px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">Powerful Features</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">Everything you need to manage your farm efficiently and profitably.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {[
            {
              icon: <Sprout className="h-10 w-10 text-primary" />,
              title: "Smart Crop Recommendation",
              desc: "Get personalized crop suggestions based on your soil type, season, and real-time weather data to maximize yield."
            },
            {
              icon: <Droplets className="h-10 w-10 text-accent" />,
              title: "Smart Irrigation Advisory",
              desc: "Save water and improve crop health with AI-driven irrigation schedules based on soil moisture and weather forecasts."
            },
            {
              icon: <Stethoscope className="h-10 w-10 text-destructive" />,
              title: "Crop Disease Detection",
              desc: "Simply upload a photo of your crop to instantly identify diseases and get expert treatment recommendations."
            }
          ].map((feature, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="h-full hover:shadow-lg transition-shadow border-border/50 bg-card/50 backdrop-blur">
                <CardContent className="p-8 flex flex-col items-center text-center">
                  <div className="mb-6 p-4 rounded-full bg-background shadow-sm">
                    {feature.icon}
                  </div>
                  <h3 className="text-xl font-bold mb-3">{feature.title}</h3>
                  <p className="text-muted-foreground leading-relaxed">{feature.desc}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How it Works */}
      <section className="py-24 bg-muted/30">
        <div className="container px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">How It Works</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">Four simple steps to transform your farming experience.</p>
          </div>

          <div className="grid md:grid-cols-4 gap-8 relative">
            <div className="hidden md:block absolute top-1/2 left-0 right-0 h-0.5 bg-border -z-10 transform -translate-y-1/2" />
            {[
              { step: 1, title: "Register Farm", desc: "Enter your location and farm details." },
              { step: 2, title: "AI Collects Data", desc: "System fetches weather & soil data." },
              { step: 3, title: "Analysis", desc: "AI models process the information." },
              { step: 4, title: "Get Guidance", desc: "Receive actionable recommendations." }
            ].map((item, i) => (
              <div key={i} className="flex flex-col items-center text-center">
                <div className="w-12 h-12 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold text-xl mb-4 shadow-md ring-4 ring-background">
                  {item.step}
                </div>
                <h3 className="font-bold text-lg mb-2">{item.title}</h3>
                <p className="text-muted-foreground text-sm">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="py-24 container px-4">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="text-3xl md:text-4xl font-bold mb-6">Why Choose KrishiMitra AI?</h2>
            <p className="text-muted-foreground mb-8 text-lg">
              Designed specifically for small and marginal farmers, our platform breaks down complex agricultural science into easy-to-understand, actionable advice.
            </p>
            <div className="grid sm:grid-cols-2 gap-4">
              {[
                { icon: TrendingUp, text: "Increase Yield" },
                { icon: Droplets, text: "Save Water" },
                { icon: ShieldCheck, text: "Reduce Crop Loss" },
                { icon: Zap, text: "AI Assistance" },
                { icon: Languages, text: "Local Language Support" },
                { icon: Stethoscope, text: "Photo Diagnosis" },
              ].map((benefit, i) => (
                <div key={i} className="flex items-center gap-3 bg-muted/50 p-3 rounded-lg">
                  <benefit.icon className="h-5 w-5 text-primary" />
                  <span className="font-medium text-sm">{benefit.text}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-tr from-primary/20 to-transparent rounded-3xl transform translate-x-4 translate-y-4" />
            <img 
              src="https://images.unsplash.com/photo-1592982537447-6f2a6a0b94cb?q=80&w=2070" 
              alt="Farmer using smartphone" 
              className="rounded-3xl shadow-xl relative z-10 object-cover aspect-square md:aspect-[4/3]"
            />
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-24 bg-muted/30">
        <div className="container px-4 max-w-3xl">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">Frequently Asked Questions</h2>
          </div>
          <Accordion type="single" collapsible className="w-full">
            <AccordionItem value="item-1" className="bg-background mb-4 px-6 rounded-lg border">
              <AccordionTrigger className="hover:no-underline font-semibold">Is the platform free to use?</AccordionTrigger>
              <AccordionContent className="text-muted-foreground">
                Yes, the core features of KrishiMitra AI are completely free for small and marginal farmers. We believe in democratizing agricultural intelligence.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-2" className="bg-background mb-4 px-6 rounded-lg border">
              <AccordionTrigger className="hover:no-underline font-semibold">Do I need an internet connection?</AccordionTrigger>
              <AccordionContent className="text-muted-foreground">
                An internet connection is required to fetch real-time weather and AI predictions. However, you can receive critical updates via our SMS service even without a smartphone.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-3" className="bg-background mb-4 px-6 rounded-lg border">
              <AccordionTrigger className="hover:no-underline font-semibold">Which languages are supported?</AccordionTrigger>
              <AccordionContent className="text-muted-foreground">
                Currently, we support English, Hindi, Telugu, Tamil, and Marathi. We are constantly working to add more regional languages.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </section>
    </div>
  );
}
