import type { Metadata } from "next";
import { SettingsPage } from "@/components/dashboard/settings-page";

export const metadata: Metadata = { title: "Settings" };

export default function Settings() {
  return <SettingsPage />;
}
