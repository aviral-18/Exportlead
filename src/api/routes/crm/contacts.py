"""Contact management routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from src.core.database import get_session
from src.crm.models import Contact

router = APIRouter(prefix="/contacts")


class ContactCreate(BaseModel):
    lead_id: int
    name: str
    title: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_primary: bool = False
    preferred_contact_method: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    notes: Optional[str] = None


class ContactPatch(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    is_primary: Optional[bool] = None
    preferred_contact_method: Optional[str] = None
    do_not_contact: Optional[bool] = None
    notes: Optional[str] = None


def _fmt(c: Contact) -> dict:
    return {
        "id": c.id, "lead_id": c.lead_id,
        "name": c.name, "title": c.title, "department": c.department,
        "email": c.email, "phone": c.phone, "whatsapp": c.whatsapp,
        "linkedin_url": c.linkedin_url,
        "is_primary": c.is_primary,
        "preferred_contact_method": c.preferred_contact_method,
        "language": c.language, "timezone": c.timezone,
        "do_not_contact": c.do_not_contact,
        "last_contacted_at": c.last_contacted_at.isoformat() if c.last_contacted_at else None,
        "notes": c.notes,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


@router.get("/", summary="List contacts for a lead")
async def list_contacts(
    lead_id: int = Query(..., description="Filter by lead ID"),
    include_dnc: bool = Query(False, description="Include do-not-contact"),
):
    async with get_session() as db:
        stmt = select(Contact).where(Contact.lead_id == lead_id)
        if not include_dnc:
            stmt = stmt.where(Contact.do_not_contact == False)
        stmt = stmt.order_by(Contact.is_primary.desc(), Contact.name)
        rows = (await db.execute(stmt)).scalars().all()
    return {"lead_id": lead_id, "count": len(rows), "contacts": [_fmt(r) for r in rows]}


@router.post("/", summary="Add a contact to a lead", status_code=201)
async def create_contact(body: ContactCreate):
    async with get_session() as db:
        contact = Contact(**body.model_dump(exclude_none=True))
        db.add(contact)
        await db.commit()
        await db.refresh(contact)
    return _fmt(contact)


@router.get("/{contact_id}", summary="Get contact by ID")
async def get_contact(contact_id: int):
    async with get_session() as db:
        c = await db.get(Contact, contact_id)
    if not c:
        raise HTTPException(404, "Contact not found")
    return _fmt(c)


@router.patch("/{contact_id}", summary="Update contact")
async def patch_contact(contact_id: int, body: ContactPatch):
    async with get_session() as db:
        c = await db.get(Contact, contact_id)
        if not c:
            raise HTTPException(404, "Contact not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(c, k, v)
        c.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(c)
    return _fmt(c)


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(contact_id: int):
    async with get_session() as db:
        c = await db.get(Contact, contact_id)
        if not c:
            raise HTTPException(404, "Contact not found")
        await db.delete(c)
        await db.commit()
