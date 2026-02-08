import * as React from "react";
import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "success" | "warning" | "destructive" | "outline";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants = {
    default: "bg-primary/20 text-primary border-primary/30",
    success: "bg-green-500/20 text-green-400 border-green-500/30",
    warning: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    destructive: "bg-red-500/20 text-red-400 border-red-500/30",
    outline: "border-border text-muted-foreground",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };
