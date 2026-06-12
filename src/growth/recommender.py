"""
Daily top-10 buyer recommendation engine.

Pulls the highest-ranked growth opportunities, enriches each with
reasoning, and persists a DailyRecommendation record per slot.
"""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select

from src.core.database import get_session
from src.core.models import CanonicalBuyer, LeadScore
from src.growth.models import DailyRecommendation, GrowthOpportunity
from src.growth.ranker import rank


async def build_recommendations(run_id: int | None = None, top_n: int = 10) -> list[dict]:
    """
    Select top_n active growth opportunities ordered by opportunity_score,
    persist DailyRecommendation rows, and return the list as dicts.
    """
    today_str = date.today().isoformat()

    async with get_session() as session:
        # Fetch top active opportunities with buyer + score data
        stmt = (
            select(GrowthOpportunity, CanonicalBuyer, LeadScore)
            .join(CanonicalBuyer, GrowthOpportunity.canonical_id == CanonicalBuyer.id)
            .outerjoin(LeadScore, LeadScore.canonical_id == CanonicalBuyer.id)
            .where(GrowthOpportunity.status == "active")
            .order_by(GrowthOpportunity.opportunity_score.desc())
            .limit(top_n * 3)  # fetch more, dedup, take top_n
        )
        rows = (await session.execute(stmt)).all()

        seen: set[int] = set()
        recommendations = []
        rank_pos = 1

        for opp, buyer, ls in rows:
            if buyer.id in seen:
                continue
            if ls is None:
                continue
            seen.add(buyer.id)

            opp_rank = rank(buyer, ls)

            signals = json.loads(opp.market_signals_json or "[]")
            reasoning = _build_reasoning(buyer, ls, opp_rank, rank_pos)

            rec = DailyRecommendation(
                run_date=today_str,
                discovery_run_id=run_id,
                rank_position=rank_pos,
                canonical_id=buyer.id,
                opportunity_score=opp_rank.opportunity_score,
                composite_lead_score=float(ls.composite_score or 0),
                reasoning=reasoning,
                key_signals_json=json.dumps(signals[:5]),
                action_type=opp_rank.action_type,
                email_template=opp_rank.email_template,
                status="pending",
            )
            session.add(rec)

            recommendations.append({
                "rank": rank_pos,
                "canonical_id": buyer.id,
                "company_name": buyer.company_name,
                "country_code": buyer.country_code,
                "buyer_type": buyer.buyer_type,
                "opportunity_score": opp_rank.opportunity_score,
                "composite_lead_score": float(ls.composite_score or 0),
                "estimated_value_usd": opp_rank.estimated_value_usd,
                "reasoning": reasoning,
                "key_signals": signals[:5],
                "action_type": opp_rank.action_type,
                "email_template": opp_rank.email_template,
            })

            rank_pos += 1
            if rank_pos > top_n:
                break

        await session.commit()

    return recommendations


def _build_reasoning(buyer, ls, opp_rank, rank_pos: int) -> str:
    company = buyer.company_name or "This buyer"
    cc = (buyer.country_code or "").upper()
    btype = (buyer.buyer_type or "importer").lower()
    iip = float(ls.india_import_probability or 0)
    pfs = float(ls.product_fit_score or 0)
    gts = float(ls.growth_trend_score or 0)
    composite = float(ls.composite_score or 0)
    vol = float(buyer.estimated_annual_volume_usd or 0)

    parts = [f"#{rank_pos}: {company} ({cc}) — opportunity score {opp_rank.opportunity_score:.0f}/100."]

    if iip < 30 and pfs > 55:
        parts.append(
            f"Product fit is {pfs:.0f}/100 but India import probability is only {iip:.0f}% — "
            f"they are sourcing brass products but not yet from India, creating a direct entry window."
        )
    elif iip >= 30:
        parts.append(
            f"Already importing {iip:.0f}% probability from India — re-engagement or supplier-switch play."
        )

    if gts > 65:
        parts.append(f"Growth trend score {gts:.0f} indicates expanding import activity.")

    if vol >= 10_000_000:
        parts.append(f"Estimated annual volume ${vol/1e6:.1f}M makes this a high-value target.")

    opp_score_context = (
        "top-priority" if opp_rank.opportunity_score >= 80
        else ("priority" if opp_rank.opportunity_score >= 65
              else "qualified")
    )
    parts.append(
        f"Classified as {opp_score_context} — "
        f"recommend {opp_rank.action_type.replace('_', ' ')} using the "
        f"'{opp_rank.email_template}' template."
    )

    return " ".join(parts)
