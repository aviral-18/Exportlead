"use client";

import { useTheme } from "next-themes";
import { useAuthStore } from "@/store/auth";
import { Moon, Sun, Monitor, LogOut, User, Bell, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

export function SettingsPage() {
  const { setTheme, resolvedTheme } = useTheme();
  const { user, logout } = useAuthStore();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    toast.success("Logged out");
    router.push("/login");
  }

  const themes = [
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
    { value: "system", label: "System", icon: Monitor },
  ] as const;

  return (
    <div className="space-y-6 max-w-2xl animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Manage your account and preferences</p>
      </div>

      {/* Profile */}
      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2 mb-4">
          <User className="w-4 h-4 text-primary" /> Profile
        </h2>
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center">
              <span className="text-lg font-bold text-primary">
                {user?.full_name?.charAt(0) ?? "U"}
              </span>
            </div>
            <div>
              <p className="font-semibold text-foreground">{user?.full_name ?? "—"}</p>
              <p className="text-sm text-muted-foreground">{user?.email ?? "—"}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 pt-1">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Role</p>
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-primary/10 text-primary capitalize">
                {user?.role ?? "viewer"}
              </span>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1">Status</p>
              <span className={cn(
                "inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium",
                user?.is_verified
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400"
                  : "bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400"
              )}>
                {user?.is_verified ? "Verified" : "Unverified"}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Appearance */}
      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2 mb-4">
          <Monitor className="w-4 h-4 text-primary" /> Appearance
        </h2>
        <div>
          <p className="text-xs text-muted-foreground mb-2">Theme</p>
          <div className="flex gap-2">
            {themes.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                onClick={() => setTheme(value)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 text-sm rounded-lg border transition-colors",
                  resolvedTheme === value || (value === "system" && !resolvedTheme)
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-background border-border text-foreground hover:bg-accent"
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Platform info */}
      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2 mb-4">
          <Globe className="w-4 h-4 text-primary" /> Platform
        </h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {[
            ["Platform", "BrassExport Intelligence v2.0"],
            ["Coverage", "50M+ buyers · 25+ data sources"],
            ["Markets", "40+ countries"],
            ["Daily pipeline", "02:00 UTC scrape → 11:00 UTC forecast"],
          ].map(([k, v]) => (
            <div key={k}>
              <p className="text-xs text-muted-foreground">{k}</p>
              <p className="text-sm text-foreground mt-0.5">{v}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Sign out */}
      <section className="rounded-xl border border-destructive/20 bg-card p-5">
        <h2 className="text-sm font-semibold text-foreground mb-3">Danger Zone</h2>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 px-4 py-2 text-sm text-destructive border border-destructive/30 rounded-lg hover:bg-destructive/10 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </section>
    </div>
  );
}
