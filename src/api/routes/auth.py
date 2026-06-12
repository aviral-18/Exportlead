"""Authentication endpoints — email/password + Google OAuth."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import httpx
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from src.auth.jwt import (
    create_access_token,
    create_refresh_token,
    get_current_user_id,
    verify_token,
)
from src.auth.models import RefreshToken, User
from src.auth.password import hash_password, verify_password
from src.core.config import settings
from src.core.database import get_session

_redis: aioredis.Redis | None = None
_OAUTH_STATE_TTL = 300  # 5 minutes


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "is_verified": user.is_verified,
    }


async def _issue_tokens(user: User) -> TokenResponse:
    access = create_access_token(user.id, extra={"role": user.role, "email": user.email})
    refresh = create_refresh_token(user.id)
    token_hash = hashlib.sha256(refresh.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    async with get_session() as session:
        session.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires))
        user.last_login_at = datetime.now(timezone.utc)
        await session.commit()

    return TokenResponse(access_token=access, refresh_token=refresh, user=_user_dict(user))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    async with get_session() as session:
        existing = (await session.execute(
            select(User).where(User.email == body.email)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(
            email=body.email,
            hashed_password=hash_password(body.password),
            full_name=body.full_name,
            role="analyst",
            is_verified=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    log.info("user_registered", email=body.email, user_id=user.id)
    return await _issue_tokens(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    async with get_session() as session:
        user = (await session.execute(
            select(User).where(User.email == body.email, User.is_active.is_(True))
        )).scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return await _issue_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest):
    payload = verify_token(body.refresh_token, token_type="refresh")
    user_id = int(payload["sub"])
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()

    async with get_session() as session:
        rt = (await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
            )
        )).scalar_one_or_none()

        if not rt or rt.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Refresh token invalid or expired")

        rt.revoked = True
        user = (await session.execute(
            select(User).where(User.id == user_id, User.is_active.is_(True))
        )).scalar_one_or_none()
        await session.commit()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return await _issue_tokens(user)


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    user_id: int = Depends(get_current_user_id),
):
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    async with get_session() as session:
        rt = (await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == user_id,
            )
        )).scalar_one_or_none()
        if rt:
            rt.revoked = True
            await session.commit()
    return {"message": "Logged out"}


@router.get("/me")
async def me(user_id: int = Depends(get_current_user_id)) -> dict:
    async with get_session() as session:
        user = (await session.execute(
            select(User).where(User.id == user_id)
        )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_dict(user)


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    """Redirect URL for Google OAuth initiation (called from frontend)."""
    state = secrets.token_urlsafe(16)
    await _get_redis().setex(f"oauth:state:{state}", _OAUTH_STATE_TTL, "1")
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.google_client_id}"
        f"&redirect_uri={settings.google_redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        f"&state={state}"
        "&access_type=offline"
    )
    return {"url": url, "state": state}


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(code: str, state: str):
    valid = await _get_redis().getdel(f"oauth:state:{state}")
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        google_user = userinfo_resp.json()

    async with get_session() as session:
        user = (await session.execute(
            select(User).where(User.google_id == google_user["sub"])
        )).scalar_one_or_none()

        if not user:
            user = (await session.execute(
                select(User).where(User.email == google_user["email"])
            )).scalar_one_or_none()

        if not user:
            user = User(
                email=google_user["email"],
                full_name=google_user.get("name", ""),
                google_id=google_user["sub"],
                avatar_url=google_user.get("picture"),
                role="analyst",
                is_verified=True,
                is_active=True,
            )
            session.add(user)
        else:
            user.google_id = google_user["sub"]
            user.avatar_url = google_user.get("picture")
            user.is_verified = True

        await session.commit()
        await session.refresh(user)

    return await _issue_tokens(user)
