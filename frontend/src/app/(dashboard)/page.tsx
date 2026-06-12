import type { Metadata } from "next";
import { ExecutiveDashboard } from "@/components/dashboard/executive-dashboard";

export const metadata: Metadata = { title: "Executive Dashboard" };

export default function ExecutivePage() {
  return <ExecutiveDashboard />;
}
