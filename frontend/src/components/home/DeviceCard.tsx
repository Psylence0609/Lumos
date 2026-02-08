import { useEffect, useId, useRef, useState } from "react";
import { motion } from "framer-motion";
import { animate, stagger, createScope } from "animejs";
import { Lock, LockOpen } from "lucide-react";
import { cn, formatWatts, apiFetch } from "@/lib/utils";
import type { DeviceState } from "@/types";

/* ================================================================
   COLOUR PALETTE  — unique per device type
   ================================================================ */
const COLORS = {
  light: { on: "#fbbf24", off: "#52525b" },          // amber‑400 (dynamic RGB overrides when available)
  coffee_maker: { on: "#ea580c", off: "#52525b" },    // orange‑600
  smart_plug: { on: "#22d3ee", off: "#64748b" },      // cyan‑400
  thermostat: { cold: "#3b82f6", mid: "#22c55e", hot: "#ef4444" }, // blue / green / red
  lock: { locked: "#10b981", unlocked: "#f97316" },   // emerald‑500 / orange‑500
  battery: { high: "#22c55e", mid: "#eab308", low: "#ef4444" },
  sensor: { on: "#06b6d4", off: "#52525b" },          // cyan‑500
  default: { on: "#4ade80", off: "#52525b" },
};

/* ================================================================
   CUSTOM SVG ICONS  (48×48 viewBox, inline, ON / OFF states)
   ================================================================ */

type LightKind = "ceiling" | "ambient" | "nightstand" | "desk";

function detectLightKind(name: string): LightKind {
  const s = name.toLowerCase();
  if (s.includes("ambient") || s.includes("mood") || s.includes("led") || s.includes("strip")) return "ambient";
  if (s.includes("nightstand") || s.includes("bedside") || s.includes("night")) return "nightstand";
  if (s.includes("desk") || s.includes("task") || s.includes("reading")) return "desk";
  return "ceiling";
}

/* ── Ceiling / Main Light ── flush‑mount fixture with light cone */
function SvgCeilingLight({ on, r, g, b }: { on: boolean; r: number; g: number; b: number }) {
  const c = on ? `rgb(${r},${g},${b})` : COLORS.light.off;
  const glow = `rgba(${r},${g},${b},0.6)`;
  return (
    <svg viewBox="0 0 48 48" className="w-12 h-12">
      {/* ceiling rod */}
      <line x1="24" y1="0" x2="24" y2="8" stroke={c} strokeWidth="2" strokeLinecap="round" opacity="0.5" />
      {/* canopy */}
      <ellipse cx="24" cy="8" rx="6" ry="2" fill={c} opacity="0.4" />
      {/* shade */}
      <path d="M14 14 Q14 10 24 10 Q34 10 34 14 L38 26 Q38 30 24 30 Q10 30 10 26 Z"
        fill={on ? `rgba(${r},${g},${b},0.12)` : "none"} stroke={c} strokeWidth="2" strokeLinejoin="round"
        style={on ? { filter: `drop-shadow(0 0 8px ${glow})` } : undefined} />
      {/* light cone when on */}
      {on && (
        <path d="M12 30 L4 46 L44 46 L36 30" fill={`rgba(${r},${g},${b},0.06)`} />
      )}
      {/* rays */}
      {on && [0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
        <line key={deg} className="dc-ray"
          x1="24" y1="20" x2="24" y2="6"
          stroke={`rgba(${r},${g},${b},0.45)`} strokeWidth="1.2" strokeLinecap="round"
          transform={`rotate(${deg} 24 20)`} opacity="0" />
      ))}
    </svg>
  );
}

/* ── Ambient / LED strip light ── horizontal bar with glow */
function SvgAmbientLight({ on, r, g, b }: { on: boolean; r: number; g: number; b: number }) {
  const c = on ? `rgb(${r},${g},${b})` : COLORS.light.off;
  const glow = `rgba(${r},${g},${b},0.5)`;
  return (
    <svg viewBox="0 0 48 48" className="w-12 h-12">
      {/* LED strip bar */}
      <rect x="4" y="20" width="40" height="8" rx="4" fill={on ? `rgba(${r},${g},${b},0.15)` : "none"}
        stroke={c} strokeWidth="2"
        style={on ? { filter: `drop-shadow(0 0 10px ${glow})` } : undefined} />
      {/* LED dots */}
      {[10, 18, 24, 30, 38].map((x) => (
        <circle key={x} cx={x} cy="24" r="1.5"
          fill={on ? `rgb(${r},${g},${b})` : c} opacity={on ? 0.9 : 0.3} />
      ))}
      {/* glow halo top */}
      {on && <ellipse cx="24" cy="18" rx="20" ry="8" fill={`rgba(${r},${g},${b},0.05)`} />}
      {/* glow halo bottom */}
      {on && <ellipse cx="24" cy="30" rx="20" ry="8" fill={`rgba(${r},${g},${b},0.05)`} />}
      {/* rays */}
      {on && [0, 60, 120, 180, 240, 300].map((deg) => (
        <line key={deg} className="dc-ray"
          x1="24" y1="24" x2="24" y2="10"
          stroke={`rgba(${r},${g},${b},0.35)`} strokeWidth="1" strokeLinecap="round"
          transform={`rotate(${deg} 24 24)`} opacity="0" />
      ))}
    </svg>
  );
}

