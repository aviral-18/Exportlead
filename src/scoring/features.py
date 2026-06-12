"""
Feature extraction layer.
Converts a CanonicalBuyer ORM row into a flat feature dict
consumed by every individual scorer.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Optional

# ── Constants ──────────────────────────────────────────────────────────────────

BRASS_HS_CODES: set[str] = {
    "741810", "741820", "741900",
    "830600", "830610", "830620",
    "691300", "691390",
    "940540", "940550",
    "630260", "630291",  # textiles / hotel linen (hospitality cross-sell)
}

# Sources that indicate India trade specifically
INDIA_SOURCES: set[str] = {
    "india_export_data", "tradeindia", "indiamart",
    "ihgf", "volza",  # volza is used by Indian exporters to find buyers
}

# Sources that indicate active RFQ / open sourcing
RFQ_SOURCES: set[str] = {
    "alibaba", "global_sources", "tradekey", "ec21",
    "eworldtrade", "tradeindia", "indiamart", "made_in_china",
}

# Countries that are historically top importers of Indian brass/crafts
INDIA_BUYER_COUNTRIES: set[str] = {
    "US", "GB", "DE", "FR", "AU", "CA", "NL", "BE", "AE",
    "SA", "KW", "QA", "IT", "ES", "CH", "SE", "DK", "NO",
    "SG", "JP", "ZA", "BR",
}

BRASS_KEYWORDS: list[str] = [
    "brass", "metal", "handicraft", "decor", "statue", "figurine",
    "giftware", "hotelware", "religious", "artifact", "garden decor",
    "candleholder", "lamp", "vase", "ornament", "craft", "idol",
    "temple", "pooja", "incense", "planter", "tray", "bowl",
]

# Ideal buyer types for Moradabad brass
IDEAL_BUYER_TYPES: set[str] = {
    "retailer", "distributor", "wholesaler",
    "hospitality", "sourcing_company",
}


def extract(buyer) -> dict[str, Any]:
    """
    Build feature dict from a CanonicalBuyer or dict-like object.
    Works with both SQLAlchemy models and plain dicts.
    """
    def _f(attr, default=None):
        if isinstance(buyer, dict):
            return buyer.get(attr, default)
        return getattr(buyer, attr, default)

    today = date.today()

    # ── Dates ──────────────────────────────────────────────────────────────────
    last_import = _f("last_import_date")
    first_import = _f("first_import_date")

    if isinstance(last_import, str):
        try:
            last_import = date.fromisoformat(last_import)
        except (ValueError, TypeError):
            last_import = None

    if isinstance(first_import, str):
        try:
            first_import = date.fromisoformat(first_import)
        except (ValueError, TypeError):
            first_import = None

    recency_days = (today - last_import).days if last_import else 999
    first_import_days = (today - first_import).days if first_import else 9999

    # ── Lists ──────────────────────────────────────────────────────────────────
    hs_codes: list[str] = _f("hs_codes") or []
    if isinstance(hs_codes, str):
        import json
        try:
            hs_codes = json.loads(hs_codes)
        except Exception:
            hs_codes = []

    categories: list[str] = _f("product_categories") or []
    if isinstance(categories, str):
        import json
        try:
            categories = json.loads(categories)
        except Exception:
            categories = []

    data_sources: list[str] = _f("data_sources") or []
    if isinstance(data_sources, str):
        import json
        try:
            data_sources = json.loads(data_sources)
        except Exception:
            data_sources = []

    # ── Numeric ───────────────────────────────────────────────────────────────
    volume = float(_f("estimated_annual_volume_usd") or 0)
    total_shipments = int(_f("total_shipments") or 0)
    source_count = int(_f("source_count") or len(data_sources) or 1)
    confidence = float(_f("confidence_score") or 0.5)

    # ── Category text ─────────────────────────────────────────────────────────
    cat_text = " ".join(str(c) for c in categories).lower()
    brass_keyword_hits = sum(1 for kw in BRASS_KEYWORDS if kw in cat_text)
    hs_brass_overlap = len(set(hs_codes) & BRASS_HS_CODES)

    india_source_count = len(set(data_sources) & INDIA_SOURCES)
    rfq_source_count = len(set(data_sources) & RFQ_SOURCES)
    country_code = (_f("country_code") or "").upper()
    buyer_type = _f("buyer_type") or "unknown"
    import_frequency = _f("import_frequency") or "unknown"

    # ── Volume normalisation (log scale 0-1 over $1K → $500M) ────────────────
    vol_log_norm = 0.0
    if volume > 1_000:
        vol_log_norm = min(1.0, (math.log10(volume) - 3) / (math.log10(500_000_000) - 3))

    return {
        # Identity
        "buyer_type": buyer_type,
        "country_code": country_code,
        "import_frequency": import_frequency,
        # Dates
        "recency_days": recency_days,
        "first_import_days": first_import_days,
        # Trade volume
        "annual_volume_usd": volume,
        "vol_log_norm": vol_log_norm,
        "total_shipments": total_shipments,
        # Source signals
        "source_count": source_count,
        "data_sources": data_sources,
        "india_source_count": india_source_count,
        "rfq_source_count": rfq_source_count,
        "from_india_buyer_country": country_code in INDIA_BUYER_COUNTRIES,
        # Product alignment
        "hs_codes": hs_codes,
        "hs_brass_overlap": hs_brass_overlap,
        "brass_keyword_hits": brass_keyword_hits,
        # Quality
        "confidence_score": confidence,
    }
