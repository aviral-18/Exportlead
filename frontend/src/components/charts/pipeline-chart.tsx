"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { formatCurrency } from "@/lib/utils";

const STAGE_COLORS: Record<string, string> = {
  qualified: "#8b5cf6",
  proposal: "#3b82f6",
  sample_sent: "#f59e0b",
  quoted: "#f97316",
  negotiating: "#ef4444",
  won: "#10b981",
};

interface PipelineChartProps {
  data: Array<{ stage: string; count: number; value: number }>;
  loading?: boolean;
}

export function PipelineChart({ data, loading }: PipelineChartProps) {
  if (loading) {
    return (
      <div className="h-40 flex items-end gap-3 px-2">
        {[60, 45, 80, 55, 30].map((h, i) => (
          <div key={i} className="flex-1 skeleton rounded-t" style={{ height: `${h}%` }} />
        ))}
      </div>
    );
  }

  if (!data?.length) return (
    <div className="h-40 flex items-center justify-center text-sm text-muted-foreground">
      No pipeline data
    </div>
  );

  const chartData = data.map((d) => ({
    stage: d.stage.replace("_", " "),
    Value: d.value,
    Count: d.count,
    color: STAGE_COLORS[d.stage] ?? "#6b7280",
  }));

  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
        <XAxis dataKey="stage" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
        <YAxis
          tickFormatter={(v) => formatCurrency(v, "USD", "compact")}
          tick={{ fontSize: 10 }}
          stroke="hsl(var(--muted-foreground))"
          width={55}
        />
        <Tooltip
          formatter={(v: number, name: string) => [
            name === "Value" ? formatCurrency(v) : v,
            name,
          ]}
          contentStyle={{
            backgroundColor: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Bar dataKey="Value" radius={[4, 4, 0, 0]}>
          {chartData.map((entry, index) => (
            <Cell key={index} fill={entry.color} opacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
