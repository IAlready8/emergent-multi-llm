import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useRef } from "react";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth.jsx";
import api from "@/lib/api";
import Landing from "@/pages/Landing.jsx";
import Login from "@/pages/Login.jsx";
import Signup from "@/pages/Signup.jsx";
import Dashboard from "@/pages/Dashboard.jsx";
import NewRun from "@/pages/NewRun.jsx";
import RunView from "@/pages/RunView.jsx";
import History from "@/pages/History.jsx";
import Workflows from "@/pages/Workflows.jsx";
import Billing from "@/pages/Billing.jsx";
import Settings from "@/pages/Settings.jsx";
import Admin from "@/pages/Admin.jsx";
import PaymentSuccess from "@/pages/PaymentSuccess.jsx";

function AuthCallback() {
  const navigate = useNavigate();
  const processed = useRef(false);
  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    const hash = window.location.hash || "";
    const sid = new URLSearchParams(hash.replace(/^#/, "")).get("session_id");
    if (!sid) { navigate("/login"); return; }
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    api.post("/auth/google/session", { session_id: sid })
      .then(() => {
        window.location.hash = "";
        navigate("/app", { replace: true });
        window.location.reload();
      })
      .catch(() => navigate("/login"));
  }, [navigate]);
  return <div className="min-h-screen flex items-center justify-center text-zinc-400 font-mono text-sm">Establishing session…</div>;
}

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-zinc-400 font-mono text-sm">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/app" element={<Protected><Dashboard /></Protected>} />
      <Route path="/app/new" element={<Protected><NewRun /></Protected>} />
      <Route path="/app/runs/:runId" element={<Protected><RunView /></Protected>} />
      <Route path="/app/history" element={<Protected><History /></Protected>} />
      <Route path="/app/workflows" element={<Protected><Workflows /></Protected>} />
      <Route path="/app/billing" element={<Protected><Billing /></Protected>} />
      <Route path="/app/settings" element={<Protected><Settings /></Protected>} />
      <Route path="/app/admin" element={<Protected><Admin /></Protected>} />
      <Route path="/payment/success" element={<Protected><PaymentSuccess /></Protected>} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRouter />
        <Toaster theme="dark" position="top-right" richColors />
      </BrowserRouter>
    </AuthProvider>
  );
}
