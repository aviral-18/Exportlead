"""Follow-up scheduling routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select

from src.core.database import get_session
from src.crm.models import FollowUp, Lead

router = APIRouter(prefix="/followups")


class FollowUpCreate(BaseModel):
    lead_id: int
    title: str
    description: Optional[str] = None
    follow_up_type: str = "follow_up"
    priority: str = "medium"
    assigned_to: Optional[str] = None
    scheduled_at: datetime
    opportunity_id: Optional[int] = None
    contact_id: Optional[int] = None


class FollowUpPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    follow_up_type: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    is_completed: Optional[bool] = None
    outcome_notes: Optional[str] = None


def _fmt(f: FollowUp) -> dict:
    return {
        "id": f.id, "lead_id": f.lead_id,
        "opportunity_id": f.opportunity_id, "contact_id": f.contact_id,
        "title": f.title, "description": f.description,
        "follow_up_type": f.follow_up_type, "priority": f.priority,
        "assigned_to": f.assigned_to,
        "scheduled_at": f.scheduled_at.isoformat(),
        "completed_at": f.completed_at.isoformat() if f.completed_at else None,
        "is_completed": f.is_completed,
        "outcome_notes": f.outcome_notes,
        "created_at": f.created_at.isoformat(),
        "updated_at": f.updated_at.isoformat(),
    }


@router.get("/", summary="List follow-ups with filters")
async def list_followups(
    lead_id: Optional[int] = Query(None),
    assigned_to: Optional[str] = Query(None),
    is_completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    overdue_only: bool = Query(False, description="Only overdue (past scheduled_at and not completed)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    async with get_session() as db:
        stmt = select(FollowUp)
        if lead_id is not None:
            stmt = stmt.where(FollowUp.lead_id == lead_id)
        if assigned_to:
            stmt = stmt.where(FollowUp.assigned_to == assigned_to)
        if is_completed is not None:
            stmt = stmt.where(FollowUp.is_completed == is_completed)
        if priority:
            stmt = stmt.where(FollowUp.priority == priority)
        if overdue_only:
            now = datetime.now(timezone.utc)
            stmt = stmt.where(
                and_(FollowUp.scheduled_at < now, FollowUp.is_completed == False)
            )
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(FollowUp.scheduled_at.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "results": [_fmt(r) for r in rows],
    }


@router.post("/", summary="Schedule a follow-up", status_code=201)
async def create_followup(body: FollowUpCreate):
    async with get_session() as db:
        fu = FollowUp(**body.model_dump(exclude_none=True))
        db.add(fu)
        # Increment open follow-ups counter on lead
        lead = await db.get(Lead, body.lead_id)
        if lead:
            lead.open_followups = (lead.open_followups or 0) + 1
        await db.commit()
        await db.refresh(fu)
    return _fmt(fu)


@router.patch("/{followup_id}", summary="Update follow-up")
async def patch_followup(followup_id: int, body: FollowUpPatch):
    async with get_session() as db:
        fu = await db.get(FollowUp, followup_id)
        if not fu:
            raise HTTPException(404, "Follow-up not found")
        was_open = not fu.is_completed
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(fu, k, v)
        if body.is_completed and was_open:
            fu.completed_at = datetime.now(timezone.utc)
            # Decrement open follow-ups counter
            lead = await db.get(Lead, fu.lead_id)
            if lead and lead.open_followups:
                lead.open_followups = max(0, lead.open_followups - 1)
        fu.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(fu)
    return _fmt(fu)


@router.post("/{followup_id}/complete", summary="Mark follow-up as completed")
async def complete_followup(followup_id: int, outcome_notes: Optional[str] = None):
    async with get_session() as db:
        fu = await db.get(FollowUp, followup_id)
        if not fu:
            raise HTTPException(404, "Follow-up not found")
        if not fu.is_completed:
            fu.is_completed = True
            fu.completed_at = datetime.now(timezone.utc)
            if outcome_notes:
                fu.outcome_notes = outcome_notes
            lead = await db.get(Lead, fu.lead_id)
            if lead and lead.open_followups:
                lead.open_followups = max(0, lead.open_followups - 1)
            fu.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(fu)
    return _fmt(fu)


@router.delete("/{followup_id}", status_code=204)
async def delete_followup(followup_id: int):
    async with get_session() as db:
        fu = await db.get(FollowUp, followup_id)
        if not fu:
            raise HTTPException(404, "Follow-up not found")
        await db.delete(fu)
        await db.commit()
