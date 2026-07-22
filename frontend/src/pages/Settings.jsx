import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth.jsx";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Download, Trash2 } from "lucide-react";

export default function Settings() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [feedback, setFeedback] = useState("");

  const exportData = async () => {
    try {
      const { data } = await api.get("/gdpr/export", { responseType: "blob" });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a"); a.href = url; a.download = "prometheus_export.json"; a.click(); URL.revokeObjectURL(url);
    } catch (e) { toast.error(e?.response?.data?.detail || "Export failed"); }
  };

  const deleteAcct = async () => {
    if (!confirm("This permanently deletes your account and all data. Continue?")) return;
    try {
      await api.delete("/gdpr/account");
      toast.success("Account deleted");
      await logout();
      nav("/");
    } catch (e) { toast.error("Deletion failed"); }
  };

  const submitFb = async () => {
    if (!feedback.trim()) return;
    await api.post("/feedback", { message: feedback });
    setFeedback(""); toast.success("Thanks for the feedback!");
  };

  return (
    <Layout title="Settings">
      <div className="grid gap-4 max-w-3xl">
        <div className="p-6 bg-zinc-900/60 border border-white/10 rounded-lg">
          <div className="overline text-zinc-500 mb-2">ACCOUNT</div>
          <div className="text-sm"><span className="text-zinc-400">Email:</span> <span className="font-mono">{user?.email}</span></div>
          <div className="text-sm mt-1"><span className="text-zinc-400">Provider:</span> <span className="font-mono">{user?.provider}</span></div>
        </div>

        <div className="p-6 bg-zinc-900/60 border border-white/10 rounded-lg">
          <div className="overline text-zinc-500 mb-2">GDPR</div>
          <p className="text-sm text-zinc-400 mb-4">Export or delete your data anytime.</p>
          <div className="flex gap-2">
            <Button onClick={exportData} variant="outline" className="border-white/10" data-testid="gdpr-export"><Download className="w-4 h-4 mr-1" />Export data (JSON)</Button>
            <Button onClick={deleteAcct} variant="destructive" data-testid="gdpr-delete"><Trash2 className="w-4 h-4 mr-1" />Delete account</Button>
          </div>
        </div>

        <div className="p-6 bg-zinc-900/60 border border-white/10 rounded-lg">
          <div className="overline text-zinc-500 mb-2">FEEDBACK</div>
          <Textarea rows={4} value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="Ideas, bugs, praise…" data-testid="feedback-input" />
          <Button onClick={submitFb} className="mt-3 bg-amber-500 hover:bg-amber-400 text-black" data-testid="feedback-submit">Send feedback</Button>
        </div>
      </div>
    </Layout>
  );
}
