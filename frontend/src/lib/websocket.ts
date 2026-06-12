/**
 * WebSocket client with auto-reconnect and typed event dispatch.
 */
import Cookies from "js-cookie";
import type { WsEvent } from "@/types";

type EventHandler = (event: WsEvent) => void;
type ChannelType = "global" | "buyers" | "crm" | "pipeline";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
const RECONNECT_DELAYS = [1000, 2000, 5000, 10000, 30000];

class BrassWebSocket {
  private ws: WebSocket | null = null;
  private channel: ChannelType = "global";
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldConnect = false;

  connect(channel: ChannelType = "global"): void {
    this.channel = channel;
    this.shouldConnect = true;
    this._connect();
  }

  disconnect(): void {
    this.shouldConnect = false;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.close(1000, "client disconnect");
      this.ws = null;
    }
  }

  subscribe(eventType: string, handler: EventHandler): () => void {
    if (!this.handlers.has(eventType)) this.handlers.set(eventType, new Set());
    this.handlers.get(eventType)!.add(handler);
    return () => this.handlers.get(eventType)?.delete(handler);
  }

  subscribeAll(handler: EventHandler): () => void {
    return this.subscribe("*", handler);
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private _connect(): void {
    if (typeof window === "undefined") return;
    const token = Cookies.get("access_token") ?? "";
    const url = `${WS_URL}/ws/dashboard?channel=${this.channel}&token=${encodeURIComponent(token)}`;
    try {
      this.ws = new WebSocket(url);
    } catch {
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempt = 0;
      this._dispatch({ event: "system.ws_open", data: { channel: this.channel }, ts: new Date().toISOString() });
    };

    this.ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data as string) as WsEvent;
        if (msg.type === "ping") {
          this.ws?.send(JSON.stringify({ type: "pong" }));
          return;
        }
        this._dispatch(msg);
      } catch { /* ignore malformed */ }
    };

    this.ws.onclose = (evt) => {
      this._dispatch({ event: "system.ws_closed", data: { code: evt.code }, ts: new Date().toISOString() });
      if (this.shouldConnect && evt.code !== 1000) {
        this._scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private _scheduleReconnect(): void {
    const delay = RECONNECT_DELAYS[Math.min(this.reconnectAttempt, RECONNECT_DELAYS.length - 1)];
    this.reconnectAttempt++;
    this.reconnectTimer = setTimeout(() => {
      if (this.shouldConnect) this._connect();
    }, delay);
  }

  private _dispatch(event: WsEvent): void {
    const specific = this.handlers.get(event.event);
    specific?.forEach((h) => h(event));
    const wildcard = this.handlers.get("*");
    wildcard?.forEach((h) => h(event));
  }
}

export const wsClient = new BrassWebSocket();
