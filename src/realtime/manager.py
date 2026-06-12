"""WebSocket connection manager for real-time push."""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # channel -> set of websockets
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, channel: str = "global") -> None:
        await ws.accept()
        async with self._lock:
            self._channels[channel].add(ws)
        log.debug("ws_connect channel=%s total=%d", channel, self.connection_count(channel))

    async def disconnect(self, ws: WebSocket, channel: str = "global") -> None:
        async with self._lock:
            self._channels[channel].discard(ws)
        log.debug("ws_disconnect channel=%s total=%d", channel, self.connection_count(channel))

    def connection_count(self, channel: str = "global") -> int:
        return len(self._channels.get(channel, set()))

    async def broadcast(self, payload: dict[str, Any], channel: str = "global") -> None:
        message = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        sockets = list(self._channels.get(channel, set()))
        for ws in sockets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._channels[channel].discard(ws)

    async def broadcast_all(self, payload: dict[str, Any]) -> None:
        """Broadcast to every connected socket across all channels."""
        message = json.dumps(payload, default=str)
        all_sockets: list[tuple[str, WebSocket]] = [
            (ch, ws)
            for ch, sockets in self._channels.items()
            for ws in list(sockets)
        ]
        dead: list[tuple[str, WebSocket]] = []
        for ch, ws in all_sockets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append((ch, ws))

        if dead:
            async with self._lock:
                for ch, ws in dead:
                    self._channels[ch].discard(ws)

    async def send_personal(self, ws: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await ws.send_text(json.dumps(payload, default=str))
        except Exception as exc:
            log.warning("ws_send_personal failed: %s", exc)


ws_manager = ConnectionManager()