/* ── Nightstand / Bedside lamp ── classic table lamp with shade */
function SvgNightstandLight({ on, r, g, b }: { on: boolean; r: number; g: number; b: number }) {
  const c = on ? `rgb(${r},${g},${b})` : COLORS.light.off;
  const glow = `rgba(${r},${g},${b},0.6)`;
  return (
    <svg viewBox="0 0 48 48" className="w-12 h-12">
      {/* base */}
      <ellipse cx="24" cy="44" rx="10" ry="3" fill={c} opacity="0.4" />
      {/* stem */}
      <rect x="22" y="30" width="4" height="14" rx="2" fill={c} opacity="0.5" />
      {/* shade (trapezoid) */}
      <path d="M12 30 L16 12 L32 12 L36 30 Z"
        fill={on ? `rgba(${r},${g},${b},0.12)` : "none"} stroke={c} strokeWidth="2" strokeLinejoin="round"
        style={on ? { filter: `drop-shadow(0 0 8px ${glow})` } : undefined} />
      {/* bulb visible through shade */}
      {on && <ellipse cx="24" cy="22" rx="4" ry="5" fill={`rgba(${r},${g},${b},0.2)`} />}
      {/* warm glow above */}
      {on && <ellipse cx="24" cy="8" rx="12" ry="6" fill={`rgba(${r},${g},${b},0.06)`} />}
      {/* rays */}
      {on && [0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
        <line key={deg} className="dc-ray"
          x1="24" y1="20" x2="24" y2="8"
          stroke={`rgba(${r},${g},${b},0.4)`} strokeWidth="1" strokeLinecap="round"
          transform={`rotate(${deg} 24 20)`} opacity="0" />
      ))}
    </svg>
  );
}

/* ── Desk / Task lamp ── angled arm lamp */
function SvgDeskLight({ on, r, g, b }: { on: boolean; r: number; g: number; b: number }) {
  const c = on ? `rgb(${r},${g},${b})` : COLORS.light.off;
  const glow = `rgba(${r},${g},${b},0.6)`;
  return (
    <svg viewBox="0 0 48 48" className="w-12 h-12">
      {/* base */}
      <ellipse cx="14" cy="44" rx="10" ry="3" fill={c} opacity="0.4" />
      {/* lower arm */}
      <line x1="14" y1="44" x2="20" y2="26" stroke={c} strokeWidth="2.5" strokeLinecap="round" />
      {/* joint */}
      <circle cx="20" cy="26" r="2" fill={c} opacity="0.5" />
      {/* upper arm */}
      <line x1="20" y1="26" x2="34" y2="12" stroke={c} strokeWidth="2.5" strokeLinecap="round" />
      {/* lamp head */}
      <path d="M28 14 L40 8 L42 14 L30 18 Z"
        fill={on ? `rgba(${r},${g},${b},0.15)` : "none"} stroke={c} strokeWidth="2" strokeLinejoin="round"
        style={on ? { filter: `drop-shadow(0 0 6px ${glow})` } : undefined} />
      {/* light cone */}
      {on && <path d="M30 18 L26 38 L46 38 L42 14" fill={`rgba(${r},${g},${b},0.05)`} />}
      {/* rays from head */}
      {on && [200, 220, 240, 260].map((deg) => (
        <line key={deg} className="dc-ray"
          x1="36" y1="14" x2="36" y2="2"
          stroke={`rgba(${r},${g},${b},0.4)`} strokeWidth="1" strokeLinecap="round"
          transform={`rotate(${deg} 36 14)`} opacity="0" />
      ))}
    </svg>
  );
}

const LIGHT_SVG_MAP: Record<LightKind, React.FC<{ on: boolean; r: number; g: number; b: number }>> = {
  ceiling: SvgCeilingLight,
  ambient: SvgAmbientLight,
  nightstand: SvgNightstandLight,
  desk: SvgDeskLight,
};

type CoffeePhase = "off" | "brewing" | "ready";

