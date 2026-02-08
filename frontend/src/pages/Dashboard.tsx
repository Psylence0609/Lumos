import { useState, useCallback, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { createLayout, stagger } from "animejs";
import { Send, Wifi, WifiOff } from "lucide-react";
import { DeviceCard } from "@/components/home/DeviceCard";
import { ThreatBanner } from "@/components/home/ThreatBanner";
import { EnergyWidget } from "@/components/home/EnergyWidget";
import { VoiceAlert } from "@/components/home/VoiceAlert";
import { VoiceChatButton } from "@/components/home/VoiceChatButton";
import { LumosTitle } from "@/components/home/LumosTitle";
import { TimelineOverlay } from "@/components/sim/TimelineOverlay";
import { MetricsPanel } from "@/components/sim/MetricsPanel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useWebSocket } from "@/hooks/useWebSocket";
import { apiFetch } from "@/lib/utils";
import type { DeviceState, EnergyData, ThreatAssessment, VoiceAlert as VoiceAlertType, RoomDevices, ScenarioStep } from "@/types";

const ROOM_LABELS: Record<string, string> = {
  living_room: "Living Room",
  bedroom: "Bedroom",
  kitchen: "Kitchen",
  office: "Office",
  front_door: "Front Door",
  utility_room: "Utility Room",
  energy_system: "Energy System",
};

/* inject keyframes — transform/opacity only for 60fps compositor */
const cssId = "dash-anim-css";
const css = `
@keyframes dash-dot { 0%,80%,100%{transform:scale(0.6) translateZ(0);opacity:0.3} 40%{transform:scale(1) translateZ(0);opacity:1} }
@keyframes dash-wifi { 0%,100%{transform:scale(0.95) translateZ(0);opacity:0.5} 50%{transform:scale(1.05) translateZ(0);opacity:1} }
@keyframes dash-glow { 0%,100%{box-shadow:0 0 0 rgba(139,92,246,0)} 50%{box-shadow:0 0 12px rgba(139,92,246,0.25)} }
`;

export default function Dashboard() {
  const [rooms, setRooms] = useState<Record<string, RoomDevices>>({});
  const [energy, setEnergy] = useState<EnergyData | null>(null);
  const [threat, setThreat] = useState<ThreatAssessment | null>(null);
  const [voiceAlert, setVoiceAlert] = useState<VoiceAlertType | null>(null);
  const [command, setCommand] = useState("");
  const [commandLoading, setCommandLoading] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);
  const roomsContainerRef = useRef<HTMLDivElement>(null);
  const layoutRef = useRef<ReturnType<typeof createLayout> | null>(null);
  const prevLayoutKeyRef = useRef<string>("");

  /** Stable key for grid structure: when this changes we run layout.animate() */
  const getLayoutKey = useCallback((r: Record<string, RoomDevices>) => {
    return Object.entries(r)
      .map(([roomId, roomData]) => `${roomId}:${roomData.devices.map((d) => d.device_id).join(",")}`)
      .join("|");
  }, []);

  /* inject CSS */
  useEffect(() => {
    if (document.getElementById(cssId)) return;
    const s = document.createElement("style");
    s.id = cssId;
    s.textContent = css;
    document.head.appendChild(s);
  }, []);

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
        const [devData, enData] = await Promise.all([
          apiFetch<Record<string, RoomDevices>>("/devices"),
          apiFetch<EnergyData>("/devices/energy"),
        ]);
        setRooms(devData);
        setEnergy(enData);
      } catch (e) {
        console.error("Initial load failed:", e);
      }
    };
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, []);

  /* anime.js Layout: animate grid when rooms or device list changes (record → React re-render → animate) */
  useEffect(() => {
    const root = roomsContainerRef.current;
    if (!root) return;

    const layoutKey = getLayoutKey(rooms);
    if (layoutKey === "") return;

    if (!layoutRef.current) {
      layoutRef.current = createLayout(root, {
        duration: 500,
        ease: "out(4)",
        delay: stagger(40, { from: "first" }),
        enterFrom: {
          opacity: 0,
          transform: "translateY(14px) scale(0.99) translateZ(0)",
          duration: 420,
          ease: "out(4)",
        },
        leaveTo: {
          opacity: 0,
          transform: "translateY(-6px) scale(0.99) translateZ(0)",
          duration: 320,
          ease: "in(3)",
        },
      });
      layoutRef.current.record();
      prevLayoutKeyRef.current = layoutKey;
      return;
    }

    if (layoutKey === prevLayoutKeyRef.current) return;
    prevLayoutKeyRef.current = layoutKey;

    layoutRef.current.animate({
      duration: 500,
      ease: "out(4)",
      delay: stagger(40, { from: "first" }),
      onComplete: () => {
        layoutRef.current?.record();
      },
    });
  }, [rooms, getLayoutKey]);

  // WebSocket handlers
  const { connected } = useWebSocket({
    initial_state: useCallback((msg: any) => {
      if (msg.data.devices) setRooms(msg.data.devices);
      if (msg.data.energy) setEnergy(msg.data.energy);
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
    <div className="min-h-screen px-3 py-4 sm:p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header — title centred, status badge on right */}
      <div className="flex items-center justify-between gap-2 mb-4 sm:mb-6">
        <div className="flex-1 min-w-0 flex justify-center">
          <LumosTitle />
        </div>
        <Badge variant={connected ? "success" : "destructive"} className="gap-1 shrink-0 text-xs">
          {connected ? (
            <span style={{ animation: "dash-wifi 2s ease-in-out infinite", display: "inline-flex" }}>
              <Wifi className="w-3 h-3" />
            </span>
          ) : (
            <WifiOff className="w-3 h-3" />
          )}
          <span className="hidden sm:inline">{connected ? "Live" : "Disconnected"}</span>
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
      <div className="mb-4 sm:mb-6">
        <ThreatBanner threat={threat} />
      </div>

      {/* Command Bar — full width on mobile, 44px touch targets; stacks on narrow screens */}
      <div className="flex flex-col sm:flex-row gap-2 mb-4 sm:mb-6">
        <input
          type="text"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendCommand()}
          onFocus={() => setInputFocused(true)}
          onBlur={() => setInputFocused(false)}
          placeholder='Ask anything... or hold 🎤'
          className="flex-1 min-w-0 min-h-[44px] sm:min-h-0 h-10 sm:h-9 px-3 text-sm bg-muted border border-border rounded-md placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-ring transition-shadow duration-300 smooth-transition"
          style={inputFocused ? { animation: "dash-glow 1.5s ease-in-out infinite" } : undefined}
        />
        <div className="flex gap-2 shrink-0">
          <Button size="default" className="min-h-[44px] sm:min-h-0 h-11 sm:h-9 min-w-[44px] flex-1 sm:flex-initial" onClick={() => sendCommand()} disabled={commandLoading}>
            <Send className="w-4 h-4" />
          </Button>
          <VoiceChatButton
            onTranscript={handleVoiceTranscript}
            disabled={commandLoading}
            compact
          />
        </div>
      </div>

      {/* Typing indicator dots */}
      <AnimatePresence>
        {commandLoading && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.35, ease: [0.33, 1, 0.68, 1] }}
            className="flex items-center gap-1.5 mb-4 pl-1"
          >
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-primary/60"
                style={{ animation: `dash-dot 1.2s ${i * 0.15}s ease-in-out infinite` }}
              />
            ))}
            <span className="text-[10px] text-muted-foreground ml-1">Processing…</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Feedback message — slide-in from left */}
      <AnimatePresence>
        {commandFeedback && (
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.35, ease: [0.33, 1, 0.68, 1] }}
            className="mb-4 p-3 rounded-md bg-yellow-500/10 border border-yellow-500/30 text-yellow-200 text-sm flex items-center gap-2"
          >
            <span>⚠️</span>
            <span>{commandFeedback}</span>
            <button onClick={() => setCommandFeedback(null)} className="ml-auto text-yellow-400 hover:text-yellow-200 text-xs">✕</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Mobile: sidebar widgets as horizontal scrollable strip — narrow cards on small phones */}
      <div className="lg:hidden mb-4 sm:mb-6 -mx-3 sm:-mx-4 px-3 sm:px-4">
        <div className="flex gap-2 sm:gap-3 overflow-x-auto pb-3 snap-x snap-mandatory scrollbar-hide -webkit-overflow-scrolling-touch">
          <div className="min-w-[280px] sm:min-w-[300px] max-w-[85vw] sm:max-w-[340px] snap-start shrink-0"><EnergyWidget energy={energy} /></div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 sm:gap-6">
        {/* Devices Grid — 2 cols on xs (bigger touch), 3 sm, 4 md+ */}
        <div ref={roomsContainerRef} className="layout-animate-root lg:col-span-3 space-y-4 sm:space-y-6">
          {Object.entries(rooms).map(([roomId, roomData]) => (
            <div key={roomId} data-room={roomId}>
              <h2 className="text-xs sm:text-sm font-semibold mb-2 sm:mb-3" style={{ color: 'var(--color-room-label)' }}>
                {ROOM_LABELS[roomId] || roomId}
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 sm:gap-3">
                {roomData.devices.map((device) => (
                  <DeviceCard key={device.device_id} device={device} />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Sidebar (1 column) — hidden on mobile (shown above as scroll strip) */}
        <div className="hidden lg:block space-y-4">
          <EnergyWidget energy={energy} />
        </div>
      </div>

      {/* Voice Alert Overlay */}
      <VoiceAlert alert={voiceAlert} onDismiss={() => setVoiceAlert(null)} />
    </div>
  );
}
