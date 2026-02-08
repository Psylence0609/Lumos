import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Home, Settings, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import Dashboard from "@/pages/Dashboard";
import SimDashboard from "@/pages/SimDashboard";

function NavLink({ to, icon: Icon, label, onClick }: { to: string; icon: any; label: string; onClick?: () => void }) {
  const location = useLocation();
  const active = location.pathname === to;

  return (
    <Link
      to={to}
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-colors min-h-[44px]",
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
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  /* close menu on route change */
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen">
      {/* Top Nav — safe-area aware for notched phones */}
      <nav className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 h-12 flex items-center justify-between">
          {/* Desktop nav links */}
          <div className="hidden md:flex items-center gap-1">
            <NavLink to="/" icon={Home} label="Dashboard" />
            <NavLink to="/simulation" icon={Settings} label="Simulation" />
          </div>

          {/* Mobile: brand + hamburger */}
          <div className="flex md:hidden items-center justify-between w-full">
            <span className="text-sm font-semibold text-foreground">Lumos</span>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className="flex items-center justify-center w-10 h-10 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              aria-label="Toggle menu"
            >
              {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile drawer */}
        <AnimatePresence>
          {menuOpen && (
            <>
              {/* backdrop */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-40 bg-black/40 md:hidden"
                onClick={() => setMenuOpen(false)}
              />
              {/* slide-out panel */}
              <motion.div
                initial={{ x: "-100%" }}
                animate={{ x: 0 }}
                exit={{ x: "-100%" }}
                transition={{ type: "spring", stiffness: 380, damping: 28 }}
                className="fixed top-0 left-0 z-50 h-full w-[min(280px,85vw)] max-w-[85vw] bg-background border-r border-border p-4 pt-[calc(1rem+env(safe-area-inset-top))] pb-[env(safe-area-inset-bottom)] space-y-1 md:hidden overflow-y-auto"
              >
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-3 px-4">Navigation</p>
                <NavLink to="/" icon={Home} label="Dashboard" onClick={() => setMenuOpen(false)} />
                <NavLink to="/simulation" icon={Settings} label="Simulation" onClick={() => setMenuOpen(false)} />
              </motion.div>
            </>
          )}
        </AnimatePresence>
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
