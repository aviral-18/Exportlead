"use client";

import { useAppStore } from "@/store/app";
import { relativeTime, COUNTRY_FLAGS } from "@/lib/utils";
import { Activity, Users, TrendingUp, Mail, Target } from "lucide-react";

const EVENT_ICONS: Record<string, React.ElementType> = {
  "buyer.discovered": Users,
  "buyer.scored": Activity,
  "opportunity.created": TrendingUp,
  "opportunity.ranked": TrendingUp,
  "email.replied": Mail,
  "deal.probability_updated": Target,
};

const EVENT_LABELS: Record<string, string> = {
  "buyer.discovered": "New buyer discovered",
  "buyer.scored": "Buyer scored",
  "buyer.emerging": "Emerging importer flagged",
  "opportunity.created": "Opportunity created",
  "opportunity.ranked": "Opportunity ranked",
  "email.replied": "Reply received",
  "deal.probability_updated": "Deal probability updated",
  "discovery.run_complete": "Discovery run complete",
  "forecast.updated": "Forecast updated",
};

export function LiveFeed() {
  const { liveFeed } = useAppStore();

  if (liveFeed.length === 0) {
    return (
      <div className="text-center py-6">
        <Activity className="w-6 h-6 mx-auto mb-2 text-muted-foreground opacity-40" />
        <p className="text-xs text-muted-foreground">Waiting for live events...</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {liveFeed.slice(0, 20).map((item) => {
        const Icon = EVENT_ICONS[item.event] ?? Activity;
        const label = EVENT_LABELS[item.event] ?? item.event;
        const data = item.data as Record<string, unknown>;

        return (
          <div key={item.id} className="flex items-start gap-2.5 py-2 px-3 rounded-lg hover:bg-accent/50 transition-colors">
            <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
              <Icon className="w-2.5 h-2.5 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-foreground">{label}</p>
              {(data?.company_name as string | undefined) && (
                <p className="text-[10px] text-muted-foreground truncate">
                  {data.country ? `${COUNTRY_FLAGS[data.country as string] ?? ""} ` : ""}
                  {data.company_name as string}
                </p>
              )}
              <p className="text-[10px] text-muted-foreground">{relativeTime(item.ts)}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