function SvgCoffeeCup({ phase }: { phase: CoffeePhase }) {
  const active = phase !== "off";
  const c = active ? COLORS.coffee_maker.on : COLORS.coffee_maker.off;

  return (
    <div className="relative w-12 h-12">
      {/* ── Layer 1: Brewing state (cup with rising liquid, vigorous steam) ── */}
      <svg
        viewBox="0 0 48 48"
        className="absolute inset-0 w-12 h-12 overflow-visible"
        style={{
          opacity: phase === "brewing" ? 1 : 0,
          transition: "opacity 0.5s cubic-bezier(0.33,1,0.68,1)",
          pointerEvents: "none",
        }}
      >
        {/* vigorous steam */}
        {[14, 22, 30].map((x, i) => (
          <path
            key={i}
            className="dc-steam"
            d={`M${x} 14 Q${x - 3} 8 ${x} 2`}
            fill="none"
            stroke="rgba(234,88,12,0.35)"
            strokeWidth="2.5"
            strokeLinecap="round"
            opacity="0.8"
          />
        ))}
        {/* saucer */}
        <ellipse cx="22" cy="44" rx="18" ry="3" fill={c} opacity="0.2" />
        {/* cup body */}
        <path d="M8 18 L12 42 L32 42 L36 18 Z"
          fill="rgba(234,88,12,0.08)" stroke={c} strokeWidth="2" strokeLinejoin="round" />
        {/* liquid rising */}
        <path
          className="dc-liquid"
          d="M11 30 Q16 32 22 30 Q28 28 33 30 L32 42 L12 42 Z"
          fill="rgba(154,52,18,0.4)"
        />
        {/* handle */}
        <path d="M36 22 Q44 22 44 30 Q44 38 36 38"
          fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" />
        {/* loading dots */}
        {[16, 22, 28].map((cx, i) => (
          <circle key={i} cx={cx} cy="36" r="1.2" fill={c} opacity="0.4">
            <animate attributeName="opacity" values="0.2;0.7;0.2" dur="1s" begin={`${i * 0.25}s`} repeatCount="indefinite" />
          </circle>
        ))}
      </svg>

      {/* ── Layer 2: Ready state (full cup, gentle steam, checkmark) ── */}
      <svg
        viewBox="0 0 48 48"
        className="absolute inset-0 w-12 h-12 overflow-visible"
        style={{
          opacity: phase === "ready" ? 1 : 0,
          transform: phase === "ready" ? "scale(1)" : "scale(0.9)",
          transition: "opacity 0.5s cubic-bezier(0.33,1,0.68,1), transform 0.5s cubic-bezier(0.34,1.56,0.64,1)",
          pointerEvents: "none",
        }}
      >
        {/* gentle lazy steam wisps */}
        {[16, 22, 28].map((x, i) => (
          <path
            key={i}
            d={`M${x} 14 Q${x - 2} 9 ${x + 1} 4`}
            fill="none"
            stroke="rgba(200,200,200,0.3)"
            strokeWidth="1.5"
            strokeLinecap="round"
          >
            <animate attributeName="opacity" values="0.1;0.4;0.1" dur={`${2 + i * 0.4}s`} repeatCount="indefinite" />
            <animate attributeName="d"
              values={`M${x} 14 Q${x-2} 9 ${x+1} 4;M${x} 14 Q${x+2} 9 ${x-1} 4;M${x} 14 Q${x-2} 9 ${x+1} 4`}
              dur={`${2.5 + i * 0.3}s`} repeatCount="indefinite" />
          </path>
        ))}
        {/* saucer */}
        <ellipse cx="22" cy="44" rx="18" ry="3" fill={c} opacity="0.25" />
        {/* cup body */}
        <path d="M8 18 L12 42 L32 42 L36 18 Z"
          fill="rgba(234,88,12,0.1)" stroke={c} strokeWidth="2" strokeLinejoin="round" />
        {/* full coffee liquid */}
        <path
          d="M9.5 22 Q16 24 22 22 Q28 20 34.5 22 L32 42 L12 42 Z"
          fill="rgba(120,53,15,0.55)"
        />
        {/* crema / foam line */}
        <path d="M9.5 22 Q16 24 22 22 Q28 20 34.5 22" fill="none"
          stroke="rgba(217,119,6,0.5)" strokeWidth="1.5" strokeLinecap="round" />
        {/* handle */}
        <path d="M36 22 Q44 22 44 30 Q44 38 36 38"
          fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" />
        {/* small check badge */}
        <circle cx="36" cy="14" r="5" fill="#22c55e" opacity="0.9" />
        <path d="M33.5 14 L35.5 16 L38.5 12" fill="none" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>

      {/* ── Layer 0: OFF state (grey outline) ── */}
      <svg
        viewBox="0 0 48 48"
        className="absolute inset-0 w-12 h-12 overflow-visible"
        style={{
          opacity: phase === "off" ? 1 : 0,
          transition: "opacity 0.4s cubic-bezier(0.33,1,0.68,1)",
          pointerEvents: "none",
        }}
      >
        <ellipse cx="22" cy="44" rx="18" ry="3" fill={COLORS.coffee_maker.off} opacity="0.2" />
        <path d="M8 18 L12 42 L32 42 L36 18 Z"
          fill="none" stroke={COLORS.coffee_maker.off} strokeWidth="2" strokeLinejoin="round" />
        <path d="M36 22 Q44 22 44 30 Q44 38 36 38"
          fill="none" stroke={COLORS.coffee_maker.off} strokeWidth="2" strokeLinecap="round" />
      </svg>
    </div>
  );
}

