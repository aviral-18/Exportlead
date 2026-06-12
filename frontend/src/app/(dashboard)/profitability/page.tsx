import type { Metadata } from "next";
import { ProfitabilityDashboard } from "@/components/dashboard/profitability-dashboard";

export const metadata: Metadata = { title: "Profitability Calculator" };

export default function ProfitabilityPage() {
  return <ProfitabilityDashboard />;
}
