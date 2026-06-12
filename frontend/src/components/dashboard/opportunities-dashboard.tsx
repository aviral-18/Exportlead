"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { growthApi } from "@/lib/api";
import { cn, formatCurrency, COUNTRY_FLAGS, relativeTime } from "@/lib/utils";
import {
  TrendingUp, Zap, Star, Globe, Plus, ChevronLeft, ChevronRight,
  CheckCircle, ArrowRight,
} from "lucide-react";
import { toast } from "sonner";
import type { GrowthOpportunity, Recommendation } from "@/types";

const TABS = [
  { id: "recommendations", label: "Top 10 Today", icon: Star },
  { id: "opportunities", label: "All Opportunities", icon: TrendingUp },
  { id: "emerging", label: "Emerging Importers", icon: Zap },
] as const;

type Tab = typeof TABS[number]["id"];

export function OpportunitiesDashboard() {
  const [tab, setTab] = useState<Tab>("recommendations");
  const [page, setPage] = useState(1);
  const [emergingOnly, setEmergingOnly] = useState(false);
  const qc = useQueryClient();

  const { data: recs, isLoading: loadingRecs } = useQuery({
    queryKey: ["growth", "recommendations"],
    queryFn: growthApi.recommendations,
    enabled: tab === "recommendations",
    staleTime: 300_000,
  });

  const { data: opps, isLoading: loadingOpps } = useQuery({
    queryKey: ["growth", "opportunities", page, emergingOnly],
    queryFn: () => growthApi.opportunities({ page, page_size: 20, emerging_only: emergingOnly }),
    enabled: tab === "opportunities",
    staleTime: 60_000,
  });

  const { data: emerging, isLoading: loadingEmerging } = useQuery({
    queryKey: ["growth", "emerging", page],
    queryFn: () => growthApi.emerging({ page, page_size: 20 }),
    enabled: tab === "emerging",
    staleTime: 60_000,
  });

  const addToCrmMutation = useMutation({
    mutationFn: growthApi.addToCrm,
    onSuccess: () => {
      toast.success("Added to CRM successfully");
      qc.invalidateQueries({ queryKey: ["crm"] });
    },
    onError: () => toast.error("Failed to add to CRM"),
  });

  const triggerMutation = useMutation({
    mutationFn: growthApi.triggerDiscovery,
    onSuccess: () => toast.success("Discovery run triggered — check back in a few minutes"),
    onError: () => toast.error("Failed to trigger discovery"),
  });

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Opportunities</h1>
          <p className="text-sm text-muted-foreground mt-0.5">AI-ranked global buyer opportunities</p>
        </div>
        <button
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-70"
        >
          <TrendingUp className="w-4 h-4" />
          {triggerMutation.isPending ? "Running..." : "Run Discovery"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-muted p-1 rounded-lg w-fit">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => { setTab(id); setPage(1); }}
            className={cn(
              "flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-all",
              tab === id
                ? "bg-card text-foreground font-medium shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Top 10 Recommendations */}
      {tab === "recommendations" && (
        <div className="space-y-3">
          {loadingRecs ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-20 skeleton rounded-xl" />
            ))
          ) : recs?.length === 0 ? (
            <EmptyState
              icon={Star}
              title="No recommendations today"
              description="Run discovery to generate today's top 10 buyer recommendations"
            />
          ) : (
            recs?.map((rec: Recommendation, idx) => (
              <RecommendationCard
                key={rec.opportunity_id}
                rec={rec}
                rank={idx + 1}
                onAddToCrm={() => addToCrmMutation.mutate(rec.opportunity_id)}
                isPending={addToCrmMutation.isPending}
              />
            ))
          )}
        </div>
      )}

      {/* All Opportunities */}
      {tab === "opportunities" && (
        <>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={emergingOnly}
                onChange={(e) => { setEmergingOnly(e.target.checked); setPage(1); }}
                className="rounded accent-primary"
              />
              Emerging importers only
            </label>
          </div>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Company</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Country</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">Opp Score</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">1st Order %</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Revenue Est.</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Action</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">Add to CRM</th>
                </tr>
              </thead>
              <tbody>
                {loadingOpps ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-border">
                      {Array.from({ length: 7 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 skeleton rounded w-3/4" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : opps?.items.map((opp: GrowthOpportunity) => (
                  <tr key={opp.id} className="border-b border-border last:border-0 hover:bg-accent/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-foreground">{opp.buyer?.canonical_name ?? `Buyer #${opp.canonical_id}`}</p>
                        {opp.is_emerging_importer && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                            <Zap className="w-2.5 h-2.5" /> Emerging
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5 truncate max-w-xs">{opp.reasoning}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1">
                        {COUNTRY_FLAGS[opp.buyer?.country ?? ""] ?? "🌍"}
                        {opp.buyer?.country ?? "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <ScoreBadge score={opp.opportunity_score} />
                    </td>
                    <td className="px-4 py-3 text-center text-sm text-foreground">
                      {(opp.first_order_probability * 100).toFixed(0)}%
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-foreground">
                      {formatCurrency(opp.revenue_estimate_usd)}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-2 py-0.5 rounded bg-primary/10 text-primary">
                        {opp.action_recommended?.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => addToCrmMutation.mutate(opp.id)}
                        disabled={addToCrmMutation.isPending}
                        className="p-1.5 rounded-md hover:bg-primary/10 text-primary transition-colors"
                        title="Add to CRM"
                      >
                        <Plus className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination
              page={page}
              total={opps?.pages ?? 1}
              onChange={setPage}
            />
          </div>
        </>
      )}

      {/* Emerging importers */}
      {tab === "emerging" && (
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Company</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">Active (mo)</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">Shipments</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">Velocity</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">Overall</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Annual Volume</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Category</th>
              </tr>
            </thead>
            <tbody>
              {loadingEmerging ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3"><div className="h-4 skeleton rounded w-3/4" /></td>
                    ))}
                  </tr>
                ))
              ) : emerging?.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">
                    <Zap className="w-8 h-8 mx-auto mb-2 opacity-40" />
                    No emerging importers detected yet
                  </td>
                </tr>
              ) : emerging?.items.map((e) => (
                <tr key={e.id} className="border-b border-border last:border-0 hover:bg-accent/30">
                  <td className="px-4 py-3">
                    <p className="font-medium text-foreground">{e.buyer?.canonical_name ?? `Buyer #${e.canonical_id}`}</p>
                    <p className="text-xs text-muted-foreground">{e.buyer?.country ?? "?"} · {e.action_recommended?.replace("_", " ")}</p>
                  </td>
                  <td className="px-4 py-3 text-center text-foreground">{e.months_active}</td>
                  <td className="px-4 py-3 text-center text-foreground">{e.shipment_count}</td>
                  <td className="px-4 py-3 text-center">
                    <ScoreBadge score={e.growth_velocity_score} />
                  </td>
                  <td className="px-4 py-3 text-center">
                    <ScoreBadge score={e.overall_score} />
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-foreground">
                    {formatCurrency(e.annual_volume_usd)}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 capitalize">
                      {e.category}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination page={page} total={emerging?.pages ?? 1} onChange={setPage} />
        </div>
      )}
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80 ? "text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 dark:text-emerald-400" :
    score >= 60 ? "text-blue-600 bg-blue-50 dark:bg-blue-900/20 dark:text-blue-400" :
    score >= 40 ? "text-amber-600 bg-amber-50 dark:bg-amber-900/20 dark:text-amber-400" :
    "text-muted-foreground bg-muted";
  return (
    <span className={cn("inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-bold font-mono", color)}>
      {score?.toFixed(1)}
    </span>
  );
}

function RecommendationCard({ rec, rank, onAddToCrm, isPending }: {
  rec: Recommendation; rank: number; onAddToCrm: () => void; isPending: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-start gap-4">
        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary font-bold text-sm shrink-0">
          {rank}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-semibold text-foreground">{rec.company_name}</p>
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              {COUNTRY_FLAGS[rec.country] ?? "🌍"} {rec.country}
            </span>
            {rec.is_emerging && (
              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700">
                <Zap className="w-2.5 h-2.5" /> Emerging
              </span>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{rec.reasoning}</p>
          <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
            <span>Revenue est. <strong className="text-foreground">{formatCurrency(rec.revenue_estimate_usd)}</strong></span>
            <span>1st order <strong className="text-foreground">{(rec.first_order_probability * 100).toFixed(0)}%</strong></span>
            <span className="capitalize">Action: <strong className="text-primary">{rec.action_recommended?.replace("_", " ")}</strong></span>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <ScoreBadge score={rec.opportunity_score} />
          <button
            onClick={onAddToCrm}
            disabled={isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-70"
          >
            <Plus className="w-3.5 h-3.5" />
            CRM
          </button>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ icon: Icon, title, description }: { icon: React.ElementType; title: string; description: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-12 text-center">
      <Icon className="w-10 h-10 mx-auto mb-3 text-muted-foreground opacity-40" />
      <p className="font-medium text-foreground">{title}</p>
      <p className="text-sm text-muted-foreground mt-1">{description}</p>
    </div>
  );
}

function Pagination({ page, total, onChange }: { page: number; total: number; onChange: (p: number) => void }) {
  if (total <= 1) return null;
  return (
    <div className="px-4 py-3 border-t border-border flex items-center justify-end gap-2 bg-muted/20">
      <button onClick={() => onChange(Math.max(1, page - 1))} disabled={page === 1}
        className="p-1.5 rounded-md hover:bg-accent disabled:opacity-40 transition-colors">
        <ChevronLeft className="w-4 h-4" />
      </button>
      <span className="text-xs font-medium text-foreground">{page} / {total}</span>
      <button onClick={() => onChange(Math.min(total, page + 1))} disabled={page === total}
        className="p-1.5 rounded-md hover:bg-accent disabled:opacity-40 transition-colors">
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
