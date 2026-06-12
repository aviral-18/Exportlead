import type { Metadata } from "next";
import { BuyerDiscovery } from "@/components/dashboard/buyer-discovery";

export const metadata: Metadata = { title: "Buyer Discovery" };

export default function BuyersPage() {
  return <BuyerDiscovery />;
}
