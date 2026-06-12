"""Tests for the /scores router.

Verifies the critical route-ordering fix: GET /scores/distribution must be
reachable and must NOT be swallowed by GET /scores/{buyer_id: int}.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.routes.scoring import router as scoring_router


@pytest.fixture()
def scoring_app() -> FastAPI:
    app = FastAPI()
    app.include_router(scoring_router, prefix="/scores")
    return app


@pytest.mark.anyio
async def test_distribution_route_is_reachable(scoring_app: FastAPI):
    """GET /scores/distribution must return 200 or a DB-related error, NOT 422.

    Before the fix, FastAPI matched /distribution against /{buyer_id: int}
    first and raised 422 Unprocessable Entity because "distribution" is not
    an integer.  After the fix the literal route is declared first and returns
    a proper response (may fail on DB but never with 422 type-coercion error).
    """
    async with AsyncClient(transport=ASGITransport(app=scoring_app), base_url="http://test") as client:
        resp = await client.get("/scores/distribution")
    # 422 would mean the route-ordering bug is still present
    assert resp.status_code != 422, (
        f"Route ordering bug: /scores/distribution returned 422 — "
        f"'distribution' is being coerced to int by /{'{'}buyer_id{'}'}"
    )


@pytest.mark.anyio
async def test_integer_buyer_id_still_works(scoring_app: FastAPI):
    """GET /scores/42 must still match the /{buyer_id: int} route."""
    async with AsyncClient(transport=ASGITransport(app=scoring_app), base_url="http://test") as client:
        resp = await client.get("/scores/42")
    # 404 = route matched, buyer not found in DB — that is fine
    # 422 = type-coercion error — would mean something is broken
    assert resp.status_code != 422


@pytest.mark.anyio
async def test_non_integer_buyer_id_returns_422(scoring_app: FastAPI):
    """GET /scores/notanint (not a reserved word) should 422 on bad type."""
    async with AsyncClient(transport=ASGITransport(app=scoring_app), base_url="http://test") as client:
        resp = await client.get("/scores/notanint")
    assert resp.status_code == 422
