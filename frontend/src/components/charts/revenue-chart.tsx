"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import type { ForecastMonth } from "@/types";
import { formatCurrency } from "@/lib/utils";

interface RevenueChartProps {
  data: ForecastMonth[];
  loading?: boolean;
}

function SkeletonChart() {
  return (
    <div className="h-48 flex items-end gap-2 px-2">
      {[40, 55, 35, 70, 60, 80].map((h, i) => (
        <div key={i} className="flex-1 skeleton rounded-t" style={{ height: `${h}%` }} />
      ))}
    </div>
  );
}

export function RevenueChart({ data, loading }: RevenueChartProps) {
  if (loading) return <SkeletonChart />;
  if (!data?.length) return (
    <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
      No forecast data available
    </div>
  );

  const chartData = data.map((d) => ({
    month: d.month,
    Base: Math.round(d.base_usd),
    Upside: Math.round(d.upside_usd),
    Confirmed: Math.round(d.confirmed_usd),
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorBase" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorUpside" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorConfirmed" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
        <YAxis
          tickFormatter={(v) => formatCurrency(v, "USD", "compact")}
          tick={{ fontSize: 10 }}
          stroke="hsl(var(--muted-foreground))"
          width={60}
        />
        <Tooltip
          formatter={(v: number) => [formatCurrency(v), undefined]}
          contentStyle={{
            backgroundColor: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Legend wrapperStyle={{ fontSize: "11px" }} />
        <Area type="monotone" dataKey="Upside" stroke="#10b981" strokeWidth={1.5} fill="url(#colorUpside)" strokeDasharray="4 2" />
        <Area type="monotone" dataKey="Base" stroke="hsl(var(--primary))" strokeWidth={2} fill="url(#colorBase)" />
        <Area type="monotone" dataKey="Confirmed" stroke="#3b82f6" strokeWidth={2} fill="url(#colorConfirmed)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
