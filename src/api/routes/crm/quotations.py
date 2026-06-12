"""Quotation tracking routes."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from src.core.database import get_session
from src.crm.models import Quotation, QuotationStatus

router = APIRouter(prefix="/quotations")


class QuotationCreate(BaseModel):
    lead_id: int
    opportunity_id: Optional[int] = None
    line_items: Optional[dict] = None
    currency: str = "USD"
    total_value: Optional[float] = None
    incoterms: Optional[str] = "FOB"
    payment_terms: Optional[str] = "30% advance, 70% before shipment"
    validity_days: int = 30
    delivery_weeks: Optional[int] = None
    port_of_loading: Optional[str] = "Nhava Sheva, India"
    port_of_discharge: Optional[str] = None
    packing_details: Optional[str] = None
    special_terms: Optional[str] = None
    profitability: Optional[dict] = None


class QuotationPatch(BaseModel):
    line_items: Optional[dict] = None
    total_value: Optional[float] = None
    status: Optional[str] = None
    incoterms: Optional[str] = None
    payment_terms: Optional[str] = None
    validity_days: Optional[int] = None
    delivery_weeks: Optional[int] = None
    rejection_reason: Optional[str] = None
    profitability: Optional[dict] = None


def _fmt(q: Quotation) -> dict:
    return {
        "id": q.id,
        "quotation_number": q.quotation_number,
        "lead_id": q.lead_id,
        "opportunity_id": q.opportunity_id,
        "line_items": q.line_items,
        "currency": q.currency,
        "total_value": float(q.total_value) if q.total_value else None,
        "incoterms": q.incoterms,
        "payment_terms": q.payment_terms,
        "validity_days": q.validity_days,
        "delivery_weeks": q.delivery_weeks,
        "port_of_loading": q.port_of_loading,
        "port_of_discharge": q.port_of_discharge,
        "packing_details": q.packing_details,
        "special_terms": q.special_terms,
        "status": q.status,
        "sent_at": q.sent_at.isoformat() if q.sent_at else None,
        "valid_until": q.valid_until.isoformat() if q.valid_until else None,
        "accepted_at": q.accepted_at.isoformat() if q.accepted_at else None,
        "rejected_at": q.rejected_at.isoformat() if q.rejected_at else None,
        "rejection_reason": q.rejection_reason,
        "profitability": q.profitability,
        "created_at": q.created_at.isoformat(),
        "updated_at": q.updated_at.isoformat(),
    }


@router.get("/", summary="List quotations")
async def list_quotations(
    lead_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    async with get_session() as db:
        stmt = select(Quotation)
        if lead_id is not None:
            stmt = stmt.where(Quotation.lead_id == lead_id)
        if status:
            stmt = stmt.where(Quotation.status == status)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(Quotation.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
    return {"total": total, "page": page, "results": [_fmt(r) for r in rows]}


@router.post("/", summary="Create a quotation", status_code=201)
async def create_quotation(body: QuotationCreate):
    import secrets
    async with get_session() as db:
        data = body.model_dump(exclude_none=True)
        data["quotation_number"] = f"QT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        q = Quotation(**data)
        db.add(q)
        await db.commit()
        await db.refresh(q)
    return _fmt(q)


@router.get("/{quot_id}", summary="Get quotation by ID")
async def get_quotation(quot_id: int):
    async with get_session() as db:
        q = await db.get(Quotation, quot_id)
    if not q:
        raise HTTPException(404, "Quotation not found")
    return _fmt(q)


@router.patch("/{quot_id}", summary="Update quotation")
async def patch_quotation(quot_id: int, body: QuotationPatch):
    async with get_session() as db:
        q = await db.get(Quotation, quot_id)
        if not q:
            raise HTTPException(404, "Quotation not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(q, k, v)
        if body.status == "accepted" and not q.accepted_at:
            q.accepted_at = datetime.now(timezone.utc)
        elif body.status == "rejected" and not q.rejected_at:
            q.rejected_at = datetime.now(timezone.utc)
        q.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(q)
    return _fmt(q)


@router.post("/{quot_id}/send", summary="Mark quotation as sent")
async def send_quotation(quot_id: int):
    async with get_session() as db:
        q = await db.get(Quotation, quot_id)
        if not q:
            raise HTTPException(404, "Quotation not found")
        q.status = QuotationStatus.SENT
        q.sent_at = datetime.now(timezone.utc)
        q.valid_until = (datetime.now(timezone.utc) + timedelta(days=q.validity_days)).date()
        q.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(q)
    return _fmt(q)


@router.get("/stats/overview", summary="Quotation conversion stats")
async def quotation_stats():
    async with get_session() as db:
        stmt = (
            select(Quotation.status, func.count(Quotation.id).label("count"),
                   func.sum(Quotation.total_value).label("total_value"))
            .group_by(Quotation.status)
        )
        rows = (await db.execute(stmt)).fetchall()
        total_sent = sum(r.count for r in rows if r.status not in ("draft",))
        total_accepted = sum(r.count for r in rows if r.status == "accepted")
    return {
        "conversion_rate_pct": round(total_accepted / total_sent * 100, 1) if total_sent else 0,
        "by_status": [
            {"status": r.status, "count": r.count, "total_value_usd": float(r.total_value or 0)}
            for r in rows
        ],
    }
