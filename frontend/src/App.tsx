import { BrowserRouter, Navigate, Routes, Route, Outlet } from "react-router-dom";
import { LeftSidebar } from "@/components/layout/LeftSidebar";
import { useAuth } from "@/contexts/AuthContext";
import Dashboard from "@/pages/Dashboard";
import Patterns from "@/pages/Patterns";
import SimDashboard from "@/pages/SimDashboard";
import { LandingPage } from "@/components/landing/LandingPage";

function Layout() {
  return (
    <div className="min-h-screen flex">
      <LeftSidebar />
      <main className="flex-1 min-w-0 pl-24">
        <Outlet />
      </main>
    </div>
  );
}

function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/" replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/patterns" element={<Patterns />} />
            <Route path="/simulation" element={<SimDashboard />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
