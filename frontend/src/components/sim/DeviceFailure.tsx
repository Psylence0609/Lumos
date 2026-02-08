import { useState } from "react";
import { WifiOff } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/utils";
import type { DeviceState } from "@/types";

interface Props {
  devices: DeviceState[];
}

export function DeviceFailure({ devices }: Props) {
  const [failing, setFailing] = useState<Set<string>>(new Set());

  const toggleFailure = async (deviceId: string) => {
    const isCurrentlyFailing = failing.has(deviceId);
    await apiFetch("/simulation/device-failure", {
      method: "POST",
      body: JSON.stringify({ device_id: deviceId, offline: !isCurrentlyFailing }),
    });
    setFailing((prev) => {
      const next = new Set(prev);
      if (isCurrentlyFailing) next.delete(deviceId);
      else next.add(deviceId);
      return next;
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <WifiOff className="w-4 h-4 text-red-400" />
          Device Failure
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {devices.map((d) => (
            <div key={d.device_id} className="flex items-center justify-between py-1 px-1.5 rounded hover:bg-muted/50">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-[10px] text-muted-foreground truncate">{d.room}</span>
                <span className="text-xs truncate">{d.display_name}</span>
                {!d.online && <Badge variant="destructive">offline</Badge>}
              </div>
              <Button
                size="sm"
                variant={failing.has(d.device_id) ? "destructive" : "outline"}
                className="text-[10px] h-6 px-2 shrink-0"
                onClick={() => toggleFailure(d.device_id)}
              >
                {failing.has(d.device_id) ? "Restore" : "Fail"}
              </Button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
