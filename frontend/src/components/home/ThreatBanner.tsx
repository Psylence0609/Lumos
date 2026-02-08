import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Shield, ShieldAlert, ShieldCheck } from "lucide-react";
import { cn, getThreatBg, getThreatColor } from "@/lib/utils";
import type { ThreatAssessment } from "@/types";

interface Props {
  threat: ThreatAssessment | null;
}

export function ThreatBanner({ threat }: Props) {
  if (!threat || threat.threat_level === "none") {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-500/5 border border-green-500/20">
        <ShieldCheck className="w-4 h-4 text-green-500" />
        <span className="text-xs text-green-400">All Clear — No threats detected</span>
      </div>
    );
  }

  const Icon = threat.threat_level === "critical" ? ShieldAlert :
               threat.threat_level === "high" ? AlertTriangle : Shield;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className={cn(
          "px-4 py-3 rounded-lg border",
          getThreatBg(threat.threat_level)
        )}
      >
        <div className="flex items-start gap-3">
          <motion.div
            animate={{ scale: [1, 1.1, 1] }}
            transition={{ repeat: threat.threat_level === "critical" ? Infinity : 0, duration: 1.5 }}
          >
            <Icon className={cn("w-5 h-5 mt-0.5", getThreatColor(threat.threat_level))} />
          </motion.div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={cn("text-sm font-semibold capitalize", getThreatColor(threat.threat_level))}>
                {threat.threat_level} — {threat.threat_type.replace(/_/g, " ")}
              </span>
              <span className="text-[10px] text-muted-foreground">
                Urgency: {(threat.urgency_score * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{threat.summary}</p>
            {threat.recommended_actions.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {threat.recommended_actions.map((action, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-muted-foreground">
                    {action}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
