import { useState } from "react";
import { Battery, Sun } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/utils";

export function BatteryControl() {
  const [batteryPct, setBatteryPct] = useState(75);
  const [solarWatts, setSolarWatts] = useState(2000);

  const applyBattery = async () => {
    await apiFetch("/simulation/battery", {
      method: "POST",
      body: JSON.stringify({ battery_pct: batteryPct }),
    });
  };

  const applySolar = async () => {
    await apiFetch("/simulation/solar", {
      method: "POST",
      body: JSON.stringify({ watts: solarWatts }),
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Battery className="w-4 h-4 text-green-400" />
          Battery & Solar
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
            <span>Battery Level</span>
            <span>{batteryPct}%</span>
          </div>
          <input type="range" min={0} max={100} value={batteryPct} onChange={(e) => setBatteryPct(+e.target.value)} className="w-full h-1 accent-green-500" />
          <div className="grid grid-cols-4 gap-1 mt-1">
            {[10, 30, 60, 90].map((v) => (
              <Button key={v} size="sm" variant="outline" className="text-[10px] h-6" onClick={() => setBatteryPct(v)}>
                {v}%
              </Button>
            ))}
          </div>
          <Button size="sm" className="w-full mt-2 h-7" onClick={applyBattery}>Set Battery</Button>
        </div>

        <div>
          <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
            <span><Sun className="w-3 h-3 inline mr-1" />Solar Generation</span>
            <span>{solarWatts} W</span>
          </div>
          <input type="range" min={0} max={5000} value={solarWatts} onChange={(e) => setSolarWatts(+e.target.value)} className="w-full h-1 accent-amber-500" />
          <div className="grid grid-cols-4 gap-1 mt-1">
            {[0, 1000, 3000, 5000].map((v) => (
              <Button key={v} size="sm" variant="outline" className="text-[10px] h-6" onClick={() => setSolarWatts(v)}>
                {v}W
              </Button>
            ))}
          </div>
          <Button size="sm" className="w-full mt-2 h-7" onClick={applySolar}>Set Solar</Button>
        </div>
      </CardContent>
    </Card>
  );
}
