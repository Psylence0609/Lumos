import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { animate } from "animejs";
import { Bot } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { AgentInfo } from "@/types";

interface Props {
  agents: AgentInfo[];
}

const STATUS_COLORS: Record<string, string> = {
  running: "bg-green-400",
  idle: "bg-blue-400",
  error: "bg-red-400",
  stopped: "bg-zinc-600",
};

const STATUS_TEXT_COLORS: Record<string, string> = {
  running: "text-green-400",
  idle: "text-blue-400",
  error: "text-red-400",
  stopped: "text-zinc-600",
};

/* ── Breathing Status Dot ── */
function StatusDot({ status }: { status: string }) {
  const bgClass = STATUS_COLORS[status] || "bg-zinc-600";
  const isActive = status === "running";
  const isIdle = status === "idle";
  const isError = status === "error";

  return (
    <span className="relative flex items-center justify-center w-3 h-3">
      <span className={cn("w-2 h-2 rounded-full relative z-10", bgClass)} />
      {isActive && (
        <span className={cn("absolute inset-0 rounded-full opacity-40", bgClass)}
          style={{ animation: "aa-breathe 1.2s ease-in-out infinite" }} />
      )}
      {isIdle && (
        <span className={cn("absolute inset-0 rounded-full opacity-25", bgClass)}
          style={{ animation: "aa-breathe 2.5s ease-in-out infinite" }} />
      )}
      {isError && (
        <span className={cn("absolute inset-0 rounded-full opacity-50", bgClass)}
          style={{ animation: "aa-flash 0.6s ease-in-out infinite" }} />
      )}
    </span>
  );
}

/* ── Typewriter text ── */
function TypewriterText({ text }: { text: string }) {
  const [shown, setShown] = useState(text);
  const prevRef = useRef(text);
  const [reveal, setReveal] = useState(text.length);

  useEffect(() => {
    if (prevRef.current === text) return;
    prevRef.current = text;
    setShown(text);
    setReveal(0);
    const len = text.length;
    const step = Math.max(1, Math.floor(len / 30)); // finish in ~30 ticks
    let i = 0;
    const id = setInterval(() => {
      i += step;
      if (i >= len) { setReveal(len); clearInterval(id); }
      else setReveal(i);
    }, 20);
    return () => clearInterval(id);
  }, [text]);

  return (
    <span className="text-[10px] text-muted-foreground">
      {shown.slice(0, reveal)}
      {reveal < shown.length && (
        <span className="inline-block w-0.5 h-2.5 bg-muted-foreground/40 align-middle ml-px animate-pulse" />
      )}
    </span>
  );
}

/* ── Single Agent Row ── */
function AgentRow({ agent, index }: { agent: AgentInfo; index: number }) {
  const rowRef = useRef<HTMLDivElement>(null);

  /* error shake */
  useEffect(() => {
    if (agent.status !== "error" || !rowRef.current) return;
    animate(rowRef.current, { translateX: [-3, 3, -2, 2, 0], duration: 420, ease: "out(3)" });
  }, [agent.status]);

  return (
    <motion.div
      ref={rowRef}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.07, duration: 0.4, ease: [0.33, 1, 0.68, 1] }}
      className="p-2 rounded-md bg-muted/30 border border-border/50"
      style={agent.status === "idle" ? { animation: "aa-float 4s ease-in-out infinite" } : undefined}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <StatusDot status={agent.status} />
          <span className="text-xs font-medium">{agent.display_name}</span>
        </div>
        <span className={cn("text-[10px]", STATUS_TEXT_COLORS[agent.status] || "text-zinc-600")}>
          {agent.status}
        </span>
      </div>
      {agent.last_action && (
        <div className="truncate">
          <TypewriterText text={agent.last_action} />
        </div>
      )}
      {agent.error && (
        <p className="text-[10px] text-red-400 truncate">Error: {agent.error}</p>
      )}
    </motion.div>
  );
}

/* inject keyframes */
const cssId = "aa-anim-css";
const css = `
@keyframes aa-breathe { 0%,100%{transform:scale(0.8) translateZ(0);opacity:0.3} 50%{transform:scale(1.5) translateZ(0);opacity:0.6} }
@keyframes aa-flash { 0%,100%{opacity:0.2} 50%{opacity:0.8} }
@keyframes aa-float { 0%,100%{transform:translateY(0) translateZ(0)} 50%{transform:translateY(-1.5px) translateZ(0)} }
`;

export function AgentActivity({ agents }: Props) {
  useEffect(() => {
    if (document.getElementById(cssId)) return;
    const s = document.createElement("style");
    s.id = cssId;
    s.textContent = css;
    document.head.appendChild(s);
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-blue-400" />
          Agents
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <AnimatePresence>
          {agents.map((agent, i) => (
            <AgentRow key={agent.agent_id} agent={agent} index={i} />
          ))}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}
