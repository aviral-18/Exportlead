"""Sample tracking routes."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from src.core.database import get_session
from src.crm.models import Sample, SampleStatus

router = APIRouter(prefix="/samples")


def _next_sample_number() -> str:
    from datetime import date
    return f"SMP-{date.today().strftime('%Y%m')}-{id(object()):06x}"[-16:]


class SampleCreate(BaseModel):
    lead_id: int
    opportunity_id: Optional[int] = None
    products: Optional[dict] = None
    quantity_pieces: Optional[int] = None
    weight_kg: Optional[float] = None
    courier: Optional[str] = None
    tracking_number: Optional[str] = None
    sent_date: Optional[date] = None
    estimated_delivery: Optional[date] = None
    cost_inr: Optional[float] = None
    cost_usd: Optional[float] = None
    paid_by_buyer: bool = False
    notes: Optional[str] = None


class SamplePatch(BaseModel):
    status: Optional[str] = None
    courier: Optional[str] = None
    tracking_number: Optional[str] = None
    sent_date: Optional[date] = None
    estimated_delivery: Optional[date] = None
    delivered_date: Optional[date] = None
    feedback: Optional[str] = None
    feedback_date: Optional[date] = None
    approved_for_bulk: Optional[bool] = None
    cost_inr: Optional[float] = None
    cost_usd: Optional[float] = None
    paid_by_buyer: Optional[bool] = None
    notes: Optional[str] = None


def _fmt(s: Sample) -> dict:
    return {
        "id": s.id,
        "sample_number": s.sample_number,
        "lead_id": s.lead_id,
        "opportunity_id": s.opportunity_id,
        "products": s.products,
        "quantity_pieces": s.quantity_pieces,
        "weight_kg": float(s.weight_kg) if s.weight_kg else None,
        "courier": s.courier,
        "tracking_number": s.tracking_number,
        "sent_date": s.sent_date.isoformat() if s.sent_date else None,
        "estimated_delivery": s.estimated_delivery.isoformat() if s.estimated_delivery else None,
        "delivered_date": s.delivered_date.isoformat() if s.delivered_date else None,
        "status": s.status,
        "cost_inr": float(s.cost_inr) if s.cost_inr else None,
        "cost_usd": float(s.cost_usd) if s.cost_usd else None,
        "paid_by_buyer": s.paid_by_buyer,
        "feedback": s.feedback,
        "feedback_date": s.feedback_date.isoformat() if s.feedback_date else None,
        "approved_for_bulk": s.approved_for_bulk,
        "notes": s.notes,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


@router.get("/", summary="List sample shipments")
async def list_samples(
    lead_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    async with get_session() as db:
        stmt = select(Sample)
        if lead_id is not None:
            stmt = stmt.where(Sample.lead_id == lead_id)
        if status:
            stmt = stmt.where(Sample.status == status)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(Sample.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
    return {"total": total, "page": page, "results": [_fmt(r) for r in rows]}


@router.post("/", summary="Create sample shipment", status_code=201)
async def create_sample(body: SampleCreate):
    import secrets
    async with get_session() as db:
        data = body.model_dump(exclude_none=True)
        data["sample_number"] = f"SMP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        s = Sample(**data)
        db.add(s)
        await db.commit()
        await db.refresh(s)
    return _fmt(s)


@router.get("/{sample_id}", summary="Get sample by ID")
async def get_sample(sample_id: int):
    async with get_session() as db:
        s = await db.get(Sample, sample_id)
    if not s:
        raise HTTPException(404, "Sample not found")
    return _fmt(s)


@router.patch("/{sample_id}", summary="Update sample status / feedback")
async def patch_sample(sample_id: int, body: SamplePatch):
    async with get_session() as db:
        s = await db.get(Sample, sample_id)
        if not s:
            raise HTTPException(404, "Sample not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(s, k, v)
        s.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(s)
    return _fmt(s)


@router.get("/stats/overview", summary="Sample pipeline stats")
async def sample_stats():
    async with get_session() as db:
        stmt = (
            select(Sample.status, func.count(Sample.id).label("count"))
            .group_by(Sample.status)
        )
        rows = (await db.execute(stmt)).fetchall()
        approved = (await db.execute(
            select(func.count(Sample.id)).where(Sample.approved_for_bulk == True)
        )).scalar_one()
        total_cost = (await db.execute(
            select(func.sum(Sample.cost_usd))
        )).scalar_one()
    return {
        "by_status": [{"status": r.status, "count": r.count} for r in rows],
        "approved_for_bulk": approved,
        "total_cost_usd": float(total_cost or 0),
    }
