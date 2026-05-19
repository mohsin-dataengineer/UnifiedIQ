"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fmtValue } from "@/lib/format";
import type { Row } from "@/lib/types";

const PALETTE = [
  "#4f46e5",
  "#16a34a",
  "#ea580c",
  "#0891b2",
  "#db2777",
  "#7c3aed",
  "#ca8a04",
];

const axis = { stroke: "#94a3b8", fontSize: 12 } as const;

export function ChartRenderer({
  type,
  x,
  y,
  data,
}: {
  type: "bar" | "line" | "area" | "pie";
  x: string;
  y: string[];
  data: Row[];
}) {
  const tip = (
    <Tooltip
      formatter={(v: unknown) => fmtValue(v)}
      contentStyle={{
        borderRadius: 10,
        border: "1px solid #e6e8f0",
        fontSize: 12,
      }}
    />
  );
  const grid = <CartesianGrid strokeDasharray="3 3" stroke="#eef0f6" />;

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {type === "line" ? (
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4 }}>
            {grid}
            <XAxis dataKey={x} {...axis} />
            <YAxis {...axis} />
            {tip}
            <Legend />
            {y.map((k, i) => (
              <Line
                key={k}
                type="monotone"
                dataKey={k}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        ) : type === "area" ? (
          <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 4 }}>
            {grid}
            <XAxis dataKey={x} {...axis} />
            <YAxis {...axis} />
            {tip}
            <Legend />
            {y.map((k, i) => (
              <Area
                key={k}
                type="monotone"
                dataKey={k}
                stroke={PALETTE[i % PALETTE.length]}
                fill={PALETTE[i % PALETTE.length]}
                fillOpacity={0.18}
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        ) : type === "pie" ? (
          <PieChart>
            {tip}
            <Legend />
            <Pie
              data={data}
              dataKey={y[0]}
              nameKey={x}
              outerRadius={110}
              innerRadius={55}
              paddingAngle={2}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Pie>
          </PieChart>
        ) : (
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: 4 }}>
            {grid}
            <XAxis dataKey={x} {...axis} />
            <YAxis {...axis} />
            {tip}
            <Legend />
            {y.map((k, i) => (
              <Bar
                key={k}
                dataKey={k}
                fill={PALETTE[i % PALETTE.length]}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
