import { motion, AnimatePresence } from "framer-motion";
import { Clock, ChevronRight } from "lucide-react";
import type { ScenarioStep } from "@/types";

interface Props {
  step: ScenarioStep | null;
  scenarioName: string | null;
}

export function TimelineOverlay({ step, scenarioName }: Props) {
  if (!step || !scenarioName) return null;

  const progress = ((step.current_step + 1) / step.total_steps) * 100;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="mb-4 rounded-xl border border-primary/30 bg-primary/5 overflow-hidden"
      >
        {/* Progress bar */}
        <div className="h-1 bg-muted/30">
          <motion.div
            className="h-full bg-primary"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          />
        </div>

        <div className="p-4">
          {/* Scenario name + step counter */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-primary">
                {scenarioName}
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span>Step {step.current_step + 1} of {step.total_steps}</span>
              <div className="flex gap-0.5 ml-1">
                {Array.from({ length: step.total_steps }).map((_, i) => (
                  <div
                    key={i}
                    className={`w-1.5 h-1.5 rounded-full transition-colors ${
                      i <= step.current_step
                        ? "bg-primary"
                        : "bg-muted-foreground/30"
                    }`}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Current event */}
          <div className="flex items-start gap-3">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary/20 text-primary shrink-0">
              <Clock className="w-3.5 h-3.5" />
              <span className="text-sm font-mono font-bold">{step.timestamp}</span>
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold flex items-center gap-1.5">
                <ChevronRight className="w-3.5 h-3.5 text-primary" />
                {step.title}
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">{step.description}</p>
            </div>
          </div>

          {/* Metrics */}
          {step.metrics && Object.keys(step.metrics).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(step.metrics).map(([key, value]) => (
                <div
                  key={key}
                  className="px-2 py-1 rounded-md bg-muted/50 text-xs"
                >
                  <span className="text-muted-foreground">
                    {key.replace(/_/g, " ")}:
                  </span>{" "}
                  <span className="font-medium text-foreground">{value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