/* ────────────────────────────────────────
   SMART PLUG — appliance detection + icons
   ──────────────────────────────────────── */

type Appliance = "tv" | "fridge" | "computer" | "generic";

function detectAppliance(name: string, id: string): Appliance {
  const s = `${name} ${id}`.toLowerCase();
  if (s.includes("tv") || s.includes("television")) return "tv";
  if (s.includes("fridge") || s.includes("refrigerator")) return "fridge";
  if (s.includes("computer") || s.includes("pc") || s.includes("monitor") || s.includes("desktop")) return "computer";
  return "generic";
}

/* Mini appliance SVGs shown when ON (plugged in) */
function ApplianceTV({ c }: { c: string }) {
  return (
    <g>
      {/* screen */}
      <rect x="8" y="6" width="32" height="22" rx="2" fill="rgba(34,211,238,0.08)" stroke={c} strokeWidth="2" />
      {/* screen shine */}
      <line x1="12" y1="10" x2="20" y2="10" stroke={c} strokeWidth="1" opacity="0.3" strokeLinecap="round" />
      {/* stand neck */}
      <rect x="21" y="28" width="6" height="6" fill={c} opacity="0.5" />
      {/* stand base */}
      <rect x="14" y="34" width="20" height="3" rx="1.5" fill={c} opacity="0.6" />
      {/* power dot */}
      <circle cx="24" cy="40" r="1.5" fill={c} opacity="0.4" />
      {/* play icon on screen */}
      <path d="M20 14 L20 22 L28 18 Z" fill={c} opacity="0.25" />
    </g>
  );
}

function ApplianceFridge({ c }: { c: string }) {
  return (
    <g>
      {/* body */}
      <rect x="12" y="4" width="24" height="40" rx="3" fill="rgba(34,211,238,0.06)" stroke={c} strokeWidth="2" />
      {/* door split line */}
      <line x1="12" y1="20" x2="36" y2="20" stroke={c} strokeWidth="1.5" opacity="0.5" />
      {/* top door handle */}
      <line x1="30" y1="10" x2="30" y2="17" stroke={c} strokeWidth="2.5" strokeLinecap="round" opacity="0.6" />
      {/* bottom door handle */}
      <line x1="30" y1="24" x2="30" y2="34" stroke={c} strokeWidth="2.5" strokeLinecap="round" opacity="0.6" />
      {/* cold indicator */}
      <circle cx="20" cy="12" r="2" fill={c} opacity="0.2">
        <animate attributeName="opacity" values="0.1;0.4;0.1" dur="2s" repeatCount="indefinite" />
      </circle>
    </g>
  );
}

function ApplianceComputer({ c }: { c: string }) {
  return (
    <g>
      {/* monitor */}
      <rect x="10" y="4" width="28" height="20" rx="2" fill="rgba(34,211,238,0.08)" stroke={c} strokeWidth="2" />
      {/* screen content lines */}
      <line x1="14" y1="10" x2="26" y2="10" stroke={c} strokeWidth="1" opacity="0.25" strokeLinecap="round" />
      <line x1="14" y1="14" x2="22" y2="14" stroke={c} strokeWidth="1" opacity="0.2" strokeLinecap="round" />
      <line x1="14" y1="18" x2="30" y2="18" stroke={c} strokeWidth="1" opacity="0.15" strokeLinecap="round" />
      {/* stand */}
      <rect x="20" y="24" width="8" height="4" fill={c} opacity="0.4" />
      <rect x="16" y="28" width="16" height="2" rx="1" fill={c} opacity="0.5" />
      {/* keyboard */}
      <rect x="10" y="34" width="28" height="6" rx="2" fill="rgba(34,211,238,0.05)" stroke={c} strokeWidth="1.5" opacity="0.6" />
      {/* keys */}
      {[14,18,22,26,30,34].map((x) => (
        <rect key={x} x={x} y="36" width="2" height="2" rx="0.5" fill={c} opacity="0.3" />
      ))}
    </g>
  );
}

function ApplianceGeneric({ c }: { c: string }) {
  return (
    <g>
      {/* power symbol circle */}
      <circle cx="24" cy="22" r="12" fill="none" stroke={c} strokeWidth="2" opacity="0.6" />
      {/* power symbol line */}
      <line x1="24" y1="10" x2="24" y2="22" stroke={c} strokeWidth="2.5" strokeLinecap="round" opacity="0.7" />
      {/* small plug icon at bottom */}
      <rect x="20" y="38" width="8" height="4" rx="1" fill={c} opacity="0.3" />
      <rect x="22" y="42" width="1.5" height="3" rx="0.5" fill={c} opacity="0.3" />
      <rect x="25" y="42" width="1.5" height="3" rx="0.5" fill={c} opacity="0.3" />
    </g>
  );
}

