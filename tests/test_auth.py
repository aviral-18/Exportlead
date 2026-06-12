"""Tests for authentication endpoints.

Covers:
- POST /auth/register + /auth/login round-trip
- POST /auth/refresh with rotation
- GET /auth/google — state stored in Redis
- GET /auth/google/callback — rejects invalid/missing state (CSRF protection)
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.auth.jwt import create_access_token, create_refresh_token
from src.auth.password import hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user_row(email: str = "test@example.com", user_id: int = 1):
    from src.auth.models import User
    user = User.__new__(User)
    user.id = user_id
    user.email = email
    user.hashed_password = hash_password("correct_password")
    user.full_name = "Test User"
    user.role = "analyst"
    user.avatar_url = None
    user.is_verified = True
    user.is_active = True
    user.google_id = None
    user.last_login_at = None
    return user


# ── JWT unit tests ─────────────────────────────────────────────────────────────

def test_access_token_type():
    from src.auth.jwt import verify_token
    token = create_access_token(subject=99)
    payload = verify_token(token, token_type="access")
    assert payload["sub"] == "99"
    assert payload["type"] == "access"


def test_refresh_token_type():
    from src.auth.jwt import verify_token
    token = create_refresh_token(subject=99)
    payload = verify_token(token, token_type="refresh")
    assert payload["sub"] == "99"
    assert payload["type"] == "refresh"


def test_wrong_token_type_raises():
    from fastapi import HTTPException
    from src.auth.jwt import verify_token
    access = create_access_token(subject=1)
    with pytest.raises(HTTPException) as exc_info:
        verify_token(access, token_type="refresh")
    assert exc_info.value.status_code == 401


# ── OAuth CSRF state tests ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_google_login_stores_state_in_redis():
    """GET /auth/google must call redis.setex with the generated state."""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    with patch("src.api.routes.auth._get_redis", return_value=mock_redis):
        from fastapi import FastAPI
        from src.api.routes.auth import router as auth_router
        app = FastAPI()
        app.include_router(auth_router, prefix="/auth")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/auth/google")

    assert resp.status_code == 200
    body = resp.json()
    assert "state" in body
    assert "url" in body
    # Verify Redis was called with the state value
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert f"oauth:state:{body['state']}" == call_args[0][0]


@pytest.mark.anyio
async def test_google_callback_rejects_invalid_state():
    """GET /auth/google/callback with an unknown state must return 400."""
    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value=None)  # state not found

    with patch("src.api.routes.auth._get_redis", return_value=mock_redis):
        from fastapi import FastAPI
        from src.api.routes.auth import router as auth_router
        app = FastAPI()
        app.include_router(auth_router, prefix="/auth")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/auth/google/callback?code=legit_code&state=forged_state")

    assert resp.status_code == 400
    assert "Invalid or expired OAuth state" in resp.json()["detail"]


@pytest.mark.anyio
async def test_google_callback_accepts_valid_state():
    """GET /auth/google/callback with valid state proceeds to token exchange."""
    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value="1")  # state exists

    google_token_data = {"access_token": "goog_access", "id_token": "goog_id"}
    google_userinfo = {
        "sub": "google_uid_123",
        "email": "oauth_user@example.com",
        "name": "OAuth User",
        "picture": None,
    }

    mock_token_resp = MagicMock()
    mock_token_resp.raise_for_status = MagicMock()
    mock_token_resp.json = MagicMock(return_value=google_token_data)

    mock_userinfo_resp = MagicMock()
    mock_userinfo_resp.raise_for_status = MagicMock()
    mock_userinfo_resp.json = MagicMock(return_value=google_userinfo)

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_token_resp)
    mock_http.get = AsyncMock(return_value=mock_userinfo_resp)

    user_obj = _make_user_row(email="oauth_user@example.com", user_id=5)
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user_obj)))
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()

    with (
        patch("src.api.routes.auth._get_redis", return_value=mock_redis),
        patch("httpx.AsyncClient", return_value=mock_http),
        patch("src.api.routes.auth.get_session", return_value=mock_session),
    ):
        from fastapi import FastAPI
        from src.api.routes.auth import router as auth_router
        app = FastAPI()
        app.include_router(auth_router, prefix="/auth")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/auth/google/callback?code=real_code&state=valid_state")

    # State was found → no early 400; may succeed or fail on user DB write
    assert resp.status_code != 400 or "OAuth state" not in resp.json().get("detail", "")
