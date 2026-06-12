"""Opportunity management routes."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from src.core.database import get_session
from src.crm.models import Opportunity, OpportunityStage

router = APIRouter(prefix="/opportunities")


class OpportunityCreate(BaseModel):
    lead_id: int
    title: str
    stage: str = "prospecting"
    probability_pct: int = 20
    estimated_value_usd: Optional[float] = None
    currency: str = "USD"
    products: Optional[dict] = None
    quantity_kg: Optional[float] = None
    incoterms: Optional[str] = None
    payment_terms: Optional[str] = None
    expected_close_date: Optional[date] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


class OpportunityPatch(BaseModel):
    title: Optional[str] = None
    stage: Optional[str] = None
    probability_pct: Optional[int] = None
    estimated_value_usd: Optional[float] = None
    products: Optional[dict] = None
    quantity_kg: Optional[float] = None
    incoterms: Optional[str] = None
    payment_terms: Optional[str] = None
    expected_close_date: Optional[date] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    lost_reason: Optional[str] = None


# Stage-to-probability defaults
STAGE_PROBABILITY = {
    "prospecting": 10, "qualification": 25, "proposal": 45,
    "negotiation": 70, "won": 100, "lost": 0,
}


def _fmt(o: Opportunity) -> dict:
    return {
        "id": o.id, "uuid": o.uuid, "lead_id": o.lead_id,
        "title": o.title, "stage": o.stage,
        "probability_pct": o.probability_pct,
        "estimated_value_usd": float(o.estimated_value_usd) if o.estimated_value_usd else None,
        "weighted_value_usd": (
            float(o.estimated_value_usd or 0) * (o.probability_pct or 0) / 100
        ),
        "currency": o.currency,
        "products": o.products,
        "quantity_kg": float(o.quantity_kg) if o.quantity_kg else None,
        "incoterms": o.incoterms, "payment_terms": o.payment_terms,
        "expected_close_date": o.expected_close_date.isoformat() if o.expected_close_date else None,
        "actual_close_date": o.actual_close_date.isoformat() if o.actual_close_date else None,
        "won_at": o.won_at.isoformat() if o.won_at else None,
        "lost_at": o.lost_at.isoformat() if o.lost_at else None,
        "lost_reason": o.lost_reason,
        "assigned_to": o.assigned_to, "notes": o.notes,
        "created_at": o.created_at.isoformat(),
        "updated_at": o.updated_at.isoformat(),
    }


@router.get("/", summary="List opportunities")
async def list_opportunities(
    lead_id: Optional[int] = Query(None),
    stage: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    async with get_session() as db:
        stmt = select(Opportunity)
        if lead_id is not None:
            stmt = stmt.where(Opportunity.lead_id == lead_id)
        if stage:
            stmt = stmt.where(Opportunity.stage == stage)
        if assigned_to:
            stmt = stmt.where(Opportunity.assigned_to == assigned_to)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(Opportunity.estimated_value_usd.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "results": [_fmt(r) for r in rows],
    }


@router.post("/", summary="Create opportunity", status_code=201)
async def create_opportunity(body: OpportunityCreate):
    async with get_session() as db:
        data = body.model_dump(exclude_none=True)
        if "probability_pct" not in data:
            data["probability_pct"] = STAGE_PROBABILITY.get(data.get("stage", "prospecting"), 20)
        opp = Opportunity(**data)
        db.add(opp)
        await db.commit()
        await db.refresh(opp)
    return _fmt(opp)


@router.get("/funnel", summary="Pipeline funnel by stage")
async def funnel():
    async with get_session() as db:
        stmt = (
            select(
                Opportunity.stage,
                func.count(Opportunity.id).label("count"),
                func.sum(Opportunity.estimated_value_usd).label("total_value"),
            )
            .group_by(Opportunity.stage)
        )
        rows = (await db.execute(stmt)).fetchall()
    stage_order = ["prospecting", "qualification", "proposal", "negotiation", "won", "lost"]
    by_stage = {r.stage: r for r in rows}
    return [
        {
            "stage": s,
            "count": by_stage[s].count if s in by_stage else 0,
            "total_value_usd": float(by_stage[s].total_value or 0) if s in by_stage else 0,
            "default_probability": STAGE_PROBABILITY.get(s, 0),
        }
        for s in stage_order
    ]


@router.get("/{opp_id}", summary="Get opportunity by ID")
async def get_opportunity(opp_id: int):
    async with get_session() as db:
        opp = await db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    return _fmt(opp)


@router.patch("/{opp_id}", summary="Update opportunity")
async def patch_opportunity(opp_id: int, body: OpportunityPatch):
    async with get_session() as db:
        opp = await db.get(Opportunity, opp_id)
        if not opp:
            raise HTTPException(404, "Opportunity not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(opp, k, v)
        if body.stage == "won" and not opp.won_at:
            opp.won_at = datetime.now(timezone.utc)
            opp.actual_close_date = datetime.now(timezone.utc).date()
            opp.probability_pct = 100
        elif body.stage == "lost" and not opp.lost_at:
            opp.lost_at = datetime.now(timezone.utc)
            opp.actual_close_date = datetime.now(timezone.utc).date()
            opp.probability_pct = 0
        elif body.stage and body.stage not in ("won", "lost"):
            if body.probability_pct is None:
                opp.probability_pct = STAGE_PROBABILITY.get(body.stage, opp.probability_pct)
        opp.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(opp)
    return _fmt(opp)


@router.delete("/{opp_id}", status_code=204)
async def delete_opportunity(opp_id: int):
    async with get_session() as db:
        opp = await db.get(Opportunity, opp_id)
        if not opp:
            raise HTTPException(404, "Opportunity not found")
        await db.delete(opp)
        await db.commit()
