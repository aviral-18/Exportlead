"use client";

import { useQuery } from "@tanstack/react-query";
import { analyticsApi, executiveApi } from "@/lib/api";
import { formatCurrency, COUNTRY_FLAGS } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis,
} from "recharts";
import { BarChart3, Globe, TrendingUp, Users, Star, Activity } from "lucide-react";
import { RevenueChart } from "@/components/charts/revenue-chart";

const TIER_COLORS: Record<string, string> = {
  A: "#10b981",
  B: "#3b82f6",
  C: "#f59e0b",
  D: "#f97316",
  F: "#ef4444",
};

export function AnalyticsDashboard() {
  const { data: overview, isLoading: loadingOverview } = useQuery({
    queryKey: ["analytics", "overview"],
    queryFn: analyticsApi.overview,
    staleTime: 300_000,
  });

  const { data: forecast, isLoading: loadingForecast } = useQuery({
    queryKey: ["executive", "forecast"],
    queryFn: executiveApi.forecast,
    staleTime: 300_000,
  });

  const { data: scoreDist, isLoading: loadingScores } = useQuery({
    queryKey: ["scoring", "distribution"],
    queryFn: analyticsApi.scoring.distribution,
    staleTime: 300_000,
  });

  const { data: topBuyers, isLoading: loadingTop } = useQuery({
    queryKey: ["scoring", "top-buyers"],
    queryFn: () => analyticsApi.scoring.topBuyers(10),
    staleTime: 120_000,
  });

  const { data: countryTrends, isLoading: loadingCountries } = useQuery({
    queryKey: ["analytics", "country-trends"],
    queryFn: analyticsApi.countryTrends,
    staleTime: 300_000,
  });

  // Transform tier distribution data
  const tierData = scoreDist?.by_tier
    ? Object.entries(scoreDist.by_tier as Record<string, number>).map(([tier, count]) => ({
        name: `Tier ${tier}`,
        value: count,
        color: TIER_COLORS[tier] ?? "#6b7280",
      }))
    : [];

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Analytics & Forecasts</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Buyer intelligence · Pipeline trends · Revenue projections
        </p>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: "Total Buyers Scored",
            value: loadingScores ? "—" : (scoreDist?.total_scored?.toLocaleString() ?? "—"),
            icon: Users,
            color: "text-blue-500",
          },
          {
            label: "Tier A Buyers",
            value: loadingScores ? "—" : (scoreDist?.by_tier?.A?.toLocaleString() ?? "0"),
            icon: Star,
            color: "text-emerald-500",
          },
          {
            label: "Avg Composite Score",
            value: loadingScores ? "—" : `${(scoreDist?.avg_score ?? 0).toFixed(1)}`,
            icon: Activity,
            color: "text-primary",
          },
          {
            label: "Countries Covered",
            value: loadingCountries ? "—" : ((countryTrends as unknown[])?.length?.toString() ?? "—"),
            icon: Globe,
            color: "text-violet-500",
          },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-muted-foreground">{label}</p>
              <Icon className={`w-4 h-4 ${color}`} />
            </div>
            <p className="text-2xl font-bold text-foreground">{value}</p>
          </div>
        ))}
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Revenue forecast */}
        <div className="rounded-xl border border-border bg-card p-5">
          <h2 className="text-sm font-semibold text-foreground mb-1">6-Month Export Forecast</h2>
          <p className="text-xs text-muted-foreground mb-4">Base · Upside · Confirmed (seasonal factors applied)</p>
          <RevenueChart data={forecast ?? []} loading={loadingForecast} />
        </div>

        {/* Tier distribution */}
        <div className="rounded-xl border border-border bg-card p-5">
          <h2 className="text-sm font-semibold text-foreground mb-1">Buyer Tier Distribution</h2>
          <p className="text-xs text-muted-foreground mb-4">AI scoring across global buyer database</p>
          {loadingScores ? (
            <div className="h-48 skeleton rounded-xl" />
          ) : tierData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={tierData} cx="50%" cy="50%" innerRadius={55} outerRadius={80}
                  paddingAngle={3} dataKey="value">
                  {tierData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => [v.toLocaleString(), "Buyers"]} />
                <Legend wrapperStyle={{ fontSize: "11px" }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
              No scoring data available
            </div>
          )}
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top buyers by score */}
        <div className="rounded-xl border border-border bg-card p-5">
          <h2 className="text-sm font-semibold text-foreground mb-4">Top 10 Buyers by AI Score</h2>
          {loadingTop ? (
            <div className="h-48 skeleton rounded-xl" />
          ) : (topBuyers as Array<{ name: string; score: number; country: string }>)?.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={(topBuyers as Array<{ name: string; score: number; country: string }>)?.slice(0, 10)}
                layout="vertical"
                margin={{ left: 10, right: 20, top: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fontSize: 9 }}
                  width={90}
                  tickFormatter={(v: string) => v.length > 12 ? `${v.slice(0, 12)}...` : v}
                />
                <Tooltip
                  formatter={(v: number) => [`${v.toFixed(1)}`, "Score"]}
                  contentStyle={{
                    backgroundColor: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="score" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} opacity={0.9} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
              Score buyers to see results
            </div>
          )}
        </div>

        {/* Country distribution */}
        <div className="rounded-xl border border-border bg-card p-5">
          <h2 className="text-sm font-semibold text-foreground mb-4">Buyers by Country</h2>
          {loadingCountries ? (
            <div className="h-48 skeleton rounded-xl" />
          ) : (countryTrends as Array<{ country: string; count: number; avg_score: number }>)?.length > 0 ? (
            <div className="space-y-2 max-h-52 overflow-y-auto scrollbar-thin">
              {(countryTrends as Array<{ country: string; count: number; avg_score: number }>)
                ?.slice(0, 15)
                .map((c) => (
                  <div key={c.country} className="flex items-center gap-3">
                    <span className="text-sm shrink-0">{COUNTRY_FLAGS[c.country] ?? "🌍"}</span>
                    <span className="text-xs font-medium text-foreground w-12 shrink-0">{c.country}</span>
                    <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all"
                        style={{
                          width: `${Math.min(100, (c.count / ((countryTrends as Array<{ count: number }>)[0]?.count ?? 1)) * 100)}%`,
                        }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground font-mono w-12 text-right shrink-0">
                      {c.count.toLocaleString()}
                    </span>
                    <span className="text-xs text-muted-foreground font-mono w-10 text-right shrink-0">
                      {c.avg_score?.toFixed(0)}
                    </span>
                  </div>
                ))}
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
              No country data available
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
