"use client";

import { useQuery } from "@tanstack/react-query";
import { executiveApi, growthApi } from "@/lib/api";
import { KpiCard } from "./kpi-card";
import { RevenueChart } from "@/components/charts/revenue-chart";
import { PipelineChart } from "@/components/charts/pipeline-chart";
import {
  Users, TrendingUp, DollarSign, Briefcase,
  Globe, Star, Activity, Target,
} from "lucide-react";
import { formatCurrency, getScoreColor, COUNTRY_FLAGS } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { CountryHeatmapEntry, Opportunity, Recommendation } from "@/types";

export function ExecutiveDashboard() {
  const { data: overview, isLoading: loadingOverview } = useQuery({
    queryKey: ["executive", "overview"],
    queryFn: executiveApi.overview,
    refetchInterval: 60_000,
  });

  const { data: forecast, isLoading: loadingForecast } = useQuery({
    queryKey: ["executive", "forecast"],
    queryFn: executiveApi.forecast,
    staleTime: 300_000,
  });

  const { data: activeDeals, isLoading: loadingDeals } = useQuery({
    queryKey: ["executive", "activeDeals"],
    queryFn: executiveApi.activeDeals,
    refetchInterval: 120_000,
  });

  const { data: heatmap, isLoading: loadingHeatmap } = useQuery({
    queryKey: ["executive", "countryHeatmap"],
    queryFn: executiveApi.countryHeatmap,
    staleTime: 300_000,
  });

  const { data: recommendations, isLoading: loadingRecs } = useQuery({
    queryKey: ["executive", "recommendations"],
    queryFn: growthApi.recommendations,
    staleTime: 300_000,
  });

  // Normalise API responses — endpoints may return a bare array OR {items:[...]}
  const dealsArray: Opportunity[] = Array.isArray(activeDeals)
    ? activeDeals
    : ((activeDeals as unknown as { items?: Opportunity[] })?.items ?? []);

  const recsArray: Recommendation[] = Array.isArray(recommendations)
    ? recommendations
    : ((recommendations as unknown as { items?: Recommendation[] })?.items ?? []);

  const heatmapArray: CountryHeatmapEntry[] = Array.isArray(heatmap)
    ? heatmap
    : ((heatmap as unknown as { items?: CountryHeatmapEntry[] })?.items ?? []);

  // Pipeline by stage
  const pipelineData = (() => {
    const byStage: Record<string, { count: number; value: number }> = {};
    for (const deal of dealsArray) {
      const s = deal.stage ?? "unknown";
      if (!byStage[s]) byStage[s] = { count: 0, value: 0 };
      byStage[s].count++;
      byStage[s].value += deal.estimated_value_usd ?? 0;
    }
    return Object.entries(byStage).map(([stage, d]) => ({ stage, ...d }));
  })();

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Executive Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Real-time export intelligence overview</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="New Buyers Today"
          value={overview?.new_buyers_today ?? 0}
          icon={Users}
          iconColor="text-blue-500"
          loading={loadingOverview}
          description="Discovered & scored"
        />
        <KpiCard
          title="Active Pipeline"
          value={overview?.total_pipeline_value_usd ?? 0}
          format="currency"
          icon={DollarSign}
          iconColor="text-emerald-500"
          loading={loadingOverview}
          description="Weighted deal value"
        />
        <KpiCard
          title="Active Deals"
          value={overview?.active_deals ?? 0}
          icon={Briefcase}
          iconColor="text-violet-500"
          loading={loadingOverview}
          description="Open opportunities"
        />
        <KpiCard
          title="Avg Deal Probability"
          value={overview?.avg_deal_probability ?? 0}
          format="percent"
          icon={Target}
          iconColor="text-amber-500"
          loading={loadingOverview}
          description="Closure prediction"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 6-month forecast */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-foreground">6-Month Revenue Forecast</h2>
            <p className="text-xs text-muted-foreground mt-0.5">Base · Upside · Confirmed</p>
          </div>
          <RevenueChart data={forecast ?? []} loading={loadingForecast} />
        </div>

        {/* Pipeline by stage */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-foreground">Pipeline by Stage</h2>
            <p className="text-xs text-muted-foreground mt-0.5">{dealsArray.length} active deals</p>
          </div>
          <PipelineChart data={pipelineData} loading={loadingDeals} />
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top 10 recommendations */}
        <div className="rounded-xl border border-border bg-card">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Today's Top Opportunities</h2>
              <p className="text-xs text-muted-foreground">AI-ranked for immediate outreach</p>
            </div>
            <Activity className="w-4 h-4 text-primary" />
          </div>
          <div className="divide-y divide-border">
            {loadingRecs ? (
              Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="px-5 py-3 flex items-center gap-3">
                  <div className="w-6 h-6 skeleton rounded-full" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3.5 w-36 skeleton rounded" />
                    <div className="h-3 w-24 skeleton rounded" />
                  </div>
                  <div className="h-6 w-12 skeleton rounded-full" />
                </div>
              ))
            ) : recsArray.slice(0, 8).map((rec, idx) => (
              <div key={rec.opportunity_id} className="px-5 py-3 flex items-center gap-3 hover:bg-accent/30 transition-colors">
                <span className="text-xs font-mono text-muted-foreground w-5 text-right shrink-0">
                  {rec.rank ?? idx + 1}
                </span>
                <span className="text-base shrink-0">
                  {COUNTRY_FLAGS[rec.country] ?? "🌍"}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{rec.company_name}</p>
                  <p className="text-xs text-muted-foreground">{rec.country} · {rec.buyer_type}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className={cn("text-sm font-bold", getScoreColor(rec.opportunity_score))}>
                    {rec.opportunity_score?.toFixed(0)}
                  </p>
                  {rec.is_emerging && (
                    <span className="text-[10px] text-amber-500 font-medium">Emerging</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Country heatmap */}
        <div className="rounded-xl border border-border bg-card">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Country Opportunity Index</h2>
              <p className="text-xs text-muted-foreground">Top markets by opportunity score</p>
            </div>
            <Globe className="w-4 h-4 text-primary" />
          </div>
          <div className="px-5 py-3 space-y-2 max-h-80 overflow-y-auto scrollbar-thin">
            {loadingHeatmap ? (
              Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="h-3.5 w-24 skeleton rounded" />
                  <div className="flex-1 h-2 skeleton rounded-full" />
                  <div className="h-3.5 w-10 skeleton rounded" />
                </div>
              ))
            ) : heatmapArray.slice(0, 12).map((entry) => (
              <div key={entry.country} className="flex items-center gap-3">
                <div className="flex items-center gap-1.5 w-28 shrink-0">
                  <span className="text-sm">{COUNTRY_FLAGS[entry.country] ?? "🌍"}</span>
                  <span className="text-xs font-medium text-foreground">{entry.country}</span>
                </div>
                <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all"
                    style={{ width: `${(entry.opportunity_index / 100) * 100}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-muted-foreground w-10 text-right shrink-0">
                  {entry.opportunity_index?.toFixed(1)}
                </span>
                <span className="text-xs text-muted-foreground w-16 text-right shrink-0">
                  {formatCurrency(entry.pipeline_value_usd, "USD", "compact")}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Lead status breakdown */}
      {overview?.leads_by_status && (
        <div className="rounded-xl border border-border bg-card p-5">
          <h2 className="text-sm font-semibold text-foreground mb-4">Lead Status Distribution</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            {Object.entries(overview.leads_by_status).map(([status, count]) => (
              <div key={status} className="text-center">
                <p className="text-lg font-bold text-foreground">{count}</p>
                <p className="text-xs text-muted-foreground capitalize">{status.replace("_", " ")}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
