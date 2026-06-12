"""
Opportunity ranking engine.

Combines AI lead scores with market intelligence to produce a single
opportunity_score (0-100) for each buyer, used to prioritize outreach.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# Country-level opportunity scores — reflecting India brass import growth,
# market maturity, Moradabad exporter presence, and duty landscape.
COUNTRY_OPPORTUNITY: dict[str, float] = {
    "US": 85, "GB": 82, "DE": 78, "AU": 76, "CA": 74, "FR": 72,
    "NL": 70, "BE": 68, "AE": 88, "SA": 85, "KW": 80, "QA": 78,
    "IT": 66, "ES": 64, "CH": 70, "SE": 65, "DK": 63, "NO": 60,
    "SG": 75, "JP": 60, "ZA": 58, "BR": 45, "KR": 55, "MX": 50,
    "MY": 62, "TH": 58, "VN": 52, "ID": 55, "PL": 60, "CZ": 55,
    "TR": 50, "NG": 42, "KE": 40, "EG": 48, "AR": 38, "NZ": 55,
    "FI": 55, "PT": 52, "HU": 48, "GR": 45, "AT": 60, "HK": 80,
}

# Brass export seasonality: multiplier by month (1-based)
SEASONAL_FACTORS: dict[int, float] = {
    1: 1.20,  # Jan  - post-Christmas restocking + NY gift season
    2: 1.15,  # Feb  - trade fair season (Ambiente, NY Now)
    3: 1.05,  # Mar  - spring ordering
    4: 0.95,  # Apr  - mid-season
    5: 0.90,  # May  - pre-summer lull
    6: 0.85,  # Jun  - summer slowdown
    7: 0.80,  # Jul  - lowest period
    8: 0.90,  # Aug  - back-to-school/home prep
    9: 1.05,  # Sep  - IHGF Delhi + pre-Diwali
    10: 1.30, # Oct  - IHGF + Diwali + Christmas ordering peak
    11: 1.35, # Nov  - Christmas ordering (highest)
    12: 1.25, # Dec  - year-end retail push
}

# Import-frequency scoring map
FREQ_SCORE: dict[str, float] = {
    "daily": 100, "weekly": 90, "monthly": 70, "quarterly": 45,
    "annual": 25, "sporadic": 15, "unknown": 30,
}

# Buyer-type opportunity multipliers
TYPE_MULT: dict[str, float] = {
    "hospitality": 1.15,
    "sourcing_company": 1.12,
    "importer": 1.10,
    "distributor": 1.08,
    "wholesaler": 1.05,
    "retailer": 1.00,
    "procurement_agency": 0.90,
    "oem": 0.85,
    "government": 0.60,
    "unknown": 0.80,
}


@dataclass
class OpportunityRank:
    canonical_id: int
    opportunity_score: float
    composite_lead_score: float
    india_import_probability: float
    competitive_gap_score: float
    market_timing_score: float
    country_market_score: float
    estimated_value_usd: float
    reasoning: str
    key_signals: list[str]
    action_type: str
    email_template: str


def rank(buyer: Any, lead_score: Any, current_month: int | None = None) -> OpportunityRank:
    """
    Produce an opportunity rank for a buyer given its AI lead score.

    buyer      — ORM object or dict with canonical buyer fields
    lead_score — ORM object or dict with scoring fields
    """
    from datetime import date
    month = current_month or date.today().month

    def _g(obj, attr, default=None):
        if hasattr(obj, attr):
            return getattr(obj, attr)
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return default

    composite = float(_g(lead_score, "composite_score") or 0)
    iip = float(_g(lead_score, "india_import_probability") or 0)
    pfs = float(_g(lead_score, "product_fit_score") or 0)
    gts = float(_g(lead_score, "growth_trend_score") or 0)
    nis = float(_g(lead_score, "new_importer_score") or 0)
    cc = (_g(buyer, "country_code") or "").upper()
    btype = (_g(buyer, "buyer_type") or "unknown").lower()
    vol = float(_g(buyer, "estimated_annual_volume_usd") or 0)
    freq = (_g(buyer, "import_frequency") or "unknown").lower()

    # ── 1. Country market score (20 %) ───────────────────────────────────────
    country_score = COUNTRY_OPPORTUNITY.get(cc, 50)

    # ── 2. Competitive gap (15 %) ────────────────────────────────────────────
    # High gap = buyer has good product fit but hasn't yet sourced from India
    competitive_gap = max(0, pfs - iip + 30)
    competitive_gap = min(100, competitive_gap)

    # ── 3. Market timing score (15 %) ────────────────────────────────────────
    seasonal = SEASONAL_FACTORS.get(month, 1.0)
    freq_s = FREQ_SCORE.get(freq, 30)
    timing = min(100, (seasonal * 60) + (freq_s * 0.40))

    # ── 4. Volume tier ───────────────────────────────────────────────────────
    if vol >= 100_000_000:
        vol_bonus = 20
    elif vol >= 20_000_000:
        vol_bonus = 15
    elif vol >= 5_000_000:
        vol_bonus = 10
    elif vol >= 1_000_000:
        vol_bonus = 5
    else:
        vol_bonus = 0

    # ── 5. Composite opportunity score ───────────────────────────────────────
    raw = (
        composite * 0.38
        + country_score * 0.20
        + competitive_gap * 0.15
        + timing * 0.15
        + gts * 0.07
        + nis * 0.05
    ) + vol_bonus

    type_mult = TYPE_MULT.get(btype, 0.90)
    opp_score = round(min(100.0, max(0.0, raw * type_mult)), 2)

    # ── Reasoning + signals ──────────────────────────────────────────────────
    signals: list[str] = []
    if iip < 30 and pfs > 60:
        signals.append(f"Strong product fit ({pfs:.0f}) but only {iip:.0f}% India import probability — clear opening")
    if country_score >= 80:
        signals.append(f"{cc} is a top-tier market for Moradabad brass exports")
    if seasonal >= 1.15:
        signals.append(f"Prime ordering season (month {month}) — buyers actively sourcing now")
    if nis > 65:
        signals.append("Recently started importing — establishing supplier relationships")
    if gts > 70:
        signals.append(f"High growth trend ({gts:.0f}/100) — expanding sourcing budget")
    if vol >= 20_000_000:
        signals.append(f"Estimated annual volume ${vol/1e6:.1f}M — significant order potential")
    if btype in ("hospitality", "sourcing_company"):
        signals.append(f"Buyer type '{btype}' has highest brass import affinity")

    if not signals:
        signals.append(f"Composite lead score {composite:.0f} qualifies for priority outreach")

    reasoning = (
        f"Opportunity score {opp_score:.0f}/100 — "
        + "; ".join(signals[:3])
    )

    # ── Action recommendation ────────────────────────────────────────────────
    if iip < 25 and pfs > 55:
        action = "initial_contact"
        template = "initial_introduction"
    elif iip > 30 and nis > 60:
        action = "emerging_opportunity"
        template = "emerging_importer"
    elif seasonal >= 1.20:
        action = "seasonal_campaign"
        template = "trade_fair"
    else:
        action = "initial_contact"
        template = "initial_introduction"

    return OpportunityRank(
        canonical_id=int(_g(buyer, "id") or _g(buyer, "canonical_id") or 0),
        opportunity_score=opp_score,
        composite_lead_score=composite,
        india_import_probability=iip,
        competitive_gap_score=round(competitive_gap, 2),
        market_timing_score=round(timing, 2),
        country_market_score=round(country_score, 2),
        estimated_value_usd=vol,
        reasoning=reasoning,
        key_signals=signals,
        action_type=action,
        email_template=template,
    )