const APPLIANCE_MAP: Record<Appliance, React.FC<{ c: string }>> = {
  tv: ApplianceTV,
  fridge: ApplianceFridge,
  computer: ApplianceComputer,
  generic: ApplianceGeneric,
};

type PlugPhase = "unplugged" | "plugging" | "appliance";

function SvgSmartPlug({ phase, appliance }: { phase: PlugPhase; appliance: Appliance }) {
  const isPlugged = phase !== "unplugged";
  const cSocket = isPlugged ? COLORS.smart_plug.on : COLORS.smart_plug.off;
  const AppIcon = APPLIANCE_MAP[appliance];

  return (
    <div className="relative w-12 h-14 flex items-center justify-center">
      {/* ── Layer 1: Socket + Plug (visible during "unplugged" and "plugging") ── */}
      <svg
        viewBox="0 0 48 56"
        className="absolute inset-0 w-12 h-14 overflow-visible"
        style={{
          opacity: phase === "appliance" ? 0 : 1,
          transform: phase === "appliance" ? "scale(0.85)" : "scale(1)",
          transition: "opacity 0.45s cubic-bezier(0.33,1,0.68,1), transform 0.45s cubic-bezier(0.33,1,0.68,1)",
        }}
      >
        {/* socket plate */}
        <rect x="8" y="24" width="32" height="28" rx="4" fill="none" stroke={cSocket} strokeWidth="2" />
        {/* socket holes */}
        <rect x="17" y="34" width="4" height="8" rx="2" fill={cSocket} opacity="0.4" />
        <rect x="27" y="34" width="4" height="8" rx="2" fill={cSocket} opacity="0.4" />
        {/* plug body — slides down when plugging */}
        <g style={{
          transform: isPlugged ? "translateY(0px)" : "translateY(-14px)",
          transition: "transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)",
        }}>
          <rect x="12" y="8" width="24" height="16" rx="3"
            fill={isPlugged ? "rgba(34,211,238,0.1)" : "none"}
            stroke={cSocket} strokeWidth="2"
          />
          <rect x="18" y="24" width="3" height="10" rx="1" fill={cSocket} />
          <rect x="27" y="24" width="3" height="10" rx="1" fill={cSocket} />
          <line x1="24" y1="2" x2="24" y2="8" stroke={cSocket} strokeWidth="2" strokeLinecap="round" />
        </g>
        {/* sparks when plug connects */}
        {phase === "plugging" && (
          <>
            <path d="M15 32 L11 27" stroke="rgba(34,211,238,0.8)" strokeWidth="1.5" strokeLinecap="round">
              <animate attributeName="opacity" values="0;1;0" dur="0.6s" repeatCount="indefinite" />
            </path>
            <path d="M33 32 L37 27" stroke="rgba(34,211,238,0.8)" strokeWidth="1.5" strokeLinecap="round">
              <animate attributeName="opacity" values="0;1;0" dur="0.6s" begin="0.3s" repeatCount="indefinite" />
            </path>
            <circle cx="24" cy="38" r="2" fill="rgba(34,211,238,0.2)">
              <animate attributeName="r" values="2;10;2" dur="0.8s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.5;0;0.5" dur="0.8s" repeatCount="indefinite" />
            </circle>
          </>
        )}
      </svg>

      {/* ── Layer 2: Appliance icon (fades in after plugging completes) ── */}
      <svg
        viewBox="0 0 48 48"
        className="absolute w-12 h-12"
        style={{
          opacity: phase === "appliance" ? 1 : 0,
          transform: phase === "appliance" ? "scale(1)" : "scale(0.7)",
          transition: "opacity 0.5s cubic-bezier(0.33,1,0.68,1) 0.05s, transform 0.5s cubic-bezier(0.34,1.56,0.64,1) 0.05s",
        }}
      >
        {/* glow ring */}
        <circle cx="24" cy="24" r="22" fill="none" stroke="rgba(34,211,238,0.12)" strokeWidth="1">
          <animate attributeName="r" values="20;23;20" dur="2.5s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.3;0.08;0.3" dur="2.5s" repeatCount="indefinite" />
        </circle>
        <AppIcon c={COLORS.smart_plug.on} />
      </svg>
    </div>
  );
}

function SvgThermostat({ on, progress }: { on: boolean; progress: number }) {
  const r = 19;
  const circ = 2 * Math.PI * r;
  const arcColour = progress < 0.3 ? COLORS.thermostat.cold : progress < 0.7 ? COLORS.thermostat.mid : COLORS.thermostat.hot;
  return (
    <svg viewBox="0 0 48 48" className="w-12 h-12">
      {Array.from({ length: 12 }).map((_, i) => (
        <line
          key={i}
          x1="24" y1="3" x2="24" y2="6"
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="1" strokeLinecap="round"
          transform={`rotate(${i * 30} 24 24)`}
        />
      ))}
      <circle cx="24" cy="24" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
      <circle
        className="dc-thermo-arc"
        cx="24" cy="24" r={r}
        fill="none" stroke={on ? arcColour : "#52525b"}
        strokeWidth="3.5"
        strokeDasharray={circ} strokeDashoffset={circ}
        strokeLinecap="round"
        style={{ transform: "rotate(-90deg)", transformOrigin: "center" }}
      />
      {on && (
        <circle
          className="dc-thermo-glow"
          cx="24" cy="24" r={r}
          fill="none" stroke={arcColour}
          strokeWidth="6"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - progress)}
          strokeLinecap="round"
          opacity="0.25"
          style={{ transform: "rotate(-90deg)", transformOrigin: "center", filter: "blur(3px)" }}
        />
      )}
      <circle cx="24" cy="24" r="8" fill="rgba(255,255,255,0.04)" />
    </svg>
  );
}

