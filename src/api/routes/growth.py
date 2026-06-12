"""
Growth engine API routes.

GET  /api/v1/growth/recommendations         — today's top-10 buyer recommendations
GET  /api/v1/growth/opportunities           — ranked opportunity list with filters
GET  /api/v1/growth/emerging                — emerging importers
GET  /api/v1/growth/discovery/history       — discovery run log
POST /api/v1/growth/discovery/run           — trigger manual discovery run (async)
POST /api/v1/growth/opportunities/{id}/status  — update opportunity status
POST /api/v1/growth/opportunities/{id}/add-to-crm  — convert to CRM lead
"""
from __future__ import annotations

import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import func, select

from src.core.database import get_session
from src.core.models import CanonicalBuyer, LeadScore
from src.growth.models import (
    DailyRecommendation,
    DiscoveryRun,
    EmergingImporter,
    GrowthOpportunity,
)
from src.growth.ranker import rank

router = APIRouter(prefix="/growth", tags=["growth"])


# ── Helpers ───────────────────────────────────────────────────────────────────
def _out_opp(opp: GrowthOpportunity, buyer: Optional[CanonicalBuyer] = None) -> dict:
    d = {
        "id": opp.id,
        "canonical_id": opp.canonical_id,
        "opportunity_score": float(opp.opportunity_score or 0),
        "rank_position": opp.rank_position,
        "country_code": opp.country_code,
        "buyer_type": opp.buyer_type,
        "estimated_value_usd": float(opp.estimated_value_usd or 0),
        "india_import_probability": float(opp.india_import_probability or 0),
        "product_fit_score": float(opp.product_fit_score or 0),
        "competitive_gap_score": float(opp.competitive_gap_score or 0),
        "market_timing_score": float(opp.market_timing_score or 0),
        "country_market_score": float(opp.country_market_score or 0),
        "is_new_discovery": opp.is_new_discovery,
        "is_emerging": opp.is_emerging,
        "reasoning": opp.reasoning,
        "market_signals": json.loads(opp.market_signals_json or "[]"),
        "status": opp.status,
        "crm_lead_id": opp.crm_lead_id,
        "discovered_at": opp.discovered_at.isoformat() if opp.discovered_at else None,
    }
    if buyer:
        d["company_name"] = buyer.company_name
        d["city"] = buyer.city
        d["website"] = buyer.website
        d["import_frequency"] = buyer.import_frequency
        d["last_import_date"] = buyer.last_import_date.isoformat() if buyer.last_import_date else None
    return d


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/recommendations", summary="Today's top-10 ranked buyer recommendations")
async def get_recommendations(
    run_date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
    limit: int = Query(10, ge=1, le=50),
):
    target_date = run_date or date.today().isoformat()
    async with get_session() as session:
        recs = (await session.execute(
            select(DailyRecommendation, CanonicalBuyer, LeadScore)
            .join(CanonicalBuyer, DailyRecommendation.canonical_id == CanonicalBuyer.id)
            .outerjoin(LeadScore, LeadScore.canonical_id == CanonicalBuyer.id)
            .where(DailyRecommendation.run_date == target_date)
            .order_by(DailyRecommendation.rank_position.asc())
            .limit(limit)
        )).all()

        if not recs:
            # Fall back to most recent run date
            latest_date = (await session.execute(
                select(DailyRecommendation.run_date)
                .order_by(DailyRecommendation.run_date.desc())
                .limit(1)
            )).scalar_one_or_none()
            if latest_date:
                recs = (await session.execute(
                    select(DailyRecommendation, CanonicalBuyer, LeadScore)
                    .join(CanonicalBuyer, DailyRecommendation.canonical_id == CanonicalBuyer.id)
                    .outerjoin(LeadScore, LeadScore.canonical_id == CanonicalBuyer.id)
                    .where(DailyRecommendation.run_date == latest_date)
                    .order_by(DailyRecommendation.rank_position.asc())
                    .limit(limit)
                )).all()
                target_date = latest_date

    results = []
    for rec, buyer, ls in recs:
        opp_data = None
        if ls:
            opp_rank = rank(buyer, ls)
            opp_data = {
                "opportunity_score": opp_rank.opportunity_score,
                "competitive_gap_score": opp_rank.competitive_gap_score,
                "market_timing_score": opp_rank.market_timing_score,
                "country_market_score": opp_rank.country_market_score,
            }
        results.append({
            "rank": rec.rank_position,
            "recommendation_id": rec.id,
            "canonical_id": rec.canonical_id,
            "company_name": buyer.company_name,
            "country_code": buyer.country_code,
            "country_name": buyer.country_name,
            "city": buyer.city,
            "buyer_type": buyer.buyer_type,
            "website": buyer.website,
            "email": json.loads(buyer.email_json or "[]"),
            "opportunity_score": float(rec.opportunity_score or 0),
            "composite_lead_score": float(rec.composite_lead_score or 0),
            "estimated_value_usd": float(buyer.estimated_annual_volume_usd or 0),
            "reasoning": rec.reasoning,
            "key_signals": json.loads(rec.key_signals_json or "[]"),
            "action_type": rec.action_type,
            "email_template": rec.email_template,
            "status": rec.status,
            **(opp_data or {}),
        })

    return {
        "run_date": target_date,
        "count": len(results),
        "recommendations": results,
    }


