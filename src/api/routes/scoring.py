"""
Scoring API routes.
GET  /api/v1/scores/{buyer_id}   — scores for a single canonical buyer
POST /api/v1/scores/{buyer_id}/rescore — trigger re-score for one buyer
GET  /api/v1/scores/top          — paginated top-scored buyers
POST /api/v1/scores/run          — trigger full scoring run (async background)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import func, select

from src.core.database import get_session
from src.core.models import CanonicalBuyer, LeadScore

router = APIRouter(prefix="/scores", tags=["scoring"])


def _fmt(ls: LeadScore) -> dict:
    return {
        "canonical_id": ls.canonical_id,
        "composite_score": float(ls.composite_score or 0),
        "tier": ls.tier,
        "dimensions": {
            "india_import_probability": float(ls.india_import_probability or 0),
            "supplier_switch_probability": float(ls.supplier_switch_probability or 0),
            "product_fit_score": float(ls.product_fit_score or 0),
            "growth_trend_score": float(ls.growth_trend_score or 0),
            "new_importer_score": float(ls.new_importer_score or 0),
            "import_activity_score": float(ls.import_activity_score or 0),
        },
        "scored_at": ls.scored_at.isoformat() if ls.scored_at else None,
    }


@router.get("/top", summary="Top scored buyers with full profile")
async def top_scores(
    limit: int = Query(50, ge=1, le=500),
    min_composite: float = Query(0.0, ge=0, le=100),
    tier: Optional[str] = Query(None, description="A, B, C, D, or F"),
):
    async with get_session() as db:
        stmt = (
            select(CanonicalBuyer, LeadScore)
            .join(LeadScore, CanonicalBuyer.id == LeadScore.canonical_id)
            .where(CanonicalBuyer.is_active == True)
        )
        if min_composite > 0:
            stmt = stmt.where(LeadScore.composite_score >= min_composite)
        if tier:
            stmt = stmt.where(LeadScore.tier == tier.upper())
        stmt = stmt.order_by(LeadScore.composite_score.desc()).limit(limit)
        rows = (await db.execute(stmt)).all()

    results = []
    for buyer, ls in rows:
        results.append({
            "id": buyer.id,
            "company_name": buyer.company_name,
            "country_code": buyer.country_code,
            "buyer_type": buyer.buyer_type,
            "estimated_annual_volume_usd": float(buyer.estimated_annual_volume_usd or 0),
            "last_import_date": buyer.last_import_date.isoformat() if buyer.last_import_date else None,
            "score": _fmt(ls),
        })
    return {"count": len(results), "results": results}


# NOTE: /distribution MUST be declared before /{buyer_id} — otherwise FastAPI
# matches the parameterised route first and raises 422 on "distribution" → int.
@router.get("/distribution", summary="Score tier distribution — totals, average, by-tier breakdown")
async def score_distribution():
    """Aggregated stats needed by the analytics dashboard."""
    async with get_session() as db:
        total = (await db.execute(select(func.count(LeadScore.id)))).scalar_one()
        avg = (await db.execute(select(func.avg(LeadScore.composite_score)))).scalar_one() or 0
        tier_rows = (await db.execute(
            select(LeadScore.tier, func.count(LeadScore.id).label("cnt"))
            .group_by(LeadScore.tier)
        )).fetchall()
    by_tier = {r.tier: r.cnt for r in tier_rows}
    return {
        "total_scored": total,
        "avg_score": round(float(avg), 2),
        "by_tier": by_tier,
    }


@router.get("/{buyer_id}", summary="Get lead score for a single canonical buyer")
async def get_score(buyer_id: int):
    async with get_session() as db:
        ls = (
            await db.execute(select(LeadScore).where(LeadScore.canonical_id == buyer_id))
        ).scalar_one_or_none()
        if not ls:
            raise HTTPException(404, f"No score found for buyer_id={buyer_id}. Run /scores/{buyer_id}/rescore first.")
    return _fmt(ls)


@router.post("/{buyer_id}/rescore", summary="Re-score a single buyer immediately")
async def rescore_buyer(buyer_id: int):
    from src.scoring.engine import score_single_buyer
    result = await score_single_buyer(buyer_id)
    if result is None:
        raise HTTPException(404, f"Buyer {buyer_id} not found")
    return {"canonical_id": buyer_id, "scored": True, "scores": result}


@router.post("/run", summary="Trigger full scoring run in background")
async def run_scoring(
    background_tasks: BackgroundTasks,
    only_unscored: bool = Query(False, description="Only score buyers with no existing score"),
    min_confidence: float = Query(0.0, ge=0, le=1),
):
    from src.scoring.engine import score_all_buyers
    background_tasks.add_task(score_all_buyers, only_unscored=only_unscored, min_confidence=min_confidence)
    return {"status": "started", "message": "Scoring run queued in background"}
