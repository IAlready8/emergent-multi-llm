import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import Layout from "@/components/Layout";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth.jsx";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Loader2 } from "lucide-react";

export default function PaymentSuccess() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const [status, setStatus] = useState("pending");
  const { refreshMe } = useAuth();
  const nav = useNavigate();

  useEffect(() => {
    let tries = 0;
    const poll = async () => {
      tries += 1;
      try {
        const { data } = await api.get(`/billing/status/${sessionId}`);
        if (data.payment_status === "paid") {
          setStatus("paid");
          await refreshMe();
          return;
        }
      } catch {}
      if (tries < 15) setTimeout(poll, 2000);
      else setStatus("timeout");
    };
    if (sessionId) poll();
  }, [sessionId, refreshMe]);

  return (
    <Layout title="Payment">
      <div className="max-w-md mx-auto p-8 bg-zinc-900/60 border border-white/10 rounded-lg text-center" data-testid="payment-success">
        {status === "pending" && (<><Loader2 className="w-10 h-10 text-amber-500 animate-spin mx-auto mb-4" /><h2 className="text-xl font-semibold">Confirming payment…</h2></>)}
        {status === "paid" && (<><CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-4" /><h2 className="text-2xl font-semibold">Payment confirmed</h2><p className="text-zinc-400 mt-2">Your plan has been upgraded.</p><Button onClick={() => nav("/app")} className="mt-6 bg-amber-500 text-black hover:bg-amber-400" data-testid="go-dashboard">Go to Dashboard</Button></>)}
        {status === "timeout" && (<><h2 className="text-xl font-semibold">Still processing…</h2><p className="text-zinc-400 mt-2">Check your billing page shortly.</p><Button onClick={() => nav("/app/billing")} className="mt-6">Billing</Button></>)}
      </div>
    </Layout>
  );
}
