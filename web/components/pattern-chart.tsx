"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface PatternChartProps {
  x: number[];
  y: number[];
}

export function PatternChart({ x, y }: PatternChartProps) {
  const data = x
    .map((twoTheta, index) => ({
      twoTheta,
      intensity: y[index],
    }))
    .filter((point) => Number.isFinite(point.twoTheta) && Number.isFinite(point.intensity));

  if (!data.length) {
    return (
      <div className="grid h-80 place-items-center rounded-lg border border-dashed border-line bg-slate-50 text-sm text-slate-500">
        Canonical experimental XY data is not available.
      </div>
    );
  }

  return (
    <div className="h-[360px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 20, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#e7edf2" vertical={false} />
          <XAxis
            dataKey="twoTheta"
            type="number"
            domain={["dataMin", "dataMax"]}
            tick={{ fill: "#617487", fontSize: 11 }}
            tickFormatter={(value: number) => value.toFixed(1)}
            label={{
              value: "2θ (deg)",
              position: "insideBottom",
              offset: -2,
              fill: "#617487",
              fontSize: 12,
            }}
          />
          <YAxis
            tick={{ fill: "#617487", fontSize: 11 }}
            tickFormatter={(value: number) => Number(value).toLocaleString()}
            width={66}
            label={{
              value: "Intensity",
              angle: -90,
              position: "insideLeft",
              fill: "#617487",
              fontSize: 12,
            }}
          />
          <Tooltip
            contentStyle={{
              border: "1px solid #d9e2ea",
              borderRadius: 8,
              boxShadow: "0 8px 24px rgba(29, 43, 58, 0.08)",
            }}
            labelFormatter={(value) => `2θ ${Number(value).toFixed(4)}°`}
            formatter={(value) => [Number(value).toLocaleString(), "Intensity"]}
          />
          <Line
            type="monotone"
            dataKey="intensity"
            dot={false}
            stroke="#2474bb"
            strokeWidth={1.5}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
