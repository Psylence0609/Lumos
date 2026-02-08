import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/utils";

export function useApi<T>(path: string, pollInterval?: number) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      const result = await apiFetch<T>(path);
      setData(result);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    fetch();
    if (pollInterval) {
      const id = setInterval(fetch, pollInterval);
      return () => clearInterval(id);
    }
  }, [fetch, pollInterval]);

  return { data, loading, error, refetch: fetch };
}
