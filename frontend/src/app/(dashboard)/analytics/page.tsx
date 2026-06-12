import type { Metadata } from "next";
import { AnalyticsDashboard } from "@/components/dashboard/analytics-dashboard";

export const metadata: Metadata = { title: "Analytics & Forecasts" };

export default function AnalyticsPage() {
  return <AnalyticsDashboard />;
}
