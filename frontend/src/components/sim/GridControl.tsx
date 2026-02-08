import { useState } from "react";
import { Activity, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/utils";

export function GridControl() {
  const [loadPct, setLoadPct] = useState(65);
  const [lmpPrice, setLmpPrice] = useState(25);
  const [reserves, setReserves] = useState(3000);

  const applyGrid = async () => {
    const alertLevel = loadPct > 95 ? "eea3" : loadPct > 90 ? "eea2" : loadPct > 85 ? "eea1" : loadPct > 80 ? "conservation" : loadPct > 70 ? "elevated" : "normal";
    await apiFetch("/simulation/grid", {
      method: "POST",
      body: JSON.stringify({
        load_capacity_pct: loadPct,
        lmp_price: lmpPrice,
        system_load_mw: loadPct * 800,
        operating_reserves_mw: reserves,
        grid_alert_level: alertLevel,
      }),
    });
  };

  const clearGrid = async () => {
    await apiFetch("/simulation/grid", { method: "DELETE" });
  };

  const presets = [
    { label: "Normal", loadPct: 65, lmpPrice: 25, reserves: 3000 },
    { label: "Elevated", loadPct: 82, lmpPrice: 75, reserves: 2500 },
    { label: "EEA1", loadPct: 88, lmpPrice: 200, reserves: 2000 },
    { label: "EEA3 (Crisis)", loadPct: 98, lmpPrice: 5000, reserves: 500 },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-orange-400" />
          ERCOT Grid
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-1.5">
          {presets.map((p) => (
            <Button
              key={p.label}
              variant="outline"
              size="sm"
              className="text-[10px] h-7"
              onClick={() => {
                setLoadPct(p.loadPct); setLmpPrice(p.lmpPrice); setReserves(p.reserves);
              }}
            >
              {p.label}
            </Button>
          ))}
        </div>

        <div className="space-y-2">
          <div>
            <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>Load Capacity</span>
              <span>{loadPct}%</span>
            </div>
            <input type="range" min={30} max={100} value={loadPct} onChange={(e) => setLoadPct(+e.target.value)} className="w-full h-1 accent-orange-500" />
          </div>
          <div>
            <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>LMP Price</span>
              <span>${lmpPrice}/MWh</span>
            </div>
            <input type="range" min={10} max={9000} value={lmpPrice} onChange={(e) => setLmpPrice(+e.target.value)} className="w-full h-1 accent-orange-500" />
          </div>
          <div>
            <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>Op. Reserves</span>
              <span>{reserves} MW</span>
            </div>
            <input type="range" min={0} max={5000} value={reserves} onChange={(e) => setReserves(+e.target.value)} className="w-full h-1 accent-orange-500" />
          </div>
        </div>

        <div className="flex gap-2">
          <Button size="sm" className="flex-1" onClick={applyGrid}>Apply</Button>
          <Button size="sm" variant="outline" onClick={clearGrid}><X className="w-3 h-3" /></Button>
        </div>
      </CardContent>
    </Card>
  );
}
