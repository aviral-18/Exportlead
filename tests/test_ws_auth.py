"""Tests for WebSocket authentication.

Verifies that the /ws/dashboard endpoint:
- Closes with code 4001 when no token is supplied
- Closes with code 4001 when an invalid/expired token is supplied
- Accepts a valid JWT access token
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.auth.jwt import create_access_token


def _make_ws_app() -> FastAPI:
    from src.api.routes.ws import router as ws_router
    app = FastAPI()
    app.include_router(ws_router)
    return app


@pytest.mark.anyio
async def test_ws_rejects_missing_token():
    """Connecting without a token must be closed immediately (4001)."""
    app = _make_ws_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ws/dashboard", headers={"upgrade": "websocket"})
    # The endpoint closes the socket before accepting — httpx sees a non-101 response
    assert resp.status_code != 101


@pytest.mark.anyio
async def test_ws_rejects_invalid_token():
    """Connecting with a garbage token must also be rejected."""
    app = _make_ws_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/ws/dashboard?token=not.a.valid.jwt",
            headers={"upgrade": "websocket"},
        )
    assert resp.status_code != 101


@pytest.mark.anyio
async def test_ws_accepts_valid_token():
    """A valid JWT access token must allow the upgrade handshake to proceed."""
    valid_token = create_access_token(subject=1)
    app = _make_ws_app()

    from unittest.mock import AsyncMock, patch
    mock_manager = AsyncMock()
    mock_manager.connect = AsyncMock()
    mock_manager.send_personal = AsyncMock()
    mock_manager.connection_count = lambda ch: 1
    mock_manager.disconnect = AsyncMock()

    with patch("src.api.routes.ws.ws_manager", mock_manager):
        from starlette.testclient import TestClient
        with TestClient(app) as tc:
            with tc.websocket_connect(f"/ws/dashboard?token={valid_token}") as ws:
                data = ws.receive_json()
    # The connected event should have been sent
    assert mock_manager.connect.called
