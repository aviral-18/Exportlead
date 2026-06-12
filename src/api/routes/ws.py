"""WebSocket endpoints for real-time dashboard updates."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from src.realtime.manager import ws_manager

log = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])

_PING_INTERVAL = 25  # seconds


@router.websocket("/dashboard")
async def ws_dashboard(
    websocket: WebSocket,
    channel: str = Query(default="global"),
    token: Optional[str] = Query(default=None),
):
    """
    Real-time dashboard feed. Requires a valid JWT access token via ?token= query param.
    Clients subscribe to channels: global | buyers | crm | pipeline
    """
    from src.auth.jwt import verify_token

    if not token:
        await websocket.close(code=4001)
        return
    try:
        verify_token(token, token_type="access")
    except HTTPException:
        await websocket.close(code=4001)
        return

    await ws_manager.connect(websocket, channel=channel)
    try:
        await ws_manager.send_personal(websocket, {
            "event": "system.connected",
            "data": {"channel": channel, "connections": ws_manager.connection_count(channel)},
        })

        ping_task = asyncio.create_task(_ping_loop(websocket))
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                    if msg.get("type") == "pong":
                        continue
                    if msg.get("type") == "subscribe":
                        new_ch = msg.get("channel", "global")
                        await ws_manager.disconnect(websocket, channel)
                        channel = new_ch
                        await ws_manager.connect(websocket, channel)
                        await ws_manager.send_personal(websocket, {
                            "event": "system.subscribed",
                            "data": {"channel": channel},
                        })
                except (json.JSONDecodeError, KeyError):
                    pass
        finally:
            ping_task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket, channel)


async def _ping_loop(ws: WebSocket) -> None:
    while True:
        await asyncio.sleep(_PING_INTERVAL)
        try:
            await ws.send_text('{"type":"ping"}')
        except Exception:
            break


@router.get("/stats", tags=["websocket"])
async def ws_stats() -> dict:
    return {
        "channels": {
            ch: ws_manager.connection_count(ch)
            for ch in ["global", "buyers", "crm", "pipeline"]
        }
    }
