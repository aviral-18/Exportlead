"use client";

import { cn, formatCurrency, formatNumber } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KpiCardProps {
  title: string;
  value: number | string;
  format?: "number" | "currency" | "percent" | "raw";
  change?: number;
  changeLabel?: string;
  icon: LucideIcon;
  iconColor?: string;
  loading?: boolean;
  description?: string;
}

export function KpiCard({
  title,
  value,
  format = "number",
  change,
  changeLabel,
  icon: Icon,
  iconColor = "text-primary",
  loading = false,
  description,
}: KpiCardProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex justify-between items-start mb-3">
          <div className="h-4 w-24 skeleton rounded" />
          <div className="h-8 w-8 skeleton rounded-md" />
        </div>
        <div className="h-8 w-32 skeleton rounded mb-2" />
        <div className="h-3 w-20 skeleton rounded" />
      </div>
    );
  }

  const displayValue =
    typeof value === "string"
      ? value
      : format === "currency"
      ? formatCurrency(value)
      : format === "percent"
      ? `${value.toFixed(1)}%`
      : formatNumber(value, "compact");

  const positive = change !== undefined && change > 0;
  const negative = change !== undefined && change < 0;

  return (
    <div className="rounded-xl border border-border bg-card p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between gap-3 mb-3">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        <div className={cn("p-2 rounded-lg bg-primary/10", iconColor.replace("text-", "bg-").replace("500", "500/10"))}>
          <Icon className={cn("w-4 h-4", iconColor)} />
        </div>
      </div>
      <p className="text-2xl font-bold text-foreground">{displayValue}</p>
      {description && <p className="text-xs text-muted-foreground mt-1">{description}</p>}
      {change !== undefined && (
        <div className={cn("flex items-center gap-1 mt-2 text-xs font-medium", {
          "text-emerald-600 dark:text-emerald-400": positive,
          "text-red-500 dark:text-red-400": negative,
          "text-muted-foreground": !positive && !negative,
        })}>
          {positive ? <TrendingUp className="w-3 h-3" /> :
           negative ? <TrendingDown className="w-3 h-3" /> :
           <Minus className="w-3 h-3" />}
          <span>{positive ? "+" : ""}{change.toFixed(1)}%</span>
          {changeLabel && <span className="text-muted-foreground font-normal">{changeLabel}</span>}
        </div>
      )}
    </div>
  );
}
