import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth.jsx";
import { Flame } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      navigate("/app");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  const googleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/app";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 flex items-center justify-center px-4 relative grid-bg">
      <div className="w-full max-w-md p-8 bg-zinc-900/80 border border-white/10 rounded-lg relative">
        <Link to="/" className="flex items-center gap-2 mb-6" data-testid="login-logo">
          <Flame className="w-5 h-5 text-amber-500" />
          <span className="font-semibold tracking-tight">Prometheus</span>
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight mb-1">Welcome back</h1>
        <p className="text-sm text-zinc-400 mb-6">Sign in to your mission control.</p>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="login-email" autoComplete="email" />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required data-testid="login-password" autoComplete="current-password" />
          </div>
          <Button type="submit" disabled={busy} className="w-full bg-amber-500 hover:bg-amber-400 text-black font-semibold" data-testid="login-submit">
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <div className="my-5 flex items-center gap-3 text-xs text-zinc-500">
          <div className="h-px bg-white/10 flex-1" /> OR <div className="h-px bg-white/10 flex-1" />
        </div>

        <Button onClick={googleLogin} variant="outline" className="w-full border-white/20 hover:bg-zinc-800" data-testid="login-google">
          Continue with Google
        </Button>

        <p className="text-sm text-zinc-400 mt-6 text-center">
          No account? <Link to="/signup" className="text-amber-500 hover:underline" data-testid="login-signup-link">Sign up</Link>
        </p>
      </div>
    </div>
  );
}
