"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { ThemeProvider } from "next-themes";
import { useEffect, useRef } from "react";
import { wsClient } from "@/lib/websocket";
import { useAppStore } from "@/store/app";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
});

function WsProvider({ children }: { children: React.ReactNode }) {
  const { addLiveFeedItem, addNotification, setWsConnected } = useAppStore();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    wsClient.connect("global");

    const unsubOpen = wsClient.subscribe("system.ws_open", () => setWsConnected(true));
    const unsubClose = wsClient.subscribe("system.ws_closed", () => setWsConnected(false));
    const unsubAll = wsClient.subscribeAll((evt) => {
      if (evt.event.startsWith("system.")) return;
      addLiveFeedItem(evt);
      // Surface important events as notifications
      if (evt.event === "buyer.discovered") {
        const d = evt.data as { company_name?: string; country?: string };
        addNotification({
          level: "info",
          title: "New Buyer Discovered",
          message: `${d.company_name ?? "Unknown"} from ${d.country ?? "?"}`,
        });
      }
      if (evt.event === "email.replied") {
        const d = evt.data as { from?: string; sentiment?: string };
        addNotification({
          level: d.sentiment === "positive" ? "success" : "info",
          title: "Email Reply Received",
          message: `${d.from ?? "Unknown"} — ${d.sentiment ?? "unknown"} sentiment`,
        });
      }
    });

    return () => {
      unsubOpen();
      unsubClose();
      unsubAll();
      wsClient.disconnect();
    };
  }, [addLiveFeedItem, addNotification, setWsConnected]);

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
        <WsProvider>{children}</WsProvider>
      </ThemeProvider>
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  );
}
