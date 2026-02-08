import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import { LeftSidebar } from "@/components/layout/LeftSidebar";
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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/patterns" element={<Patterns />} />
          <Route path="/simulation" element={<SimDashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
