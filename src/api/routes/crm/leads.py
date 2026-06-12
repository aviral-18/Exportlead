"""Lead management routes."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from src.core.database import get_session
from src.crm.models import Lead, LeadPriority, LeadSource, LeadStatus

router = APIRouter(prefix="/leads")


# ── Schemas ───────────────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    company_name: str
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    canonical_buyer_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_linkedin: Optional[str] = None
    contact_whatsapp: Optional[str] = None
    status: str = "new"
    source: str = "database"
    priority: str = "warm"
    assigned_to: Optional[str] = None
    product_interest: Optional[dict] = None
    estimated_value_usd: Optional[float] = None
    currency: str = "USD"
    expected_close_date: Optional[date] = None
    tags: Optional[dict] = None


class LeadPatch(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_whatsapp: Optional[str] = None
    estimated_value_usd: Optional[float] = None
    expected_close_date: Optional[date] = None
    last_contact_date: Optional[date] = None
    product_interest: Optional[dict] = None
    tags: Optional[dict] = None


def _fmt(l: Lead) -> dict:
    return {
        "id": l.id, "uuid": l.uuid,
        "company_name": l.company_name,
        "country_code": l.country_code, "country_name": l.country_name,
        "canonical_buyer_id": l.canonical_buyer_id,
        "contact_name": l.contact_name, "contact_title": l.contact_title,
        "contact_email": l.contact_email, "contact_phone": l.contact_phone,
        "contact_linkedin": l.contact_linkedin, "contact_whatsapp": l.contact_whatsapp,
        "status": l.status, "source": l.source, "priority": l.priority,
        "assigned_to": l.assigned_to,
        "product_interest": l.product_interest,
        "estimated_value_usd": float(l.estimated_value_usd) if l.estimated_value_usd else None,
        "currency": l.currency,
        "last_contact_date": l.last_contact_date.isoformat() if l.last_contact_date else None,
        "expected_close_date": l.expected_close_date.isoformat() if l.expected_close_date else None,
        "notes_count": l.notes_count,
        "interactions_count": l.interactions_count,
        "open_followups": l.open_followups,
        "tags": l.tags,
        "created_at": l.created_at.isoformat(),
        "updated_at": l.updated_at.isoformat(),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", summary="List leads with filters")
async def list_leads(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc"),
):
    async with get_session() as db:
        stmt = select(Lead)
        if status:
            stmt = stmt.where(Lead.status == status)
        if priority:
            stmt = stmt.where(Lead.priority == priority)
        if assigned_to:
            stmt = stmt.where(Lead.assigned_to == assigned_to)
        if country_code:
            stmt = stmt.where(Lead.country_code == country_code.upper())
        if source:
            stmt = stmt.where(Lead.source == source)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        col = getattr(Lead, sort_by, Lead.updated_at)
        stmt = stmt.order_by(col.desc() if sort_order == "desc" else col.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "results": [_fmt(r) for r in rows],
    }


@router.post("/", summary="Create a new lead", status_code=201)
async def create_lead(body: LeadCreate):
    async with get_session() as db:
        lead = Lead(**body.model_dump(exclude_none=True))
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
    return _fmt(lead)


@router.get("/pipeline", summary="Pipeline summary by stage and total value")
async def pipeline_summary():
    async with get_session() as db:
        stmt = (
            select(
                Lead.status,
                func.count(Lead.id).label("count"),
                func.sum(Lead.estimated_value_usd).label("total_value"),
                func.avg(Lead.estimated_value_usd).label("avg_value"),
            )
            .group_by(Lead.status)
            .order_by(func.count(Lead.id).desc())
        )
        rows = (await db.execute(stmt)).fetchall()
        total_pipeline = (await db.execute(
            select(func.sum(Lead.estimated_value_usd)).where(
                Lead.status.in_(["qualified", "proposal", "negotiation"])
            )
        )).scalar_one()
    return {
        "pipeline_value_usd": float(total_pipeline or 0),
        "by_status": [
            {
                "status": r.status, "count": r.count,
                "total_value_usd": float(r.total_value or 0),
                "avg_value_usd": float(r.avg_value or 0),
            }
            for r in rows
        ],
    }


@router.get("/{lead_id}", summary="Get lead by ID")
async def get_lead(lead_id: int):
    async with get_session() as db:
        lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return _fmt(lead)


@router.patch("/{lead_id}", summary="Update lead fields")
async def patch_lead(lead_id: int, body: LeadPatch):
    async with get_session() as db:
        lead = await db.get(Lead, lead_id)
        if not lead:
            raise HTTPException(404, "Lead not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(lead, k, v)
        lead.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(lead)
    return _fmt(lead)


@router.delete("/{lead_id}", summary="Delete a lead", status_code=204)
async def delete_lead(lead_id: int):
    async with get_session() as db:
        lead = await db.get(Lead, lead_id)
        if not lead:
            raise HTTPException(404, "Lead not found")
        await db.delete(lead)
        await db.commit()


@router.post("/{lead_id}/convert", summary="Convert lead from canonical buyer")
async def convert_from_buyer(lead_id: int):
    """Link this lead to its canonical buyer's AI lead score."""
    from src.core.models import CanonicalBuyer, LeadScore
    async with get_session() as db:
        lead = await db.get(Lead, lead_id)
        if not lead:
            raise HTTPException(404, "Lead not found")
        if not lead.canonical_buyer_id:
            raise HTTPException(400, "Lead has no canonical_buyer_id set")
        ls = (await db.execute(
            select(LeadScore).where(LeadScore.canonical_id == lead.canonical_buyer_id)
        )).scalar_one_or_none()
    return {
        "lead_id": lead_id,
        "canonical_buyer_id": lead.canonical_buyer_id,
        "ai_score": {
            "composite": float(ls.composite_score) if ls else None,
            "tier": ls.tier if ls else None,
            "product_fit": float(ls.product_fit_score) if ls else None,
            "india_import_probability": float(ls.india_import_probability) if ls else None,
        } if ls else None,
    }
