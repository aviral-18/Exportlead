"""Role-based access control."""
from __future__ import annotations

from enum import Enum
from functools import wraps

from fastapi import Depends, HTTPException, status

from src.auth.jwt import get_current_user_id
from src.core.database import get_session
from src.auth.models import User
from sqlalchemy import select


class Role(str, Enum):
    admin = "admin"
    manager = "manager"
    analyst = "analyst"
    viewer = "viewer"


_HIERARCHY: dict[str, int] = {
    Role.admin: 40,
    Role.manager: 30,
    Role.analyst: 20,
    Role.viewer: 10,
}


def require_role(minimum_role: Role):
    """FastAPI dependency: raises 403 if authenticated user's role is below minimum."""
    async def _check(
        user_id: int = Depends(get_current_user_id),
    ) -> User:
        async with get_session() as session:
            user = (await session.execute(
                select(User).where(User.id == user_id, User.is_active.is_(True))
            )).scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        if _HIERARCHY.get(user.role, 0) < _HIERARCHY.get(minimum_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' does not have permission. Required: '{minimum_role}'",
            )
        return user

    return _check
