import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth.jsx";
import { Flame } from "lucide-react";

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await signup(email, password, name);
      toast.success("Welcome to Prometheus!");
      navigate("/app");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Signup failed");
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
    <div className="min-h-screen bg-[#09090b] text-zinc-100 flex items-center justify-center px-4 grid-bg">
      <div className="w-full max-w-md p-8 bg-zinc-900/80 border border-white/10 rounded-lg">
        <Link to="/" className="flex items-center gap-2 mb-6" data-testid="signup-logo">
          <Flame className="w-5 h-5 text-amber-500" />
          <span className="font-semibold tracking-tight">Prometheus</span>
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight mb-1">Create your account</h1>
        <p className="text-sm text-zinc-400 mb-6">Free tier: 10 runs / month · No card required.</p>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="name">Name</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required data-testid="signup-name" />
          </div>
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="signup-email" autoComplete="email" />
          </div>
          <div>
            <Label htmlFor="password">Password (min 8 chars)</Label>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} data-testid="signup-password" autoComplete="new-password" />
          </div>
          <Button type="submit" disabled={busy} className="w-full bg-amber-500 hover:bg-amber-400 text-black font-semibold" data-testid="signup-submit">
            {busy ? "Creating…" : "Create account"}
          </Button>
        </form>

        <div className="my-5 flex items-center gap-3 text-xs text-zinc-500">
          <div className="h-px bg-white/10 flex-1" /> OR <div className="h-px bg-white/10 flex-1" />
        </div>

        <Button onClick={googleLogin} variant="outline" className="w-full border-white/20 hover:bg-zinc-800" data-testid="signup-google">
          Continue with Google
        </Button>

        <p className="text-sm text-zinc-400 mt-6 text-center">
          Have an account? <Link to="/login" className="text-amber-500 hover:underline" data-testid="signup-login-link">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
