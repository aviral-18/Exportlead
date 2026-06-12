"""
Outreach API routes.

GET  /api/v1/outreach/campaigns              — list campaigns
POST /api/v1/outreach/campaigns              — create campaign
GET  /api/v1/outreach/campaigns/{id}         — campaign detail + stats
PATCH /api/v1/outreach/campaigns/{id}        — update campaign
POST /api/v1/outreach/campaigns/{id}/launch  — activate campaign + queue emails

GET  /api/v1/outreach/emails                 — list emails with filters
POST /api/v1/outreach/generate               — generate email for a buyer (preview)
POST /api/v1/outreach/emails/{id}/send       — mark email as sent
POST /api/v1/outreach/emails/{id}/open       — webhook: email opened
POST /api/v1/outreach/emails/{id}/click      — webhook: email link clicked

POST /api/v1/outreach/replies/ingest         — ingest inbound reply
GET  /api/v1/outreach/replies                — list classified replies
GET  /api/v1/outreach/stats/overview         — global outreach KPIs
GET  /api/v1/outreach/templates              — list available templates
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from src.core.database import get_session
from src.core.models import CanonicalBuyer
from src.outreach.generator import AVAILABLE_TEMPLATES, generate
from src.outreach.models import EmailReply, OutreachCampaign, OutreachEmail
from src.outreach.tracker import process_inbound_reply

router = APIRouter(prefix="/outreach", tags=["outreach"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    campaign_type: str = "cold_outreach"
    target_country: Optional[str] = None
    target_buyer_type: Optional[str] = None
    target_tier: Optional[str] = None
    min_score: Optional[float] = None
    template_name: Optional[str] = None
    language: str = "en"
    created_by: Optional[str] = None


class GenerateEmailRequest(BaseModel):
    canonical_id: int
    template_name: str = "initial_introduction"
    language: str = "en"
    sender_name: Optional[str] = None
    sender_title: Optional[str] = None
    sender_company: Optional[str] = None
    custom_vars: Optional[dict] = None


class IngestReplyRequest(BaseModel):
    from_email: str
    from_name: Optional[str] = None
    subject: Optional[str] = None
    body_text: str
    outreach_email_id: Optional[int] = None
    received_at: Optional[datetime] = None


# ── Helpers ───────────────────────────────────────────────────────────────────
def _out_campaign(c: OutreachCampaign) -> dict:
    return {
        "id": c.id, "name": c.name, "description": c.description,
        "campaign_type": c.campaign_type, "status": c.status,
        "target_country": c.target_country, "target_buyer_type": c.target_buyer_type,
        "template_name": c.template_name, "language": c.language,
        "emails_sent": c.emails_sent, "emails_opened": c.emails_opened,
        "replies_received": c.replies_received, "positive_replies": c.positive_replies,
        "crm_leads_created": c.crm_leads_created,
        "open_rate": float(c.open_rate or 0), "reply_rate": float(c.reply_rate or 0),
        "conversion_rate": float(c.conversion_rate or 0),
        "start_date": c.start_date, "end_date": c.end_date,
        "created_by": c.created_by,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _out_email(e: OutreachEmail) -> dict:
    return {
        "id": e.id, "campaign_id": e.campaign_id, "lead_id": e.lead_id,
        "canonical_id": e.canonical_id,
        "to_email": e.to_email, "to_name": e.to_name, "to_company": e.to_company,
        "to_country": e.to_country, "subject": e.subject,
        "template_name": e.template_name, "language": e.language,
        "status": e.status, "open_count": e.open_count, "click_count": e.click_count,
        "reply_received": e.reply_received,
        "sent_at": e.sent_at.isoformat() if e.sent_at else None,
        "opened_at": e.opened_at.isoformat() if e.opened_at else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _out_reply(r: EmailReply) -> dict:
    return {
        "id": r.id, "outreach_email_id": r.outreach_email_id, "lead_id": r.lead_id,
        "from_email": r.from_email, "from_name": r.from_name, "subject": r.subject,
        "sentiment": r.sentiment, "intent": r.intent,
        "confidence_score": float(r.confidence_score or 0),
        "signals": json.loads(r.extracted_signals_json or "{}"),
        "is_processed": r.is_processed, "auto_response_sent": r.auto_response_sent,
        "received_at": r.received_at.isoformat() if r.received_at else None,
        "notes": r.notes,
    }


# ── Campaign endpoints ────────────────────────────────────────────────────────
@router.get("/campaigns", summary="List all outreach campaigns")
async def list_campaigns(status: Optional[str] = Query(None), page: int = Query(1), page_size: int = Query(50)):
    async with get_session() as session:
        stmt = select(OutreachCampaign)
        if status:
            stmt = stmt.where(OutreachCampaign.status == status)
        total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await session.execute(stmt.order_by(OutreachCampaign.created_at.desc())
                                      .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"total": total, "campaigns": [_out_campaign(c) for c in rows]}


@router.post("/campaigns", status_code=201, summary="Create a new outreach campaign")
async def create_campaign(body: CampaignCreate):
    async with get_session() as session:
        c = OutreachCampaign(**body.model_dump(exclude_none=True))
        session.add(c)
        await session.commit()
        await session.refresh(c)
    return _out_campaign(c)


@router.get("/campaigns/{campaign_id}", summary="Campaign detail with stats")
async def get_campaign(campaign_id: int):
    async with get_session() as session:
        c = await session.get(OutreachCampaign, campaign_id)
        if not c:
            raise HTTPException(404, "Campaign not found")
        email_count = (await session.execute(
            select(func.count(OutreachEmail.id)).where(OutreachEmail.campaign_id == campaign_id)
        )).scalar_one()
    result = _out_campaign(c)
    result["total_emails"] = email_count
    return result


@router.patch("/campaigns/{campaign_id}", summary="Update campaign")
async def update_campaign(campaign_id: int, body: dict):
    async with get_session() as session:
        c = await session.get(OutreachCampaign, campaign_id)
        if not c:
            raise HTTPException(404, "Campaign not found")
        for k, v in body.items():
            if hasattr(OutreachCampaign, k) and k not in ("id", "created_at"):
                setattr(c, k, v)
        await session.commit()
        await session.refresh(c)
    return _out_campaign(c)


@router.post("/campaigns/{campaign_id}/launch", summary="Activate campaign and queue outreach emails")
async def launch_campaign(campaign_id: int, limit: int = Query(100, le=1000)):
    async with get_session() as session:
        campaign = await session.get(OutreachCampaign, campaign_id)
        if not campaign:
            raise HTTPException(404, "Campaign not found")
        if campaign.status not in ("draft", "paused"):
            raise HTTPException(400, f"Campaign is '{campaign.status}' — only draft/paused campaigns can be launched")

        # Find buyers matching campaign criteria
        stmt = select(CanonicalBuyer).where(CanonicalBuyer.is_active == True)
        if campaign.target_country:
            stmt = stmt.where(CanonicalBuyer.country_code == campaign.target_country.upper())
        if campaign.target_buyer_type:
            stmt = stmt.where(CanonicalBuyer.buyer_type == campaign.target_buyer_type)
        buyers = (await session.execute(stmt.limit(limit))).scalars().all()

        queued = 0
        for buyer in buyers:
            emails = json.loads(buyer.email_json or "[]")
            if not emails:
                continue
            template = campaign.template_name or "initial_introduction"
            email_gen = generate(template, buyer, language=campaign.language or "en")
            email = OutreachEmail(
                campaign_id=campaign_id,
                canonical_id=buyer.id,
                to_email=emails[0],
                to_name=buyer.company_name,
                to_company=buyer.company_name,
                to_country=buyer.country_code,
                subject=email_gen.subject,
                body_text=email_gen.body_text,
                body_html=email_gen.body_html,
                template_name=template,
                language=campaign.language or "en",
                personalization_json=json.dumps(email_gen.personalization),
                status="queued",
            )
            session.add(email)
            queued += 1

        campaign.status = "active"
        campaign.start_date = datetime.now(tz=timezone.utc).date().isoformat()
        await session.commit()

    return {"campaign_id": campaign_id, "status": "active", "emails_queued": queued}


# ── Email endpoints ───────────────────────────────────────────────────────────
@router.get("/emails", summary="List outreach emails")
async def list_emails(
    campaign_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    reply_received: Optional[bool] = Query(None),
    page: int = Query(1), page_size: int = Query(50),
):
    async with get_session() as session:
        stmt = select(OutreachEmail)
        if campaign_id:
            stmt = stmt.where(OutreachEmail.campaign_id == campaign_id)
        if status:
            stmt = stmt.where(OutreachEmail.status == status)
        if reply_received is not None:
            stmt = stmt.where(OutreachEmail.reply_received == reply_received)
        total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await session.execute(
            stmt.order_by(OutreachEmail.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
    return {"total": total, "page": page, "emails": [_out_email(e) for e in rows]}


@router.post("/generate", summary="Generate a personalised email for preview — does not send")
async def generate_email(body: GenerateEmailRequest):
    async with get_session() as session:
        buyer = await session.get(CanonicalBuyer, body.canonical_id)
        if not buyer:
            raise HTTPException(404, "Buyer not found")
    sender_override = {}
    if body.sender_name:
        sender_override["name"] = body.sender_name
    if body.sender_title:
        sender_override["title"] = body.sender_title
    if body.sender_company:
        sender_override["company"] = body.sender_company

    result = generate(
        template_name=body.template_name,
        buyer=buyer,
        sender=sender_override or None,
        language=body.language,
        custom_vars=body.custom_vars,
    )
    return {
        "canonical_id": body.canonical_id,
        "template_name": body.template_name,
        "subject": result.subject,
        "body_text": result.body_text,
        "body_html": result.body_html,
        "personalization": result.personalization,
    }


@router.post("/emails/{email_id}/send", summary="Mark email as sent (integrate with your ESP)")
async def mark_sent(email_id: int, message_id: Optional[str] = None):
    async with get_session() as session:
        email = await session.get(OutreachEmail, email_id)
        if not email:
            raise HTTPException(404, "Email not found")
        email.status = "sent"
        email.sent_at = datetime.now(tz=timezone.utc)
        if message_id:
            email.message_id = message_id
        # Update campaign counter
        if email.campaign_id:
            campaign = await session.get(OutreachCampaign, email.campaign_id)
            if campaign:
                campaign.emails_sent = (campaign.emails_sent or 0) + 1
        await session.commit()
    return {"email_id": email_id, "status": "sent"}


@router.post("/emails/{email_id}/open", summary="Webhook: email opened tracking pixel hit")
async def track_open(email_id: int):
    async with get_session() as session:
        email = await session.get(OutreachEmail, email_id)
        if not email:
            raise HTTPException(404)
        email.open_count = (email.open_count or 0) + 1
        if not email.opened_at:
            email.opened_at = datetime.now(tz=timezone.utc)
            email.status = "opened"
            if email.campaign_id:
                campaign = await session.get(OutreachCampaign, email.campaign_id)
                if campaign and campaign.emails_sent:
                    campaign.emails_opened = (campaign.emails_opened or 0) + 1
                    campaign.open_rate = round(campaign.emails_opened / campaign.emails_sent * 100, 2)
        await session.commit()
    return {"ok": True}


@router.post("/emails/{email_id}/click", summary="Webhook: email link clicked")
async def track_click(email_id: int):
    async with get_session() as session:
        email = await session.get(OutreachEmail, email_id)
        if not email:
            raise HTTPException(404)
        email.click_count = (email.click_count or 0) + 1
        if not email.clicked_at:
            email.clicked_at = datetime.now(tz=timezone.utc)
            email.status = "clicked"
            if email.campaign_id:
                campaign = await session.get(OutreachCampaign, email.campaign_id)
                if campaign and campaign.emails_sent:
                    campaign.emails_clicked = (campaign.emails_clicked or 0) + 1
        await session.commit()
    return {"ok": True}


# ── Reply endpoints ───────────────────────────────────────────────────────────
@router.post("/replies/ingest", status_code=201, summary="Ingest and classify an inbound email reply")
async def ingest_reply(body: IngestReplyRequest):
    result = await process_inbound_reply(
        from_email=body.from_email,
        subject=body.subject or "",
        body_text=body.body_text,
        received_at=body.received_at,
        outreach_email_id=body.outreach_email_id,
        from_name=body.from_name,
    )
    return result


@router.get("/replies", summary="List classified inbound replies")
async def list_replies(
    sentiment: Optional[str] = Query(None),
    intent: Optional[str] = Query(None),
    campaign_id: Optional[int] = Query(None),
    is_processed: Optional[bool] = Query(None),
    page: int = Query(1), page_size: int = Query(50),
):
    async with get_session() as session:
        stmt = select(EmailReply)
        if sentiment:
            stmt = stmt.where(EmailReply.sentiment == sentiment)
        if intent:
            stmt = stmt.where(EmailReply.intent == intent)
        if campaign_id:
            stmt = stmt.where(EmailReply.campaign_id == campaign_id)
        if is_processed is not None:
            stmt = stmt.where(EmailReply.is_processed == is_processed)
        total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await session.execute(
            stmt.order_by(EmailReply.received_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
    return {"total": total, "replies": [_out_reply(r) for r in rows]}


# ── Global stats ──────────────────────────────────────────────────────────────
@router.get("/stats/overview", summary="Global outreach KPIs")
async def outreach_stats():
    async with get_session() as session:
        campaigns_total = (await session.execute(select(func.count(OutreachCampaign.id)))).scalar_one()
        active_campaigns = (await session.execute(
            select(func.count(OutreachCampaign.id)).where(OutreachCampaign.status == "active")
        )).scalar_one()
        emails_sent = (await session.execute(select(func.sum(OutreachCampaign.emails_sent)))).scalar_one() or 0
        emails_opened = (await session.execute(select(func.sum(OutreachCampaign.emails_opened)))).scalar_one() or 0
        total_replies = (await session.execute(select(func.count(EmailReply.id)))).scalar_one()
        positive = (await session.execute(
            select(func.count(EmailReply.id)).where(EmailReply.sentiment == "positive")
        )).scalar_one()
        by_intent = (await session.execute(
            select(EmailReply.intent, func.count(EmailReply.id).label("count"))
            .group_by(EmailReply.intent).order_by(func.count(EmailReply.id).desc())
        )).fetchall()
    return {
        "campaigns": {"total": campaigns_total, "active": active_campaigns},
        "emails": {
            "sent": int(emails_sent),
            "opened": int(emails_opened),
            "open_rate_pct": round(emails_opened / max(1, emails_sent) * 100, 2),
        },
        "replies": {
            "total": total_replies,
            "positive": positive,
            "positive_rate_pct": round(positive / max(1, total_replies) * 100, 2),
            "by_intent": [{"intent": r.intent, "count": r.count} for r in by_intent],
        },
    }


@router.get("/templates", summary="List available email templates")
async def list_templates():
    descriptions = {
        "initial_introduction": "First cold outreach to a buyer who has never engaged",
        "warm_followup": "Follow-up 10–14 days after no reply to initial introduction",
        "trade_fair": "Pre/post trade fair outreach tied to IHGF, Ambiente, NY Now, etc.",
        "sample_offer": "Offer complimentary samples to accelerate evaluation",
        "quote_followup": "Chase a sent quotation to close the deal",
        "emerging_importer": "Targeted approach for buyers who recently started importing",
        "re_engagement": "Reconnect with a lead that has gone cold (60+ days)",
    }
    return [{"name": t, "description": descriptions.get(t, "")} for t in AVAILABLE_TEMPLATES]
