import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LeftSidebar } from "@/components/layout/LeftSidebar";
import Dashboard from "@/pages/Dashboard";
import Patterns from "@/pages/Patterns";
import SimDashboard from "@/pages/SimDashboard";

function Layout() {
  return (
    <div className="min-h-screen flex">
      {/* Left sidebar — skewed 3D nav (Dashboard, Patterns, Logout) */}
      <LeftSidebar />
      {/* Main content — right of fixed left sidebar */}
      <main className="flex-1 min-w-0 pl-24">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/patterns" element={<Patterns />} />
          <Route path="/simulation" element={<SimDashboard />} />
        </Routes>
      </main>
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
