import { useState } from "react";
import { Play, Square, Zap, Presentation } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/utils";
import type { Scenario } from "@/types";

interface Props {
  scenarios: Scenario[];
  activeScenario: string | null;
  onUpdate: () => void;
}

export function ScenarioRunner({ scenarios, activeScenario, onUpdate }: Props) {
  const [loading, setLoading] = useState<string | null>(null);

  const runScenario = async (id: string) => {
    setLoading(id);
    try {
      await apiFetch("/simulation/scenarios/run", {
        method: "POST",
        body: JSON.stringify({ scenario_id: id }),
      });
      onUpdate();
    } catch (e) {
      console.error("Scenario failed:", e);
    }
    setLoading(null);
  };

  const stopScenario = async () => {
    await apiFetch("/simulation/scenarios/stop", { method: "POST" });
    onUpdate();
  };

  // Split into demo and regular scenarios
  const demoScenarios = scenarios.filter((s) => s.temporal);
  const regularScenarios = scenarios.filter((s) => !s.temporal);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            Scenarios
          </CardTitle>
          {activeScenario && (
            <Button size="sm" variant="destructive" onClick={stopScenario}>
              <Square className="w-3 h-3 mr-1" /> Stop
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Demo Scenarios */}
        {demoScenarios.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Presentation className="w-3.5 h-3.5 text-primary" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-primary">
                Hackathon Demos
              </span>
            </div>
            <div className="space-y-2">
              {demoScenarios.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-primary/5 border border-primary/20"
                >
                  <div className="flex-1 min-w-0 mr-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium">{s.name}</span>
                      {activeScenario === s.id && (
                        <Badge variant="success">running</Badge>
                      )}
                      {s.total_steps && (
                        <Badge variant="outline" className="text-[9px]">
                          {s.total_steps} steps
                        </Badge>
                      )}
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-2">
                      {s.description}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="default"
                    onClick={() => runScenario(s.id)}
                    disabled={loading !== null || activeScenario === s.id}
                    className="shrink-0"
                  >
                    <Play className="w-3 h-3 mr-1" />
                    {loading === s.id ? "..." : "Demo"}
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Regular Scenarios */}
        {regularScenarios.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Zap className="w-3.5 h-3.5 text-yellow-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                Quick Tests
              </span>
            </div>
            <div className="space-y-1.5">
              {regularScenarios.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between p-2 rounded-lg bg-muted/30 border border-border/50"
                >
                  <div className="flex-1 min-w-0 mr-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium">{s.name}</span>
                      {activeScenario === s.id && (
                        <Badge variant="success">active</Badge>
                      )}
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-0.5 truncate">
                      {s.description}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => runScenario(s.id)}
                    disabled={loading !== null || activeScenario === s.id}
                    className="shrink-0"
                  >
                    <Play className="w-3 h-3 mr-1" />
                    {loading === s.id ? "..." : "Run"}
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
