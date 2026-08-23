"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";

const MAX_MESSAGES = 12;

interface Tick {
  id: number;
  text: string;
  at: number;
}

/**
 * A live stream as a tape of arriving rows.
 *
 * Replaces a `<ul>` of five truncated strings that gave no sense of *rate* —
 * whether a stream was producing two rows a second or two hundred looked
 * identical. New rows enter at the top with the arrival gap printed beside
 * them, so the tape reads as motion rather than a list that occasionally
 * changes.
 */
export function StreamPreview({ wsUrl }: { wsUrl: string }) {
  const [connected, setConnected] = useState(false);
  const [ticks, setTicks] = useState<Tick[]>([]);
  const [rate, setRate] = useState(0);
  const socketRef = useRef<WebSocket | null>(null);
  const seq = useRef(0);
  const lastAt = useRef<number | null>(null);
  const reduced = useReducedMotion();

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
      const now = performance.now();
      const gap = lastAt.current === null ? 0 : now - lastAt.current;
      lastAt.current = now;
      // Smoothed, because a raw instantaneous rate from one gap jitters too
      // hard to read.
      if (gap > 0) setRate((prev) => (prev === 0 ? 1000 / gap : prev * 0.7 + (1000 / gap) * 0.3));
      setTicks((prev) =>
        [{ id: seq.current++, text: String(event.data), at: gap }, ...prev].slice(0, MAX_MESSAGES)
      );
    };
  };

  const stop = () => {
    socketRef.current?.close();
    socketRef.current = null;
    lastAt.current = null;
    setConnected(false);
    setRate(0);
  };

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-line bg-surface-2 p-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5">
          <span
            className={cn(
              "size-1.5 rounded-full",
              connected ? "bg-sev-ok" : "bg-ink-faint",
              connected && !reduced && "sf-pulse"
            )}
          />
          <span className="eyebrow">{connected ? "receiving" : "not connected"}</span>
          {connected && rate > 0 && (
            <span className="font-mono text-xs text-ink-faint">
              ~{rate.toFixed(1)}/s
            </span>
          )}
        </span>
        <Button variant="outline" size="xs" onClick={connected ? stop : start}>
          {connected ? "Disconnect" : "Connect"}
        </Button>
      </div>

      <div className="relative h-40 overflow-hidden rounded border border-line-soft bg-surface">
        {ticks.length === 0 ? (
          <p className="flex h-full items-center justify-center text-[13px] text-ink-faint">
            {connected ? "Waiting for the first batch…" : "Connect to watch rows arrive."}
          </p>
        ) : (
          <ul className="flex h-full flex-col overflow-hidden">
            {ticks.map((tick, index) => (
              <li
                key={tick.id}
                className={cn(
                  "flex shrink-0 items-baseline gap-2 border-b border-line-soft px-2 py-1 font-mono text-[13px]",
                  index === 0 && !reduced && "sf-rise"
                )}
                style={{
                  // Older rows fade toward the bottom of the tape, so the eye
                  // goes to what just arrived.
                  opacity: Math.max(0.25, 1 - index * 0.09),
                }}
              >
                <span className="w-12 shrink-0 text-right text-ink-faint">
                  {tick.at > 0 ? `+${Math.round(tick.at)}ms` : "—"}
                </span>
                <span className="truncate text-ink-dim">{tick.text}</span>
              </li>
            ))}
          </ul>
        )}
        {/* The tape runs off the bottom rather than stopping at a hard edge. */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-surface to-transparent" />
      </div>
    </div>
  );
}
