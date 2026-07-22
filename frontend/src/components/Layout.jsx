import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth.jsx";
import { Flame, LayoutDashboard, PlusCircle, History, Boxes, CreditCard, Settings as SettingsIcon, Shield, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";

const items = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, id: "nav-dashboard" },
  { to: "/app/new", label: "New Run", icon: PlusCircle, id: "nav-new-run" },
  { to: "/app/history", label: "History", icon: History, id: "nav-history" },
  { to: "/app/workflows", label: "Workflows", icon: Boxes, id: "nav-workflows" },
  { to: "/app/billing", label: "Billing", icon: CreditCard, id: "nav-billing" },
  { to: "/app/settings", label: "Settings", icon: SettingsIcon, id: "nav-settings" },
];

export default function Layout({ children, title }) {
  const { user, subscription, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex bg-[#09090b] text-zinc-100">
      <aside className="w-60 border-r border-white/10 flex flex-col shrink-0" data-testid="sidebar">
        <div className="p-5 border-b border-white/10">
          <Link to="/app" className="flex items-center gap-2" data-testid="sidebar-logo">
            <Flame className="w-5 h-5 text-amber-500" />
            <span className="font-semibold tracking-tight">Prometheus</span>
          </Link>
          <p className="overline text-zinc-500 mt-2">MISSION CONTROL</p>
        </div>
        <nav className="flex-1 p-2">
          {items.map((it) => {
            const active = location.pathname === it.to;
            const Icon = it.icon;
            return (
              <Link key={it.to} to={it.to} data-testid={it.id}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm mb-1 transition-colors ${active ? "bg-zinc-800 text-white" : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"}`}>
                <Icon className="w-4 h-4" />
                {it.label}
              </Link>
            );
          })}
          {user?.is_admin && (
            <Link to="/app/admin" data-testid="nav-admin"
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm mb-1 transition-colors ${location.pathname === "/app/admin" ? "bg-zinc-800 text-white" : "text-amber-500 hover:bg-zinc-900"}`}>
              <Shield className="w-4 h-4" />
              Admin
            </Link>
          )}
        </nav>
        <div className="p-4 border-t border-white/10">
          <div className="text-xs text-zinc-400 mb-2 truncate" data-testid="sidebar-email">{user?.email}</div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 border border-white/10 text-amber-500 uppercase tracking-widest" data-testid="sidebar-tier">
              {subscription?.tier || "free"}
            </span>
            <Button variant="ghost" size="sm" onClick={() => { logout(); navigate("/"); }} data-testid="logout-btn">
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </aside>
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 border-b border-white/10 flex items-center px-6">
          <h1 className="text-sm uppercase tracking-[0.2em] text-zinc-400" data-testid="page-title">{title}</h1>
        </header>
        <div className="flex-1 overflow-auto p-6">{children}</div>
      </main>
    </div>
  );
}
