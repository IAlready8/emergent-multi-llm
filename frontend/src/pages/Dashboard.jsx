import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "@/components/Layout";
import { useAuth } from "@/lib/auth.jsx";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { PlusCircle, Zap, Activity, TrendingUp } from "lucide-react";

export default function Dashboard() {
  const { user, subscription, tierConfig } = useAuth();
  const [runs, setRuns] = useState([]);

  useEffect(() => {
    api.get("/runs?limit=5").then((r) => setRuns(r.data.runs)).catch(() => {});
  }, []);

  const usedPct = tierConfig?.runs_per_period
    ? Math.min(100, ((subscription?.runs_used || 0) / tierConfig.runs_per_period) * 100)
    : 0;

  return (
    <Layout title="Dashboard">
      <div className="mb-8">
        <h2 className="text-3xl font-semibold tracking-tight">Welcome, {user?.name}</h2>
        <p className="text-zinc-400 mt-1">Your agent fleet stands ready.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatCard testid="stat-tier" icon={Zap} label="Current tier" value={subscription?.tier?.toUpperCase() || "FREE"} sub={tierConfig?.runs_per_period ? `${tierConfig.runs_per_period} runs/mo` : "Unlimited"} />
        <StatCard testid="stat-usage" icon={Activity} label="Runs used" value={`${subscription?.runs_used || 0}`} sub={tierConfig?.runs_per_period ? `of ${tierConfig.runs_per_period}` : "no cap"} pct={usedPct} />
        <StatCard testid="stat-agents" icon={TrendingUp} label="Agents unlocked" value={`${tierConfig?.agents?.length || 0}/5`} sub={tierConfig?.agents?.join(", ")} />
        <StatCard testid="stat-history" icon={Activity} label="History window" value={tierConfig?.history_days ? `${tierConfig.history_days}d` : "∞"} sub="rolling" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        <Link to="/app/new" className="lg:col-span-2 p-8 bg-gradient-to-br from-zinc-900 to-zinc-900/50 border border-amber-500/40 rounded-lg hover:border-amber-500 transition-colors" data-testid="cta-new-run">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-amber-500/10 rounded-md border border-amber-500/30">
              <PlusCircle className="w-6 h-6 text-amber-500" />
            </div>
            <div>
              <h3 className="text-xl font-semibold">Launch a new run</h3>
              <p className="text-zinc-400 mt-1">Upload a document, paste data, fetch a URL, or design a custom workflow.</p>
            </div>
          </div>
        </Link>
        <Link to="/app/workflows" className="p-8 bg-zinc-900/60 border border-white/10 rounded-lg hover:border-white/30 transition-colors" data-testid="cta-workflows">
          <h3 className="text-xl font-semibold">Workflows</h3>
          <p className="text-zinc-400 mt-1 text-sm">Manage saved pipelines and templates.</p>
        </Link>
      </div>

      <div>
        <h3 className="text-sm uppercase tracking-[0.2em] text-zinc-400 mb-3" data-testid="recent-runs-header">Recent runs</h3>
        {runs.length === 0 ? (
          <div className="p-8 bg-zinc-900/40 border border-dashed border-white/10 rounded-lg text-center text-zinc-500" data-testid="empty-runs">
            No runs yet. <Link to="/app/new" className="text-amber-500 hover:underline">Launch your first</Link>.
          </div>
        ) : (
          <div className="space-y-2">
            {runs.map((r) => <RunRow key={r.run_id} run={r} />)}
          </div>
        )}
      </div>
    </Layout>
  );
}

function StatCard({ icon: Icon, label, value, sub, pct, testid }) {
  return (
    <div className="p-5 bg-zinc-900/60 border border-white/10 rounded-lg" data-testid={testid}>
      <div className="flex items-center justify-between mb-3">
        <span className="overline text-zinc-500">{label}</span>
        <Icon className="w-4 h-4 text-amber-500" />
      </div>
      <div className="text-2xl font-semibold font-mono">{value}</div>
      {typeof pct === "number" && (
        <div className="w-full h-1 bg-zinc-800 mt-3 rounded"><div className="h-full bg-amber-500 rounded" style={{ width: `${pct}%` }} /></div>
      )}
      <p className="text-xs text-zinc-500 mt-2 truncate">{sub}</p>
    </div>
  );
}

function RunRow({ run }) {
  const colors = { completed: "text-emerald-500", running: "text-amber-500", streaming: "text-amber-500", failed: "text-red-500", queued: "text-zinc-500" };
  return (
    <Link to={`/app/runs/${run.run_id}`} className="flex items-center gap-3 p-3 bg-zinc-900/40 border border-white/10 rounded-lg hover:bg-zinc-900 transition-colors" data-testid={`run-row-${run.run_id}`}>
      <span className={`w-2 h-2 rounded-full ${(run.status === "streaming" || run.status === "running") ? "bg-amber-500 pulse-dot" : run.status === "completed" ? "bg-emerald-500" : run.status === "failed" ? "bg-red-500" : "bg-zinc-500"}`} />
      <div className="flex-1 min-w-0">
        <div className="font-mono text-xs text-zinc-400 truncate">{run.run_id}</div>
        <div className="text-xs text-zinc-500">{run.input_type} · {run.agents?.length || 0} agents</div>
      </div>
      <span className={`text-xs font-mono uppercase ${colors[run.status] || "text-zinc-400"}`}>{run.status}</span>
    </Link>
  );
}
