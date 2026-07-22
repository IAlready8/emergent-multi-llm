import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "@/components/Layout";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";

export default function History() {
  const [runs, setRuns] = useState([]);
  const [status, setStatus] = useState("");

  const load = () => api.get(`/runs?limit=100${status ? `&status=${status}` : ""}`).then((r) => setRuns(r.data.runs));
  useEffect(() => { load(); }, [status]);

  const del = async (rid) => {
    if (!confirm("Delete this run?")) return;
    await api.delete(`/runs/${rid}`);
    toast.success("Deleted");
    load();
  };

  return (
    <Layout title="History">
      <div className="flex items-center gap-2 mb-4">
        {["", "completed", "failed", "streaming"].map((s) => (
          <Button key={s || "all"} variant={status === s ? "default" : "outline"} size="sm" className={status === s ? "bg-amber-500 text-black" : "border-white/10"} onClick={() => setStatus(s)} data-testid={`filter-${s || "all"}`}>
            {s || "All"}
          </Button>
        ))}
      </div>
      {runs.length === 0 ? (
        <div className="p-8 border border-dashed border-white/10 text-center text-zinc-500 rounded-lg" data-testid="history-empty">No runs yet.</div>
      ) : (
        <div className="border border-white/10 rounded-lg overflow-hidden" data-testid="history-list">
          {runs.map((r) => (
            <div key={r.run_id} className="flex items-center gap-3 px-4 py-3 border-b border-white/10 hover:bg-zinc-900/60">
              <Link to={`/app/runs/${r.run_id}`} className="flex-1 min-w-0" data-testid={`history-run-${r.run_id}`}>
                <div className="text-xs font-mono text-zinc-400 truncate">{r.run_id}</div>
                <div className="text-xs text-zinc-500">{r.created_at?.slice(0, 19)} · {r.input_type} · {r.agents?.length} agents</div>
              </Link>
              <span className={`text-xs font-mono uppercase ${r.status === "completed" ? "text-emerald-500" : r.status === "failed" ? "text-red-500" : "text-amber-500"}`}>{r.status}</span>
              <Button variant="ghost" size="sm" onClick={() => del(r.run_id)} data-testid={`delete-${r.run_id}`}><Trash2 className="w-4 h-4" /></Button>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
