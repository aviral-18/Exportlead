"""
Dashboard routes — four curated buyer lists for the sales team.

GET /api/v1/dashboard/top-buyers      — highest composite_score, recently active
GET /api/v1/dashboard/new-buyers      — new_importer_score > 60
GET /api/v1/dashboard/high-growth     — growth_trend_score > 65
GET /api/v1/dashboard/untapped        — product_fit > 70 AND india_import < 40
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import and_, select

from src.core.database import get_session
from src.core.models import CanonicalBuyer, LeadScore

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _row(buyer: CanonicalBuyer, ls: LeadScore) -> dict:
    return {
        "id": buyer.id,
        "company_name": buyer.company_name,
        "country_code": buyer.country_code,
        "country_name": buyer.country_name,
        "city": buyer.city,
        "buyer_type": buyer.buyer_type,
        "import_frequency": buyer.import_frequency,
        "estimated_annual_volume_usd": float(buyer.estimated_annual_volume_usd or 0),
        "last_import_date": buyer.last_import_date.isoformat() if buyer.last_import_date else None,
        "first_import_date": buyer.first_import_date.isoformat() if buyer.first_import_date else None,
        "total_shipments": buyer.total_shipments,
        "source_count": buyer.source_count,
        "website": buyer.website,
        "composite_score": float(ls.composite_score or 0),
        "tier": ls.tier,
        "india_import_probability": float(ls.india_import_probability or 0),
        "supplier_switch_probability": float(ls.supplier_switch_probability or 0),
        "product_fit_score": float(ls.product_fit_score or 0),
        "growth_trend_score": float(ls.growth_trend_score or 0),
        "new_importer_score": float(ls.new_importer_score or 0),
        "import_activity_score": float(ls.import_activity_score or 0),
        "scored_at": ls.scored_at.isoformat() if ls.scored_at else None,
    }


@router.get("/top-buyers", summary="Highest composite score, recently active buyers")
async def top_buyers(
    limit: int = Query(50, ge=1, le=500),
    min_composite: float = Query(60.0, ge=0, le=100),
    country_code: Optional[str] = Query(None),
    buyer_type: Optional[str] = Query(None),
):
    """Hot leads — high overall score AND active importers."""
    async with get_session() as db:
        stmt = (
            select(CanonicalBuyer, LeadScore)
            .join(LeadScore, CanonicalBuyer.id == LeadScore.canonical_id)
            .where(
                CanonicalBuyer.is_active == True,
                LeadScore.composite_score >= min_composite,
            )
        )
        if country_code:
            stmt = stmt.where(CanonicalBuyer.country_code == country_code.upper())
        if buyer_type:
            stmt = stmt.where(CanonicalBuyer.buyer_type == buyer_type)
        stmt = stmt.order_by(LeadScore.composite_score.desc()).limit(limit)
        rows = (await db.execute(stmt)).all()

    return {
        "view": "top_buyers",
        "filter": f"composite >= {min_composite}",
        "count": len(rows),
        "results": [_row(b, ls) for b, ls in rows],
    }


@router.get("/new-buyers", summary="Newly active importers - high urgency to contact")
async def new_buyers(
    limit: int = Query(50, ge=1, le=500),
    min_new_score: float = Query(60.0, ge=0, le=100),
    country_code: Optional[str] = Query(None),
):
    """Fresh importers who just started — reach them before competitors do."""
    async with get_session() as db:
        stmt = (
            select(CanonicalBuyer, LeadScore)
            .join(LeadScore, CanonicalBuyer.id == LeadScore.canonical_id)
            .where(
                CanonicalBuyer.is_active == True,
                LeadScore.new_importer_score >= min_new_score,
            )
        )
        if country_code:
            stmt = stmt.where(CanonicalBuyer.country_code == country_code.upper())
        stmt = stmt.order_by(
            LeadScore.new_importer_score.desc(),
            LeadScore.composite_score.desc(),
        ).limit(limit)
        rows = (await db.execute(stmt)).all()

    return {
        "view": "new_buyers",
        "filter": f"new_importer_score >= {min_new_score}",
        "count": len(rows),
        "results": [_row(b, ls) for b, ls in rows],
    }


@router.get("/high-growth", summary="Buyers with strong growth trajectory")
async def high_growth(
    limit: int = Query(50, ge=1, le=500),
    min_growth: float = Query(65.0, ge=0, le=100),
    country_code: Optional[str] = Query(None),
    buyer_type: Optional[str] = Query(None),
):
    """Trending upward — frequent importers, high volume, recently active."""
    async with get_session() as db:
        stmt = (
            select(CanonicalBuyer, LeadScore)
            .join(LeadScore, CanonicalBuyer.id == LeadScore.canonical_id)
            .where(
                CanonicalBuyer.is_active == True,
                LeadScore.growth_trend_score >= min_growth,
            )
        )
        if country_code:
            stmt = stmt.where(CanonicalBuyer.country_code == country_code.upper())
        if buyer_type:
            stmt = stmt.where(CanonicalBuyer.buyer_type == buyer_type)
        stmt = stmt.order_by(
            LeadScore.growth_trend_score.desc(),
            LeadScore.composite_score.desc(),
        ).limit(limit)
        rows = (await db.execute(stmt)).all()

    return {
        "view": "high_growth",
        "filter": f"growth_trend >= {min_growth}",
        "count": len(rows),
        "results": [_row(b, ls) for b, ls in rows],
    }


@router.get("/untapped", summary="Product fit match but not yet importing from India")
async def untapped(
    limit: int = Query(50, ge=1, le=500),
    min_product_fit: float = Query(70.0, ge=0, le=100),
    max_india_prob: float = Query(40.0, ge=0, le=100),
    country_code: Optional[str] = Query(None),
):
    """
    Best unconverted opportunity — buyer needs exactly what Moradabad makes,
    but hasn't yet been sourcing from India. High outreach ROI.
    """
    async with get_session() as db:
        stmt = (
            select(CanonicalBuyer, LeadScore)
            .join(LeadScore, CanonicalBuyer.id == LeadScore.canonical_id)
            .where(
                CanonicalBuyer.is_active == True,
                LeadScore.product_fit_score >= min_product_fit,
                LeadScore.india_import_probability <= max_india_prob,
            )
        )
        if country_code:
            stmt = stmt.where(CanonicalBuyer.country_code == country_code.upper())
        stmt = stmt.order_by(
            LeadScore.product_fit_score.desc(),
            LeadScore.india_import_probability.asc(),
        ).limit(limit)
        rows = (await db.execute(stmt)).all()

    return {
        "view": "untapped",
        "filter": f"product_fit >= {min_product_fit} AND india_import_prob <= {max_india_prob}",
        "count": len(rows),
        "results": [_row(b, ls) for b, ls in rows],
    }
