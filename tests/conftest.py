"""Shared fixtures for the BrassExport test suite.

Uses SQLite in-memory so tests run without PostgreSQL or Redis.
The real app's DB engine is monkey-patched per test session.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

SQLITE_URL = "sqlite+aiosqlite:///:memory:"

_engine = create_async_engine(SQLITE_URL, future=True)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    from src.auth.models import Base as AuthBase
    async with _engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine):
    async with _SessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def api_client(db_engine, monkeypatch):
    """HTTP client pointed at the FastAPI app with SQLite DB injected."""
    from src.core import database as _db_mod

    async def _override_session():
        async with _SessionLocal() as s:
            yield s

    monkeypatch.setattr(_db_mod, "get_session", _override_session)

    from src.api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
