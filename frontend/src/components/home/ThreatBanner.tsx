import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { animate } from "animejs";
import { AlertTriangle, Shield, ShieldAlert, ShieldCheck } from "lucide-react";
import { cn, getThreatBg, getThreatColor } from "@/lib/utils";
import type { ThreatAssessment } from "@/types";

interface Props {
  threat: ThreatAssessment | null;
}

/* border glow keyframes */
const glowKeyframes = `
@keyframes tb-glow-critical {
  0%,100% { box-shadow: 0 0 8px rgba(239,68,68,0.3), inset 0 0 8px rgba(239,68,68,0.05); }
  50% { box-shadow: 0 0 20px rgba(239,68,68,0.5), inset 0 0 12px rgba(239,68,68,0.08); }
}
@keyframes tb-glow-high {
  0%,100% { box-shadow: 0 0 6px rgba(245,158,11,0.2); }
  50% { box-shadow: 0 0 16px rgba(245,158,11,0.4); }
}
@keyframes tb-glow-medium {
  0%,100% { box-shadow: 0 0 4px rgba(59,130,246,0.15); }
  50% { box-shadow: 0 0 12px rgba(59,130,246,0.3); }
}
`;

export function ThreatBanner({ threat }: Props) {
  const bannerRef = useRef<HTMLDivElement>(null);

  /* inject glow keyframes once */
  useEffect(() => {
    if (document.getElementById("tb-glow-css")) return;
    const s = document.createElement("style");
    s.id = "tb-glow-css";
    s.textContent = glowKeyframes;
    document.head.appendChild(s);
  }, []);

  /* critical shake every 3s */
  useEffect(() => {
    if (!threat || threat.threat_level !== "critical" || !bannerRef.current) return;
    const el = bannerRef.current;
    const shake = () => {
      animate(el, { translateX: [-3, 3, -3, 2, -1, 0], duration: 480, ease: "out(3)" });
    };
    shake();
    const id = setInterval(shake, 3000);
    return () => clearInterval(id);
  }, [threat?.threat_level]);

  /* ── All Clear ── */
  if (!threat || threat.threat_level === "none") {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-500/5 border border-green-500/20">
        <span className="relative flex items-center justify-center shrink-0">
          <ShieldCheck className="w-4 h-4 text-green-500 relative z-10" />
          <span className="absolute inset-0 rounded-full bg-green-500/20 animate-pulse" />
        </span>
        <span className="text-xs text-green-400 min-w-0">All Clear — No threats detected</span>
      </div>
    );
  }

  const Icon = threat.threat_level === "critical" ? ShieldAlert :
               threat.threat_level === "high" ? AlertTriangle : Shield;

  const glowAnim = threat.threat_level === "critical" ? "tb-glow-critical"
    : threat.threat_level === "high" ? "tb-glow-high" : "tb-glow-medium";

  const iconScale = threat.threat_level === "critical" ? [1, 1.35, 1]
    : threat.threat_level === "high" ? [1, 1.2, 1] : [1, 1.1, 1];
  const iconDur = threat.threat_level === "critical" ? 0.8 : 1.5;

  return (
    <AnimatePresence>
      <motion.div
        ref={bannerRef}
        initial={{ opacity: 0, y: -40 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -30 }}
        transition={{ type: "spring", stiffness: 380, damping: 28 }}
        className={cn("px-3 py-2.5 sm:px-4 sm:py-3 rounded-lg border", getThreatBg(threat.threat_level))}
        style={{ animation: `${glowAnim} 2s ease-in-out infinite` }}
      >
        <div className="flex items-start gap-2 sm:gap-3">
          {/* pulsing icon */}
          <motion.div
            animate={{ scale: iconScale }}
            transition={{ repeat: Infinity, duration: iconDur, ease: "easeInOut" }}
            className="shrink-0"
          >
            <Icon className={cn("w-5 h-5 mt-0.5", getThreatColor(threat.threat_level))} />
          </motion.div>

          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mb-1">
              <span className={cn("text-xs sm:text-sm font-semibold capitalize break-words", getThreatColor(threat.threat_level))}>
                {threat.threat_level} — {threat.threat_type.replace(/_/g, " ")}
              </span>
              <span className="text-[10px] text-muted-foreground shrink-0">
                Urgency: {(threat.urgency_score * 100).toFixed(0)}%
              </span>
            </div>

            {/* urgency meter bar */}
            <div className="h-1 w-full rounded-full bg-white/5 mb-2 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${threat.urgency_score * 100}%` }}
                transition={{ duration: 1, ease: [0.33, 1, 0.68, 1] }}
                className={cn("h-full rounded-full", threat.threat_level === "critical" ? "bg-red-500" : threat.threat_level === "high" ? "bg-amber-500" : "bg-blue-500")}
              />
            </div>

            <p className="text-xs text-muted-foreground break-words">{threat.summary}</p>

            {/* staggered action chips */}
            {threat.recommended_actions.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {threat.recommended_actions.map((action, i) => (
                  <motion.span
                    key={i}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 + i * 0.1, duration: 0.35, ease: [0.33, 1, 0.68, 1] }}
                    className="text-[10px] px-2 py-1 rounded-full bg-white/5 text-muted-foreground"
                  >
                    {action}
                  </motion.span>
                ))}
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
