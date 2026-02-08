import { useState } from "react";
import { Sparkles, Check, X, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/utils";
import type { Pattern } from "@/types";

interface Props {
  patterns: Pattern[];
  onUpdate?: () => void;
}

export function PatternPanel({ patterns, onUpdate }: Props) {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleApprove = async (patternId: string) => {
    await apiFetch(`/patterns/${patternId}/approve`, { method: "POST" });
    onUpdate?.();
  };

  const handleDelete = async (patternId: string) => {
    if (deletingId === patternId) {
      // Second click = confirm delete
      await apiFetch(`/patterns/${patternId}/dismiss`, { method: "POST" });
      setDeletingId(null);
      onUpdate?.();
    } else {
      // First click = ask to confirm
      setDeletingId(patternId);
      // Auto-cancel after 3 seconds
      setTimeout(() => setDeletingId((prev) => (prev === patternId ? null : prev)), 3000);
    }
  };

  if (patterns.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400" />
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
          <Sparkles className="w-4 h-4 text-purple-400" />
          Patterns ({patterns.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {patterns.map((pattern) => (
          <div key={pattern.pattern_id} className="p-2.5 rounded-lg bg-muted/50 border border-border group">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium truncate mr-2">{pattern.name}</span>
              <div className="flex items-center gap-1">
                <Badge variant={pattern.approved ? "success" : "warning"}>
                  {pattern.approved ? "active" : `${(pattern.confidence * 100).toFixed(0)}%`}
                </Badge>
              </div>
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
                  onClick={() => handleDelete(pattern.pattern_id)}
                >
                  <Trash2 className="w-3 h-3 mr-0.5" />
                  {deletingId === pattern.pattern_id ? "Confirm" : "Delete"}
                </Button>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
