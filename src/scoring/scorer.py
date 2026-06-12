"""
Six scoring dimensions + composite.
Every function takes a feature dict (from features.extract()) and returns float 0-100.
All scoring is deterministic rule-based — no ML training required.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from src.scoring.features import (
    IDEAL_BUYER_TYPES, INDIA_BUYER_COUNTRIES, extract,
)

# ── Weight table for composite ─────────────────────────────────────────────────
COMPOSITE_WEIGHTS: dict[str, float] = {
    "import_activity":          0.25,
    "product_fit":              0.25,
    "india_import_probability": 0.20,
    "growth_trend":             0.15,
    "supplier_switch":          0.10,
    "new_importer":             0.05,
}


# ── 1. India Import Probability ────────────────────────────────────────────────

def india_import_probability(f: dict) -> float:
    """
    Probability (0-100) that this buyer is already importing from India
    or is a strong candidate to do so.
    """
    score = 20.0  # base prior

    # Direct India data source signal (strongest)
    india_src = f["india_source_count"]
    if india_src >= 3:
        score += 45
    elif india_src == 2:
        score += 35
    elif india_src == 1:
        score += 22

    # HS code alignment with India's top export codes
    hs_overlap = f["hs_brass_overlap"]
    score += min(18, hs_overlap * 4)

    # Keyword hits (handicraft, brass, religious, etc.)
    score += min(12, f["brass_keyword_hits"] * 2)

    # Buyer type natural fit for India sourcing
    bt_bonus = {
        "hospitality": 9, "retailer": 7, "distributor": 8,
        "wholesaler": 6, "sourcing_company": 11, "importer": 5,
        "oem": 9, "procurement_agency": 4,
    }.get(f["buyer_type"], 0)
    score += bt_bonus

    # Country historically buys from India
    if f["from_india_buyer_country"]:
        score += 5

    # Government penalty
    if f["buyer_type"] == "government":
        score -= 18

    # High confidence data = more reliable India signal
    score *= (0.85 + 0.15 * f["confidence_score"])

    return round(min(100.0, max(0.0, score)), 2)


# ── 2. Supplier Switch Probability ────────────────────────────────────────────

def supplier_switch_probability(f: dict) -> float:
    """
    Probability (0-100) that this buyer is open to switching / adding
    a new supplier from India.
    """
    score = 12.0  # base

    # Active RFQ / open sourcing platforms
    rfq = f["rfq_source_count"]
    if rfq >= 4:
        score += 28
    elif rfq >= 2:
        score += 20
    elif rfq == 1:
        score += 10

    # Stale last import (buyer may be looking)
    recency = f["recency_days"]
    if recency > 730:
        score += 22
    elif recency > 365:
        score += 15
    elif recency > 180:
        score += 8
    elif recency > 90:
        score += 3

    # New / small importer — less locked in to existing suppliers
    shipments = f["total_shipments"]
    if shipments < 5:
        score += 22
    elif shipments < 15:
        score += 14
    elif shipments < 30:
        score += 7

    # Multi-source presence = actively evaluating options
    sc = f["source_count"]
    if sc >= 5:
        score += 14
    elif sc >= 3:
        score += 8
    elif sc >= 2:
        score += 4

    # High-volume buyers actively manage supply chain
    vol = f["annual_volume_usd"]
    if vol > 20_000_000:
        score += 9
    elif vol > 5_000_000:
        score += 6
    elif vol > 1_000_000:
        score += 3

    return round(min(100.0, max(0.0, score)), 2)


# ── 3. Product Fit Score ──────────────────────────────────────────────────────

def product_fit_score(f: dict) -> float:
    """
    How well does this buyer's product profile match Moradabad brass / metal decor?
    """
    score = 15.0  # base

    # HS code direct match (most reliable signal)
    hs_overlap = f["hs_brass_overlap"]
    score += min(38, hs_overlap * 9)

    # Keyword alignment in categories
    kw_hits = f["brass_keyword_hits"]
    score += min(28, kw_hits * 4)

    # Buyer type alignment
    bt = f["buyer_type"]
    if bt in IDEAL_BUYER_TYPES:
        score += 16
    elif bt in {"importer", "oem"}:
        score += 10
    elif bt == "procurement_agency":
        score += 7
    elif bt == "government":
        score += 2

    # Volume tier (tiny buyers are low priority)
    vol = f["annual_volume_usd"]
    if vol > 50_000_000:
        score += 5
    elif vol > 5_000_000:
        score += 3
    elif vol < 50_000:
        score -= 8

    # Confidence bonus
    score *= (0.9 + 0.1 * f["confidence_score"])

    return round(min(100.0, max(0.0, score)), 2)


# ── 4. Growth Trend Score ─────────────────────────────────────────────────────

def growth_trend_score(f: dict) -> float:
    """
    Is this buyer's import activity trending upward?
    Proxy using recency, frequency, source diversity, and volume tier.
    """
    score = 35.0  # neutral baseline

    # Import frequency
    freq_bonus = {
        "daily": 28, "weekly": 25, "monthly": 18,
        "quarterly": 8, "annual": 3, "sporadic": -6, "unknown": 0,
    }.get(f["import_frequency"], 0)
    score += freq_bonus

    # Recency
    recency = f["recency_days"]
    if recency < 15:
        score += 22
    elif recency < 30:
        score += 16
    elif recency < 90:
        score += 10
    elif recency < 180:
        score += 4
    elif recency < 365:
        score -= 5
    elif recency < 730:
        score -= 14
    else:
        score -= 22

    # Source diversity (growing buyers appear on more platforms)
    sc = f["source_count"]
    score += min(12, (sc - 1) * 3)

    # Volume tier
    vol = f["annual_volume_usd"]
    if vol > 100_000_000:
        score += 10
    elif vol > 20_000_000:
        score += 7
    elif vol > 5_000_000:
        score += 4
    elif vol > 1_000_000:
        score += 2
    elif vol < 100_000:
        score -= 5

    # High shipment count = established, growing relationship
    shipments = f["total_shipments"]
    if shipments > 150:
        score += 6
    elif shipments > 50:
        score += 3

    return round(min(100.0, max(0.0, score)), 2)


# ── 5. New Importer Score ─────────────────────────────────────────────────────

def new_importer_score(f: dict) -> float:
    """
    Is this a freshly active buyer we should reach first?
    High score = newly active = high urgency to contact.
    """
    first_days = f["first_import_days"]

    # Age-based base score
    if first_days < 90:
        score = 100.0
    elif first_days < 180:
        score = 88.0
    elif first_days < 365:
        score = 72.0
    elif first_days < 730:
        score = 52.0
    elif first_days < 1095:
        score = 34.0
    elif first_days < 1825:
        score = 20.0
    else:
        score = 10.0

    # Few shipments = still new relationship
    shipments = f["total_shipments"]
    if shipments < 3:
        score += 15
    elif shipments < 8:
        score += 9
    elif shipments < 20:
        score += 4

    # From RFQ source = actively looking now
    if f["rfq_source_count"] >= 1:
        score += 8

    # Cap: if first import is very old and shipments are many, not a new importer
    if first_days > 1825 and shipments > 50:
        score = min(score, 18.0)

    return round(min(100.0, max(0.0, score)), 2)


# ── 6. Import Activity Score ──────────────────────────────────────────────────

def import_activity_score(f: dict) -> float:
    """
    Overall import activity level — how intensely is this buyer importing?
    """
    score = 0.0

    # Volume (log-normalised, contributes up to 30 pts)
    score += f["vol_log_norm"] * 30

    # Frequency (up to 25 pts)
    freq_pts = {
        "daily": 25, "weekly": 25, "monthly": 20,
        "quarterly": 12, "annual": 6, "sporadic": 3, "unknown": 5,
    }.get(f["import_frequency"], 5)
    score += freq_pts

    # Shipment count (up to 20 pts)
    score += min(20, f["total_shipments"] * 0.12)

    # Platform diversity (up to 15 pts)
    score += min(15, f["source_count"] * 3)

    # Recency (up to 10 pts)
    recency = f["recency_days"]
    if recency < 30:
        score += 10
    elif recency < 90:
        score += 7
    elif recency < 180:
        score += 4
    elif recency < 365:
        score += 2

    return round(min(100.0, max(0.0, score)), 2)


# ── Composite ─────────────────────────────────────────────────────────────────

@dataclass
class LeadScoreResult:
    india_import_probability: float
    supplier_switch_probability: float
    product_fit: float
    growth_trend: float
    new_importer: float
    import_activity: float
    composite: float

    def to_dict(self) -> dict:
        return {
            "india_import_probability": self.india_import_probability,
            "supplier_switch_probability": self.supplier_switch_probability,
            "product_fit": self.product_fit,
            "growth_trend": self.growth_trend,
            "new_importer": self.new_importer,
            "import_activity": self.import_activity,
            "composite": self.composite,
        }

    @property
    def tier(self) -> str:
        if self.composite >= 80:
            return "A"
        if self.composite >= 65:
            return "B"
        if self.composite >= 50:
            return "C"
        if self.composite >= 35:
            return "D"
        return "F"

    @property
    def priority_label(self) -> str:
        return {
            "A": "Hot Lead",
            "B": "Warm Lead",
            "C": "Prospect",
            "D": "Watch",
            "F": "Cold",
        }[self.tier]


def score_buyer(buyer) -> LeadScoreResult:
    """Main entry point: accepts ORM object or dict, returns LeadScoreResult."""
    f = extract(buyer)

    iip = india_import_probability(f)
    ssp = supplier_switch_probability(f)
    pfs = product_fit_score(f)
    gts = growth_trend_score(f)
    nis = new_importer_score(f)
    ias = import_activity_score(f)

    composite = (
        ias  * COMPOSITE_WEIGHTS["import_activity"]
        + pfs * COMPOSITE_WEIGHTS["product_fit"]
        + iip * COMPOSITE_WEIGHTS["india_import_probability"]
        + gts * COMPOSITE_WEIGHTS["growth_trend"]
        + ssp * COMPOSITE_WEIGHTS["supplier_switch"]
        + nis * COMPOSITE_WEIGHTS["new_importer"]
    )

    return LeadScoreResult(
        india_import_probability=iip,
        supplier_switch_probability=ssp,
        product_fit=pfs,
        growth_trend=gts,
        new_importer=nis,
        import_activity=ias,
        composite=round(composite, 2),
    )
