"""
Executive Dashboard API.

Provides a real-time, consolidated view of the entire export growth platform:
  - Business KPIs and health metrics
  - Top growth opportunities
  - Deal pipeline analysis with closure probabilities
  - Country opportunity heatmap
  - Buyer segment matrix
  - 6-month revenue forecast
  - Emerging importer report
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import func, select, text

from src.core.database import get_session
from src.core.models import CanonicalBuyer, LeadScore
from src.crm.models import Lead, Opportunity, PurchaseOrder, Sample, Quotation
from src.growth.models import (
    DailyRecommendation,
    DiscoveryRun,
    EmergingImporter,
    ExportForecast,
    GrowthOpportunity,
)
from src.intelligence.closure import score_opportunity_sync, _compute
from src.outreach.models import EmailReply, OutreachCampaign

router = APIRouter(prefix="/executive", tags=["executive-dashboard"])


# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW — Main KPI dashboard
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/overview", summary="Executive KPI overview — real-time health of the export platform")
async def overview():
    today = date.today()
    async with get_session() as session:
        # Buyer intelligence
        total_buyers = (await session.execute(
            select(func.count(CanonicalBuyer.id)).where(CanonicalBuyer.is_active == True)
        )).scalar_one()
        avg_score = (await session.execute(select(func.avg(LeadScore.composite_score)))).scalar_one() or 0
        hot_buyers = (await session.execute(
            select(func.count(LeadScore.id)).where(LeadScore.tier.in_(["A", "B"]))
        )).scalar_one()

        # CRM pipeline
        crm_leads = (await session.execute(select(func.count(Lead.id)))).scalar_one()
        active_opps = (await session.execute(
            select(func.count(Opportunity.id)).where(Opportunity.stage.notin_(["won", "lost"]))
        )).scalar_one()
        pipeline_val = (await session.execute(
            select(func.sum(Opportunity.estimated_value_usd)).where(Opportunity.stage.notin_(["won", "lost"]))
        )).scalar_one() or 0
        won_val = (await session.execute(
            select(func.sum(Opportunity.estimated_value_usd)).where(Opportunity.stage == "won")
        )).scalar_one() or 0

        # Growth engine
        active_opps_growth = (await session.execute(
            select(func.count(GrowthOpportunity.id)).where(GrowthOpportunity.status == "active")
        )).scalar_one()
        emerging_count = (await session.execute(
            select(func.count(EmergingImporter.id)).where(EmergingImporter.is_active == True)
        )).scalar_one()

        # Outreach
        emails_sent = (await session.execute(select(func.sum(OutreachCampaign.emails_sent)))).scalar_one() or 0
        positive_replies = (await session.execute(
            select(func.count(EmailReply.id)).where(EmailReply.sentiment == "positive")
        )).scalar_one()

        # Revenue (confirmed POs)
        confirmed_rev = (await session.execute(
            select(func.sum(PurchaseOrder.total_value)).where(
                PurchaseOrder.status.in_(["shipped", "delivered"])
            )
        )).scalar_one() or 0

        # Last discovery run
        last_run = (await session.execute(
            select(DiscoveryRun).where(DiscoveryRun.status == "completed")
            .order_by(DiscoveryRun.run_at.desc()).limit(1)
        )).scalar_one_or_none()

    return {
        "generated_at": date.today().isoformat(),
        "buyer_intelligence": {
            "total_buyers": total_buyers,
            "avg_lead_score": round(float(avg_score), 2),
            "tier_a_b_buyers": hot_buyers,
            "active_growth_opportunities": active_opps_growth,
            "emerging_importers": emerging_count,
        },
        "crm_pipeline": {
            "total_leads": crm_leads,
            "active_opportunities": active_opps,
            "pipeline_value_usd": float(pipeline_val),
            "won_value_usd": float(won_val),
        },
        "outreach": {
            "total_emails_sent": int(emails_sent),
            "positive_replies": positive_replies,
        },
        "revenue": {
            "confirmed_shipped_usd": float(confirmed_rev),
        },
        "last_discovery_run": {
            "run_at": last_run.run_at.isoformat() if last_run else None,
            "new_buyers_found": last_run.new_buyers_found if last_run else 0,
            "opportunities_created": last_run.opportunities_created if last_run else 0,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# NEW OPPORTUNITIES — recently discovered, ranked
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/opportunities", summary="New and ranked growth opportunities")
async def opportunities(
    days_back: int = Query(7),
    min_score: float = Query(55.0),
    limit: int = Query(25),
):
    since = date.today() - timedelta(days=days_back)
    async with get_session() as session:
        rows = (await session.execute(
            select(GrowthOpportunity, CanonicalBuyer, LeadScore)
            .join(CanonicalBuyer, GrowthOpportunity.canonical_id == CanonicalBuyer.id)
            .outerjoin(LeadScore, LeadScore.canonical_id == CanonicalBuyer.id)
            .where(
                GrowthOpportunity.status == "active",
                GrowthOpportunity.opportunity_score >= min_score,
            )
            .order_by(GrowthOpportunity.opportunity_score.desc())
            .limit(limit)
        )).all()
    return {
        "count": len(rows),
        "min_score": min_score,
        "opportunities": [
            {
                "opportunity_score": float(opp.opportunity_score or 0),
                "company_name": buyer.company_name,
                "country_code": opp.country_code,
                "buyer_type": opp.buyer_type,
                "estimated_value_usd": float(opp.estimated_value_usd or 0),
                "composite_lead_score": float(ls.composite_score or 0) if ls else None,
                "india_import_probability": float(ls.india_import_probability or 0) if ls else None,
                "competitive_gap": float(opp.competitive_gap_score or 0),
                "timing_score": float(opp.market_timing_score or 0),
                "is_new": opp.is_new_discovery,
                "is_emerging": opp.is_emerging,
                "reasoning": opp.reasoning,
                "signals": json.loads(opp.market_signals_json or "[]"),
                "canonical_id": opp.canonical_id,
            }
            for opp, buyer, ls in rows
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVE DEALS — CRM pipeline with closure probabilities
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/active-deals", summary="Active CRM deals with AI closure probability")
async def active_deals(stage: Optional[str] = Query(None)):
    async with get_session() as session:
        stmt = select(Opportunity, Lead).outerjoin(Lead, Opportunity.lead_id == Lead.id)
        if stage:
            stmt = stmt.where(Opportunity.stage == stage)
        else:
            stmt = stmt.where(Opportunity.stage.notin_(["won", "lost"]))
        rows = (await session.execute(stmt.order_by(Opportunity.estimated_value_usd.desc()).limit(100))).all()

        results = []
        for opp, lead in rows:
            ls = None
            samples = []
            quotations = []
            if lead and lead.canonical_buyer_id:
                ls = (await session.execute(
                    select(LeadScore).where(LeadScore.canonical_id == lead.canonical_buyer_id)
                )).scalar_one_or_none()
                samples = (await session.execute(
                    select(Sample).where(Sample.opportunity_id == opp.id)
                )).scalars().all()
                quotations = (await session.execute(
                    select(Quotation).where(Quotation.opportunity_id == opp.id)
                )).scalars().all()

            prob = _compute(opp, lead, ls, list(samples), list(quotations))
            results.append({
                "opportunity_id": opp.id,
                "title": opp.title,
                "lead_company": lead.company_name if lead else None,
                "country_code": lead.country_code if lead else None,
                "stage": opp.stage,
                "estimated_value_usd": float(opp.estimated_value_usd or 0),
                "probability_pct": prob.probability_pct,
                "weighted_value_usd": prob.weighted_value_usd,
                "days_to_close_est": prob.days_to_close_est,
                "confidence_level": prob.confidence_level,
                "positive_signals": prob.positive_signals[:3],
                "risk_factors": prob.risk_factors[:2],
                "expected_close_date": opp.expected_close_date.isoformat() if opp.expected_close_date else None,
                "incoterms": opp.incoterms,
                "assigned_to": opp.assigned_to,
            })

    total_pipeline = sum(r["estimated_value_usd"] for r in results)
    weighted_pipeline = sum(r["weighted_value_usd"] for r in results)
    return {
        "total_active_deals": len(results),
        "total_pipeline_usd": round(total_pipeline, 2),
        "weighted_pipeline_usd": round(weighted_pipeline, 2),
        "by_stage": _group_by_stage(results),
        "deals": results,
    }


def _group_by_stage(deals: list) -> list:
    from collections import defaultdict
    stages = defaultdict(lambda: {"count": 0, "value": 0, "weighted": 0})
    for d in deals:
        s = d["stage"]
        stages[s]["count"] += 1
        stages[s]["value"] += d["estimated_value_usd"]
        stages[s]["weighted"] += d["weighted_value_usd"]
    order = ["prospecting", "qualification", "proposal", "negotiation", "won"]
    return [
        {
            "stage": s,
            "count": stages[s]["count"],
            "total_value_usd": round(stages[s]["value"], 2),
            "weighted_value_usd": round(stages[s]["weighted"], 2),
        }
        for s in order if s in stages
    ]


# ══════════════════════════════════════════════════════════════════════════════
# COUNTRY OPPORTUNITIES — heatmap data
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/country-heatmap", summary="Country opportunity matrix — buyer count, value, score")
async def country_heatmap(min_buyers: int = Query(2)):
    from src.growth.ranker import COUNTRY_OPPORTUNITY
    async with get_session() as session:
        # Buyers with scores by country
        rows = (await session.execute(
            select(
                CanonicalBuyer.country_code,
                CanonicalBuyer.country_name,
                func.count(CanonicalBuyer.id).label("buyer_count"),
                func.sum(CanonicalBuyer.estimated_annual_volume_usd).label("total_volume"),
                func.avg(LeadScore.composite_score).label("avg_score"),
                func.count(LeadScore.id).filter(LeadScore.tier.in_(["A", "B"])).label("hot_buyers"),
            )
            .outerjoin(LeadScore, LeadScore.canonical_id == CanonicalBuyer.id)
            .where(CanonicalBuyer.is_active == True)
            .group_by(CanonicalBuyer.country_code, CanonicalBuyer.country_name)
            .having(func.count(CanonicalBuyer.id) >= min_buyers)
            .order_by(func.sum(CanonicalBuyer.estimated_annual_volume_usd).desc())
        )).fetchall()

        # Pipeline by country (from active opportunities)
        pipeline_rows = (await session.execute(
            select(Lead.country_code, func.sum(Opportunity.estimated_value_usd).label("pipeline"))
            .join(Opportunity, Opportunity.lead_id == Lead.id)
            .where(Opportunity.stage.notin_(["won", "lost"]))
            .group_by(Lead.country_code)
        )).fetchall()
        pipeline_by_country = {r.country_code: float(r.pipeline or 0) for r in pipeline_rows}

    heatmap = []
    for r in rows:
        cc = r.country_code or "XX"
        market_score = COUNTRY_OPPORTUNITY.get(cc, 50)
        buyer_count = r.buyer_count
        avg_lead = float(r.avg_score or 0)
        hot = r.hot_buyers or 0
        total_vol = float(r.total_volume or 0)
        pipeline = pipeline_by_country.get(cc, 0)
        # Composite opportunity index
        opp_index = round(market_score * 0.40 + avg_lead * 0.40 + min(100, hot * 10) * 0.20, 2)
        heatmap.append({
            "country_code": cc,
            "country_name": r.country_name,
            "buyer_count": buyer_count,
            "tier_a_b_buyers": hot,
            "total_volume_usd": total_vol,
            "active_pipeline_usd": pipeline,
            "avg_lead_score": round(avg_lead, 2),
            "market_opportunity_score": market_score,
            "country_opportunity_index": opp_index,
        })

    heatmap.sort(key=lambda x: x["country_opportunity_index"], reverse=True)
    return {"country_count": len(heatmap), "heatmap": heatmap}


# ══════════════════════════════════════════════════════════════════════════════
# REVENUE PIPELINE — funnel metrics
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/pipeline-analysis", summary="Deep pipeline analysis with velocity and win-rate metrics")
async def pipeline_analysis():
    async with get_session() as session:
        # Stage distribution
        by_stage = (await session.execute(
            select(
                Opportunity.stage,
                func.count(Opportunity.id).label("count"),
                func.sum(Opportunity.estimated_value_usd).label("value"),
                func.avg(Opportunity.probability_pct).label("avg_prob"),
            )
            .group_by(Opportunity.stage)
        )).fetchall()

        total_opps = (await session.execute(select(func.count(Opportunity.id)))).scalar_one()
        won = next((r for r in by_stage if r.stage == "won"), None)
        lost = next((r for r in by_stage if r.stage == "lost"), None)
        closed = (won.count if won else 0) + (lost.count if lost else 0)
        win_rate = round((won.count / max(1, closed)) * 100, 2) if won else 0

        # Sample + Quote conversion metrics
        samples_sent = (await session.execute(select(func.count(Sample.id)))).scalar_one()
        samples_approved = (await session.execute(
            select(func.count(Sample.id)).where(Sample.approved_for_bulk == True)
        )).scalar_one()
        quotes_sent = (await session.execute(
            select(func.count(Quotation.id)).where(Quotation.status == "sent")
        )).scalar_one()
        quotes_accepted = (await session.execute(
            select(func.count(Quotation.id)).where(Quotation.status == "accepted")
        )).scalar_one()

        # Average deal size
        avg_deal = (await session.execute(
            select(func.avg(Opportunity.estimated_value_usd))
            .where(Opportunity.stage.notin_(["lost"]))
        )).scalar_one() or 0

    stage_data = [
        {
            "stage": r.stage,
            "count": r.count,
            "total_value_usd": float(r.value or 0),
            "avg_probability_pct": round(float(r.avg_prob or 0), 2),
            "weighted_value_usd": round(float(r.value or 0) * float(r.avg_prob or 0) / 100, 2),
        }
        for r in by_stage
        if r.stage not in ("won", "lost")
    ]
    stage_data.sort(key=lambda x: ["prospecting", "qualification", "proposal", "negotiation"].index(x["stage"])
                    if x["stage"] in ["prospecting", "qualification", "proposal", "negotiation"] else 99)

    return {
        "summary": {
            "total_opportunities": total_opps,
            "win_rate_pct": win_rate,
            "avg_deal_size_usd": round(float(avg_deal), 2),
            "won_value_usd": float(won.value or 0) if won else 0,
            "lost_count": lost.count if lost else 0,
        },
        "conversion_rates": {
            "sample_approval_rate_pct": round(samples_approved / max(1, samples_sent) * 100, 2),
            "quote_acceptance_rate_pct": round(quotes_accepted / max(1, quotes_sent) * 100, 2),
            "samples_sent": samples_sent,
            "samples_approved": samples_approved,
            "quotes_sent": quotes_sent,
            "quotes_accepted": quotes_accepted,
        },
        "pipeline_by_stage": stage_data,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MONTHLY FORECAST
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/forecast", summary="6-month export revenue forecast")
async def get_forecast(months_ahead: int = Query(6, ge=1, le=12), refresh: bool = Query(False)):
    async with get_session() as session:
        # Try cached forecast first
        if not refresh:
            cached = (await session.execute(
                select(ExportForecast)
                .where(ExportForecast.is_current == True)
                .order_by(ExportForecast.forecast_month.asc())
                .limit(months_ahead)
            )).scalars().all()
            if len(cached) >= months_ahead:
                return {
                    "months_ahead": months_ahead,
                    "generated_at": cached[0].generated_at.isoformat() if cached else None,
                    "total_base_case_usd": round(sum(float(f.base_case_usd or 0) for f in cached), 2),
                    "total_upside_usd": round(sum(float(f.upside_case_usd or 0) for f in cached), 2),
                    "total_confirmed_usd": round(sum(float(f.confirmed_usd or 0) for f in cached), 2),
                    "forecast": [
                        {
                            "month": f.forecast_month,
                            "base_case_usd": float(f.base_case_usd or 0),
                            "upside_case_usd": float(f.upside_case_usd or 0),
                            "downside_case_usd": float(f.downside_case_usd or 0),
                            "confirmed_usd": float(f.confirmed_usd or 0),
                            "weighted_pipeline_usd": float(f.weighted_pipeline_usd or 0),
                            "seasonal_factor": float(f.seasonal_factor or 1),
                            "active_opportunities": f.active_opportunities,
                            "avg_close_probability_pct": float(f.avg_close_probability or 0),
                        }
                        for f in cached
                    ],
                }

    from src.growth.forecast import build_forecast
    forecasts = await build_forecast(months_ahead=months_ahead)
    return {
        "months_ahead": months_ahead,
        "generated_at": date.today().isoformat(),
        "total_base_case_usd": round(sum(f["base_case_usd"] for f in forecasts), 2),
        "total_upside_usd": round(sum(f["upside_case_usd"] for f in forecasts), 2),
        "total_confirmed_usd": round(sum(f["confirmed_usd"] for f in forecasts), 2),
        "forecast": forecasts,
    }


# ══════════════════════════════════════════════════════════════════════════════
# BUYER HEATMAP — segment matrix
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/buyer-heatmap", summary="Buyer segment matrix: type × tier × country")
async def buyer_heatmap():
    async with get_session() as session:
        rows = (await session.execute(
            select(
                CanonicalBuyer.buyer_type,
                LeadScore.tier,
                func.count(CanonicalBuyer.id).label("count"),
                func.sum(CanonicalBuyer.estimated_annual_volume_usd).label("volume"),
                func.avg(LeadScore.composite_score).label("avg_score"),
            )
            .join(LeadScore, LeadScore.canonical_id == CanonicalBuyer.id)
            .where(CanonicalBuyer.is_active == True)
            .group_by(CanonicalBuyer.buyer_type, LeadScore.tier)
        )).fetchall()

    matrix: dict[str, dict] = {}
    for r in rows:
        btype = r.buyer_type or "unknown"
        tier = r.tier or "F"
        if btype not in matrix:
            matrix[btype] = {}
        matrix[btype][tier] = {
            "count": r.count,
            "total_volume_usd": float(r.volume or 0),
            "avg_lead_score": round(float(r.avg_score or 0), 2),
        }

    return {
        "tiers": ["A", "B", "C", "D", "F"],
        "buyer_types": sorted(matrix.keys()),
        "matrix": matrix,
    }


# ══════════════════════════════════════════════════════════════════════════════
# EMERGING IMPORTERS REPORT
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/emerging-importers", summary="Emerging importer intelligence report")
async def emerging_report(min_score: float = Query(50.0), limit: int = Query(20)):
    async with get_session() as session:
        rows = (await session.execute(
            select(EmergingImporter, CanonicalBuyer, LeadScore)
            .join(CanonicalBuyer, EmergingImporter.canonical_id == CanonicalBuyer.id)
            .outerjoin(LeadScore, LeadScore.canonical_id == CanonicalBuyer.id)
            .where(EmergingImporter.is_active == True, EmergingImporter.overall_score >= min_score)
            .order_by(EmergingImporter.overall_score.desc())
            .limit(limit)
        )).all()

        by_category = (await session.execute(
            select(
                EmergingImporter.category,
                func.count(EmergingImporter.id).label("count"),
                func.avg(EmergingImporter.overall_score).label("avg_score"),
            )
            .where(EmergingImporter.is_active == True)
            .group_by(EmergingImporter.category)
        )).fetchall()

    return {
        "total": len(rows),
        "by_category": [
            {"category": r.category, "count": r.count, "avg_score": round(float(r.avg_score or 0), 2)}
            for r in by_category
        ],
        "importers": [
            {
                "rank": i + 1,
                "canonical_id": em.canonical_id,
                "company_name": buyer.company_name,
                "country_code": buyer.country_code,
                "buyer_type": buyer.buyer_type,
                "months_active": em.months_active,
                "shipment_count": em.shipment_count,
                "annual_volume_usd": float(em.annual_volume_usd or 0),
                "growth_velocity_score": float(em.growth_velocity_score or 0),
                "overall_score": float(em.overall_score or 0),
                "category": em.category,
                "confidence": em.confidence,
                "action_recommended": em.action_recommended,
                "composite_lead_score": float(ls.composite_score or 0) if ls else None,
                "detected_at": em.detected_at.isoformat() if em.detected_at else None,
            }
            for i, (em, buyer, ls) in enumerate(rows)
        ],
    }
