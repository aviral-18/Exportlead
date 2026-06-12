"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { buyersApi } from "@/lib/api";
import { cn, formatCurrency, getTierBadgeColor, COUNTRY_FLAGS, relativeTime } from "@/lib/utils";
import { Search, Filter, Globe, TrendingUp, ChevronDown, ChevronLeft, ChevronRight, X } from "lucide-react";
import type { Buyer } from "@/types";

const BUYER_TYPES = ["retailer", "distributor", "wholesaler", "importer", "manufacturer", "marketplace", "government", "ngo"];
const COUNTRIES = ["AE", "US", "SA", "GB", "DE", "AU", "CA", "FR", "NL", "JP", "SG", "KW", "OM", "QA"];
const TIERS = ["A", "B", "C", "D", "F"];

interface Filters {
  search: string;
  country: string;
  buyer_type: string;
  min_score: number;
  tier: string;
}

export function BuyerDiscovery() {
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    search: "",
    country: "",
    buyer_type: "",
    min_score: 0,
    tier: "",
  });

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["buyers", "list", page, filters],
    queryFn: () =>
      buyersApi.list({
        page,
        page_size: 25,
        ...(filters.country && { country: filters.country }),
        ...(filters.buyer_type && { buyer_type: filters.buyer_type }),
        ...(filters.min_score > 0 && { min_score: filters.min_score }),
        ...(filters.search && { search: filters.search }),
      }),
    staleTime: 60_000,
  });

  const setFilter = useCallback(<K extends keyof Filters>(key: K, value: Filters[K]) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({ search: "", country: "", buyer_type: "", min_score: 0, tier: "" });
    setPage(1);
  }, []);

  const activeFilterCount = [
    filters.country, filters.buyer_type, filters.tier, filters.min_score > 0 ? "score" : "",
  ].filter(Boolean).length;

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Buyer Discovery</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {data?.total ? `${data.total.toLocaleString()} buyers found` : "Global buyer database"}
          </p>
        </div>
      </div>

      {/* Search + filter bar */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by company name, country, product..."
            value={filters.search}
            onChange={(e) => setFilter("search", e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 text-sm bg-card border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors"
          />
          {filters.search && (
            <button onClick={() => setFilter("search", "")} className="absolute right-3 top-1/2 -translate-y-1/2">
              <X className="w-3.5 h-3.5 text-muted-foreground" />
            </button>
          )}
        </div>
        <button
          onClick={() => setFiltersOpen(!filtersOpen)}
          className={cn(
            "flex items-center gap-2 px-4 py-2.5 text-sm rounded-lg border transition-colors",
            filtersOpen || activeFilterCount > 0
              ? "bg-primary text-primary-foreground border-primary"
              : "bg-card border-border text-foreground hover:bg-accent"
          )}
        >
          <Filter className="w-4 h-4" />
          <span>Filters</span>
          {activeFilterCount > 0 && (
            <span className="flex items-center justify-center w-4 h-4 rounded-full bg-white/20 text-[10px] font-bold">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      {/* Filter panel */}
      {filtersOpen && (
        <div className="bg-card border border-border rounded-xl p-4 animate-fade-in">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Country */}
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Country</label>
              <select
                value={filters.country}
                onChange={(e) => setFilter("country", e.target.value)}
                className="w-full text-sm bg-background border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">All countries</option>
                {COUNTRIES.map((c) => (
                  <option key={c} value={c}>{COUNTRY_FLAGS[c] ?? ""} {c}</option>
                ))}
              </select>
            </div>

            {/* Buyer type */}
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Buyer Type</label>
              <select
                value={filters.buyer_type}
                onChange={(e) => setFilter("buyer_type", e.target.value)}
                className="w-full text-sm bg-background border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">All types</option>
                {BUYER_TYPES.map((t) => (
                  <option key={t} value={t} className="capitalize">{t}</option>
                ))}
              </select>
            </div>

            {/* Tier */}
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Score Tier</label>
              <select
                value={filters.tier}
                onChange={(e) => setFilter("tier", e.target.value)}
                className="w-full text-sm bg-background border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">All tiers</option>
                {TIERS.map((t) => (
                  <option key={t} value={t}>Tier {t}</option>
                ))}
              </select>
            </div>

            {/* Min score */}
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">
                Min Score: <span className="text-foreground font-semibold">{filters.min_score}</span>
              </label>
              <input
                type="range"
                min={0}
                max={90}
                step={10}
                value={filters.min_score}
                onChange={(e) => setFilter("min_score", Number(e.target.value))}
                className="w-full accent-primary"
              />
            </div>
          </div>
          {activeFilterCount > 0 && (
            <button
              onClick={clearFilters}
              className="mt-3 text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
            >
              <X className="w-3 h-3" />
              Clear all filters
            </button>
          )}
        </div>
      )}

      {/* Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Company</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Country</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Type</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Product</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Import Value</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">Score</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground">Tier</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {isLoading || isFetching ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    {Array.from({ length: 8 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 skeleton rounded" style={{ width: `${50 + Math.random() * 50}%` }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : data?.items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                    <Globe className="w-8 h-8 mx-auto mb-2 opacity-40" />
                    <p>No buyers match your filters</p>
                  </td>
                </tr>
              ) : (
                data?.items.map((buyer: Buyer) => (
                  <BuyerRow key={buyer.id} buyer={buyer} />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div className="px-4 py-3 border-t border-border flex items-center justify-between bg-muted/20">
            <p className="text-xs text-muted-foreground">
              Showing {((page - 1) * 25) + 1}–{Math.min(page * 25, data.total)} of {data.total.toLocaleString()}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-md hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs text-foreground font-medium px-2">
                {page} / {data.pages}
              </span>
              <button
                onClick={() => setPage(Math.min(data.pages, page + 1))}
                disabled={page === data.pages}
                className="p-1.5 rounded-md hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function BuyerRow({ buyer }: { buyer: Buyer }) {
  const score = buyer.score?.composite_score ?? 0;
  const tier = buyer.score?.tier ?? "F";

  return (
    <tr className="border-b border-border last:border-0 hover:bg-accent/30 transition-colors cursor-default">
      <td className="px-4 py-3">
        <div>
          <p className="font-medium text-foreground">{buyer.canonical_name}</p>
          {buyer.website && (
            <a href={`https://${buyer.website}`} target="_blank" rel="noopener noreferrer"
               className="text-xs text-primary hover:underline">
              {buyer.website}
            </a>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        <span className="flex items-center gap-1.5">
          <span>{COUNTRY_FLAGS[buyer.country] ?? "🌍"}</span>
          <span className="text-foreground">{buyer.country}</span>
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="capitalize text-foreground">{buyer.buyer_type}</span>
      </td>
      <td className="px-4 py-3">
        <span className="text-foreground">{buyer.primary_product}</span>
      </td>
      <td className="px-4 py-3 text-right font-mono text-foreground">
        {formatCurrency(buyer.annual_import_value_usd)}
      </td>
      <td className="px-4 py-3 text-center">
        <span className={cn("text-sm font-bold",
          score >= 80 ? "text-emerald-500" :
          score >= 60 ? "text-blue-500" :
          score >= 40 ? "text-amber-500" : "text-muted-foreground"
        )}>
          {score > 0 ? score.toFixed(0) : "—"}
        </span>
      </td>
      <td className="px-4 py-3 text-center">
        <span className={cn("inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold", getTierBadgeColor(tier))}>
          {tier}
        </span>
      </td>
      <td className="px-4 py-3 text-right text-xs text-muted-foreground">
        {relativeTime(buyer.last_seen)}
      </td>
    </tr>
  );
}
