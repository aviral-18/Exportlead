"""
Reference rate tables for the export profitability calculator.
All INR values at 83.5 INR/USD exchange rate.
Update periodically from RBI / freight forwarder quotes.
"""
from __future__ import annotations

# ── Exchange ──────────────────────────────────────────────────────────────────
INR_PER_USD: float = 83.5

# ── Brass product categories ──────────────────────────────────────────────────
# cost_inr_per_kg = raw_material + manufacturing + finishing + packaging
PRODUCT_COSTS: dict[str, dict] = {
    "decorative": {
        "label": "Decorative Items (vases, bowls, figurines)",
        "hs_codes": ["830600", "830610", "830620"],
        "raw_material_inr_kg": 390,
        "manufacturing_inr_kg": 210,
        "finishing_inr_kg": 110,   # lacquer, polish
        "packaging_inr_kg": 30,
        "avg_pieces_per_kg": 2.5,
    },
    "religious": {
        "label": "Religious & Temple Items (idols, diyas, pooja sets)",
        "hs_codes": ["830600", "691300"],
        "raw_material_inr_kg": 410,
        "manufacturing_inr_kg": 230,
        "finishing_inr_kg": 85,
        "packaging_inr_kg": 28,
        "avg_pieces_per_kg": 3.0,
    },
    "hospitality": {
        "label": "Hotel & Hospitality Ware (lamps, candle holders, trays)",
        "hs_codes": ["940540", "940550", "830600"],
        "raw_material_inr_kg": 400,
        "manufacturing_inr_kg": 215,
        "finishing_inr_kg": 125,
        "packaging_inr_kg": 35,
        "avg_pieces_per_kg": 1.8,
    },
    "garden": {
        "label": "Garden Decor (planters, fountains, lanterns)",
        "hs_codes": ["830600", "830620"],
        "raw_material_inr_kg": 365,
        "manufacturing_inr_kg": 185,
        "finishing_inr_kg": 65,
        "packaging_inr_kg": 25,
        "avg_pieces_per_kg": 1.2,
    },
    "gifting": {
        "label": "Premium Gifting (engraved, gift-boxed sets)",
        "hs_codes": ["830600", "830610"],
        "raw_material_inr_kg": 420,
        "manufacturing_inr_kg": 240,
        "finishing_inr_kg": 135,
        "packaging_inr_kg": 45,
        "avg_pieces_per_kg": 4.0,
    },
    "industrial": {
        "label": "Industrial / OEM Fittings",
        "hs_codes": ["741810", "741820", "741900"],
        "raw_material_inr_kg": 355,
        "manufacturing_inr_kg": 175,
        "finishing_inr_kg": 45,
        "packaging_inr_kg": 20,
        "avg_pieces_per_kg": 5.0,
    },
    "statues": {
        "label": "Statues & Sculptures (large pieces)",
        "hs_codes": ["830600", "691390"],
        "raw_material_inr_kg": 380,
        "manufacturing_inr_kg": 280,
        "finishing_inr_kg": 150,
        "packaging_inr_kg": 40,
        "avg_pieces_per_kg": 0.8,
    },
}

