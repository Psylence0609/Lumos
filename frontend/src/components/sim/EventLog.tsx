import { useEffect, useState } from "react";
import { ScrollText } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/utils";
import type { SystemEvent } from "@/types";

export function EventLog() {
  const [events, setEvents] = useState<SystemEvent[]>([]);

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const data = await apiFetch<SystemEvent[]>("/events?limit=30");
        setEvents(data);
      } catch {}
    };
    fetchEvents();
    const id = setInterval(fetchEvents, 5000);
    return () => clearInterval(id);
  }, []);

  const typeColor: Record<string, string> = {
    device_state_change: "default",
    device_command: "default",
    agent_decision: "warning",
    threat_assessment: "destructive",
    pattern_detected: "success",
    user_action: "success",
    system_event: "outline",
    voice_alert: "warning",
    simulation_override: "outline",
  } as any;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ScrollText className="w-4 h-4 text-zinc-400" />
          Event Log
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1 max-h-96 overflow-y-auto">
          {events.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">No events yet</p>
          ) : (
            events.map((event, i) => (
              <div key={`${event.event_id}-${i}`} className="flex items-start gap-2 py-1 px-1.5 rounded hover:bg-muted/30 text-[10px]">
                <span className="text-zinc-600 shrink-0 w-12">
                  {new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
                <Badge variant={(typeColor[event.event_type] as any) || "outline"} className="shrink-0">
                  {event.event_type.replace(/_/g, " ")}
                </Badge>
                <span className="text-muted-foreground truncate flex-1">
                  {event.source}: {JSON.stringify(event.data).slice(0, 80)}
                </span>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
