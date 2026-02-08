import { useState, useEffect, useCallback } from "react";
import { Settings, Wifi, WifiOff, Trash2 } from "lucide-react";
import { ScenarioRunner } from "@/components/sim/ScenarioRunner";
import { WeatherInjector } from "@/components/sim/WeatherInjector";
import { GridControl } from "@/components/sim/GridControl";
import { GPSControl } from "@/components/sim/GPSControl";
import { BatteryControl } from "@/components/sim/BatteryControl";
import { DeviceFailure } from "@/components/sim/DeviceFailure";
import { EventLog } from "@/components/sim/EventLog";
import { AgentInspector } from "@/components/sim/AgentInspector";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useWebSocket } from "@/hooks/useWebSocket";
import { apiFetch } from "@/lib/utils";
import type { DeviceState, AgentInfo, SimulationStatus, Scenario } from "@/types";

export default function SimDashboard() {
  const [devices, setDevices] = useState<DeviceState[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [simStatus, setSimStatus] = useState<SimulationStatus | null>(null);

  const fetchAll = async () => {
    try {
      const [devData, agData, simData] = await Promise.all([
        apiFetch<DeviceState[]>("/devices/flat"),
        apiFetch<AgentInfo[]>("/agents"),
        apiFetch<SimulationStatus>("/simulation/status"),
      ]);
      setDevices(devData);
      setAgents(agData);
      setSimStatus(simData);
    } catch (e) {
      console.error("Fetch failed:", e);
    }
  };

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 8000);
    return () => clearInterval(id);
  }, []);

  const { connected } = useWebSocket({
    device_state: useCallback((msg: any) => {
      setDevices((prev) => prev.map((d) => d.device_id === msg.data.device_id ? msg.data : d));
    }, []),
    agent_action: useCallback(() => {
      apiFetch<AgentInfo[]>("/agents").then(setAgents).catch(() => {});
    }, []),
    simulation_override: useCallback(() => {
      apiFetch<SimulationStatus>("/simulation/status").then(setSimStatus).catch(() => {});
    }, []),
    scenario_active: useCallback(() => {
      apiFetch<SimulationStatus>("/simulation/status").then(setSimStatus).catch(() => {});
    }, []),
    scenario_stopped: useCallback(() => {
      apiFetch<SimulationStatus>("/simulation/status").then(setSimStatus).catch(() => {});
    }, []),
  });

  const clearAll = async () => {
    await apiFetch("/simulation/overrides", { method: "DELETE" });
    fetchAll();
  };

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Settings className="w-5 h-5 text-orange-400" />
          <h1 className="text-lg font-bold">Simulation Control</h1>
        </div>
        <div className="flex items-center gap-2">
          {simStatus?.active_scenario && (
            <Badge variant="warning">
              Scenario: {simStatus.active_scenario.replace(/_/g, " ")}
            </Badge>
          )}
          <Badge variant={connected ? "success" : "destructive"} className="gap-1">
            {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {connected ? "Live" : "Disconnected"}
          </Badge>
          <Button size="sm" variant="outline" onClick={clearAll}>
            <Trash2 className="w-3 h-3 mr-1" /> Clear All
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {/* Scenarios */}
        <ScenarioRunner
          scenarios={simStatus?.available_scenarios || []}
          activeScenario={simStatus?.active_scenario || null}
          onUpdate={fetchAll}
        />

        {/* Environment Controls */}
        <WeatherInjector />
        <GridControl />
        <GPSControl />
        <BatteryControl />
        <DeviceFailure devices={devices} />

        {/* Inspection */}
        <div className="md:col-span-2 xl:col-span-2">
          <EventLog />
        </div>
        <AgentInspector agents={agents} onRefresh={fetchAll} />
      </div>
    </div>
  );
}
