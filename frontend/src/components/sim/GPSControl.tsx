import { useState } from "react";
import { MapPin, Home, Car, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/utils";

export function GPSControl() {
  const [location, setLocation] = useState("home");
  const [lat, setLat] = useState(30.2672);
  const [lon, setLon] = useState(-97.7431);

  const setGPSLocation = async (loc: string) => {
    setLocation(loc);
    await apiFetch("/simulation/gps/location", {
      method: "POST",
      body: JSON.stringify({ location: loc }),
    });
  };

  const setCoords = async () => {
    await apiFetch("/simulation/gps/coordinates", {
      method: "POST",
      body: JSON.stringify({ lat, lon }),
    });
  };

  const clearGPS = async () => {
    await apiFetch("/simulation/gps", { method: "DELETE" });
    setLocation("home");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-emerald-400" />
          GPS Location
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-1.5">
          {[
            { loc: "home", label: "Home", icon: Home },
            { loc: "away", label: "Away", icon: Car },
            { loc: "arriving", label: "Arriving", icon: MapPin },
            { loc: "leaving", label: "Leaving", icon: MapPin },
          ].map((opt) => (
            <Button
              key={opt.loc}
              variant={location === opt.loc ? "default" : "outline"}
              size="sm"
              className="text-[10px] h-7"
              onClick={() => setGPSLocation(opt.loc)}
            >
              <opt.icon className="w-3 h-3 mr-1" /> {opt.label}
            </Button>
          ))}
        </div>

        <div className="space-y-1.5">
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-[10px] text-muted-foreground">Lat</label>
              <input
                type="number"
                step="0.001"
                value={lat}
                onChange={(e) => setLat(+e.target.value)}
                className="w-full h-7 px-2 text-xs bg-muted border border-border rounded-md"
              />
            </div>
            <div className="flex-1">
              <label className="text-[10px] text-muted-foreground">Lon</label>
              <input
                type="number"
                step="0.001"
                value={lon}
                onChange={(e) => setLon(+e.target.value)}
                className="w-full h-7 px-2 text-xs bg-muted border border-border rounded-md"
              />
            </div>
          </div>
          <Button size="sm" variant="outline" className="w-full text-[10px] h-7" onClick={setCoords}>
            Set Coordinates
          </Button>
        </div>

        <Button size="sm" variant="outline" className="w-full" onClick={clearGPS}>
          <X className="w-3 h-3 mr-1" /> Clear Override
        </Button>
      </CardContent>
    </Card>
  );
}
