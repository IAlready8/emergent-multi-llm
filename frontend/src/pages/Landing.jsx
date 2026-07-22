import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Flame, Cpu, Activity, GitBranch, ShieldCheck, Terminal } from "lucide-react";

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 relative overflow-hidden">
      <div className="absolute inset-0 grid-bg opacity-40 pointer-events-none" />
      <div className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full bg-amber-500/5 blur-3xl pointer-events-none" />

      <header className="sticky top-0 z-20 border-b border-white/10 bg-black/60 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="landing-logo">
            <Flame className="w-5 h-5 text-amber-500" />
            <span className="font-semibold tracking-tight">Prometheus</span>
          </Link>
          <nav className="flex items-center gap-4">
            <Link to="/login" className="text-sm text-zinc-400 hover:text-zinc-100" data-testid="landing-login-link">Log in</Link>
            <Link to="/signup"><Button className="bg-amber-500 hover:bg-amber-400 text-black font-semibold" data-testid="landing-signup-btn">Get Started</Button></Link>
          </nav>
        </div>
      </header>

      <section className="relative max-w-6xl mx-auto px-6 pt-24 pb-16">
        <p className="overline text-amber-500 mb-4">MULTI-AGENT ORCHESTRATION</p>
        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05] max-w-4xl">
          Dispatch a <span className="text-amber-500">fleet of AI agents</span>.<br />
          Watch them think in real time.
        </h1>
        <p className="mt-6 text-lg text-zinc-400 max-w-2xl">
          Upload documents, paste data, or design custom workflows. Five specialized agents — Analyzer, Aggregator, AnomalyDetector, Classifier, Synthesizer — stream insights live via GPT-5.2 and Gemini.
        </p>
        <div className="mt-8 flex gap-3">
          <Link to="/signup"><Button size="lg" className="bg-amber-500 hover:bg-amber-400 text-black font-semibold" data-testid="hero-cta">Start free · 10 runs/mo</Button></Link>
          <Link to="/login"><Button size="lg" variant="outline" className="border-white/20 text-zinc-100 hover:bg-zinc-900" data-testid="hero-login">Sign in</Button></Link>
        </div>
      </section>

      <section className="relative max-w-6xl mx-auto px-6 py-16 border-t border-white/10">
        <div className="grid md:grid-cols-3 gap-4">
          {[
            { icon: Cpu, title: "5 Specialized Agents", desc: "Parallel dispatch, sequential chaining, retry & timeout policies per agent." },
            { icon: Activity, title: "Live SSE Streaming", desc: "Watch every token stream from each agent in a split-pane mission-control view." },
            { icon: GitBranch, title: "Custom Workflow Builder", desc: "Compose agent chains. Pick per-agent providers on Enterprise." },
            { icon: Terminal, title: "GPT-5.2 + Gemini 3", desc: "Provider abstraction. Choose per-run on Pro, per-agent on Enterprise." },
            { icon: ShieldCheck, title: "GDPR & OWASP", desc: "Article 17 delete, Article 20 export, security headers, rate limiting." },
            { icon: Flame, title: "JSON + PDF Export", desc: "Structured JSON always. Human-readable PDF reports on Pro & Enterprise." },
          ].map((f, i) => (
            <div key={i} className="p-6 bg-zinc-900/60 border border-white/10 rounded-lg hover:border-amber-500/40 transition-colors" data-testid={`feature-card-${i}`}>
              <f.icon className="w-5 h-5 text-amber-500 mb-4" />
              <h3 className="font-semibold mb-2">{f.title}</h3>
              <p className="text-sm text-zinc-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="relative max-w-6xl mx-auto px-6 py-16 border-t border-white/10">
        <p className="overline text-amber-500 mb-4">PRICING</p>
        <h2 className="text-3xl font-semibold tracking-tight mb-8">Simple tiers. Config-driven quotas.</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {[
            { name: "Free", price: "$0", features: ["10 runs / month", "3 agents (Analyzer, Aggregator, Classifier)", "Gemini only", "5 MB uploads", "JSON export", "7-day history"] },
            { name: "Pro", price: "$29", highlight: true, features: ["500 runs / month", "All 5 agents", "GPT-5.2 or Gemini per run", "50 MB uploads", "JSON + PDF export", "90-day history", "Custom workflows"] },
            { name: "Enterprise", price: "$199", features: ["Unlimited runs (10k soft cap)", "Per-agent provider selection", "500 MB uploads", "Postgres + S3 connectors", "Unlimited history", "Priority support"] },
          ].map((p) => (
            <div key={p.name} className={`p-6 bg-zinc-900/60 border rounded-lg ${p.highlight ? "border-amber-500/60" : "border-white/10"}`} data-testid={`pricing-${p.name.toLowerCase()}`}>
              <div className="flex items-baseline justify-between mb-4">
                <h3 className="font-semibold text-lg">{p.name}</h3>
                <div><span className="text-3xl font-bold text-amber-500">{p.price}</span><span className="text-zinc-500 text-sm">/mo</span></div>
              </div>
              <ul className="space-y-2 text-sm text-zinc-300 mb-6">
                {p.features.map((f, i) => <li key={i} className="flex gap-2"><span className="text-amber-500">›</span>{f}</li>)}
              </ul>
              <Link to="/signup"><Button className={`w-full ${p.highlight ? "bg-amber-500 hover:bg-amber-400 text-black" : "bg-zinc-800 hover:bg-zinc-700 border border-white/10"}`} data-testid={`pricing-cta-${p.name.toLowerCase()}`}>Start with {p.name}</Button></Link>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-white/10 py-8 text-center text-xs text-zinc-500 relative">
        Prometheus · Multi-Agent Orchestration · Powered by GPT-5.2 & Gemini 3
      </footer>
    </div>
  );
}
