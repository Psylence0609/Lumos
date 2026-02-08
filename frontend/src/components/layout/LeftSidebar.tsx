/**
 * Left sidebar nav — three vertical icon buttons; hover enlarges; active page stays enlarged and highlighted.
 */
import { Link, useLocation } from "react-router-dom";
import { Home, LayoutGrid, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems: Array<{ to: string; icon: typeof Home; label: string; isLogout?: boolean }> = [
  { to: "/", icon: Home, label: "Dashboard" },
  { to: "/patterns", icon: LayoutGrid, label: "Patterns" },
  { to: "#", icon: LogOut, label: "Logout", isLogout: true },
];

export function LeftSidebar() {
  const location = useLocation();

  return (
    <nav
      className="left-sidebar-nav"
      aria-label="Main navigation"
    >
      <ul className="left-sidebar-list">
        {navItems.map(({ to, icon: Icon, label, isLogout }) => {
          const active = !isLogout && location.pathname === to;
          const className = cn(
            "left-sidebar-item",
            active && "left-sidebar-item-active"
          );
          if (isLogout) {
            return (
              <li key="logout">
                <button
                  type="button"
                  className={className}
                  onClick={() => {
                    /* TODO: wire to auth logout */
                    window.location.href = "/";
                  }}
                  aria-label={label}
                >
                  <Icon className="w-5 h-5 shrink-0" aria-hidden />
                </button>
              </li>
            );
          }
          return (
            <li key={to}>
              <Link to={to} className={className} aria-label={label} aria-current={active ? "page" : undefined}>
                <Icon className="w-5 h-5 shrink-0" aria-hidden />
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
