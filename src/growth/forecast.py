"""
Monthly export revenue forecast engine.

Builds a 6-month forward view from:
  - Confirmed POs (status ∈ {new, production, ready_to_ship})
  - Weighted pipeline (opportunity × deal probability)
  - Seasonal adjustment
  - Historical conversion rate
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select

from src.core.database import get_session
from src.crm.models import Opportunity, PurchaseOrder
from src.growth.models import DealProbabilityScore, ExportForecast
from src.growth.ranker import SEASONAL_FACTORS
from src.intelligence.closure import score_opportunity

# Historical conversion: % of proposal-stage opportunities that close
_HIST_CONVERSION = {
    "prospecting": 0.08,
    "qualification": 0.18,
    "proposal": 0.38,
    "negotiation": 0.65,
    "won": 1.00,
    "lost": 0.00,
}

# Average days from current stage to close (used for month allocation)
_STAGE_DAYS_TO_CLOSE = {
    "prospecting": 120,
    "qualification": 75,
    "proposal": 45,
    "negotiation": 20,
    "won": 5,
    "lost": 0,
}


async def build_forecast(months_ahead: int = 6) -> list[dict]:
    """
    Generate month-by-month forecasts for the next `months_ahead` months.
    Persists ExportForecast rows (is_current=True) and returns list of dicts.
    """
    today = date.today()
    months = [
        _month_str(today.year, today.month + i)
        for i in range(months_ahead)
    ]

    # ── 1. Collect data ───────────────────────────────────────────────────────
    async with get_session() as session:
        # Active opportunities (not won/lost)
        active_opps = (await session.execute(
            select(Opportunity).where(
                Opportunity.stage.notin_(["lost"])
            )
        )).scalars().all()

        # Confirmed POs (revenue already committed)
        confirmed_pos = (await session.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.status.in_(["new", "production", "ready_to_ship", "shipped"])
            )
        )).scalars().all()

        # Expire old forecasts
        old = (await session.execute(
            select(ExportForecast).where(ExportForecast.is_current == True)
        )).scalars().all()
        for f in old:
            f.is_current = False
        await session.commit()

    # ── 2. Confirmed revenue by month (from POs) ─────────────────────────────
    confirmed_by_month: dict[str, float] = {m: 0.0 for m in months}
    for po in confirmed_pos:
        shipment = po.shipment_date
        if shipment is None:
            # Default: 60 days from now
            shipment = today + timedelta(days=60)
        target = _month_str(shipment.year, shipment.month)
        if target in confirmed_by_month:
            confirmed_by_month[target] += float(po.total_value or 0)

    # ── 3. Weighted pipeline by month (from opportunities) ───────────────────
    pipeline_by_month: dict[str, float] = {m: 0.0 for m in months}
    opp_snapshots: list[dict] = []

    for opp in active_opps:
        if opp.stage == "won":
            continue  # already in PO pipeline or confirmed

        prob = await score_opportunity(opp)
        adj_prob = prob.probability_pct / 100.0
        val = float(opp.estimated_value_usd or 0) * adj_prob

        days_out = _STAGE_DAYS_TO_CLOSE.get(opp.stage, 60)
        close_date = today + timedelta(days=days_out)
        if opp.expected_close_date:
            close_date = opp.expected_close_date

        target = _month_str(close_date.year, close_date.month)
        if target in pipeline_by_month:
            pipeline_by_month[target] += val

        opp_snapshots.append({
            "opportunity_id": opp.id,
            "stage": opp.stage,
            "value_usd": float(opp.estimated_value_usd or 0),
            "probability_pct": prob.probability_pct,
            "weighted_usd": round(val, 2),
            "expected_close": str(close_date),
        })

    # ── 4. Build monthly forecast rows ───────────────────────────────────────
    results: list[dict] = []
    month_date = date(today.year, today.month, 1)

    async with get_session() as session:
        for m in months:
            confirmed = confirmed_by_month[m]
            weighted_pipeline = pipeline_by_month[m]
            season = SEASONAL_FACTORS.get(month_date.month, 1.0)

            base_case = (confirmed + weighted_pipeline) * season
            upside_case = base_case * 1.25
            downside_case = base_case * 0.75

            active_count = sum(
                1 for s in opp_snapshots
                if s["expected_close"][:7] == m
            )
            avg_prob = (
                sum(s["probability_pct"] for s in opp_snapshots
                    if s["expected_close"][:7] == m)
                / max(1, active_count)
            )

            fc = ExportForecast(
                forecast_month=m,
                base_case_usd=round(base_case, 2),
                upside_case_usd=round(upside_case, 2),
                downside_case_usd=round(downside_case, 2),
                confirmed_usd=round(confirmed, 2),
                weighted_pipeline_usd=round(weighted_pipeline, 2),
                seasonal_factor=round(season, 4),
                active_opportunities=active_count,
                avg_close_probability=round(avg_prob, 2),
                opportunities_json=json.dumps([
                    s for s in opp_snapshots if s["expected_close"][:7] == m
                ]),
                is_current=True,
            )
            session.add(fc)

            results.append({
                "month": m,
                "base_case_usd": round(base_case, 2),
                "upside_case_usd": round(upside_case, 2),
                "downside_case_usd": round(downside_case, 2),
                "confirmed_usd": round(confirmed, 2),
                "weighted_pipeline_usd": round(weighted_pipeline, 2),
                "seasonal_factor": round(season, 4),
                "active_opportunities": active_count,
                "avg_close_probability_pct": round(avg_prob, 2),
            })

            # Advance month
            if month_date.month == 12:
                month_date = date(month_date.year + 1, 1, 1)
            else:
                month_date = date(month_date.year, month_date.month + 1, 1)

        await session.commit()

    return results


def _month_str(year: int, month: int) -> str:
    """Normalise overflow months. e.g. month=13 → next year Jan."""
    while month > 12:
        month -= 12
        year += 1
    return f"{year}-{month:02d}"
