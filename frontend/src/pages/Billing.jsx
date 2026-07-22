import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth.jsx";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Check } from "lucide-react";

const PLANS = [
  { tier: "pro", key_month: "pro_monthly", key_year: "pro_annual", price_m: 29, price_y: 290, features: ["500 runs / month", "All 5 agents", "GPT-5.2 + Gemini per run", "50 MB uploads", "JSON + PDF export", "90-day history"] },
  { tier: "enterprise", key_month: "enterprise_monthly", key_year: "enterprise_annual", price_m: 199, price_y: 1990, features: ["Unlimited runs (soft 10k)", "Per-agent provider", "500 MB uploads", "Postgres + S3 connectors", "Unlimited history", "Priority support"] },
];

export default function Billing() {
  const { subscription, tierConfig } = useAuth();
  const [busy, setBusy] = useState(false);
  const [annual, setAnnual] = useState(false);

  const checkout = async (lookup_key) => {
    setBusy(true);
    try {
      const { data } = await api.post("/billing/checkout", { lookup_key, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch (e) { toast.error(e?.response?.data?.detail || "Checkout failed"); setBusy(false); }
  };

  const portal = async () => {
    try {
      const { data } = await api.post("/billing/portal");
      window.location.href = data.url;
    } catch (e) { toast.error(e?.response?.data?.detail || "Portal unavailable"); }
  };

  return (
    <Layout title="Billing">
      <div className="mb-6 p-6 bg-zinc-900/60 border border-white/10 rounded-lg" data-testid="current-plan">
        <div className="overline text-zinc-500 mb-2">CURRENT PLAN</div>
        <div className="flex items-baseline gap-3">
          <div className="text-3xl font-semibold text-amber-500">{subscription?.tier?.toUpperCase()}</div>
          <div className="text-sm text-zinc-400">{subscription?.status}</div>
        </div>
        <div className="text-xs text-zinc-500 mt-2">Runs used: {subscription?.runs_used || 0} {tierConfig?.runs_per_period ? `/ ${tierConfig.runs_per_period}` : ""}</div>
        {subscription?.stripe_customer_id && (
          <Button onClick={portal} className="mt-4 bg-zinc-800 hover:bg-zinc-700 border border-white/10" data-testid="portal-btn">Manage in Stripe portal</Button>
        )}
      </div>

      <div className="flex items-center gap-3 mb-4">
        <span className={annual ? "text-zinc-500" : "text-white"}>Monthly</span>
        <button onClick={() => setAnnual((a) => !a)} className="relative w-11 h-6 bg-zinc-800 rounded-full border border-white/10" data-testid="billing-cycle-toggle">
          <span className={`absolute top-0.5 w-5 h-5 bg-amber-500 rounded-full transition-all ${annual ? "left-5" : "left-0.5"}`} />
        </button>
        <span className={!annual ? "text-zinc-500" : "text-white"}>Annual <span className="text-emerald-500 text-xs">(save ~17%)</span></span>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {PLANS.map((p) => {
          const key = annual ? p.key_year : p.key_month;
          const price = annual ? p.price_y : p.price_m;
          const active = subscription?.tier === p.tier;
          return (
            <div key={p.tier} className={`p-6 bg-zinc-900/60 border rounded-lg ${p.tier === "pro" ? "border-amber-500/50" : "border-white/10"}`} data-testid={`plan-${p.tier}`}>
              <div className="flex items-baseline justify-between mb-4">
                <h3 className="text-xl font-semibold">{p.tier.charAt(0).toUpperCase() + p.tier.slice(1)}</h3>
                <div><span className="text-3xl font-bold text-amber-500">${price}</span><span className="text-zinc-500 text-sm">/{annual ? "yr" : "mo"}</span></div>
              </div>
              <ul className="space-y-2 text-sm mb-6">
                {p.features.map((f, i) => <li key={i} className="flex gap-2"><Check className="w-4 h-4 text-emerald-500 shrink-0" />{f}</li>)}
              </ul>
              <Button className="w-full bg-amber-500 hover:bg-amber-400 text-black font-semibold" onClick={() => checkout(key)} disabled={busy || active} data-testid={`upgrade-${p.tier}`}>
                {active ? "Current plan" : busy ? "…" : `Upgrade to ${p.tier}`}
              </Button>
            </div>
          );
        })}
      </div>
    </Layout>
  );
}
