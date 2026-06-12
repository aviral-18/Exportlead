"""
Emerging importer detection.

Identifies buyers who have recently begun importing and show accelerating
activity — the highest-value cold outreach targets because supplier
relationships are not yet locked in.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class EmergingSignal:
    canonical_id: int
    months_active: int
    shipment_count: int
    annual_volume_usd: float
    growth_velocity_score: float
    market_timing_score: float
    overall_score: float
    category: str
    confidence: str
    action_recommended: str
    trend: dict


# Months since first import → velocity multiplier
_VELOCITY_MAP = {
    range(0, 6):   1.40,
    range(6, 12):  1.25,
    range(12, 18): 1.10,
    range(18, 24): 0.95,
    range(24, 36): 0.80,
}

# Shipment-count × months_active density threshold
_HIGH_DENSITY_RATIO = 2.0   # > 2 shipments per month = high activity


def _velocity_mult(months: int) -> float:
    for r, m in _VELOCITY_MAP.items():
        if months in r:
            return m
    return 0.70


def _category(months: int, shipment_count: int, growth_score: float) -> str:
    density = shipment_count / max(1, months)
    if months <= 6 and density >= 1.0:
        return "new_market_entrant"
    if density >= _HIGH_DENSITY_RATIO:
        return "fast_grower"
    if growth_score >= 70:
        return "accelerating"
    return "emerging"


def detect(buyer: Any, lead_score: Any) -> EmergingSignal | None:
    """
    Return an EmergingSignal if the buyer qualifies as an emerging importer,
    else None.
    """
    def _g(obj, attr, default=None):
        if hasattr(obj, attr):
            return getattr(obj, attr)
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return default

    first_import = _g(buyer, "first_import_date")
    if first_import is None:
        return None

    if isinstance(first_import, str):
        try:
            from datetime import datetime
            first_import = datetime.strptime(first_import, "%Y-%m-%d").date()
        except ValueError:
            return None

    today = date.today()
    months_active = max(1, ((today - first_import).days) // 30)

    # Only flag buyers active ≤ 30 months
    if months_active > 30:
        return None

    shipments = int(_g(buyer, "total_shipments") or 0)
    vol = float(_g(buyer, "estimated_annual_volume_usd") or 0)
    gts = float(_g(lead_score, "growth_trend_score") or 0)
    nis = float(_g(lead_score, "new_importer_score") or 0)
    pfs = float(_g(lead_score, "product_fit_score") or 0)
    composite = float(_g(lead_score, "composite_score") or 0)

    # Must have meaningful activity
    if shipments < 2 or composite < 30:
        return None

    # Growth velocity score (0–100)
    density = shipments / months_active
    density_score = min(100, density * 20)
    vmult = _velocity_mult(months_active)
    growth_velocity = round(min(100, (density_score * vmult + gts * 0.30 + nis * 0.20)), 2)

    # Market timing (current month seasonality × product fit)
    from datetime import date as _date
    from src.growth.ranker import SEASONAL_FACTORS
    month = today.month
    seasonal = SEASONAL_FACTORS.get(month, 1.0)
    timing_score = round(min(100, pfs * seasonal), 2)

    # Overall emerging score
    overall = round(
        growth_velocity * 0.50
        + timing_score * 0.25
        + composite * 0.25,
        2,
    )

    if overall < 35:
        return None

    confidence = "high" if overall >= 70 else ("medium" if overall >= 50 else "low")
    category = _category(months_active, shipments, growth_velocity)

    trend = {
        "months_active": months_active,
        "shipments_per_month": round(density, 2),
        "growth_trend_score": gts,
        "new_importer_score": nis,
        "seasonal_factor": seasonal,
    }

    if category == "new_market_entrant":
        action = "urgent_outreach"
    elif category == "fast_grower":
        action = "priority_outreach"
    else:
        action = "standard_outreach"

    return EmergingSignal(
        canonical_id=int(_g(buyer, "id") or _g(buyer, "canonical_id") or 0),
        months_active=months_active,
        shipment_count=shipments,
        annual_volume_usd=vol,
        growth_velocity_score=growth_velocity,
        market_timing_score=timing_score,
        overall_score=overall,
        category=category,
        confidence=confidence,
        action_recommended=action,
        trend=trend,
    )
