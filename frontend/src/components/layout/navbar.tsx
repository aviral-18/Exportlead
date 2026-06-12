"use client";

import { Bell, Search, Sun, Moon, Wifi, WifiOff } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { useAppStore } from "@/store/app";
import { useAuthStore } from "@/store/auth";
import { relativeTime } from "@/lib/utils";
import Image from "next/image";

export function Navbar() {
  const { setTheme, resolvedTheme } = useTheme();
  const { unreadNotifications, notifications, markAllRead, wsConnected, setCommandPaletteOpen } =
    useAppStore();
  const { user } = useAuthStore();
  const [showNotifs, setShowNotifs] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // Keyboard shortcut: Ctrl+K / Cmd+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [setCommandPaletteOpen]);

  return (
    <header className="h-16 border-b border-border bg-card/80 backdrop-blur flex items-center px-6 gap-4 shrink-0">
      {/* Search */}
      <button
        onClick={() => setCommandPaletteOpen(true)}
        className="flex items-center gap-2 text-sm text-muted-foreground bg-muted hover:bg-muted/80 rounded-md px-3 py-1.5 flex-1 max-w-xs transition-colors"
        aria-label="Open command palette"
      >
        <Search className="w-3.5 h-3.5" />
        <span>Search buyers, leads...</span>
        <kbd className="ml-auto text-[10px] font-mono bg-background border border-border rounded px-1">⌘K</kbd>
      </button>

      <div className="ml-auto flex items-center gap-2">
        {/* WS status */}
        <div
          className="flex items-center gap-1.5 text-xs text-muted-foreground"
          title={wsConnected ? "Real-time connected" : "Disconnected"}
        >
          {wsConnected ? (
            <>
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 live-dot" />
              <span className="hidden sm:inline text-emerald-600 dark:text-emerald-400">Live</span>
            </>
          ) : (
            <>
              <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
              <span className="hidden sm:inline text-red-500">Offline</span>
            </>
          )}
        </div>

        {/* Theme toggle */}
        {mounted && (
          <button
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            className="p-2 rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            aria-label="Toggle theme"
          >
            {resolvedTheme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        )}

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => {
              setShowNotifs(!showNotifs);
              if (!showNotifs) markAllRead();
            }}
            className="p-2 rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors relative"
            aria-label="Notifications"
          >
            <Bell className="w-4 h-4" />
            {unreadNotifications > 0 && (
              <span className="absolute top-1 right-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-primary text-[9px] text-primary-foreground font-bold">
                {unreadNotifications > 9 ? "9+" : unreadNotifications}
              </span>
            )}
          </button>

          {showNotifs && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-popover border border-border rounded-lg shadow-lg z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-border">
                <p className="text-sm font-semibold">Notifications</p>
              </div>
              <div className="max-h-72 overflow-y-auto scrollbar-thin">
                {notifications.length === 0 ? (
                  <p className="text-sm text-muted-foreground p-4 text-center">No notifications</p>
                ) : (
                  notifications.slice(0, 10).map((n) => (
                    <div key={n.id} className="px-4 py-3 border-b border-border last:border-0 hover:bg-accent/50 transition-colors">
                      <div className="flex items-start gap-3">
                        <div className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${
                          n.level === "success" ? "bg-emerald-500" :
                          n.level === "warning" ? "bg-amber-500" :
                          n.level === "error" ? "bg-red-500" : "bg-blue-500"
                        }`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-foreground">{n.title}</p>
                          <p className="text-xs text-muted-foreground truncate">{n.message}</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">{relativeTime(n.ts)}</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User avatar */}
        <div className="flex items-center gap-2 pl-2 border-l border-border">
          <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center overflow-hidden">
            {user?.avatar_url ? (
              <Image src={user.avatar_url} alt={user.full_name} width={28} height={28} className="object-cover" />
            ) : (
              <span className="text-xs font-semibold text-primary">
                {user?.full_name?.charAt(0) ?? "U"}
              </span>
            )}
          </div>
          <div className="hidden sm:block">
            <p className="text-xs font-medium text-foreground leading-tight">{user?.full_name ?? "User"}</p>
            <p className="text-[10px] text-muted-foreground leading-tight capitalize">{user?.role ?? "viewer"}</p>
          </div>
        </div>
      </div>
    </header>
  );
}
