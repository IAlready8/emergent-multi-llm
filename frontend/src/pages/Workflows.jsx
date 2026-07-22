import { useEffect, useState } from "react";
import Layout from "@/components/Layout";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth.jsx";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Trash2, PlusCircle } from "lucide-react";

export default function Workflows() {
  const { tierConfig } = useAuth();
  const [wfs, setWfs] = useState([]);
  const [name, setName] = useState("");
  const [agents, setAgents] = useState([{ type: "Analyzer", provider: "gemini" }]);
  const [templates, setTemplates] = useState([]);

  const load = () => api.get("/workflows").then((r) => setWfs(r.data.workflows));
  useEffect(() => {
    load();
    api.get("/templates").then((r) => setTemplates(r.data.templates));
  }, []);

  const create = async () => {
    if (!name) return toast.error("Name required");
    try {
      await api.post("/workflows", { name, agents });
      toast.success("Workflow saved");
      setName("");
      setAgents([{ type: "Analyzer", provider: "gemini" }]);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => {
    await api.delete(`/workflows/${id}`);
    load();
  };

  return (
    <Layout title="Workflows">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm uppercase tracking-[0.2em] text-zinc-400 mb-3">Templates</h3>
          <div className="space-y-2">
            {templates.map((t) => (
              <div key={t.id} className="p-4 bg-zinc-900/60 border border-white/10 rounded-lg" data-testid={`template-${t.id}`}>
                <div className="font-semibold">{t.name}</div>
                <div className="text-sm text-zinc-400 mt-1">{t.description}</div>
                <div className="mt-2 flex gap-1 flex-wrap">
                  {t.agents.map((a, i) => <span key={i} className="text-xs px-2 py-0.5 bg-zinc-800 rounded font-mono">{a.type}</span>)}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-sm uppercase tracking-[0.2em] text-zinc-400 mb-3">Saved Workflows</h3>
          {!tierConfig?.custom_workflows ? (
            <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-sm text-amber-200" data-testid="upgrade-notice">
              Custom workflows require Pro or Enterprise. Upgrade in Billing.
            </div>
          ) : (
            <>
              <div className="p-4 bg-zinc-900/60 border border-white/10 rounded-lg mb-4">
                <Label>Name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} data-testid="wf-name" className="mt-1" />
                <Label className="mt-3 block">Agents</Label>
                <div className="space-y-2 mt-1">
                  {agents.map((a, i) => (
                    <div key={i} className="flex gap-2 items-center">
                      <Select value={a.type} onValueChange={(v) => setAgents((prev) => prev.map((x, j) => j === i ? { ...x, type: v } : x))}>
                        <SelectTrigger className="flex-1" data-testid={`wf-agent-${i}`}><SelectValue /></SelectTrigger>
                        <SelectContent>{tierConfig.agents.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                      </Select>
                      <Button variant="ghost" size="sm" onClick={() => setAgents((prev) => prev.filter((_, j) => j !== i))}><Trash2 className="w-4 h-4" /></Button>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" onClick={() => setAgents((p) => [...p, { type: "Analyzer", provider: "gemini" }])} data-testid="wf-add-agent"><PlusCircle className="w-4 h-4 mr-1" />Add</Button>
                </div>
                <Button className="mt-4 bg-amber-500 text-black hover:bg-amber-400 w-full" onClick={create} data-testid="wf-save">Save Workflow</Button>
              </div>
              {wfs.map((w) => (
                <div key={w.workflow_id} className="p-3 bg-zinc-900/40 border border-white/10 rounded-lg flex items-center gap-2 mb-2" data-testid={`wf-${w.workflow_id}`}>
                  <div className="flex-1">
                    <div className="font-semibold">{w.name}</div>
                    <div className="text-xs text-zinc-500 font-mono">{w.agents.map((a) => a.type).join(" → ")}</div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => del(w.workflow_id)}><Trash2 className="w-4 h-4" /></Button>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
