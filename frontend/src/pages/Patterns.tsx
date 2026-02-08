import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/utils";
import { PatternPanel } from "@/components/home/PatternPanel";
import type { Pattern } from "@/types";

export default function Patterns() {
  const [patterns, setPatterns] = useState<Pattern[]>([]);

  useEffect(() => {
    const load = () => {
      apiFetch<Pattern[]>("/patterns")
        .then(setPatterns)
        .catch(() => setPatterns([]));
    };
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  const refresh = () => apiFetch<Pattern[]>("/patterns").then(setPatterns);

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 pb-[env(safe-area-inset-bottom)]">
      <h1 className="text-xl font-semibold text-foreground mb-4">Detected Patterns</h1>
      <PatternPanel patterns={patterns} onUpdate={refresh} />
    </div>
  );
}
