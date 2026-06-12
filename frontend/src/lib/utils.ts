import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(
  value: number,
  currency = "USD",
  notation: Intl.NumberFormatOptions["notation"] = "standard"
): string {
  if (value >= 1_000_000) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value);
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    notation,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatNumber(value: number, notation?: Intl.NumberFormatOptions["notation"]): string {
  return new Intl.NumberFormat("en-US", { notation, maximumFractionDigits: 1 }).format(value);
}

export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

export function getScoreColor(score: number): string {
  if (score >= 80) return "text-emerald-500";
  if (score >= 60) return "text-blue-500";
  if (score >= 40) return "text-amber-500";
  return "text-red-500";
}

export function getTierBadgeColor(tier: string): string {
  const colors: Record<string, string> = {
    A: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
    B: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    C: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
    D: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
    F: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  };
  return colors[tier] ?? colors.F;
}

export function getLeadStatusColor(status: string): string {
  const colors: Record<string, string> = {
    new: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
    contacted: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
    engaged: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300",
    qualified: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
    sample_sent: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    quoted: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
    negotiating: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
    won: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
    lost: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
    inactive: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
  };
  return colors[status] ?? colors.new;
}

export function relativeTime(date: string): string {
  const d = new Date(date);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export const COUNTRY_FLAGS: Record<string, string> = {
  US: "🇺🇸", AE: "🇦🇪", SA: "🇸🇦", GB: "🇬🇧", DE: "🇩🇪",
  AU: "🇦🇺", CA: "🇨🇦", FR: "🇫🇷", NL: "🇳🇱", IT: "🇮🇹",
  JP: "🇯🇵", SG: "🇸🇬", HK: "🇭🇰", NZ: "🇳🇿", ZA: "🇿🇦",
  OM: "🇴🇲", QA: "🇶🇦", KW: "🇰🇼", BH: "🇧🇭", EG: "🇪🇬",
  MA: "🇲🇦", KE: "🇰🇪", NG: "🇳🇬", IN: "🇮🇳", CN: "🇨🇳",
  MX: "🇲🇽", BR: "🇧🇷", AR: "🇦🇷", TR: "🇹🇷", PL: "🇵🇱",
  BE: "🇧🇪", CH: "🇨🇭", SE: "🇸🇪", DK: "🇩🇰", NO: "🇳🇴",
};
