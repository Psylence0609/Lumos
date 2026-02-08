import { useEffect, useRef, useCallback, useState } from "react";
import type { WSMessage } from "@/types";

type MessageHandler = (msg: WSMessage) => void;

export function useWebSocket(handlers: Record<string, MessageHandler>) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
      setConnected(true);
      console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        const handler = handlersRef.current[msg.type];
        if (handler) handler(msg);
      } catch (e) {
        console.error("WS parse error:", e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      console.log("WebSocket disconnected, reconnecting in 3s...");
      setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected };
}
