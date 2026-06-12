"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { crmApi } from "@/lib/api";
import { cn, formatCurrency, getLeadStatusColor, COUNTRY_FLAGS, relativeTime } from "@/lib/utils";
import {
  Briefcase, Users, Clock, CheckCircle, ChevronLeft, ChevronRight,
  Bell, Filter, Search, Plus,
} from "lucide-react";
import { toast } from "sonner";
import type { Lead, FollowUp } from "@/types";

const PIPELINE_STAGES = [
  { key: "new", label: "New" },
  { key: "contacted", label: "Contacted" },
  { key: "engaged", label: "Engaged" },
  { key: "qualified", label: "Qualified" },
  { key: "sample_sent", label: "Sample Sent" },
  { key: "quoted", label: "Quoted" },
  { key: "negotiating", label: "Negotiating" },
  { key: "won", label: "Won" },
];

type CrmTab = "pipeline" | "leads" | "followups";

export function CrmDashboard() {
  const [tab, setTab] = useState<CrmTab>("pipeline");
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const qc = useQueryClient();

  const { data: leads, isLoading: loadingLeads } = useQuery({
    queryKey: ["crm", "leads", page, statusFilter],
    queryFn: () => crmApi.leads.list({ page, page_size: 20, ...(statusFilter && { status: statusFilter }) }),
    staleTime: 30_000,
  });

  const { data: followups, isLoading: loadingFollowups } = useQuery({
    queryKey: ["crm", "followups"],
    queryFn: () => crmApi.followups.due(7),
    enabled: tab === "followups",
    staleTime: 60_000,
  });

  const completeMutation = useMutation({
    mutationFn: (id: number) => crmApi.followups.complete(id),
    onSuccess: () => {
      toast.success("Follow-up marked complete");
      qc.invalidateQueries({ queryKey: ["crm", "followups"] });
    },
  });

  // Group leads by status for kanban view
  const leadsByStage = (() => {
    if (!leads?.items) return {} as Record<string, Lead[]>;
    const grouped: Record<string, Lead[]> = {};
    for (const l of leads.items) {
      if (!grouped[l.status]) grouped[l.status] = [];
      grouped[l.status].push(l);
    }
    return grouped;
  })();

  const pipelineValue = leads?.items?.reduce((sum, l) => sum + (l.estimated_value_usd ?? 0), 0) ?? 0;

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">CRM & Pipeline</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {leads?.total ?? 0} leads · {formatCurrency(pipelineValue)} pipeline
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors">
          <Plus className="w-4 h-4" />
          Add Lead
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-muted p-1 rounded-lg w-fit">
        {([
          { id: "pipeline" as CrmTab, label: "Pipeline", icon: Briefcase },
          { id: "leads" as CrmTab, label: "Leads Table", icon: Users },
          { id: "followups" as CrmTab, label: "Follow-ups", icon: Bell },
        ]).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-all",
              tab === id ? "bg-card text-foreground font-medium shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Pipeline kanban */}
      {tab === "pipeline" && (
        <div className="overflow-x-auto scrollbar-thin pb-2">
          <div className="flex gap-3" style={{ minWidth: `${PIPELINE_STAGES.length * 200}px` }}>
            {PIPELINE_STAGES.map(({ key, label }) => {
              const stageleads = leadsByStage[key] ?? [];
              const stageValue = stageleads.reduce((s, l) => s + (l.estimated_value_usd ?? 0), 0);
              return (
                <div key={key} className="w-48 shrink-0">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{label}</h3>
                    <span className="text-xs text-muted-foreground bg-muted rounded px-1.5 py-0.5">{stageleads.length}</span>
                  </div>
                  {stageValue > 0 && (
                    <p className="text-xs text-primary mb-2 font-medium">{formatCurrency(stageValue)}</p>
                  )}
                  <div className="space-y-2">
                    {loadingLeads ? (
                      Array.from({ length: 2 }).map((_, i) => (
                        <div key={i} className="h-20 skeleton rounded-lg" />
                      ))
                    ) : stageleads.length === 0 ? (
                      <div className="h-16 rounded-lg border-2 border-dashed border-border flex items-center justify-center">
                        <p className="text-xs text-muted-foreground">Empty</p>
                      </div>
                    ) : (
                      stageleads.map((lead) => (
                        <LeadCard key={lead.id} lead={lead} />
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Leads table */}
      {tab === "leads" && (
        <>
          <div className="flex gap-3">
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="text-sm bg-card border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">All statuses</option>
              {PIPELINE_STAGES.map(({ key, label }) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Company</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Country</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Status</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Value</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">Interactions</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Last Contact</th>
                </tr>
              </thead>
              <tbody>
                {loadingLeads ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-border">
                      {Array.from({ length: 6 }).map((_, j) => (
                        <td key={j} className="px-4 py-3"><div className="h-4 skeleton rounded w-3/4" /></td>
                      ))}
                    </tr>
                  ))
                ) : leads?.items.map((lead: Lead) => (
                  <tr key={lead.id} className="border-b border-border last:border-0 hover:bg-accent/30 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-foreground">{lead.company_name}</p>
                      {lead.contact_name && (
                        <p className="text-xs text-muted-foreground">{lead.contact_name}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1">
                        {COUNTRY_FLAGS[lead.country] ?? "🌍"} {lead.country}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize", getLeadStatusColor(lead.status))}>
                        {lead.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-foreground">
                      {formatCurrency(lead.estimated_value_usd)}
                    </td>
                    <td className="px-4 py-3 text-center text-foreground">{lead.interactions_count}</td>
                    <td className="px-4 py-3 text-right text-xs text-muted-foreground">
                      {lead.last_contact_date ? relativeTime(lead.last_contact_date) : "Never"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {leads && leads.pages > 1 && (
              <div className="px-4 py-3 border-t border-border flex items-center justify-end gap-2 bg-muted/20">
                <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
                  className="p-1.5 rounded hover:bg-accent disabled:opacity-40 transition-colors">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-xs font-medium">{page} / {leads.pages}</span>
                <button onClick={() => setPage(Math.min(leads.pages, page + 1))} disabled={page === leads.pages}
                  className="p-1.5 rounded hover:bg-accent disabled:opacity-40 transition-colors">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {/* Follow-ups */}
      {tab === "followups" && (
        <div className="space-y-3">
          {loadingFollowups ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-16 skeleton rounded-xl" />
            ))
          ) : (followups as FollowUp[])?.length === 0 ? (
            <div className="rounded-xl border border-border bg-card p-12 text-center">
              <CheckCircle className="w-10 h-10 mx-auto mb-3 text-emerald-500 opacity-60" />
              <p className="font-medium text-foreground">All caught up!</p>
              <p className="text-sm text-muted-foreground mt-1">No follow-ups due in the next 7 days</p>
            </div>
          ) : (followups as FollowUp[])?.map((fu: FollowUp) => (
            <div key={fu.id} className={cn(
              "rounded-xl border bg-card p-4 flex items-center gap-4 hover:shadow-sm transition-shadow",
              fu.priority === "urgent" ? "border-red-200 dark:border-red-900" :
              fu.priority === "high" ? "border-amber-200 dark:border-amber-900" :
              "border-border"
            )}>
              <div className={cn("w-2 h-2 rounded-full shrink-0",
                fu.priority === "urgent" ? "bg-red-500" :
                fu.priority === "high" ? "bg-amber-500" :
                fu.priority === "medium" ? "bg-blue-500" : "bg-gray-400"
              )} />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-foreground">{fu.title}</p>
                {fu.notes && <p className="text-xs text-muted-foreground truncate mt-0.5">{fu.notes}</p>}
                <p className="text-xs text-muted-foreground mt-1">
                  Due: <strong>{new Date(fu.due_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</strong>
                  {" · "}<span className="capitalize">{fu.priority} priority</span>
                </p>
              </div>
              <button
                onClick={() => completeMutation.mutate(fu.id)}
                disabled={completeMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-emerald-600 border border-emerald-200 dark:border-emerald-800 rounded-lg hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors disabled:opacity-70"
              >
                <CheckCircle className="w-3.5 h-3.5" />
                Complete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LeadCard({ lead }: { lead: Lead }) {
  return (
    <div className="rounded-lg border border-border bg-background p-3 cursor-pointer hover:shadow-sm transition-shadow">
      <p className="text-xs font-semibold text-foreground truncate">{lead.company_name}</p>
      <p className="text-[10px] text-muted-foreground mt-0.5">
        {COUNTRY_FLAGS[lead.country] ?? "🌍"} {lead.country}
      </p>
      <div className="flex items-center justify-between mt-2">
        <span className="text-[10px] font-mono text-primary">{formatCurrency(lead.estimated_value_usd)}</span>
        <span className="text-[10px] text-muted-foreground">{lead.interactions_count} contacts</span>
      </div>
    </div>
  );
}
