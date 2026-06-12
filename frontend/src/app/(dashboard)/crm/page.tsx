import type { Metadata } from "next";
import { CrmDashboard } from "@/components/dashboard/crm-dashboard";

export const metadata: Metadata = { title: "CRM & Pipeline" };

export default function CrmPage() {
  return <CrmDashboard />;
}
