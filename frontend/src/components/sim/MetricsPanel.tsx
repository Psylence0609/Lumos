import { motion, AnimatePresence } from "framer-motion";
import { TrendingUp, DollarSign, Zap, Battery, Thermometer, Shield, BarChart3 } from "lucide-react";

interface Props {
  metrics: Record<string, string>;
  scenarioId: string | null;
  visible: boolean;
}

const ICON_MAP: Record<string, React.ReactNode> = {
  cost_savings: <DollarSign className="w-3.5 h-3.5" />,
  daily_savings: <DollarSign className="w-3.5 h-3.5" />,
  arbitrage_profit: <TrendingUp className="w-3.5 h-3.5" />,
  monthly_savings: <DollarSign className="w-3.5 h-3.5" />,
  annual_savings: <DollarSign className="w-3.5 h-3.5" />,
  energy_shifted: <Zap className="w-3.5 h-3.5" />,
  kwh_shifted: <Zap className="w-3.5 h-3.5" />,
  peak_demand_reduced: <BarChart3 className="w-3.5 h-3.5" />,
  peak_demand_avoided: <BarChart3 className="w-3.5 h-3.5" />,
  battery_remaining: <Battery className="w-3.5 h-3.5" />,
  time_to_empty: <Battery className="w-3.5 h-3.5" />,
  home_temp: <Thermometer className="w-3.5 h-3.5" />,
  neighbors_temp: <Thermometer className="w-3.5 h-3.5" />,
  critical_devices: <Shield className="w-3.5 h-3.5" />,
  grid_status: <Zap className="w-3.5 h-3.5" />,
  roi_years: <TrendingUp className="w-3.5 h-3.5" />,
};

function getHighlightKeys(scenarioId: string | null): string[] {
  switch (scenarioId) {
    case "demo_texas_grid_crisis":
      return ["cost_savings", "energy_shifted", "home_temp"];
    case "demo_winter_storm":
      return ["battery_remaining", "time_to_empty", "home_temp"];
    case "demo_solar_battery":
      return ["daily_savings", "annual_savings", "roi_years"];
    default:
      return [];
  }
}

export function MetricsPanel({ metrics, scenarioId, visible }: Props) {
  if (!visible || !metrics || Object.keys(metrics).length === 0) return null;

  const highlights = getHighlightKeys(scenarioId);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="rounded-xl border border-green-500/30 bg-green-500/5 p-4"
      >
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-green-400" />
          <h3 className="text-sm font-bold text-green-400">Impact Metrics</h3>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {Object.entries(metrics).map(([key, value], idx) => {
            const isHighlight = highlights.includes(key);
            const icon = ICON_MAP[key] || <Zap className="w-3.5 h-3.5" />;
            const label = key.replace(/_/g, " ");

            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className={`p-2 rounded-lg ${
                  isHighlight
                    ? "bg-green-500/15 border border-green-500/30"
                    : "bg-muted/30 border border-border/50"
                }`}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className={isHighlight ? "text-green-400" : "text-muted-foreground"}>
                    {icon}
                  </span>
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider truncate">
                    {label}
                  </span>
                </div>
                <div className={`text-sm font-bold ${isHighlight ? "text-green-300" : "text-foreground"}`}>
                  {value}
                </div>
              </motion.div>
            );
          })}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
