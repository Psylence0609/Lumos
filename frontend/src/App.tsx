import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { Home, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import Dashboard from "@/pages/Dashboard";
import SimDashboard from "@/pages/SimDashboard";

function NavLink({ to, icon: Icon, label }: { to: string; icon: any; label: string }) {
  const location = useLocation();
  const active = location.pathname === to;

  return (
    <Link
      to={to}
      className={cn(
        "flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-colors",
        active
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:text-foreground hover:bg-muted"
      )}
    >
      <Icon className="w-4 h-4" />
      {label}
    </Link>
  );
}

function Layout() {
  return (
    <div className="min-h-screen">
      {/* Top Nav */}
      <nav className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 md:px-6 h-12 flex items-center gap-1">
          <NavLink to="/" icon={Home} label="Dashboard" />
          <NavLink to="/simulation" icon={Settings} label="Simulation" />
        </div>
      </nav>

      {/* Routes */}
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/simulation" element={<SimDashboard />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  );
}
