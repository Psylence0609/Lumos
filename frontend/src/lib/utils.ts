import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const API_BASE = "/api/v1";

export async function apiFetch<T = any>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export function getThreatColor(level: string): string {
  switch (level) {
    case "critical": return "text-red-500";
    case "high": return "text-orange-500";
    case "medium": return "text-yellow-500";
    case "low": return "text-blue-400";
    default: return "text-green-500";
  }
}

export function getThreatBg(level: string): string {
  switch (level) {
    case "critical": return "bg-red-500/10 border-red-500/30";
    case "high": return "bg-orange-500/10 border-orange-500/30";
    case "medium": return "bg-yellow-500/10 border-yellow-500/30";
    case "low": return "bg-blue-500/10 border-blue-500/30";
    default: return "bg-green-500/10 border-green-500/30";
  }
}

export function formatWatts(watts: number): string {
  if (watts >= 1000) return `${(watts / 1000).toFixed(1)} kW`;
  return `${watts.toFixed(0)} W`;
}
