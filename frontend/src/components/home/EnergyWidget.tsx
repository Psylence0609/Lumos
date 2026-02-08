import { Battery, Sun, Zap, ArrowDown, ArrowUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatWatts } from "@/lib/utils";
import type { EnergyData } from "@/types";

interface Props {
  energy: EnergyData | null;
}

export function EnergyWidget({ energy }: Props) {
  if (!energy) return null;

  const batteryColor = energy.battery_pct > 50 ? "text-green-400" :
                       energy.battery_pct > 20 ? "text-yellow-400" : "text-red-400";

  const isExporting = energy.net_grid_watts < 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-yellow-400" />
          Energy
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3">
          {/* Battery */}
          <div className="flex items-center gap-2">
            <Battery className={cn("w-4 h-4", batteryColor)} />
            <div>
              <p className="text-lg font-bold">{energy.battery_pct.toFixed(0)}%</p>
              <p className="text-[10px] text-muted-foreground">{energy.battery_mode}</p>
            </div>
          </div>

          {/* Solar */}
          <div className="flex items-center gap-2">
            <Sun className="w-4 h-4 text-amber-400" />
            <div>
              <p className="text-lg font-bold">{formatWatts(energy.solar_generation_watts)}</p>
              <p className="text-[10px] text-muted-foreground">solar</p>
            </div>
          </div>

          {/* Consumption */}
          <div className="flex items-center gap-2">
            <ArrowUp className="w-4 h-4 text-blue-400" />
            <div>
              <p className="text-sm font-semibold">{formatWatts(energy.total_consumption_watts)}</p>
              <p className="text-[10px] text-muted-foreground">using</p>
            </div>
          </div>

          {/* Grid */}
          <div className="flex items-center gap-2">
            {isExporting ? (
              <ArrowDown className="w-4 h-4 text-green-400" />
            ) : (
              <ArrowUp className="w-4 h-4 text-orange-400" />
            )}
            <div>
              <p className="text-sm font-semibold">
                {formatWatts(Math.abs(energy.net_grid_watts))}
              </p>
              <p className="text-[10px] text-muted-foreground">
                {isExporting ? "exporting" : "from grid"}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
