import { useState } from "react";
import { CloudSun, CloudSnow, CloudLightning, Sun, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/utils";

export function WeatherInjector() {
  const [temp, setTemp] = useState(75);
  const [humidity, setHumidity] = useState(50);
  const [wind, setWind] = useState(5);
  const [desc, setDesc] = useState("clear");

  const applyWeather = async () => {
    await apiFetch("/simulation/weather", {
      method: "POST",
      body: JSON.stringify({
        temperature_f: temp,
        humidity,
        wind_speed_mph: wind,
        description: desc,
      }),
    });
  };

  const clearWeather = async () => {
    await apiFetch("/simulation/weather", { method: "DELETE" });
  };

  const presets = [
    { label: "Extreme Heat", icon: Sun, temp: 108, humidity: 20, wind: 5, desc: "extreme heat warning" },
    { label: "Winter Storm", icon: CloudSnow, temp: 15, humidity: 80, wind: 25, desc: "winter storm warning with ice" },
    { label: "Thunderstorm", icon: CloudLightning, temp: 85, humidity: 90, wind: 40, desc: "severe thunderstorm warning" },
    { label: "Pleasant", icon: CloudSun, temp: 72, humidity: 45, wind: 8, desc: "partly cloudy" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CloudSun className="w-4 h-4 text-sky-400" />
          Weather
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Presets */}
        <div className="grid grid-cols-2 gap-1.5">
          {presets.map((p) => (
            <Button
              key={p.label}
              variant="outline"
              size="sm"
              className="text-[10px] h-7 justify-start"
              onClick={() => {
                setTemp(p.temp); setHumidity(p.humidity); setWind(p.wind); setDesc(p.desc);
              }}
            >
              <p.icon className="w-3 h-3 mr-1" /> {p.label}
            </Button>
          ))}
        </div>

        {/* Sliders */}
        <div className="space-y-2">
          <div>
            <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>Temperature</span>
              <span>{temp}°F</span>
            </div>
            <input type="range" min={-10} max={120} value={temp} onChange={(e) => setTemp(+e.target.value)} className="w-full h-1 accent-primary" />
          </div>
          <div>
            <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>Humidity</span>
              <span>{humidity}%</span>
            </div>
            <input type="range" min={0} max={100} value={humidity} onChange={(e) => setHumidity(+e.target.value)} className="w-full h-1 accent-primary" />
          </div>
          <div>
            <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>Wind</span>
              <span>{wind} mph</span>
            </div>
            <input type="range" min={0} max={80} value={wind} onChange={(e) => setWind(+e.target.value)} className="w-full h-1 accent-primary" />
          </div>
        </div>

        <div className="flex gap-2">
          <Button size="sm" className="flex-1" onClick={applyWeather}>Apply</Button>
          <Button size="sm" variant="outline" onClick={clearWeather}><X className="w-3 h-3" /></Button>
        </div>
      </CardContent>
    </Card>
  );
}
