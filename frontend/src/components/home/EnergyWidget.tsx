import { useEffect, useRef, useState } from "react";
import { animate, createScope } from "animejs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatWatts } from "@/lib/utils";
import type { EnergyData } from "@/types";

interface Props {
  energy: EnergyData | null;
}

/* ── Animated number counter ── */
function AnimatedStat({ value, format }: { value: number; format?: "watts" | "pct" }) {
  const [display, setDisplay] = useState(value);
  const objRef = useRef({ v: value });

  useEffect(() => {
    const from = objRef.current.v;
    if (Math.abs(from - value) < 0.5) { setDisplay(value); objRef.current.v = value; return; }
    animate(objRef.current, {
      v: value, duration: 700, ease: "out(4)",
      onUpdate: () => setDisplay(objRef.current.v),
    });
  }, [value]);

  if (format === "watts") return <>{formatWatts(Math.abs(display))}</>;
  if (format === "pct") return <>{display.toFixed(0)}%</>;
  return <>{display.toFixed(1)}</>;
}

/* ── Battery SVG with liquid fill (wave constrained inside clip so it doesn't escape) ── */
function BatterySvg({ pct, mode }: { pct: number; mode: string }) {
  const fillColor = pct > 50 ? "#22c55e" : pct > 20 ? "#eab308" : "#ef4444";
  const fillH = Math.max(0, 24 * pct * 0.01);
  const wy = Math.max(6, Math.min(30, 30 - fillH)); // liquid surface y (clip is 6..30)
  // Wave path entirely inside clip: ripple stays at or below wy so nothing escapes
  const wavePath = `M7 30 L7 ${wy} Q11 ${wy + 0.5} 16 ${wy + 0.15} Q20 ${wy + 0.6} 25 ${wy} L25 30 Z`;
  return (
    <svg viewBox="0 0 32 36" className="w-9 h-10 shrink-0">
      <rect x="11" y="1" width="10" height="3" rx="1.5" fill="#52525b" />
      <rect x="5" y="4" width="22" height="28" rx="3" fill="none" stroke={fillColor} strokeWidth="1.5" />
      <defs><clipPath id="ew-bc"><rect x="7" y="6" width="18" height="24" rx="1.5" /></clipPath></defs>
      <g clipPath="url(#ew-bc)">
        <path d={wavePath} fill={fillColor} opacity="0.4">
          <animateTransform attributeName="transform" type="translate" values="-0.6,0;0.6,0;-0.6,0" dur="2.5s" repeatCount="indefinite" />
        </path>
      </g>
      {pct > 0 && pct < 100 && (
        <path d="M18 12 L15 19 L18 19 L15 26" fill="none" stroke={fillColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.5">
          <animate attributeName="opacity" values="0.3;0.7;0.3" dur="1.5s" repeatCount="indefinite" />
        </path>
      )}
    </svg>
  );
}

/* ── Solar sunburst SVG ── */
function SolarSvg({ watts }: { watts: number }) {
  const intensity = Math.min(1, watts / 3000);
  const rayLen = 3 + intensity * 5;
  const c = watts > 0 ? "#f59e0b" : "#52525b";
  return (
    <svg viewBox="0 0 32 32" className="w-9 h-9 shrink-0">
      <circle cx="16" cy="16" r="6" fill={watts > 0 ? "rgba(245,158,11,0.15)" : "none"} stroke={c} strokeWidth="1.5"
        style={watts > 0 ? { filter: "drop-shadow(0 0 4px rgba(245,158,11,0.4))" } : undefined} />
      {[0,45,90,135,180,225,270,315].map((deg) => (
        <line key={deg} x1="16" y1={10 - rayLen} x2="16" y2={10 - rayLen - 2}
          stroke={c} strokeWidth="1.5" strokeLinecap="round"
          transform={`rotate(${deg} 16 16)`} opacity={watts > 0 ? undefined : "0.3"}>
          {watts > 0 && (
            <animate attributeName="opacity" values={`${0.3 + intensity * 0.2};${0.7 + intensity * 0.3};${0.3 + intensity * 0.2}`} dur="2s" begin={`${deg * 0.01}s`} repeatCount="indefinite" />
          )}
        </line>
      ))}
      {watts > 0 && (
        <circle cx="16" cy="16" r="10" fill="none" stroke="rgba(245,158,11,0.1)" strokeWidth="1">
          <animate attributeName="r" values="8;12;8" dur="3s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.3;0.08;0.3" dur="3s" repeatCount="indefinite" />
        </circle>
      )}
    </svg>
  );
}

/* ── Grid arrow SVG (pulsing) ── */
function GridArrowSvg({ exporting }: { exporting: boolean }) {
  const c = exporting ? "#22c55e" : "#f97316";
  return (
    <svg viewBox="0 0 24 24" className="w-7 h-7 shrink-0">
      {exporting ? (
        <g>
          <path d="M12 18 L12 6" stroke={c} strokeWidth="2" strokeLinecap="round" />
          <path d="M7 11 L12 6 L17 11" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          <animate attributeName="opacity" values="0.5;1;0.5" dur="1.5s" repeatCount="indefinite" />
        </g>
      ) : (
        <g>
          <path d="M12 6 L12 18" stroke={c} strokeWidth="2" strokeLinecap="round" />
          <path d="M7 13 L12 18 L17 13" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          <animate attributeName="opacity" values="0.5;1;0.5" dur="1.5s" repeatCount="indefinite" />
        </g>
      )}
    </svg>
  );
}

/* ── Consumption arc ── */
function ConsumptionArc({ watts }: { watts: number }) {
  const maxW = 5000;
  const pct = Math.min(1, watts / maxW);
  const r = 11;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct);
  const c = pct < 0.4 ? "#22c55e" : pct < 0.7 ? "#eab308" : "#ef4444";
  return (
    <svg viewBox="0 0 28 28" className="w-8 h-8 shrink-0">
      <circle cx="14" cy="14" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="2.5" />
      <circle cx="14" cy="14" r={r} fill="none" stroke={c} strokeWidth="2.5"
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        style={{ transform: "rotate(-90deg)", transformOrigin: "center", transition: "stroke-dashoffset 0.6s cubic-bezier(0.33,1,0.68,1), stroke 0.4s" }} />
      {/* up arrow inside */}
      <path d="M14 18 L14 10" stroke={c} strokeWidth="1.5" strokeLinecap="round" opacity="0.7" />
      <path d="M11 13 L14 10 L17 13" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.7" />
    </svg>
  );
}

