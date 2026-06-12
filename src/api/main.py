"""
BrassExport Intelligence — FastAPI application entry point.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import make_asgi_app

from src.api.routes import analytics, buyers, calculator, dashboard, scoring, search
from src.api.routes import crm as crm_router
from src.api.routes import growth as growth_router
from src.api.routes import outreach as outreach_router
from src.api.routes import executive as executive_router
from src.api.routes import auth as auth_router
from src.api.routes import ws as ws_router
from src.core.database import close_engine, get_engine

log = structlog.get_logger(__name__)

_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup: initialising database engine")
    get_engine()  # warm up pool
    yield
    log.info("shutdown: closing database engine")
    await close_engine()


app = FastAPI(
    title="BrassExport Intelligence",
    description=(
        "Institutional-grade export intelligence platform for Moradabad brass exporters. "
        "50M+ global buyer records across 25+ data sources."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Total-Count", "X-Request-ID"],
)

# ── Prometheus metrics endpoint ───────────────────────────────────────────────
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(ws_router.router)
app.include_router(buyers.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(scoring.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(crm_router.router, prefix="/api/v1")
app.include_router(calculator.router, prefix="/api/v1")
app.include_router(growth_router.router, prefix="/api/v1")
app.include_router(outreach_router.router, prefix="/api/v1")
app.include_router(executive_router.router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "BrassExport Intelligence"}


@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "service": "BrassExport Intelligence",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
