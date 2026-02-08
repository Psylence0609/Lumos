import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { animate, stagger } from "animejs";
import { Sparkles, Check, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/utils";
import type { Pattern } from "@/types";

interface Props {
  patterns: Pattern[];
  onUpdate?: () => void;
}

/* ── Confidence arc meter ── */
function ConfidenceArc({ confidence, approved }: { confidence: number; approved: boolean }) {
  const r = 9;
  const circ = 2 * Math.PI * r;
  const pct = approved ? 1 : confidence;
  const offset = circ * (1 - pct);
  const c = approved ? "#22c55e" : confidence >= 0.75 ? "#22c55e" : confidence >= 0.5 ? "#eab308" : "#f97316";
  return (
    <svg viewBox="0 0 24 24" className="w-6 h-6 shrink-0">
      <circle cx="12" cy="12" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="2" />
      <circle cx="12" cy="12" r={r} fill="none" stroke={c} strokeWidth="2"
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        style={{ transform: "rotate(-90deg)", transformOrigin: "center", transition: "stroke-dashoffset 0.5s cubic-bezier(0.33,1,0.68,1), stroke 0.4s" }} />
      {approved && (
        <path d="M8 12 L11 15 L16 10" stroke="#22c55e" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      )}
      {!approved && (
        <text x="12" y="13" textAnchor="middle" fontSize="6" fill={c} fontWeight="bold" dominantBaseline="middle">
          {(confidence * 100).toFixed(0)}
        </text>
      )}
    </svg>
  );
}

/* ── Pattern card ── */
function PatternCard({ pattern, index, onApprove, onDelete, deletingId }: {
  pattern: Pattern;
  index: number;
  onApprove: (id: string) => void;
  onDelete: (id: string) => void;
  deletingId: string | null;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [flashGreen, setFlashGreen] = useState(false);

  const handleApprove = (id: string) => {
    setFlashGreen(true);
    setTimeout(() => setFlashGreen(false), 600);
    onApprove(id);
  };

  return (
    <motion.div
      ref={cardRef}
      initial={{ opacity: 0, rotateX: 70, scale: 0.9 }}
      animate={{
        opacity: 1, rotateX: 0, scale: 1,
        backgroundColor: flashGreen ? "rgba(34,197,94,0.08)" : "rgba(255,255,255,0)",
      }}
      exit={{ opacity: 0, height: 0, marginBottom: 0, scaleY: 0.3, transition: { duration: 0.3, ease: [0.33, 1, 0.68, 1] } }}
      transition={{ delay: index * 0.08, duration: 0.42, ease: [0.33, 1, 0.68, 1] }}
      style={{ perspective: 600, transformOrigin: "top center" }}
      className="p-2.5 rounded-lg bg-muted/50 border border-border group overflow-hidden"
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium truncate mr-2">{pattern.name}</span>
        <ConfidenceArc confidence={pattern.confidence} approved={pattern.approved} />
      </div>
      <p className="text-[10px] text-muted-foreground mb-2">{pattern.description}</p>
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-zinc-600">
          Seen {pattern.frequency}x · {pattern.type}
        </span>
        <div className="flex gap-1">
          {!pattern.approved && pattern.ready_to_suggest && (
            <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" onClick={() => handleApprove(pattern.pattern_id)}>
              <Check className="w-3 h-3 mr-0.5" /> Accept
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className={`h-6 px-2 text-[10px] ${
              deletingId === pattern.pattern_id
                ? "text-red-400 bg-red-950/30 hover:bg-red-950/50"
                : "text-zinc-500 opacity-0 group-hover:opacity-100 hover:text-red-400"
            } transition-all`}
            onClick={() => onDelete(pattern.pattern_id)}
          >
            <Trash2 className="w-3 h-3 mr-0.5" />
            {deletingId === pattern.pattern_id ? "Confirm" : "Delete"}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

export function PatternPanel({ patterns, onUpdate }: Props) {
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  /* stagger entrance with animejs on mount */
  useEffect(() => {
    if (!listRef.current || patterns.length === 0) return;
    const cards = listRef.current.querySelectorAll("[data-pp-card]");
    if (cards.length === 0) return;
    animate(cards, { opacity: [0, 1], translateY: [12, 0], delay: stagger(60), duration: 450, ease: "out(4)" });
  }, [patterns.length]);

  const handleApprove = async (patternId: string) => {
    await apiFetch(`/patterns/${patternId}/approve`, { method: "POST" });
    onUpdate?.();
  };

  const handleDelete = async (patternId: string) => {
    if (deletingId === patternId) {
      await apiFetch(`/patterns/${patternId}/dismiss`, { method: "POST" });
      setDeletingId(null);
      onUpdate?.();
    } else {
      setDeletingId(patternId);
      setTimeout(() => setDeletingId((prev) => (prev === patternId ? null : prev)), 3000);
    }
  };

  if (patterns.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <motion.span animate={{ y: [-1, 1, -1] }} transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}>
              <Sparkles className="w-4 h-4 text-purple-400" />
            </motion.span>
            Patterns
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            No patterns detected yet. The system learns from your usage over time.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <motion.span animate={{ y: [-1, 1, -1] }} transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}>
            <Sparkles className="w-4 h-4 text-purple-400" />
          </motion.span>
          Patterns ({patterns.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div ref={listRef} className="space-y-3">
          <AnimatePresence>
            {patterns.map((pattern, i) => (
              <PatternCard
                key={pattern.pattern_id}
                pattern={pattern}
                index={i}
                onApprove={handleApprove}
                onDelete={handleDelete}
                deletingId={deletingId}
              />
            ))}
          </AnimatePresence>
        </div>
      </CardContent>
    </Card>
  );
}
