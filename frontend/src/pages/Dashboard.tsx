import { useState, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { Home, Send, Wifi, WifiOff } from "lucide-react";
import { DeviceCard } from "@/components/home/DeviceCard";
import { ThreatBanner } from "@/components/home/ThreatBanner";
import { EnergyWidget } from "@/components/home/EnergyWidget";
import { VoiceAlert } from "@/components/home/VoiceAlert";
import { PatternPanel } from "@/components/home/PatternPanel";
import { AgentActivity } from "@/components/home/AgentActivity";
import { VoiceChatButton } from "@/components/home/VoiceChatButton";
import { TimelineOverlay } from "@/components/sim/TimelineOverlay";
import { MetricsPanel } from "@/components/sim/MetricsPanel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useWebSocket } from "@/hooks/useWebSocket";
import { apiFetch } from "@/lib/utils";
import type { DeviceState, EnergyData, ThreatAssessment, AgentInfo, VoiceAlert as VoiceAlertType, Pattern, RoomDevices, ScenarioStep } from "@/types";

const ROOM_LABELS: Record<string, string> = {
  living_room: "Living Room",
  bedroom: "Bedroom",
  kitchen: "Kitchen",
  office: "Office",
  front_door: "Front Door",
  utility_room: "Utility Room",
  energy_system: "Energy System",
};

export default function Dashboard() {
  const [rooms, setRooms] = useState<Record<string, RoomDevices>>({});
  const [energy, setEnergy] = useState<EnergyData | null>(null);
  const [threat, setThreat] = useState<ThreatAssessment | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [voiceAlert, setVoiceAlert] = useState<VoiceAlertType | null>(null);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [command, setCommand] = useState("");
  const [commandLoading, setCommandLoading] = useState(false);

  // Temporal scenario state (shows on home dashboard too)
  const [currentStep, setCurrentStep] = useState<ScenarioStep | null>(null);
  const [scenarioName, setScenarioName] = useState<string | null>(null);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [finalMetrics, setFinalMetrics] = useState<Record<string, string>>({});
  const [showMetrics, setShowMetrics] = useState(false);

  // Initial data fetch
  useEffect(() => {
    const load = async () => {
      try {
        const [devData, enData, agData, ptData] = await Promise.all([
          apiFetch<Record<string, RoomDevices>>("/devices"),
          apiFetch<EnergyData>("/devices/energy"),
          apiFetch<AgentInfo[]>("/agents"),
          apiFetch<Pattern[]>("/patterns"),
        ]);
        setRooms(devData);
        setEnergy(enData);
        setAgents(agData);
        setPatterns(ptData);
      } catch (e) {
        console.error("Initial load failed:", e);
      }
    };
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, []);

  // WebSocket handlers
  const { connected } = useWebSocket({
    initial_state: useCallback((msg: any) => {
      if (msg.data.devices) setRooms(msg.data.devices);
      if (msg.data.energy) setEnergy(msg.data.energy);
      if (msg.data.agents) setAgents(msg.data.agents);
    }, []),
    device_state: useCallback((msg: any) => {
      const device: DeviceState = msg.data;
      setRooms((prev) => {
        const next = { ...prev };
        const room = next[device.room];
        if (room) {
          next[device.room] = {
            devices: room.devices.map((d) =>
              d.device_id === device.device_id ? device : d
            ),
          };
        }
        return next;
      });
    }, []),
    energy_summary: useCallback((msg: any) => setEnergy(msg.data), []),
    threat_assessment: useCallback((msg: any) => setThreat(msg.data), []),
    voice_alert: useCallback((msg: any) => setVoiceAlert(msg.data), []),
    agent_action: useCallback(() => {
      apiFetch<AgentInfo[]>("/agents").then(setAgents).catch(() => {});
    }, []),
    pattern_suggestion: useCallback(() => {
      apiFetch<Pattern[]>("/patterns").then(setPatterns).catch(() => {});
    }, []),
    // Temporal scenario events
    scenario_active: useCallback((msg: any) => {
      if (msg.data.temporal) {
        setScenarioName(msg.data.name);
        setScenarioId(msg.data.scenario_id);
        setFinalMetrics({});
        setShowMetrics(false);
        setCurrentStep(null);
      }
    }, []),
    scenario_step: useCallback((msg: any) => {
      const step: ScenarioStep = msg.data;
      setCurrentStep(step);
      if (step.metrics && Object.keys(step.metrics).length > 0) {
        setFinalMetrics((prev) => ({ ...prev, ...step.metrics }));
      }
      if (step.is_last) {
        setShowMetrics(true);
      }
    }, []),
    scenario_complete: useCallback(() => {
      setTimeout(() => {
        setCurrentStep(null);
        setScenarioName(null);
        setScenarioId(null);
        setShowMetrics(false);
        setFinalMetrics({});
      }, 25000);
    }, []),
    scenario_stopped: useCallback(() => {
      setCurrentStep(null);
      setScenarioName(null);
      setScenarioId(null);
      setFinalMetrics({});
      setShowMetrics(false);
    }, []),
  });

  const [commandFeedback, setCommandFeedback] = useState<string | null>(null);

  const sendCommand = async (text?: string) => {
    const cmd = text ?? command;
    if (!cmd.trim()) return;
    setCommandLoading(true);
    setCommandFeedback(null);
    try {
      const res = await apiFetch<{ success: boolean; error?: string; unclear?: boolean; message?: string }>("/commands", {
        method: "POST",
        body: JSON.stringify({ command: cmd, source: text ? "voice" : "text" }),
      });
      if (res.unclear && res.message) {
        setCommandFeedback(res.message);
      } else {
        setCommandFeedback(null);
      }
      // Audio feedback (for voice) and alerts are handled via WebSocket voice_alert events
      if (!text) setCommand("");
    } catch (e) {
      console.error("Command failed:", e);
    }
    setCommandLoading(false);
  };

  const handleVoiceTranscript = useCallback((text: string) => {
    sendCommand(text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Home className="w-5 h-5 text-primary" />
          <h1 className="text-lg font-bold">Smart Home</h1>
        </div>
        <Badge variant={connected ? "success" : "destructive"} className="gap-1">
          {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
          {connected ? "Live" : "Disconnected"}
        </Badge>
      </div>

      {/* Timeline Overlay for Temporal Scenarios */}
      <TimelineOverlay step={currentStep} scenarioName={scenarioName} />

      {/* Final Metrics Panel */}
      {showMetrics && (
        <div className="mb-4">
          <MetricsPanel
            metrics={finalMetrics}
            scenarioId={scenarioId}
            visible={showMetrics}
          />
        </div>
      )}

      {/* Threat Banner */}
      <div className="mb-6">
        <ThreatBanner threat={threat} />
      </div>

      {/* Command Bar */}
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendCommand()}
          placeholder='Ask anything... "Turn off all lights" or hold 🎤 to speak'
          className="flex-1 h-9 px-3 text-sm bg-muted border border-border rounded-md placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <Button size="default" onClick={() => sendCommand()} disabled={commandLoading}>
          <Send className="w-4 h-4" />
        </Button>
        <VoiceChatButton
          onTranscript={handleVoiceTranscript}
          disabled={commandLoading}
          compact
        />
      </div>

      {/* Feedback message when command is not understood */}
      {commandFeedback && (
        <div className="mb-4 p-3 rounded-md bg-yellow-500/10 border border-yellow-500/30 text-yellow-200 text-sm flex items-center gap-2">
          <span>⚠️</span>
          <span>{commandFeedback}</span>
          <button onClick={() => setCommandFeedback(null)} className="ml-auto text-yellow-400 hover:text-yellow-200 text-xs">✕</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Devices Grid (3 columns) */}
        <div className="lg:col-span-3 space-y-6">
          {Object.entries(rooms).map(([roomId, roomData]) => (
            <motion.div
              key={roomId}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <h2 className="text-sm font-semibold text-muted-foreground mb-3">
                {ROOM_LABELS[roomId] || roomId}
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {roomData.devices.map((device) => (
                  <DeviceCard key={device.device_id} device={device} />
                ))}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Sidebar (1 column) */}
        <div className="space-y-4">
          <EnergyWidget energy={energy} />
          <PatternPanel patterns={patterns} onUpdate={() => apiFetch<Pattern[]>("/patterns").then(setPatterns)} />
          <AgentActivity agents={agents} />
        </div>
      </div>

      {/* Voice Alert Overlay */}
      <VoiceAlert alert={voiceAlert} onDismiss={() => setVoiceAlert(null)} />
    </div>
  );
}
