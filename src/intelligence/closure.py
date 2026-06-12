"""
Deal closure probability engine.

Produces a calibrated probability (0–100) for each CRM opportunity,
along with days-to-close estimate, risk factors, and positive signals.
No ML training needed — uses a Bayesian-inspired weighted scoring model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select

from src.core.database import get_session
from src.crm.models import Opportunity, Sample, Quotation, Lead
from src.core.models import LeadScore

# ── Stage base probability (%) ────────────────────────────────────────────────
_STAGE_BASE = {
    "prospecting": 10,
    "qualification": 22,
    "proposal": 40,
    "negotiation": 65,
    "won": 100,
    "lost": 0,
}

# ── Expected days to close from each stage ────────────────────────────────────
_STAGE_DAYS = {
    "prospecting": 120,
    "qualification": 75,
    "proposal": 45,
    "negotiation": 18,
    "won": 3,
    "lost": 0,
}


@dataclass
class ClosureProbabilityResult:
    opportunity_id: int
    probability_pct: float
    confidence_level: str
    days_to_close_est: int
    expected_value_usd: float
    weighted_value_usd: float
    positive_signals: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    scoring_breakdown: dict = field(default_factory=dict)


async def score_opportunity(opportunity: Opportunity) -> ClosureProbabilityResult:
    """
    Score a single CRM Opportunity.
    Fetches supporting data (lead, samples, quotes, AI score) then runs the model.
    """
    async with get_session() as session:
        lead = await session.get(Lead, opportunity.lead_id) if opportunity.lead_id else None
        lead_score = None
        samples = []
        quotations = []

        if lead and lead.canonical_buyer_id:
            lead_score = (await session.execute(
                select(LeadScore).where(LeadScore.canonical_id == lead.canonical_buyer_id)
            )).scalar_one_or_none()

        if opportunity.id:
            samples = (await session.execute(
                select(Sample).where(Sample.opportunity_id == opportunity.id)
            )).scalars().all()
            quotations = (await session.execute(
                select(Quotation).where(Quotation.opportunity_id == opportunity.id)
            )).scalars().all()

    return _compute(opportunity, lead, lead_score, list(samples), list(quotations))


def score_opportunity_sync(
    opportunity,
    lead=None,
    lead_score=None,
    samples=None,
    quotations=None,
) -> ClosureProbabilityResult:
    """Synchronous version for use in non-async contexts (e.g. demo)."""
    return _compute(opportunity, lead, lead_score, samples or [], quotations or [])


def _compute(
    opp,
    lead,
    lead_score,
    samples: list,
    quotations: list,
) -> ClosureProbabilityResult:
    def _g(obj, attr, default=None):
        if obj is None:
            return default
        if hasattr(obj, attr):
            return getattr(obj, attr)
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return default

    today = date.today()
    stage = (_g(opp, "stage") or "prospecting").lower()
    value = float(_g(opp, "estimated_value_usd") or 0)
    opp_id = int(_g(opp, "id") or 0)

    positive: list[str] = []
    risks: list[str] = []
    breakdown: dict[str, float] = {}

    # ── 1. Stage component (40 %) ─────────────────────────────────────────────
    stage_score = _STAGE_BASE.get(stage, 10)
    breakdown["stage"] = stage_score

    if stage == "won":
        return ClosureProbabilityResult(
            opportunity_id=opp_id,
            probability_pct=100.0,
            confidence_level="high",
            days_to_close_est=0,
            expected_value_usd=value,
            weighted_value_usd=value,
            positive_signals=["Opportunity already won"],
            scoring_breakdown={"stage": 100},
        )
    if stage == "lost":
        return ClosureProbabilityResult(
            opportunity_id=opp_id,
            probability_pct=0.0,
            confidence_level="high",
            days_to_close_est=0,
            expected_value_usd=value,
            weighted_value_usd=0.0,
            risk_factors=["Opportunity marked as lost"],
            scoring_breakdown={"stage": 0},
        )

    # ── 2. Engagement component (25 %) ───────────────────────────────────────
    last_contact = _g(lead, "last_contact_date")
    if isinstance(last_contact, str):
        try:
            last_contact = datetime.strptime(last_contact, "%Y-%m-%d").date()
        except ValueError:
            last_contact = None

    if last_contact:
        rec_days = (today - last_contact).days
        if rec_days <= 7:
            eng_score = 90
            positive.append(f"Recent contact {rec_days} day(s) ago — high engagement")
        elif rec_days <= 21:
            eng_score = 70
            positive.append(f"Active engagement — last contact {rec_days} days ago")
        elif rec_days <= 45:
            eng_score = 50
        elif rec_days <= 90:
            eng_score = 30
            risks.append(f"No contact in {rec_days} days — pipeline may be cooling")
        else:
            eng_score = 10
            risks.append(f"Stale — no contact for {rec_days} days")
    else:
        eng_score = 25
        risks.append("No contact date recorded — engagement unknown")

    interactions = int(_g(lead, "interactions_count") or 0)
    if interactions >= 5:
        eng_score = min(100, eng_score + 15)
        positive.append(f"{interactions} total interactions logged — strong engagement history")
    breakdown["engagement"] = eng_score

    # ── 3. Sample factor (15 %) ───────────────────────────────────────────────
    if samples:
        approved = any(_g(s, "approved_for_bulk") for s in samples)
        delivered = any(_g(s, "status") in ("delivered", "feedback_received") for s in samples)
        if approved:
            sample_score = 90
            positive.append("Sample approved for bulk production — strong buying signal")
        elif delivered:
            sample_score = 65
            positive.append("Sample delivered — awaiting buyer feedback")
        else:
            sample_score = 40
        breakdown["sample"] = sample_score
    else:
        sample_score = 25
        breakdown["sample"] = sample_score

    # ── 4. Quotation factor (10 %) ────────────────────────────────────────────
    if quotations:
        accepted = any(_g(q, "status") == "accepted" for q in quotations)
        sent = any(_g(q, "status") == "sent" for q in quotations)
        rejected = any(_g(q, "status") == "rejected" for q in quotations)
        if accepted:
            quote_score = 95
            positive.append("Quotation accepted — PO expected imminently")
        elif sent:
            quote_score = 65
            positive.append("Quotation sent and under buyer review")
        elif rejected:
            quote_score = 15
            risks.append("Previous quotation rejected — re-qualification needed")
        else:
            quote_score = 35
        breakdown["quotation"] = quote_score
    else:
        quote_score = 20
        breakdown["quotation"] = quote_score

    # ── 5. AI lead score factor (10 %) ────────────────────────────────────────
    if lead_score:
        composite = float(_g(lead_score, "composite_score") or 50)
        iip = float(_g(lead_score, "india_import_probability") or 50)
        ai_score = (composite * 0.60 + iip * 0.40)
        breakdown["ai_score"] = round(ai_score, 2)
        if composite >= 75:
            positive.append(f"High AI lead score ({composite:.0f}/100)")
        if iip >= 60:
            positive.append(f"High India import probability ({iip:.0f}%) — established import relationship")
    else:
        ai_score = 50
        breakdown["ai_score"] = ai_score

    # ── 6. Pipeline staleness penalty ─────────────────────────────────────────
    updated_at = _g(opp, "updated_at")
    if isinstance(updated_at, datetime):
        days_stale = (datetime.utcnow() - updated_at).days
    elif isinstance(updated_at, str):
        try:
            days_stale = (today - datetime.fromisoformat(updated_at).date()).days
        except Exception:
            days_stale = 0
    else:
        days_stale = 0

    stale_penalty = max(0.65, 1.0 - days_stale * 0.004)
    breakdown["stale_penalty"] = round(stale_penalty, 4)
    if days_stale > 60:
        risks.append(f"Opportunity record not updated in {days_stale} days")

    # ── 7. Composite probability ──────────────────────────────────────────────
    raw = (
        stage_score * 0.40
        + eng_score * 0.25
        + sample_score * 0.15
        + quote_score * 0.10
        + ai_score * 0.10
    )
    adjusted = min(95, max(3, raw * stale_penalty))
    probability = round(adjusted, 2)

    # ── 8. Confidence level ───────────────────────────────────────────────────
    signal_count = len(positive) + len(risks)
    has_ai = lead_score is not None
    if signal_count >= 4 and has_ai:
        confidence = "high"
    elif signal_count >= 2:
        confidence = "medium"
    else:
        confidence = "low"
        risks.append("Limited data — score may not be reliable")

    # ── 9. Days to close estimate ─────────────────────────────────────────────
    base_days = _STAGE_DAYS.get(stage, 60)
    if eng_score >= 70:
        days_to_close = max(5, int(base_days * 0.75))
    elif eng_score < 30:
        days_to_close = int(base_days * 1.35)
    else:
        days_to_close = base_days

    breakdown["raw_score"] = round(raw, 2)
    breakdown["final_probability"] = probability

    return ClosureProbabilityResult(
        opportunity_id=opp_id,
        probability_pct=probability,
        confidence_level=confidence,
        days_to_close_est=days_to_close,
        expected_value_usd=value,
        weighted_value_usd=round(value * probability / 100, 2),
        positive_signals=positive,
        risk_factors=risks,
        scoring_breakdown=breakdown,
    )
