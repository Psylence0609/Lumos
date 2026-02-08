import { Bot, Circle, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AgentInfo } from "@/types";

interface Props {
  agents: AgentInfo[];
  onRefresh: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  running: "text-green-400 bg-green-400/20",
  idle: "text-blue-400 bg-blue-400/20",
  error: "text-red-400 bg-red-400/20",
  stopped: "text-zinc-500 bg-zinc-500/20",
};

export function AgentInspector({ agents, onRefresh }: Props) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-blue-400" />
            Agent Inspector
          </CardTitle>
          <Button size="icon" variant="ghost" className="h-6 w-6" onClick={onRefresh}>
            <RefreshCw className="w-3 h-3" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {agents.map((agent) => (
          <div key={agent.agent_id} className="p-2.5 rounded-lg bg-muted/30 border border-border/50">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <Circle className={cn("w-2.5 h-2.5 fill-current", STATUS_COLORS[agent.status]?.split(" ")[0] || "text-zinc-600")} />
                <span className="text-xs font-medium">{agent.display_name}</span>
              </div>
              <span className={cn("text-[10px] px-1.5 py-0.5 rounded", STATUS_COLORS[agent.status] || "text-zinc-500")}>
                {agent.status}
              </span>
            </div>

            {agent.last_action && (
              <div className="mb-1">
                <span className="text-[10px] text-muted-foreground font-medium">Action: </span>
                <span className="text-[10px] text-foreground">{agent.last_action}</span>
              </div>
            )}

            {agent.last_reasoning && (
              <div className="mb-1">
                <span className="text-[10px] text-muted-foreground font-medium">Reasoning: </span>
                <span className="text-[10px] text-zinc-400">{agent.last_reasoning.slice(0, 200)}</span>
              </div>
            )}

            {agent.last_run && (
              <span className="text-[10px] text-zinc-600">
                Last: {new Date(agent.last_run).toLocaleTimeString()}
              </span>
            )}

            {agent.error && (
              <p className="text-[10px] text-red-400 mt-1">Error: {agent.error}</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
