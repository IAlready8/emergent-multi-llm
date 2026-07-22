import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import Layout from "@/components/Layout";
import api, { API } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Download, FileText } from "lucide-react";
import { useAuth } from "@/lib/auth.jsx";

const statusColor = { pending: "bg-zinc-500", running: "bg-amber-500", retrying: "bg-amber-500", completed: "bg-emerald-500", failed: "bg-red-500", timeout: "bg-red-500", skipped: "bg-zinc-500" };

export default function RunView() {
  const { runId } = useParams();
  const { tierConfig } = useAuth();
  const [run, setRun] = useState(null);
  const [agentOutputs, setAgentOutputs] = useState({});
  const [agentStatuses, setAgentStatuses] = useState({});
  const [runStatus, setRunStatus] = useState("queued");
  const esRef = useRef(null);
  const scrollRefs = useRef({});

  useEffect(() => {
    api.get(`/runs/${runId}`).then((r) => {
      setRun(r.data);
      setRunStatus(r.data.status);
      const st = {}; r.data.agents.forEach((a) => { st[a.agent_id] = a.status; });
      setAgentStatuses(st);
      const outs = {};
      Object.entries(r.data.agent_outputs || {}).forEach(([type, text]) => {
        const ag = r.data.agents.find((a) => a.type === type);
        if (ag) outs[ag.agent_id] = text;
      });
      setAgentOutputs(outs);
    });

    const token = localStorage.getItem("access_token");
    const es = new EventSource(`${API}/runs/${runId}/stream?token=${encodeURIComponent(token || "")}`, { withCredentials: true });
    esRef.current = es;
    es.onmessage = (msg) => {
      try {
        const ev = JSON.parse(msg.data);
        if (ev.event === "agent_token") {
          setAgentOutputs((prev) => ({ ...prev, [ev.agent_id]: (prev[ev.agent_id] || "") + ev.delta }));
          const el = scrollRefs.current[ev.agent_id];
          if (el) el.scrollTop = el.scrollHeight;
        } else if (ev.event === "agent_status") {
          setAgentStatuses((prev) => ({ ...prev, [ev.agent_id]: ev.status }));
        } else if (ev.event === "run_status") {
          setRunStatus(ev.status);
        } else if (ev.event === "end") {
          es.close();
        }
      } catch {}
    };
    es.onerror = () => { es.close(); };
    return () => { es.close(); };
  }, [runId]);

  const downloadJSON = async () => {
    const { data } = await api.get(`/runs/${runId}/export.json`, { responseType: "blob" });
    const url = URL.createObjectURL(data);
    const a = document.createElement("a"); a.href = url; a.download = `run_${runId}.json`; a.click(); URL.revokeObjectURL(url);
  };

  const downloadPDF = async () => {
    try {
      const { data } = await api.get(`/runs/${runId}/export.pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a"); a.href = url; a.download = `run_${runId}.pdf`; a.click(); URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "PDF export failed");
    }
  };

  if (!run) return <Layout title="Run"><div className="text-zinc-400">Loading…</div></Layout>;

  return (
    <Layout title={`Run · ${runId.slice(0, 12)}…`}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-3">
            <span className={`w-2 h-2 rounded-full ${runStatus === "streaming" || runStatus === "running" ? "bg-amber-500 pulse-dot" : runStatus === "completed" ? "bg-emerald-500" : runStatus === "failed" ? "bg-red-500" : "bg-zinc-500"}`} />
            <span className="text-xs uppercase tracking-[0.2em] font-mono" data-testid="run-status">{runStatus}</span>
          </div>
          <div className="text-xs text-zinc-500 font-mono mt-1">{runId}</div>
        </div>
        <div className="flex gap-2">
          <Button onClick={downloadJSON} variant="outline" size="sm" className="border-white/10" data-testid="export-json"><Download className="w-4 h-4 mr-1" />JSON</Button>
          {tierConfig?.export_pdf && (
            <Button onClick={downloadPDF} variant="outline" size="sm" className="border-white/10" data-testid="export-pdf"><FileText className="w-4 h-4 mr-1" />PDF</Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <aside className="lg:col-span-1 space-y-2" data-testid="agent-graph">
          <p className="overline text-zinc-500 mb-2">AGENT GRAPH</p>
          {run.agents.map((a, i) => {
            const s = agentStatuses[a.agent_id] || a.status;
            return (
              <div key={a.agent_id} className="p-3 bg-zinc-900/60 border border-white/10 rounded-md" data-testid={`agent-node-${a.type}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-zinc-500 font-mono">#{i + 1}</span>
                  <span className={`w-2 h-2 rounded-full ${statusColor[s] || "bg-zinc-500"} ${s === "running" || s === "retrying" ? "pulse-dot" : ""}`} />
                  <span className="text-sm font-semibold">{a.type}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-500 font-mono">{a.provider}</span>
                  <span className={`font-mono uppercase ${s === "completed" ? "text-emerald-500" : s === "failed" || s === "timeout" ? "text-red-500" : s === "running" || s === "retrying" ? "text-amber-500" : "text-zinc-500"}`}>{s}</span>
                </div>
              </div>
            );
          })}
        </aside>

        <section className="lg:col-span-3 space-y-3" data-testid="agent-streams">
          {run.agents.map((a) => {
            const s = agentStatuses[a.agent_id] || a.status;
            return (
              <div key={a.agent_id} className="bg-zinc-900/60 border border-white/10 rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 border-b border-white/10 bg-black/40">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${statusColor[s] || "bg-zinc-500"} ${s === "running" ? "pulse-dot" : ""}`} />
                    <span className="text-sm font-semibold">{a.type}</span>
                    <span className="text-xs text-zinc-500 font-mono">{a.provider}</span>
                  </div>
                  <span className={`text-xs font-mono uppercase ${s === "completed" ? "text-emerald-500" : s === "failed" ? "text-red-500" : "text-amber-500"}`}>{s}</span>
                </div>
                <pre ref={(el) => { if (el) scrollRefs.current[a.agent_id] = el; }} className="log-stream max-h-72 overflow-auto p-4 text-xs font-mono text-zinc-200 whitespace-pre-wrap" data-testid={`agent-log-${a.type}`}>
                  {agentOutputs[a.agent_id] || <span className="text-zinc-600">Awaiting output…</span>}
                </pre>
              </div>
            );
          })}
        </section>
      </div>
    </Layout>
  );
}
