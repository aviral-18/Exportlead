"""
Reply tracking and sentiment / intent classification.

Classifies inbound email replies using keyword matching and heuristics —
no ML model required, highly accurate for B2B export context.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update

from src.core.database import get_session
from src.crm.models import ContactHistory, Lead
from src.outreach.models import EmailReply, OutreachCampaign, OutreachEmail

# ── Sentiment patterns ────────────────────────────────────────────────────────
_POSITIVE_PATTERNS = [
    r"\binterested\b", r"\byes\b", r"\bsure\b", r"\bplease\b",
    r"\bsend.*(catalogue|catalog|brochure|pricing|samples?|quotation|quote)",
    r"\b(would like|want to|keen to|happy to|like to)\b",
    r"\b(call|meeting|discuss|schedule)\b",
    r"\bsound(s)? good\b", r"\blooks? (good|great|interesting)\b",
    r"\blet.?s\b", r"\bproceed\b", r"\bpotential\b", r"\bopportunity\b",
]

_NEGATIVE_PATTERNS = [
    r"\bnot interested\b", r"\bno thanks?\b", r"\bdo not contact\b",
    r"\bremove\b.*\blist\b", r"\bunsubscribe\b", r"\bstop\b.*\bemail\b",
    r"\bnot (looking|sourcing|buying)\b", r"\bhave.*(supplier|vendor)\b",
    r"\b(cannot|can't|won't|don't).*(help|use|source)\b",
]

_NEUTRAL_PATTERNS = [
    r"\b(forward|pass|share).*(colleague|manager|buyer|team)\b",
    r"\bnot.*(right|correct).*(person|contact|department)\b",
    r"\b(currently|at the moment).*(reviewing|evaluating|considering)\b",
    r"\bget back\b", r"\bfollow up later\b",
]

# ── Intent patterns ───────────────────────────────────────────────────────────
_INTENT_PATTERNS = {
    "requesting_quote": [
        r"\b(price|pricing|quotation|quote|cost|rate)\b",
        r"\bhow much\b", r"\bwhat.*(price|cost)\b",
        r"\bsend.*(quote|quotation|proforma)\b",
    ],
    "requesting_sample": [
        r"\bsample\b", r"\btest order\b", r"\btrial\b",
        r"\bsend.*(piece|product|item|sample)\b",
        r"\bsee.*(product|quality|finish)\b",
    ],
    "meeting": [
        r"\b(call|meeting|video|zoom|teams|whatsapp)\b",
        r"\bschedule\b", r"\bavailable\b.*\b(monday|tuesday|wednesday|thursday|friday)\b",
        r"\bwhen.*(available|free)\b", r"\bbook.*appointment\b",
    ],
    "asking_price": [
        r"\bfob\b", r"\bcif\b", r"\bincoterms\b",
        r"\bper piece\b", r"\bper unit\b", r"\bper kg\b",
        r"\bbulk pricing\b", r"\bvolume discount\b",
    ],
    "negotiating": [
        r"\bbetter.*(price|offer|deal|terms)\b", r"\bnegotiat\b",
        r"\bcan.*(reduce|lower|match)\b", r"\bcompetitor\b.*\bprice\b",
        r"\bdiscount\b", r"\bpayment terms\b", r"\blc\b", r"\bletter of credit\b",
    ],
    "interested": [
        r"\binterested\b", r"\bpotential\b", r"\btell me more\b",
        r"\bmore information\b", r"\bmore details\b",
        r"\bsend.*(catalogue|brochure|catalog)\b",
    ],
    "lost": [
        r"\bnot interested\b", r"\bno.*(need|requirement)\b",
        r"\bcurrent.*(supplier|vendor).*(satisf|happy|good)\b",
        r"\bnot.*(budg|looking|source)\b",
    ],
    "unsubscribe": [
        r"\bunsubscribe\b", r"\bdo not.*(contact|email|send)\b",
        r"\bremove.*(list|database)\b", r"\bopt.?out\b",
    ],
}

# ── Signals to extract ────────────────────────────────────────────────────────
_SIGNAL_PATTERNS = {
    "mentions_quantity": r"\b(\d+[\s,]*\d*)\s*(pieces?|units?|pcs|sets?|cartons?|containers?)\b",
    "mentions_timeline": r"\b(q[1-4]|quarter|month|week|asap|urgent|soon|year)\b",
    "mentions_budget": r"\b(budget|usd|eur|gbp|aed)\s*\d+",
    "mentions_competitor": r"\b(aliexpress|alibaba|china|turkish|vietnam|taiwan|bangladesh)\b",
    "mentions_fair": r"\b(fair|expo|exhibition|show|ambiente|ihgf|ny now|canton)\b",
    "mentions_certification": r"\b(reach|rohs|ce|iso|grs|fsc|bsci)\b",
}


@dataclass
class ReplyAnalysis:
    sentiment: str
    intent: str
    confidence: float
    extracted_signals: dict
    suggested_next_action: str


def analyse_reply(body_text: str) -> ReplyAnalysis:
    """
    Classify sentiment and intent of an inbound reply.
    Returns a ReplyAnalysis dataclass.
    """
    text = body_text.lower()
    text = re.sub(r"\s+", " ", text)

    # ── Sentiment ────────────────────────────────────────────────────────────
    pos = sum(1 for p in _POSITIVE_PATTERNS if re.search(p, text))
    neg = sum(1 for p in _NEGATIVE_PATTERNS if re.search(p, text))
    neu = sum(1 for p in _NEUTRAL_PATTERNS if re.search(p, text))

    if neg >= 2:
        sentiment = "negative"
    elif neg == 1 and pos == 0:
        sentiment = "not_interested"
    elif pos >= 2:
        sentiment = "positive"
    elif pos == 1:
        sentiment = "positive"
    elif neu >= 1:
        sentiment = "neutral"
    else:
        sentiment = "neutral"

    # ── Intent ───────────────────────────────────────────────────────────────
    intent_scores: dict[str, int] = {}
    for intent, patterns in _INTENT_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, text))
        if score > 0:
            intent_scores[intent] = score

    if "unsubscribe" in intent_scores:
        intent = "unsubscribe"
        sentiment = "negative"
    elif intent_scores:
        intent = max(intent_scores, key=lambda k: intent_scores[k])
    else:
        intent = "interested" if sentiment == "positive" else "unknown"

    # ── Signal extraction ────────────────────────────────────────────────────
    signals: dict[str, str | bool] = {}
    for sig, pattern in _SIGNAL_PATTERNS.items():
        m = re.search(pattern, text)
        if m:
            signals[sig] = m.group(0).strip()

    # ── Confidence ───────────────────────────────────────────────────────────
    total_signals = pos + neg + neu + sum(intent_scores.values())
    confidence = min(0.99, 0.40 + total_signals * 0.08)

    # ── Next action ──────────────────────────────────────────────────────────
    next_action = _suggest_action(intent, sentiment, signals)

    return ReplyAnalysis(
        sentiment=sentiment,
        intent=intent,
        confidence=round(confidence, 4),
        extracted_signals=signals,
        suggested_next_action=next_action,
    )


def _suggest_action(intent: str, sentiment: str, signals: dict) -> str:
    if intent == "unsubscribe":
        return "mark_do_not_contact"
    if intent in ("requesting_quote", "asking_price"):
        return "send_quotation"
    if intent == "requesting_sample":
        return "create_sample_record"
    if intent == "meeting":
        return "schedule_call"
    if intent == "negotiating":
        return "escalate_to_manager"
    if sentiment in ("positive", ) and "mentions_quantity" in signals:
        return "send_quotation"
    if sentiment == "positive":
        return "send_sample_offer"
    if sentiment in ("not_interested", "negative"):
        return "close_lead"
    if sentiment == "neutral":
        return "send_warm_followup"
    return "log_and_monitor"


async def process_inbound_reply(
    from_email: str,
    subject: str,
    body_text: str,
    received_at: Optional[datetime] = None,
    outreach_email_id: Optional[int] = None,
    from_name: Optional[str] = None,
) -> dict:
    """
    Ingest an inbound reply, classify it, persist an EmailReply record,
    and create a CRM ContactHistory entry on the linked lead.
    """
    if received_at is None:
        received_at = datetime.now(tz=timezone.utc)

    analysis = analyse_reply(body_text)

    async with get_session() as session:
        # Find linked outreach email + lead
        lead_id: Optional[int] = None
        campaign_id: Optional[int] = None

        if outreach_email_id:
            oe = await session.get(OutreachEmail, outreach_email_id)
            if oe:
                lead_id = oe.lead_id
                campaign_id = oe.campaign_id
                # Mark original email as replied
                oe.reply_received = True
                await session.flush()
        else:
            # Try to find by from_email match in recent outreach
            oe_row = (await session.execute(
                select(OutreachEmail)
                .where(OutreachEmail.to_email == from_email)
                .order_by(OutreachEmail.sent_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            if oe_row:
                lead_id = oe_row.lead_id
                campaign_id = oe_row.campaign_id
                outreach_email_id = oe_row.id
                oe_row.reply_received = True

        # Create reply record
        reply = EmailReply(
            outreach_email_id=outreach_email_id,
            campaign_id=campaign_id,
            lead_id=lead_id,
            from_email=from_email,
            from_name=from_name,
            subject=subject,
            body_text=body_text,
            sentiment=analysis.sentiment,
            intent=analysis.intent,
            confidence_score=analysis.confidence,
            extracted_signals_json=json.dumps(analysis.extracted_signals),
            received_at=received_at,
            processed_at=datetime.now(tz=timezone.utc),
            is_processed=True,
        )
        session.add(reply)
        await session.flush()

        # Update campaign stats
        if campaign_id:
            campaign = await session.get(OutreachCampaign, campaign_id)
            if campaign:
                campaign.replies_received = (campaign.replies_received or 0) + 1
                if analysis.sentiment == "positive":
                    campaign.positive_replies = (campaign.positive_replies or 0) + 1
                total = campaign.emails_sent or 1
                campaign.reply_rate = round(campaign.replies_received / total * 100, 2)

        # Create CRM ContactHistory entry
        crm_history_id: Optional[int] = None
        if lead_id:
            history = ContactHistory(
                lead_id=lead_id,
                interaction_type="email",
                direction="inbound",
                subject=subject or "Inbound email reply",
                notes=body_text[:2000],
                outcome=analysis.intent,
                next_action=analysis.suggested_next_action,
                interacted_at=received_at,
            )
            session.add(history)
            await session.flush()
            crm_history_id = history.id
            reply.crm_history_id = crm_history_id

            # Update lead last contact date
            lead = await session.get(Lead, lead_id)
            if lead:
                lead.last_contact_date = received_at.date()
                lead.interactions_count = (lead.interactions_count or 0) + 1
                if analysis.intent == "unsubscribe":
                    pass  # contacts.do_not_contact handled separately
                elif analysis.sentiment == "positive" and lead.status in ("new", "contacted"):
                    lead.status = "engaged"

        await session.commit()

    return {
        "reply_id": reply.id,
        "lead_id": lead_id,
        "sentiment": analysis.sentiment,
        "intent": analysis.intent,
        "confidence": analysis.confidence,
        "signals": analysis.extracted_signals,
        "suggested_next_action": analysis.suggested_next_action,
        "crm_history_id": crm_history_id,
    }
