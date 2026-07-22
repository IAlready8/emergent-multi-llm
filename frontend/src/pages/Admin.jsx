import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import api from "@/lib/api";

export default function Admin() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/admin/overview").then((r) => setData(r.data)); }, []);

  if (!data) return <Layout title="Admin"><div className="text-zinc-400">Loading…</div></Layout>;

  return (
    <Layout title="Admin">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Metric label="Users" value={data.users} testid="admin-users" />
        <Metric label="Runs" value={data.runs} testid="admin-runs" />
        <Metric label="Failed" value={data.runs_failed} testid="admin-failed" />
        <Metric label="Est. MRR" value={`$${data.revenue_month_estimate_usd}`} testid="admin-revenue" />
      </div>

      <div className="grid gap-4 md:grid-cols-3 mb-6">
        {Object.entries(data.tier_counts).map(([k, v]) => (
          <div key={k} className="p-4 bg-zinc-900/60 border border-white/10 rounded-lg">
            <div className="overline text-zinc-500">{k.toUpperCase()}</div>
            <div className="text-2xl font-mono">{v}</div>
          </div>
        ))}
      </div>

      <h3 className="overline text-zinc-500 mb-2">Recent Runs</h3>
      <div className="border border-white/10 rounded-lg overflow-hidden mb-6">
        {data.recent_runs.map((r) => (
          <div key={r.run_id} className="px-3 py-2 border-b border-white/10 flex items-center gap-3 text-xs">
            <span className="font-mono text-zinc-400 truncate flex-1">{r.run_id}</span>
            <span className="text-zinc-500">{r.user_id?.slice(0, 12)}</span>
            <span className={`font-mono uppercase ${r.status === "completed" ? "text-emerald-500" : r.status === "failed" ? "text-red-500" : "text-amber-500"}`}>{r.status}</span>
          </div>
        ))}
      </div>

      <h3 className="overline text-zinc-500 mb-2">Recent Feedback</h3>
      <div className="space-y-2">
        {data.recent_feedback.map((f) => (
          <div key={f.feedback_id} className="p-3 bg-zinc-900/40 border border-white/10 rounded text-sm">
            <div className="text-xs text-zinc-500 font-mono mb-1">{f.email}</div>
            {f.message}
          </div>
        ))}
      </div>
    </Layout>
  );
}

function Metric({ label, value, testid }) {
  return (
    <div className="p-5 bg-zinc-900/60 border border-white/10 rounded-lg" data-testid={testid}>
      <div className="overline text-zinc-500">{label}</div>
      <div className="text-3xl font-mono font-semibold mt-1">{value}</div>
    </div>
  );
}
