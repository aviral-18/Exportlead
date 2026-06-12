"""Notes routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from src.core.database import get_session
from src.crm.models import Lead, Note

router = APIRouter(prefix="/notes")


class NoteCreate(BaseModel):
    lead_id: int
    content: str
    note_type: str = "general"
    opportunity_id: Optional[int] = None
    contact_id: Optional[int] = None
    created_by: Optional[str] = None
    is_pinned: bool = False


class NotePatch(BaseModel):
    content: Optional[str] = None
    note_type: Optional[str] = None
    is_pinned: Optional[bool] = None


def _fmt(n: Note) -> dict:
    return {
        "id": n.id, "lead_id": n.lead_id,
        "opportunity_id": n.opportunity_id, "contact_id": n.contact_id,
        "content": n.content, "note_type": n.note_type,
        "created_by": n.created_by, "is_pinned": n.is_pinned,
        "created_at": n.created_at.isoformat(),
        "updated_at": n.updated_at.isoformat(),
    }


@router.get("/", summary="Get notes for a lead")
async def list_notes(
    lead_id: int = Query(...),
    pinned_only: bool = Query(False),
    note_type: Optional[str] = Query(None),
):
    async with get_session() as db:
        stmt = select(Note).where(Note.lead_id == lead_id)
        if pinned_only:
            stmt = stmt.where(Note.is_pinned == True)
        if note_type:
            stmt = stmt.where(Note.note_type == note_type)
        stmt = stmt.order_by(Note.is_pinned.desc(), Note.created_at.desc())
        rows = (await db.execute(stmt)).scalars().all()
    return {"lead_id": lead_id, "count": len(rows), "notes": [_fmt(r) for r in rows]}


@router.post("/", summary="Create a note", status_code=201)
async def create_note(body: NoteCreate):
    async with get_session() as db:
        note = Note(**body.model_dump(exclude_none=True))
        db.add(note)
        # Update denormalized counter on lead
        lead = await db.get(Lead, body.lead_id)
        if lead:
            lead.notes_count = (lead.notes_count or 0) + 1
        await db.commit()
        await db.refresh(note)
    return _fmt(note)


@router.patch("/{note_id}", summary="Update a note")
async def patch_note(note_id: int, body: NotePatch):
    async with get_session() as db:
        note = await db.get(Note, note_id)
        if not note:
            raise HTTPException(404, "Note not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(note, k, v)
        note.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(note)
    return _fmt(note)


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: int):
    async with get_session() as db:
        note = await db.get(Note, note_id)
        if not note:
            raise HTTPException(404, "Note not found")
        # Decrement counter
        lead = await db.get(Lead, note.lead_id)
        if lead and lead.notes_count:
            lead.notes_count = max(0, lead.notes_count - 1)
        await db.delete(note)
        await db.commit()
