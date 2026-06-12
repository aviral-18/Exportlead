"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/app";
import {
  LayoutDashboard,
  Users,
  TrendingUp,
  Briefcase,
  Calculator,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
  Globe,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Executive", icon: LayoutDashboard, description: "KPIs & pipeline overview" },
  { href: "/buyers", label: "Buyers", icon: Globe, description: "Global buyer discovery" },
  { href: "/opportunities", label: "Opportunities", icon: TrendingUp, description: "Ranked growth opps" },
  { href: "/crm", label: "CRM", icon: Briefcase, description: "Pipeline & deals" },
  { href: "/profitability", label: "Profitability", icon: Calculator, description: "Export cost calculator" },
  { href: "/analytics", label: "Analytics", icon: BarChart3, description: "Trends & forecasts" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useAppStore();

  return (
    <aside
      className={cn(
        "flex flex-col h-full bg-card border-r border-border transition-all duration-200 ease-in-out",
        sidebarCollapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div className={cn("flex items-center h-16 px-4 border-b border-border gap-3 shrink-0")}>
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground shrink-0">
          <Zap className="w-4 h-4" />
        </div>
        {!sidebarCollapsed && (
          <div className="overflow-hidden">
            <p className="font-bold text-sm leading-tight text-foreground truncate">BrassExport</p>
            <p className="text-[10px] text-muted-foreground leading-tight truncate">Intelligence Platform</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 scrollbar-thin">
        <ul className="space-y-1 px-2">
          {navItems.map(({ href, label, icon: Icon, description }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  title={sidebarCollapsed ? `${label} — ${description}` : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-2 py-2 text-sm transition-colors group",
                    active
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  <Icon className={cn("shrink-0", sidebarCollapsed ? "w-5 h-5" : "w-4 h-4")} />
                  {!sidebarCollapsed && <span className="truncate">{label}</span>}
                  {active && !sidebarCollapsed && (
                    <span className="ml-auto w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Bottom */}
      <div className="px-2 py-3 space-y-1 border-t border-border shrink-0">
        <Link
          href="/settings"
          className={cn(
            "flex items-center gap-3 rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
          )}
        >
          <Settings className="w-4 h-4 shrink-0" />
          {!sidebarCollapsed && <span>Settings</span>}
        </Link>
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center gap-3 rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? (
            <ChevronRight className="w-4 h-4 shrink-0" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4 shrink-0" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
