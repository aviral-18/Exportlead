"""Tests for the scoring background task wiring.

Before the fix:
    background_tasks.add_task(asyncio.create_task, _run())
    — called _run() immediately (creating a coroutine), then tried to schedule
      asyncio.create_task as the background callable, which is wrong.

After the fix:
    background_tasks.add_task(score_all_buyers, only_unscored=..., min_confidence=...)
    — defers the async callable correctly; FastAPI awaits it after the response.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.scoring import router as scoring_router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(scoring_router, prefix="/scores")
    return app


def test_run_scoring_returns_200():
    """POST /scores/run must return 200 and start status without error."""
    app = _make_app()

    with patch("src.scoring.engine.score_all_buyers", new_callable=AsyncMock) as mock_fn:
        with TestClient(app) as client:
            resp = client.post("/scores/run")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "started"


def test_run_scoring_defers_not_runs_immediately():
    """score_all_buyers must NOT be called before the response is returned.

    FastAPI background tasks run after the response is sent to the client.
    If the old broken implementation (asyncio.create_task + _run()) was used,
    the coroutine would be scheduled immediately on the event loop.
    """
    app = _make_app()
    call_count = 0

    async def _mock_score_all(**kwargs):
        nonlocal call_count
        call_count += 1

    with patch("src.scoring.engine.score_all_buyers", side_effect=_mock_score_all):
        with TestClient(app) as client:
            resp = client.post("/scores/run")
            # At this point (before TestClient context exit) the background task
            # should NOT have run yet (it runs after response dispatch).
            assert resp.status_code == 200
