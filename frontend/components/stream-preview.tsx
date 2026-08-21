"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

const MAX_MESSAGES = 5;

export function StreamPreview({ wsUrl }: { wsUrl: string }) {
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<string[]>([]);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    return () => {
      socketRef.current?.close();
    };
  }, []);

  const start = () => {
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);
    socket.onmessage = (event) => {
      setMessages((prev) => [event.data, ...prev].slice(0, MAX_MESSAGES));
    };
  };

  const stop = () => {
    socketRef.current?.close();
    socketRef.current = null;
    setConnected(false);
  };

  return (
    <div className="flex flex-col gap-2 rounded-md border p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">
          {connected ? "Live" : "Preview"}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={connected ? stop : start}
        >
          {connected ? "Disconnect" : "Connect"}
        </Button>
      </div>
      {messages.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          {connected ? "Waiting for the first batch…" : "Not connected."}
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {messages.map((msg, i) => (
            <li key={i} className="truncate font-mono text-xs text-muted-foreground">
              {msg}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