/* ── Energy flow particles ── */
function EnergyFlow({ solar, consumption }: { solar: number; consumption: number }) {
  const hasFlow = solar > 0 || consumption > 0;
  if (!hasFlow) return null;
  const flowRight = solar > 0;
  return (
    <svg viewBox="0 0 200 20" className="w-full h-5 mt-2 mb-1 opacity-60">
      {/* path track */}
      <path id="ew-flow" d="M10 10 Q50 4 100 10 Q150 16 190 10" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
      {/* particles */}
      {[0, 0.25, 0.5, 0.75].map((off, i) => (
        <circle key={i} r="2" fill={flowRight ? "#f59e0b" : "#3b82f6"} opacity="0.6">
          <animateMotion dur="2.5s" begin={`${off * 2.5}s`} repeatCount="indefinite"
            keyPoints={flowRight ? "0;1" : "1;0"} keyTimes="0;1" calcMode="linear">
            <mpath href="#ew-flow" />
          </animateMotion>
          <animate attributeName="opacity" values="0;0.7;0" dur="2.5s" begin={`${off * 2.5}s`} repeatCount="indefinite" />
        </circle>
      ))}
      {/* labels */}
      <text x="4" y="18" fill="rgba(255,255,255,0.15)" fontSize="5" fontFamily="sans-serif">
        {flowRight ? "☀ Solar" : "⚡ Grid"}
      </text>
      <text x="165" y="18" fill="rgba(255,255,255,0.15)" fontSize="5" fontFamily="sans-serif">
        {flowRight ? "🏠 Home" : "🏠 Home"}
      </text>
    </svg>
  );
}

/* ================================================================
   MAIN WIDGET
   ================================================================ */
export function EnergyWidget({ energy }: Props) {
  if (!energy) return null;

  const isExporting = energy.net_grid_watts < 0;

  return (
    <Card className="overflow-hidden min-w-[280px] sm:min-w-[300px]">
      <CardHeader className="pb-2 sm:pb-3 px-4 sm:px-6 pt-4 sm:pt-6">
        <CardTitle className="flex items-center gap-2 text-sm sm:text-base">
          <svg viewBox="0 0 20 20" className="w-4 h-4 sm:w-5 sm:h-5 shrink-0">
            <path d="M11 1 L5 11 L9 11 L8 19 L15 9 L11 9 Z" fill="#facc15" opacity="0.9" />
          </svg>
          Energy
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 sm:px-6 pb-4 sm:pb-6">
        {/* Energy flow animation */}
        <EnergyFlow solar={energy.solar_generation_watts} consumption={energy.total_consumption_watts} />

        <div className="grid grid-cols-2 gap-3 sm:gap-4">
          {/* Battery */}
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <BatterySvg pct={energy.battery_pct} mode={energy.battery_mode} />
            <div className="min-w-0">
              <p className="text-lg sm:text-xl font-bold leading-tight truncate" style={{ transition: "color 0.45s cubic-bezier(0.33,1,0.68,1)",
                color: energy.battery_pct > 50 ? "#4ade80" : energy.battery_pct > 20 ? "#facc15" : "#ef4444" }}>
                <AnimatedStat value={energy.battery_pct} format="pct" />
              </p>
              <p className="text-xs text-muted-foreground truncate">{energy.battery_mode}</p>
            </div>
          </div>

          {/* Solar */}
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <SolarSvg watts={energy.solar_generation_watts} />
            <div className="min-w-0">
              <p className="text-lg sm:text-xl font-bold leading-tight text-amber-400 truncate">
                <AnimatedStat value={energy.solar_generation_watts} format="watts" />
              </p>
              <p className="text-xs text-muted-foreground">solar</p>
            </div>
          </div>

          {/* Consumption */}
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <ConsumptionArc watts={energy.total_consumption_watts} />
            <div className="min-w-0">
              <p className="text-sm sm:text-base font-semibold truncate">
                <AnimatedStat value={energy.total_consumption_watts} format="watts" />
              </p>
              <p className="text-xs text-muted-foreground">using</p>
            </div>
          </div>

          {/* Grid */}
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <GridArrowSvg exporting={isExporting} />
            <div className="min-w-0">
              <p className="text-sm sm:text-base font-semibold truncate">
                <AnimatedStat value={Math.abs(energy.net_grid_watts)} format="watts" />
              </p>
              <p className="text-xs text-muted-foreground truncate">
                {isExporting ? "exporting" : "from grid"}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
