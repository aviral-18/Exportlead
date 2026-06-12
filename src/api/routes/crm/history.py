"""Contact history (interaction log) routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from src.core.database import get_session
from src.crm.models import Contact, ContactHistory, Lead

router = APIRouter(prefix="/history")


class HistoryCreate(BaseModel):
    lead_id: int
    contact_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    interaction_type: str
    direction: str = "outbound"
    subject: Optional[str] = None
    notes: Optional[str] = None
    outcome: Optional[str] = None
    next_action: Optional[str] = None
    duration_minutes: Optional[int] = None
    interacted_by: Optional[str] = None
    interacted_at: Optional[datetime] = None


def _fmt(h: ContactHistory) -> dict:
    return {
        "id": h.id,
        "lead_id": h.lead_id,
        "contact_id": h.contact_id,
        "opportunity_id": h.opportunity_id,
        "interaction_type": h.interaction_type,
        "direction": h.direction,
        "subject": h.subject,
        "notes": h.notes,
        "outcome": h.outcome,
        "next_action": h.next_action,
        "duration_minutes": h.duration_minutes,
        "interacted_by": h.interacted_by,
        "interacted_at": h.interacted_at.isoformat() if h.interacted_at else None,
        "created_at": h.created_at.isoformat(),
    }


@router.get("/", summary="Get interaction history for a lead")
async def list_history(
    lead_id: int = Query(...),
    interaction_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    async with get_session() as db:
        stmt = select(ContactHistory).where(ContactHistory.lead_id == lead_id)
        if interaction_type:
            stmt = stmt.where(ContactHistory.interaction_type == interaction_type)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(ContactHistory.interacted_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
    return {
        "lead_id": lead_id,
        "total": total, "page": page, "page_size": page_size,
        "history": [_fmt(r) for r in rows],
    }


@router.post("/", summary="Log a new interaction", status_code=201)
async def log_interaction(body: HistoryCreate):
    async with get_session() as db:
        data = body.model_dump(exclude_none=True)
        if "interacted_at" not in data:
            data["interacted_at"] = datetime.now(timezone.utc)
        entry = ContactHistory(**data)
        db.add(entry)

        # Update lead last_contact_date + counter
        lead = await db.get(Lead, body.lead_id)
        if lead:
            lead.last_contact_date = entry.interacted_at.date()
            lead.interactions_count = (lead.interactions_count or 0) + 1
            lead.updated_at = datetime.now(timezone.utc)

        # Update contact last_contacted_at
        if body.contact_id:
            contact = await db.get(Contact, body.contact_id)
            if contact:
                contact.last_contacted_at = entry.interacted_at

        await db.commit()
        await db.refresh(entry)
    return _fmt(entry)


@router.get("/summary", summary="Interaction summary stats across all leads")
async def interaction_summary(assigned_to: Optional[str] = Query(None)):
    async with get_session() as db:
        stmt = (
            select(
                ContactHistory.interaction_type,
                func.count(ContactHistory.id).label("count"),
            )
            .group_by(ContactHistory.interaction_type)
            .order_by(func.count(ContactHistory.id).desc())
        )
        type_rows = (await db.execute(stmt)).fetchall()

        stmt2 = (
            select(
                ContactHistory.outcome,
                func.count(ContactHistory.id).label("count"),
            )
            .where(ContactHistory.outcome.is_not(None))
            .group_by(ContactHistory.outcome)
        )
        outcome_rows = (await db.execute(stmt2)).fetchall()

    return {
        "by_type": [{"type": r.interaction_type, "count": r.count} for r in type_rows],
        "by_outcome": [{"outcome": r.outcome, "count": r.count} for r in outcome_rows],
    }


@router.delete("/{history_id}", status_code=204)
async def delete_history(history_id: int):
    async with get_session() as db:
        h = await db.get(ContactHistory, history_id)
        if not h:
            raise HTTPException(404, "History entry not found")
        await db.delete(h)
        await db.commit()
