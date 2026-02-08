import { motion } from "framer-motion";
import {
  Lightbulb, Thermometer, Lock, Battery, Coffee, Activity,
  Plug, LockOpen, Power
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatWatts, apiFetch } from "@/lib/utils";
import type { DeviceState } from "@/types";

const DEVICE_ICONS: Record<string, any> = {
  light: Lightbulb,
  thermostat: Thermometer,
  lock: Lock,
  battery: Battery,
  coffee_maker: Coffee,
  sensor: Activity,
  smart_plug: Plug,
};

interface Props {
  device: DeviceState;
  onUpdate?: () => void;
}

export function DeviceCard({ device, onUpdate }: Props) {
  const Icon = DEVICE_ICONS[device.device_type] || Power;
  const isOn = device.power && device.online;

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

  const getStatusColor = () => {
    if (!device.online) return "text-zinc-600";
    if (device.power) return "text-green-400";
    return "text-zinc-500";
  };

  const getBgGlow = () => {
    if (!device.online) return "";
    if (device.device_type === "light" && device.power) {
      const { r = 255, g = 255, b = 255 } = device.properties.color || {};
      return `shadow-[0_0_20px_rgba(${r},${g},${b},0.15)]`;
    }
    if (device.power) return "shadow-[0_0_15px_rgba(59,130,246,0.08)]";
    return "";
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
    >
      <Card
        className={cn(
          "cursor-pointer hover:border-zinc-600 transition-all duration-300",
          getBgGlow(),
          !device.online && "opacity-50"
        )}
        onClick={handleToggle}
      >
        <CardContent className="p-3">
          <div className="flex items-center justify-between mb-2">
            <motion.div
              animate={{ color: isOn ? "#4ade80" : "#71717a" }}
              transition={{ duration: 0.3 }}
            >
              <Icon className={cn("w-5 h-5", getStatusColor())} />
            </motion.div>
            <Badge variant={device.online ? (device.power ? "success" : "outline") : "destructive"}>
              {!device.online ? "offline" : device.power ? "on" : "off"}
            </Badge>
          </div>

          <p className="text-xs font-medium text-foreground truncate">{device.display_name}</p>

          <div className="mt-1.5 space-y-0.5">
            {device.device_type === "thermostat" && (
              <p className="text-[10px] text-muted-foreground">
                {device.properties.current_temp_f?.toFixed(1)}°F → {device.properties.target_temp_f}°F
              </p>
            )}
            {device.device_type === "light" && device.power && (
              <p className="text-[10px] text-muted-foreground">
                Brightness: {device.properties.brightness}%
              </p>
            )}
            {device.device_type === "lock" && (
              <p className="text-[10px] text-muted-foreground">
                {device.properties.locked ? (
                  <span className="flex items-center gap-1"><Lock className="w-3 h-3" /> Locked</span>
                ) : (
                  <span className="flex items-center gap-1"><LockOpen className="w-3 h-3" /> Unlocked</span>
                )}
              </p>
            )}
            {device.device_type === "battery" && (
              <p className="text-[10px] text-muted-foreground">
                {device.properties.battery_pct?.toFixed(0)}% · {formatWatts(device.properties.solar_generation_watts || 0)} solar
              </p>
            )}
            {device.device_type === "coffee_maker" && device.properties.brewing && (
              <p className="text-[10px] text-yellow-400">Brewing...</p>
            )}
            <p className="text-[10px] text-zinc-600">{formatWatts(device.current_watts)}</p>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
