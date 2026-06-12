"""JWT token creation and verification."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import settings

_ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(subject), "exp": expires, "type": "access", **(extra or {})}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def create_refresh_token(subject: str | int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": str(subject), "exp": expires, "type": "refresh"}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
        if payload.get("type") != token_type:
            raise ValueError("token type mismatch")
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> int:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = verify_token(credentials.credentials)
    return int(payload["sub"])


def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> int | None:
    if not credentials:
        return None
    try:
        payload = verify_token(credentials.credentials)
        return int(payload["sub"])
    except HTTPException:
        return None
