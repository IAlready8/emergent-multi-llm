import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth.jsx";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { PlusCircle, Trash2 } from "lucide-react";

const AGENT_TYPES = ["Analyzer", "Aggregator", "AnomalyDetector", "Classifier", "Synthesizer"];

export default function NewRun() {
  const { tierConfig, subscription } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState("template");
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState("");
  const [inputText, setInputText] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [provider, setProvider] = useState("gemini");
  const [customAgents, setCustomAgents] = useState([{ type: "Analyzer", provider: "gemini" }]);
  const [file, setFile] = useState(null);

  useEffect(() => {
    api.get("/templates").then((r) => { setTemplates(r.data.templates); setTemplateId(r.data.templates[0]?.id || ""); });
  }, []);

  const providerMode = tierConfig?.provider_mode || "gemini_only";
  const canCustom = !!tierConfig?.custom_workflows;

  const start = async (bodyExtras = {}) => {
    setBusy(true);
    try {
      let file_ids = [];
      if (file && tab === "upload") {
        const fd = new FormData();
        fd.append("file", file);
        const up = await api.post("/uploads", fd, { headers: { "Content-Type": "multipart/form-data" } });
        file_ids = [up.data.file_id];
      }
      const body = {
        input_text: tab === "paste" ? inputText : "",
        input_type: tab === "template" ? "paste" : tab === "url" ? "url" : tab === "upload" ? "file" : tab === "custom" ? "paste" : "paste",
        url: tab === "url" ? url : undefined,
        file_ids: file_ids.length ? file_ids : undefined,
        template_id: tab === "template" ? templateId : undefined,
        agents: tab === "custom" ? customAgents : undefined,
        provider: providerMode === "per_run" ? provider : undefined,
        ...bodyExtras,
      };
      const { data } = await api.post("/runs", body);
      toast.success("Run launched");
      navigate(`/app/runs/${data.run_id}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to start run");
    } finally { setBusy(false); }
  };

  return (
    <Layout title="New Run">
      <div className="max-w-4xl">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-zinc-900 border border-white/10" data-testid="new-run-tabs">
            <TabsTrigger value="template" data-testid="tab-template">Template</TabsTrigger>
            <TabsTrigger value="paste" data-testid="tab-paste">Paste Text</TabsTrigger>
            <TabsTrigger value="url" data-testid="tab-url">URL</TabsTrigger>
            <TabsTrigger value="upload" data-testid="tab-upload">Upload File</TabsTrigger>
            {canCustom && <TabsTrigger value="custom" data-testid="tab-custom">Custom Workflow</TabsTrigger>}
          </TabsList>

          <div className="mt-6 p-6 bg-zinc-900/40 border border-white/10 rounded-lg">
            <TabsContent value="template">
              <Label>Template</Label>
              <Select value={templateId} onValueChange={setTemplateId}>
                <SelectTrigger className="mt-1" data-testid="template-select"><SelectValue /></SelectTrigger>
                <SelectContent>{templates.map((t) => <SelectItem key={t.id} value={t.id} data-testid={`tpl-${t.id}`}>{t.name}</SelectItem>)}</SelectContent>
              </Select>
              <Label className="mt-4 block">Input text</Label>
              <Textarea rows={8} value={inputText} onChange={(e) => setInputText(e.target.value)} className="mt-1 font-mono text-sm" data-testid="template-input" placeholder="Paste document / text to analyze…" />
            </TabsContent>

            <TabsContent value="paste">
              <Label>Text or data</Label>
              <Textarea rows={12} value={inputText} onChange={(e) => setInputText(e.target.value)} className="mt-1 font-mono text-sm" data-testid="paste-input" />
            </TabsContent>

            <TabsContent value="url">
              <Label>Public URL (http/https)</Label>
              <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/article" className="mt-1" data-testid="url-input" />
              <p className="text-xs text-zinc-500 mt-2">Private IPs and localhost blocked. Max 25 MB response.</p>
            </TabsContent>

            <TabsContent value="upload">
              <Label>Upload CSV / TXT / MD / JSON (max {tierConfig?.upload_max_mb} MB)</Label>
              <input type="file" accept=".csv,.txt,.md,.json" onChange={(e) => setFile(e.target.files?.[0] || null)} className="mt-1 block w-full text-sm text-zinc-300 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-amber-500 file:text-black file:font-semibold" data-testid="upload-file-input" />
            </TabsContent>

            {canCustom && (
              <TabsContent value="custom">
                <div className="space-y-2">
                  {customAgents.map((a, i) => (
                    <div key={i} className="flex gap-2 items-center" data-testid={`custom-agent-${i}`}>
                      <span className="text-xs text-zinc-500 w-8">#{i + 1}</span>
                      <Select value={a.type} onValueChange={(v) => setCustomAgents((prev) => prev.map((x, j) => j === i ? { ...x, type: v } : x))}>
                        <SelectTrigger className="flex-1"><SelectValue /></SelectTrigger>
                        <SelectContent>{tierConfig.agents.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                      </Select>
                      {providerMode === "per_agent" && (
                        <Select value={a.provider} onValueChange={(v) => setCustomAgents((prev) => prev.map((x, j) => j === i ? { ...x, provider: v } : x))}>
                          <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                          <SelectContent><SelectItem value="gemini">Gemini</SelectItem><SelectItem value="openai">GPT-5.2</SelectItem></SelectContent>
                        </Select>
                      )}
                      <Button variant="ghost" size="sm" onClick={() => setCustomAgents((prev) => prev.filter((_, j) => j !== i))} data-testid={`remove-agent-${i}`}><Trash2 className="w-4 h-4" /></Button>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" onClick={() => setCustomAgents((prev) => [...prev, { type: "Analyzer", provider: "gemini" }])} data-testid="add-agent-btn">
                    <PlusCircle className="w-4 h-4 mr-1" />Add agent
                  </Button>
                </div>
                <Label className="mt-4 block">Input text</Label>
                <Textarea rows={6} value={inputText} onChange={(e) => setInputText(e.target.value)} className="mt-1 font-mono text-sm" data-testid="custom-input" />
              </TabsContent>
            )}

            <div className="mt-6 flex items-center justify-between">
              {providerMode === "per_run" ? (
                <div className="flex items-center gap-3">
                  <Label className="text-xs">Provider:</Label>
                  <Select value={provider} onValueChange={setProvider}>
                    <SelectTrigger className="w-40" data-testid="provider-select"><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="gemini">Gemini 3</SelectItem><SelectItem value="openai">GPT-5.2</SelectItem></SelectContent>
                  </Select>
                </div>
              ) : <div className="text-xs text-zinc-500">Provider: {providerMode === "gemini_only" ? "Gemini (Free)" : "Per-agent (Enterprise)"}</div>}
              <Button onClick={() => start()} disabled={busy} className="bg-amber-500 hover:bg-amber-400 text-black font-semibold" data-testid="launch-run-btn">
                {busy ? "Launching…" : "Launch Run"}
              </Button>
            </div>
          </div>
        </Tabs>
      </div>
    </Layout>
  );
}