# ── Freight rates (USD/kg, sea FCL ≥ 1000 kg; LCL for smaller) ───────────────
# Format: {country_code: {fcl_usd_kg, lcl_usd_kg, air_usd_kg, transit_days_sea}}
FREIGHT_RATES: dict[str, dict] = {
    # North America
    "US": {"fcl": 1.85, "lcl": 3.60, "air": 8.50, "sea_days": 26, "region": "North America"},
    "CA": {"fcl": 2.00, "lcl": 3.80, "air": 9.00, "sea_days": 28, "region": "North America"},
    "MX": {"fcl": 2.10, "lcl": 4.00, "air": 9.50, "sea_days": 30, "region": "North America"},
    # Europe
    "DE": {"fcl": 1.55, "lcl": 3.10, "air": 7.20, "sea_days": 22, "region": "Europe"},
    "GB": {"fcl": 1.65, "lcl": 3.30, "air": 7.50, "sea_days": 23, "region": "Europe"},
    "FR": {"fcl": 1.55, "lcl": 3.10, "air": 7.20, "sea_days": 22, "region": "Europe"},
    "NL": {"fcl": 1.50, "lcl": 3.00, "air": 7.00, "sea_days": 21, "region": "Europe"},
    "BE": {"fcl": 1.55, "lcl": 3.10, "air": 7.20, "sea_days": 21, "region": "Europe"},
    "IT": {"fcl": 1.60, "lcl": 3.20, "air": 7.30, "sea_days": 22, "region": "Europe"},
    "ES": {"fcl": 1.65, "lcl": 3.30, "air": 7.40, "sea_days": 23, "region": "Europe"},
    "SE": {"fcl": 1.70, "lcl": 3.40, "air": 7.60, "sea_days": 24, "region": "Europe"},
    "DK": {"fcl": 1.70, "lcl": 3.40, "air": 7.60, "sea_days": 24, "region": "Europe"},
    "NO": {"fcl": 1.75, "lcl": 3.50, "air": 7.80, "sea_days": 25, "region": "Europe"},
    "CH": {"fcl": 1.70, "lcl": 3.40, "air": 7.60, "sea_days": 23, "region": "Europe"},
    "PL": {"fcl": 1.65, "lcl": 3.30, "air": 7.50, "sea_days": 23, "region": "Europe"},
    # Middle East
    "AE": {"fcl": 0.85, "lcl": 1.90, "air": 4.80, "sea_days": 8, "region": "Middle East"},
    "SA": {"fcl": 0.90, "lcl": 2.00, "air": 5.00, "sea_days": 9, "region": "Middle East"},
    "KW": {"fcl": 0.90, "lcl": 2.00, "air": 5.00, "sea_days": 9, "region": "Middle East"},
    "QA": {"fcl": 0.90, "lcl": 2.00, "air": 5.00, "sea_days": 9, "region": "Middle East"},
    # Asia Pacific
    "AU": {"fcl": 2.60, "lcl": 4.60, "air": 10.50, "sea_days": 18, "region": "Asia Pacific"},
    "NZ": {"fcl": 2.90, "lcl": 5.00, "air": 11.50, "sea_days": 22, "region": "Asia Pacific"},
    "SG": {"fcl": 1.05, "lcl": 2.20, "air": 5.20, "sea_days": 9, "region": "Asia Pacific"},
    "JP": {"fcl": 1.55, "lcl": 3.10, "air": 7.20, "sea_days": 14, "region": "Asia Pacific"},
    "KR": {"fcl": 1.45, "lcl": 2.90, "air": 6.80, "sea_days": 12, "region": "Asia Pacific"},
    "MY": {"fcl": 1.10, "lcl": 2.30, "air": 5.50, "sea_days": 8, "region": "Asia Pacific"},
    # South America
    "BR": {"fcl": 2.80, "lcl": 5.00, "air": 11.00, "sea_days": 32, "region": "South America"},
    "AR": {"fcl": 3.00, "lcl": 5.50, "air": 12.00, "sea_days": 35, "region": "South America"},
    # Africa
    "ZA": {"fcl": 2.20, "lcl": 4.20, "air": 9.50, "sea_days": 18, "region": "Africa"},
    "NG": {"fcl": 2.50, "lcl": 4.80, "air": 10.50, "sea_days": 20, "region": "Africa"},
    "KE": {"fcl": 2.30, "lcl": 4.40, "air": 10.00, "sea_days": 16, "region": "Africa"},
    # Default fallback
    "_DEFAULT": {"fcl": 2.20, "lcl": 4.00, "air": 9.50, "sea_days": 25, "region": "Other"},
}

# ── Export duty & incentive rates ─────────────────────────────────────────────
# RoDTEP rates for brass HS codes (approx, verify with DGFT schedule)
RODTEP_RATE: float = 0.034       # 3.4% of FOB
DUTY_DRAWBACK_RATE: float = 0.022  # 2.2% of FOB (all-industry rates)
IGST_REFUND_RATE: float = 0.10   # 10% of raw material cost (input credit)

# ── Fixed export overhead per shipment (INR) ─────────────────────────────────
EXPORT_DOC_COST_INR: float = 6_500    # Customs invoice, packing list, shipping bill
CERTIFICATE_ORIGIN_INR: float = 2_500
FUMIGATION_INR: float = 4_000
PORT_HANDLING_INR: float = 8_000

# ── Variable rates (% of FOB value) ──────────────────────────────────────────
QUALITY_INSPECTION_RATE: float = 0.015    # 1.5%
EXPORT_AGENT_COMMISSION: float = 0.02     # 2%
BANK_CHARGE_RATE: float = 0.008          # 0.8% (TT; LC adds ~0.5% more)
MARINE_INSURANCE_RATE: float = 0.004     # 0.4% of CIF
INLAND_FREIGHT_INR_PER_KG: float = 4.5  # Moradabad -> Nhava Sheva / ICD Tughlakabad

# ── Standard margin targets ───────────────────────────────────────────────────
TARGET_GROSS_MARGIN: float = 0.28        # 28% gross margin target
MIN_GROSS_MARGIN: float = 0.18           # 18% floor
INCOME_TAX_RATE: float = 0.25            # effective rate for export income
