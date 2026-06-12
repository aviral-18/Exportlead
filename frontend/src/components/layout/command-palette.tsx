"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "cmdk";
import { useAppStore } from "@/store/app";
import {
  LayoutDashboard, Globe, TrendingUp, Briefcase,
  Calculator, BarChart3, Search, ExternalLink,
} from "lucide-react";

const PAGES = [
  { label: "Executive Dashboard", href: "/", icon: LayoutDashboard, keywords: "home overview kpis" },
  { label: "Buyer Discovery", href: "/buyers", icon: Globe, keywords: "buyers global search" },
  { label: "Opportunities", href: "/opportunities", icon: TrendingUp, keywords: "growth rank" },
  { label: "CRM & Pipeline", href: "/crm", icon: Briefcase, keywords: "leads deals" },
  { label: "Profitability Calculator", href: "/profitability", icon: Calculator, keywords: "cost margin" },
  { label: "Analytics & Forecasts", href: "/analytics", icon: BarChart3, keywords: "trends forecast" },
];

export function CommandPalette() {
  const router = useRouter();
  const { commandPaletteOpen, setCommandPaletteOpen } = useAppStore();
  const [query, setQuery] = useState("");

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setCommandPaletteOpen(false);
    };
    if (commandPaletteOpen) document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [commandPaletteOpen, setCommandPaletteOpen]);

  function navigate(href: string) {
    router.push(href);
    setCommandPaletteOpen(false);
    setQuery("");
  }

  if (!commandPaletteOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20"
      onClick={() => setCommandPaletteOpen(false)}
    >
      <div
        className="w-full max-w-xl bg-popover border border-border rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <Command className="w-full" shouldFilter={false}>
          <div className="flex items-center gap-3 px-4 border-b border-border">
            <Search className="w-4 h-4 text-muted-foreground shrink-0" />
            <CommandInput
              placeholder="Search pages, buyers, leads..."
              value={query}
              onValueChange={setQuery}
              className="flex-1 py-4 text-sm bg-transparent outline-none text-foreground placeholder:text-muted-foreground"
              autoFocus
            />
            <kbd className="text-[10px] font-mono bg-muted border border-border rounded px-1.5 py-0.5 shrink-0">ESC</kbd>
          </div>
          <CommandList className="max-h-72 overflow-y-auto py-2">
            <CommandEmpty className="text-sm text-muted-foreground text-center py-6">
              No results found.
            </CommandEmpty>
            <CommandGroup heading="Navigation" className="px-2">
              {PAGES.filter((p) =>
                !query ||
                p.label.toLowerCase().includes(query.toLowerCase()) ||
                p.keywords.includes(query.toLowerCase())
              ).map((page) => (
                <CommandItem
                  key={page.href}
                  onSelect={() => navigate(page.href)}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-md cursor-pointer hover:bg-accent text-sm text-foreground aria-selected:bg-accent"
                >
                  <page.icon className="w-4 h-4 text-muted-foreground shrink-0" />
                  <span>{page.label}</span>
                  <ExternalLink className="w-3 h-3 text-muted-foreground ml-auto" />
                </CommandItem>
              ))}
            </CommandGroup>

            {!query && (
              <>
                <CommandSeparator className="my-2 border-t border-border" />
                <CommandGroup heading="Quick Actions" className="px-2">
                  <CommandItem
                    onSelect={() => navigate("/opportunities")}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-md cursor-pointer hover:bg-accent text-sm text-foreground aria-selected:bg-accent"
                  >
                    <TrendingUp className="w-4 h-4 text-primary shrink-0" />
                    <span>View today's top 10 recommendations</span>
                  </CommandItem>
                  <CommandItem
                    onSelect={() => navigate("/crm")}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-md cursor-pointer hover:bg-accent text-sm text-foreground aria-selected:bg-accent"
                  >
                    <Briefcase className="w-4 h-4 text-primary shrink-0" />
                    <span>View due follow-ups</span>
                  </CommandItem>
                </CommandGroup>
              </>
            )}
          </CommandList>
        </Command>
      </div>
    </div>
  );
}
