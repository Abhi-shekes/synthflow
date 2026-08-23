"use client";

import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";

import type { Trend } from "@/lib/types";

const POINTS = 48;

/**
 * The shape a trend will actually produce, drawn from its own parameters.
 *
 * A trend was previously six numbers in a row of text — "seasonal, base 20,
 * amplitude 5, period 24" — and whether that was the curve you meant was
 * knowable only by generating rows and reading them. The maths here mirrors
 * app.services.trends; it is a preview of the deterministic component, so the
 * random walk shows its expected drift rather than one particular walk.
 */
export function TrendPreview({ trend }: { trend: Trend }) {
  const data = Array.from({ length: POINTS }, (_, index) => ({
    x: index,
    y: valueAt(trend, index),
  }));

  const finite = data.every((point) => Number.isFinite(point.y));
  if (!finite) {
    return (
      <p className="font-mono text-[13px] text-ink-faint">
        Those parameters do not produce a drawable curve.
      </p>
    );
  }

  return (
    <div className="h-12 w-full" aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`trend-${trend.id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
            </linearGradient>
          </defs>
          {/* Domain from the data, not zero-based: these are shapes, and
              anchoring a seasonal curve to zero flattens the very variation
              the preview exists to show. */}
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Area
            type="monotone"
            dataKey="y"
            stroke="var(--series-1)"
            strokeWidth={2}
            fill={`url(#trend-${trend.id})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function valueAt(trend: Trend, step: number): number {
  const p = trend.params;
  switch (trend.trend_type) {
    case "linear":
      return (p.start ?? 0) + (p.slope ?? 1) * step;
    case "exponential":
      return (p.start ?? 1) * Math.pow(1 + (p.rate ?? 0.05), step);
    case "logistic": {
      const capacity = p.capacity ?? 100;
      const rate = p.rate ?? 0.3;
      const midpoint = p.midpoint ?? POINTS / 2;
      return capacity / (1 + Math.exp(-rate * (step - midpoint)));
    }
    case "seasonal":
    case "cyclic": {
      const base = p.base ?? 0;
      const amplitude = p.amplitude ?? 1;
      const period = p.period || 24;
      return base + amplitude * Math.sin((2 * Math.PI * step) / period);
    }
    case "random_walk":
      // The expected value of a symmetric walk is its start. Drawing one
      // sampled path would imply a shape the trend does not actually have.
      return p.start ?? 0;
    default:
      return 0;
  }
}
