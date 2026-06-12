"use client";

import { useEffect, useRef } from "react";
import { wsClient } from "@/lib/websocket";
import type { WsEvent } from "@/types";

/**
 * Subscribe to a specific WebSocket event type.
 * The handler is stable — it is NOT required to be memoized by the caller.
 */
export function useWsEvent(eventType: string, handler: (event: WsEvent) => void) {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const unsubscribe = wsClient.subscribe(eventType, (evt) => {
      handlerRef.current(evt);
    });
    return unsubscribe;
  }, [eventType]);
}

/** Subscribe to ALL WebSocket events. */
export function useWsAll(handler: (event: WsEvent) => void) {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const unsubscribe = wsClient.subscribeAll((evt) => {
      handlerRef.current(evt);
    });
    return unsubscribe;
  }, []);
}