function SvgLock({ locked }: { locked: boolean }) {
  const c = locked ? COLORS.lock.locked : COLORS.lock.unlocked;
  const ringColor = locked ? "rgba(16,185,129,0.2)" : "rgba(249,115,22,0.25)";
  return (
    <svg viewBox="0 0 48 48" className="w-12 h-12">
      <circle cx="24" cy="24" r="22" fill="none" stroke={ringColor} strokeWidth="1.5" strokeDasharray="5 4">
        {!locked && (
          <animateTransform attributeName="transform" type="rotate" from="0 24 24" to="360 24 24" dur="6s" repeatCount="indefinite" />
        )}
      </circle>
      <path
        className="dc-shackle"
        d="M16 22 L16 16 C16 10 20 7 24 7 C28 7 32 10 32 16 L32 22"
        fill="none" stroke={c} strokeWidth="3" strokeLinecap="round"
        style={{
          transform: locked ? "translateY(0)" : "translateY(-4px) rotate(-15deg)",
          transformOrigin: "32px 22px",
          transition: "transform 0.45s cubic-bezier(0.33,1,0.68,1)",
        }}
      />
      <rect x="13" y="22" width="22" height="18" rx="3"
        fill={locked ? "rgba(16,185,129,0.1)" : "rgba(249,115,22,0.08)"}
        stroke={c} strokeWidth="2"
      />
      <circle cx="24" cy="30" r="2.5" fill={c} />
      <rect x="23" y="30" width="2" height="5" rx="1" fill={c} />
    </svg>
  );
}

