import { Bot, Circle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { AgentInfo } from "@/types";

interface Props {
  agents: AgentInfo[];
}

const STATUS_COLORS: Record<string, string> = {
  running: "text-green-400",
  idle: "text-blue-400",
  error: "text-red-400",
  stopped: "text-zinc-600",
};

export function AgentActivity({ agents }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-blue-400" />
          Agents
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {agents.map((agent) => (
          <div key={agent.agent_id} className="p-2 rounded-md bg-muted/30 border border-border/50">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-1.5">
                <Circle className={cn("w-2 h-2 fill-current", STATUS_COLORS[agent.status] || "text-zinc-600")} />
                <span className="text-xs font-medium">{agent.display_name}</span>
              </div>
              <span className="text-[10px] text-muted-foreground">{agent.status}</span>
            </div>
            {agent.last_action && (
              <p className="text-[10px] text-muted-foreground truncate">{agent.last_action}</p>
            )}
            {agent.error && (
              <p className="text-[10px] text-red-400 truncate">Error: {agent.error}</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