@router.get("/opportunities", summary="Ranked growth opportunities with filters")
async def list_opportunities(
    status: str = Query("active"),
    country_code: Optional[str] = Query(None),
    buyer_type: Optional[str] = Query(None),
    min_score: float = Query(40.0),
    is_new_discovery: Optional[bool] = Query(None),
    is_emerging: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    async with get_session() as session:
        stmt = (
            select(GrowthOpportunity, CanonicalBuyer)
            .join(CanonicalBuyer, GrowthOpportunity.canonical_id == CanonicalBuyer.id)
            .where(
                GrowthOpportunity.status == status,
                GrowthOpportunity.opportunity_score >= min_score,
            )
        )
        if country_code:
            stmt = stmt.where(GrowthOpportunity.country_code == country_code.upper())
        if buyer_type:
            stmt = stmt.where(GrowthOpportunity.buyer_type == buyer_type)
        if is_new_discovery is not None:
            stmt = stmt.where(GrowthOpportunity.is_new_discovery == is_new_discovery)
        if is_emerging is not None:
            stmt = stmt.where(GrowthOpportunity.is_emerging == is_emerging)

        total = (await session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        rows = (await session.execute(
            stmt.order_by(GrowthOpportunity.opportunity_score.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [_out_opp(opp, buyer) for opp, buyer in rows],
    }


@router.patch("/opportunities/{opp_id}/status", summary="Update opportunity status")
async def update_opportunity_status(opp_id: int, status: str, notes: Optional[str] = None):
    valid = {"active", "contacted", "in_crm", "dismissed"}
    if status not in valid:
        raise HTTPException(400, f"status must be one of {valid}")
    async with get_session() as session:
        opp = await session.get(GrowthOpportunity, opp_id)
        if not opp:
            raise HTTPException(404, "Opportunity not found")
        opp.status = status
        if status == "dismissed":
            from datetime import datetime
            opp.dismissed_at = datetime.utcnow()
        await session.commit()
    return {"id": opp_id, "status": status}


@router.post("/opportunities/{opp_id}/add-to-crm", summary="Convert growth opportunity to CRM lead", status_code=201)
async def add_to_crm(opp_id: int):
    from datetime import datetime
    from uuid import uuid4
    from src.crm.models import Lead
    async with get_session() as session:
        opp = await session.get(GrowthOpportunity, opp_id)
        if not opp:
            raise HTTPException(404, "Opportunity not found")
        if opp.crm_lead_id:
            raise HTTPException(409, f"Already linked to CRM lead {opp.crm_lead_id}")
        buyer = await session.get(CanonicalBuyer, opp.canonical_id)
        if not buyer:
            raise HTTPException(404, "Canonical buyer not found")
        emails = json.loads(buyer.email_json or "[]")
        lead = Lead(
            uuid=str(uuid4()),
            canonical_buyer_id=buyer.id,
            company_name=buyer.company_name,
            country_code=buyer.country_code,
            country_name=buyer.country_name,
            contact_email=emails[0] if emails else None,
            status="new",
            source="growth_engine",
            priority="hot" if (opp.opportunity_score or 0) >= 75 else "warm",
            estimated_value_usd=float(opp.estimated_value_usd or 0),
        )
        session.add(lead)
        await session.flush()
        opp.crm_lead_id = lead.id
        opp.status = "in_crm"
        opp.added_to_crm_at = datetime.utcnow()
        await session.commit()
    return {"crm_lead_id": lead.id, "opportunity_id": opp_id}


@router.get("/emerging", summary="Emerging importers — buyers recently starting to import")
async def get_emerging(
    min_score: float = Query(40.0),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    async with get_session() as session:
        stmt = (
            select(EmergingImporter, CanonicalBuyer)
            .join(CanonicalBuyer, EmergingImporter.canonical_id == CanonicalBuyer.id)
            .where(EmergingImporter.is_active == True, EmergingImporter.overall_score >= min_score)
        )
        if category:
            stmt = stmt.where(EmergingImporter.category == category)
        total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await session.execute(
            stmt.order_by(EmergingImporter.overall_score.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )).all()
    results = []
    for em, buyer in rows:
        results.append({
            "id": em.id,
            "canonical_id": em.canonical_id,
            "company_name": buyer.company_name,
            "country_code": buyer.country_code,
            "buyer_type": buyer.buyer_type,
            "months_active": em.months_active,
            "shipment_count": em.shipment_count,
            "annual_volume_usd": float(em.annual_volume_usd or 0),
            "growth_velocity_score": float(em.growth_velocity_score or 0),
            "market_timing_score": float(em.market_timing_score or 0),
            "overall_score": float(em.overall_score or 0),
            "category": em.category,
            "confidence": em.confidence,
            "action_recommended": em.action_recommended,
            "trend": json.loads(em.trend_json or "{}"),
            "detected_at": em.detected_at.isoformat() if em.detected_at else None,
        })
    return {"total": total, "page": page, "page_size": page_size, "results": results}


@router.get("/discovery/history", summary="Discovery run history")
async def discovery_history(page: int = Query(1, ge=1), page_size: int = Query(20)):
    async with get_session() as session:
        total = (await session.execute(select(func.count(DiscoveryRun.id)))).scalar_one()
        rows = (await session.execute(
            select(DiscoveryRun).order_by(DiscoveryRun.run_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
    return {
        "total": total,
        "runs": [
            {
                "id": r.id,
                "run_at": r.run_at.isoformat() if r.run_at else None,
                "status": r.status,
                "new_buyers_found": r.new_buyers_found,
                "existing_buyers_updated": r.existing_buyers_updated,
                "scored": r.scored,
                "opportunities_created": r.opportunities_created,
                "emerging_flagged": r.emerging_flagged,
                "top_opportunity_score": float(r.top_opportunity_score or 0),
                "run_duration_seconds": float(r.run_duration_seconds or 0),
                "error_message": r.error_message,
            }
            for r in rows
        ],
    }


@router.post("/discovery/run", summary="Trigger a manual discovery run")
async def trigger_discovery(background_tasks: BackgroundTasks):
    from src.workers.tasks import run_daily_discovery_task
    run_daily_discovery_task.apply_async()
    return {"message": "Discovery run queued", "queue": "pipeline"}