function SvgBattery({ pct, clipId }: { pct: number; clipId: string }) {
  const fillColor = pct > 50 ? COLORS.battery.high : pct > 20 ? COLORS.battery.mid : COLORS.battery.low;
  const fillH = Math.max(0, 34 * pct * 0.01);
  const wy = 42 - fillH;
  return (
    <svg viewBox="0 0 48 48" className="w-12 h-12">
      <rect x="18" y="2" width="12" height="4" rx="2" fill="#52525b" />
      <rect x="10" y="6" width="28" height="38" rx="4" fill="none" stroke={pct > 0 ? fillColor : "#52525b"} strokeWidth="2" />
      <defs>
        <clipPath id={clipId}>
          <rect x="12" y="8" width="24" height="34" rx="2" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clipId})`}>
        <path
          className="dc-batt-wave"
          d={`M4 ${wy+2} Q10 ${wy-2} 16 ${wy+2} Q22 ${wy+5} 28 ${wy+1} Q34 ${wy-2} 40 ${wy+2} Q46 ${wy+5} 52 ${wy+2} L52 46 L4 46 Z`}
          fill={fillColor} opacity="0.35"
        />
      </g>
      {pct > 0 && pct < 100 && (
        <path
          d="M26 16 L22 26 L26 26 L22 36"
          fill="none" stroke={fillColor} strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round" opacity="0.6"
        >
          <animate attributeName="opacity" values="0.3;0.8;0.3" dur="1.5s" repeatCount="indefinite" />
        </path>
      )}
    </svg>
  );
}

function SvgSensor({ on }: { on: boolean }) {
  const c = on ? COLORS.sensor.on : COLORS.sensor.off;
  return (
    <svg viewBox="0 0 48 48" className="w-12 h-12">
      {[18, 14, 10].map((r, i) => (
        <path key={i} d={`M${24-r} 24 A${r} ${r} 0 0 1 ${24+r} 24`}
          fill="none" stroke={c} strokeWidth="2" strokeLinecap="round"
          opacity={on ? undefined : "0.3"}>
          {on && (<>
            <animate attributeName="opacity" values="0.15;0.7;0.15" dur="1.8s" begin={`${i*0.3}s`} repeatCount="indefinite" />
            <animate attributeName="stroke-width" values="1.5;3;1.5" dur="1.8s" begin={`${i*0.3}s`} repeatCount="indefinite" />
          </>)}
        </path>
      ))}
      <circle cx="24" cy="24" r="3" fill={c}>
        {on && <animate attributeName="r" values="2.5;4;2.5" dur="1.8s" repeatCount="indefinite" />}
      </circle>
      {[18, 14, 10].map((r, i) => (
        <path key={`b${i}`} d={`M${24-r} 24 A${r} ${r} 0 0 0 ${24+r} 24`}
          fill="none" stroke={c} strokeWidth="2" strokeLinecap="round"
          opacity={on ? undefined : "0.3"}>
          {on && (
            <animate attributeName="opacity" values="0.15;0.7;0.15" dur="1.8s" begin={`${i*0.3+0.15}s`} repeatCount="indefinite" />
          )}
        </path>
      ))}
    </svg>
  );
}

function SvgDefault({ on }: { on: boolean }) {
  const c = on ? COLORS.default.on : COLORS.default.off;
  return (
    <svg viewBox="0 0 48 48" className="w-12 h-12">
      <circle cx="24" cy="24" r="18" fill="none" stroke={c} strokeWidth="2" />
      <path d="M18 24 L22 28 L30 20" fill="none" stroke={c} strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round" opacity={on ? 1 : 0.3} />
    </svg>
  );
}

/* ================================================================
   DEVICE CARD COMPONENT
   ================================================================ */

interface Props {
  device: DeviceState;
  onUpdate?: () => void;
}


export function DeviceCard({ device, onUpdate }: Props) {
  const isOn = device.power && device.online;
  const uid = useId();

  const rootRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  const [brightnessDisplay, setBrightnessDisplay] = useState(
    device.properties.brightness || 0,
  );
  const prevPower = useRef(device.power);
  const scopeRef = useRef<ReturnType<typeof createScope> | null>(null);

  const { r = 255, g = 255, b = 255 } = device.properties.color || {};
  const rgb = `${r},${g},${b}`;
  const batteryPct = device.properties.battery_pct || 0;
  const isBrewing = device.device_type === "coffee_maker" && isOn;
  const circumference = 2 * Math.PI * 19;
  const appliance = device.device_type === "smart_plug"
    ? detectAppliance(device.display_name, device.device_id)
    : ("generic" as Appliance);
  const lightKind = device.device_type === "light"
    ? detectLightKind(device.display_name)
    : ("ceiling" as LightKind);

  /* ── Smart plug phase transition: unplugged → plugging → appliance ── */
  const [plugPhase, setPlugPhase] = useState<PlugPhase>(isOn ? "appliance" : "unplugged");
  const prevIsOn = useRef(isOn);

  useEffect(() => {
    if (device.device_type !== "smart_plug") return;
    if (prevIsOn.current === isOn) return;
    prevIsOn.current = isOn;

    if (isOn) {
      setPlugPhase("plugging");
      const timer = setTimeout(() => setPlugPhase("appliance"), 900);
      return () => clearTimeout(timer);
    } else {
      setPlugPhase("unplugged");
    }
  }, [isOn, device.device_type]);

  /* ── Coffee phase transition: off → brewing → ready ── */
  const [coffeePhase, setCoffeePhase] = useState<CoffeePhase>(
    isBrewing ? "ready" : "off",
  );
  const prevBrewing = useRef(isBrewing);

  useEffect(() => {
    if (device.device_type !== "coffee_maker") return;
    if (prevBrewing.current === isBrewing) return;
    prevBrewing.current = isBrewing;

    if (isBrewing) {
      // Phase 1: brewing animation for 5 seconds
      setCoffeePhase("brewing");
      const timer = setTimeout(() => setCoffeePhase("ready"), 5000);
      return () => clearTimeout(timer);
    } else {
      setCoffeePhase("off");
    }
  }, [isBrewing, device.device_type]);

  /* ── anime.js scoped animations ── */
  useEffect(() => {
    if (!rootRef.current) return;
    scopeRef.current = createScope({ root: rootRef }).add(() => {
      animate(".dc-ray", {
        opacity: [0, 0.8, 0],
        scaleY: [0.5, 1.3, 0.5],
        duration: 2400, loop: true, ease: "inOut(3)",
        delay: stagger(100),
      });
      const currentTemp = device.properties.current_temp_f || 65;
      const progress = Math.max(0, Math.min(1, (currentTemp - 60) / 25));
      animate(".dc-thermo-arc", {
        strokeDashoffset: circumference * (1 - progress),
        duration: 1800, ease: "out(4)",
      });
      animate(".dc-thermo-glow", {
        opacity: [0.2, 0.5, 0.2],
        duration: 2000, loop: true, ease: "inOut(2)",
      });
      animate(".dc-batt-wave", {
        translateX: [-4, 4, -4],
        duration: 2200, loop: true, ease: "inOut(2)",
      });
      animate(".dc-steam", {
        translateY: [0, -20],
        opacity: [0.8, 0],
        duration: 1600, loop: true, ease: "out(2)",
        delay: stagger(300),
      });
      animate(".dc-liquid", {
        translateX: [-1.5, 1.5, -1.5],
        duration: 1800, loop: true, ease: "inOut(2)",
      });
    });
    return () => scopeRef.current?.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOn, device.device_type, isBrewing, batteryPct,
      device.properties.current_temp_f, device.properties.locked]);

  /* Power toggle bounce */
  useEffect(() => {
    if (prevPower.current !== device.power && device.online) {
      if (cardRef.current) {
        animate(cardRef.current, {
          scale: [1, 0.93, 1.08, 1],
          duration: 500, ease: "out(4)",
        });
      }
    }
    prevPower.current = device.power;
  }, [device.power, device.online]);

  /* Brightness counter */
  useEffect(() => {
    if (device.device_type === "light" && device.power) {
      const target = device.properties.brightness || 0;
      const obj = { v: brightnessDisplay };
      animate(obj, {
        v: target, duration: 600, ease: "out(4)",
        onUpdate: () => setBrightnessDisplay(Math.round(obj.v)),
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device.properties.brightness, device.device_type, device.power]);

  /* click handler (unchanged) */
  const handleToggle = async () => {
    if (!device.online) return;
    const action = device.power ? "off" : "on";
    try {
      await apiFetch(`/devices/${device.device_id}/command`, {
        method: "POST",
        body: JSON.stringify({ action, parameters: {} }),
      });
      onUpdate?.();
    } catch (e) {
      console.error("Toggle failed:", e);
    }
  };

  /* ── render the correct SVG ── */
  const renderIcon = () => {
    const t = device.device_type;
    const currentTemp = device.properties.current_temp_f || 65;
    const progress = Math.max(0, Math.min(1, (currentTemp - 60) / 25));
    switch (t) {
      case "light": {
        const LightSvg = LIGHT_SVG_MAP[lightKind];
        return <LightSvg on={isOn} r={r} g={g} b={b} />;
      }
      case "coffee_maker": return <SvgCoffeeCup phase={coffeePhase} />;
      case "smart_plug": return <SvgSmartPlug phase={plugPhase} appliance={appliance} />;
      case "thermostat": return <SvgThermostat on={isOn} progress={progress} />;
      case "lock": return <SvgLock locked={device.properties.locked ?? true} />;
      case "battery": return <SvgBattery pct={batteryPct} clipId={`batt${uid}`} />;
      case "sensor": return <SvgSensor on={isOn} />;
      default: return <SvgDefault on={isOn} />;
    }
  };

  /* ══════════════════════════
     RENDER
     ══════════════════════════ */
  return (
    <motion.div
      ref={rootRef}
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease: [0.33, 1, 0.68, 1] }}
    >
      <div
        ref={cardRef}
        className={cn(
          "cursor-pointer transition-all duration-300 relative p-2.5 sm:p-3 flex flex-col items-center min-h-[72px] sm:min-h-0 touch-target",
          !device.online && "opacity-40 grayscale",
        )}
        onClick={handleToggle}
      >
        {/* icon */}
        <div className="flex justify-center items-center mb-2">
          {renderIcon()}
          </div>

        {/* name */}
        <p className="text-xs font-semibold truncate text-center" style={{ color: 'var(--color-device-type)' }}>
          {device.display_name}
        </p>

        {/* stats */}
        <div className="mt-1 space-y-0.5 text-center">
            {device.device_type === "thermostat" && (
              <p className="text-[10px] text-muted-foreground">
                {device.properties.current_temp_f?.toFixed(1)}°F → {device.properties.target_temp_f}°F
              </p>
            )}
            {device.device_type === "light" && device.power && (
              <p className="text-[10px] text-muted-foreground">
              Brightness: {brightnessDisplay}%
              </p>
            )}
            {device.device_type === "lock" && (
              <p className="text-[10px] text-muted-foreground">
                {device.properties.locked ? (
                <span className="inline-flex items-center gap-1">
                  <Lock className="w-3 h-3" /> Locked
                </span>
                ) : (
                <span className="inline-flex items-center gap-1 text-orange-400">
                  <LockOpen className="w-3 h-3" /> Unlocked
                </span>
                )}
              </p>
            )}
            {device.device_type === "battery" && (
              <p className="text-[10px] text-muted-foreground">
                {device.properties.battery_pct?.toFixed(0)}% · {formatWatts(device.properties.solar_generation_watts || 0)} solar
              </p>
            )}
          {coffeePhase === "brewing" && (
            <p className="text-[10px] text-orange-400">Brewing...</p>
          )}
          {coffeePhase === "ready" && (
            <p className="text-[10px] text-green-400">Ready!</p>
            )}
          {device.device_type === "water_heater" && (
              <p className="text-[10px] text-muted-foreground">
                {device.properties.temperature_f?.toFixed(0)}°F
                {device.properties.heating && <span className="text-orange-400 ml-1">Heating</span>}
                {device.properties.mode === "boost" && <span className="text-red-400 ml-1">Boost</span>}
              </p>
            )}
            <p className="text-[10px] text-zinc-600">{formatWatts(device.current_watts)}</p>
          </div>
      </div>
    </motion.div>
  );
}
