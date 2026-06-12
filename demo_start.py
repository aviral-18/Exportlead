"""
BrassExport Intelligence -- self-contained demo.
No PostgreSQL, no Redis, no external services needed.
Modules: Buyer Intelligence + AI Lead Scoring + CRM + Export Profitability Calculator.

Run:  python demo_start.py
Open: http://localhost:8000/docs
"""
from __future__ import annotations

import csv
import io
import json
import math
import random
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer,
    Numeric, String, Text, func, or_, select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# ── Database ──────────────────────────────────────────────────────────────────
SQLITE_URL = "sqlite+aiosqlite:///./brass_demo.db"
engine = create_async_engine(SQLITE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


# ══════════════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════════════

class Buyer(Base):
    __tablename__ = "buyers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False)
    company_name = Column(Text, nullable=False)
    company_name_normalized = Column(Text)
    country_code = Column(String(3))
    country_name = Column(Text)
    city = Column(Text)
    website = Column(Text)
    website_domain = Column(Text)
    email_json = Column(Text, default="[]")
    phone_json = Column(Text, default="[]")
    product_categories_json = Column(Text, default="[]")
    hs_codes_json = Column(Text, default="[]")
    buyer_type = Column(String(50))
    import_frequency = Column(String(50))
    estimated_annual_volume_usd = Column(Numeric(20, 2))
    last_import_date = Column(Date)
    first_import_date = Column(Date)
    total_shipments = Column(Integer)
    source_count = Column(Integer, default=1)
    data_sources_json = Column(Text, default="[]")
    confidence_score = Column(Numeric(5, 4), default=0.5)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class BuyerScore(Base):
    __tablename__ = "buyer_scores"
    id = Column(Integer, primary_key=True, autoincrement=True)
    buyer_id = Column(Integer, nullable=False, unique=True)
    india_import_probability = Column(Float)
    supplier_switch_probability = Column(Float)
    product_fit_score = Column(Float)
    growth_trend_score = Column(Float)
    new_importer_score = Column(Float)
    import_activity_score = Column(Float)
    composite_score = Column(Float)
    tier = Column(String(1))
    scored_at = Column(DateTime, default=datetime.utcnow)


class Lead(Base):
    __tablename__ = "crm_leads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False)
    canonical_buyer_id = Column(Integer)
    company_name = Column(Text, nullable=False)
    country_code = Column(String(3))
    country_name = Column(String(128))
    contact_name = Column(Text)
    contact_title = Column(String(128))
    contact_email = Column(Text)
    contact_phone = Column(String(50))
    contact_linkedin = Column(Text)
    contact_whatsapp = Column(String(50))
    status = Column(String(32), default="new")
    source = Column(String(32), default="database")
    priority = Column(String(16), default="warm")
    assigned_to = Column(String(128))
    product_interest_json = Column(Text, default="{}")
    estimated_value_usd = Column(Float)
    currency = Column(String(3), default="USD")
    last_contact_date = Column(Date)
    expected_close_date = Column(Date)
    notes_count = Column(Integer, default=0)
    interactions_count = Column(Integer, default=0)
    open_followups = Column(Integer, default=0)
    tags_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Contact(Base):
    __tablename__ = "crm_contacts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, nullable=False)
    name = Column(Text, nullable=False)
    title = Column(String(128))
    department = Column(String(128))
    email = Column(Text)
    phone = Column(String(50))
    whatsapp = Column(String(50))
    linkedin_url = Column(Text)
    is_primary = Column(Boolean, default=False)
    preferred_contact_method = Column(String(20))
    language = Column(String(10))
    do_not_contact = Column(Boolean, default=False)
    last_contacted_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ContactHistory(Base):
    __tablename__ = "crm_contact_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, nullable=False)
    contact_id = Column(Integer)
    opportunity_id = Column(Integer)
    interaction_type = Column(String(32), nullable=False)
    direction = Column(String(10), default="outbound")
    subject = Column(Text)
    notes = Column(Text)
    outcome = Column(String(32))
    next_action = Column(Text)
    duration_minutes = Column(Integer)
    interacted_by = Column(String(128))
    interacted_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Note(Base):
    __tablename__ = "crm_notes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, nullable=False)
    opportunity_id = Column(Integer)
    contact_id = Column(Integer)
    content = Column(Text, nullable=False)
    note_type = Column(String(32), default="general")
    created_by = Column(String(128))
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class FollowUp(Base):
    __tablename__ = "crm_followups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, nullable=False)
    opportunity_id = Column(Integer)
    contact_id = Column(Integer)
    title = Column(Text, nullable=False)
    description = Column(Text)
    follow_up_type = Column(String(32), default="follow_up")
    priority = Column(String(16), default="medium")
    assigned_to = Column(String(128))
    scheduled_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    is_completed = Column(Boolean, default=False)
    outcome_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Opportunity(Base):
    __tablename__ = "crm_opportunities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False)
    lead_id = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)
    stage = Column(String(32), default="prospecting")
    probability_pct = Column(Integer, default=20)
    estimated_value_usd = Column(Float)
    currency = Column(String(3), default="USD")
    products_json = Column(Text, default="[]")
    quantity_kg = Column(Float)
    incoterms = Column(String(10))
    payment_terms = Column(String(256))
    expected_close_date = Column(Date)
    actual_close_date = Column(Date)
    won_at = Column(DateTime)
    lost_at = Column(DateTime)
    lost_reason = Column(Text)
    assigned_to = Column(String(128))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Sample(Base):
    __tablename__ = "crm_samples"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_number = Column(String(64), unique=True, nullable=False)
    lead_id = Column(Integer, nullable=False)
    opportunity_id = Column(Integer)
    products_json = Column(Text, default="[]")
    quantity_pieces = Column(Integer)
    weight_kg = Column(Float)
    courier = Column(String(64))
    tracking_number = Column(String(128))
    sent_date = Column(Date)
    estimated_delivery = Column(Date)
    delivered_date = Column(Date)
    status = Column(String(32), default="preparing")
    cost_inr = Column(Float)
    cost_usd = Column(Float)
    paid_by_buyer = Column(Boolean, default=False)
    feedback = Column(Text)
    feedback_date = Column(Date)
    approved_for_bulk = Column(Boolean)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Quotation(Base):
    __tablename__ = "crm_quotations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    quotation_number = Column(String(64), unique=True, nullable=False)
    lead_id = Column(Integer, nullable=False)
    opportunity_id = Column(Integer)
    line_items_json = Column(Text, default="[]")
    currency = Column(String(3), default="USD")
    total_value = Column(Float)
    incoterms = Column(String(10), default="FOB")
    payment_terms = Column(String(256))
    validity_days = Column(Integer, default=30)
    delivery_weeks = Column(Integer)
    port_of_loading = Column(String(128))
    port_of_discharge = Column(String(128))
    packing_details = Column(Text)
    special_terms = Column(Text)
    status = Column(String(32), default="draft")
    sent_at = Column(DateTime)
    valid_until = Column(Date)
    accepted_at = Column(DateTime)
    rejected_at = Column(DateTime)
    rejection_reason = Column(Text)
    profitability_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class PurchaseOrder(Base):
    __tablename__ = "crm_purchase_orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    po_number = Column(String(128), nullable=False)
    our_reference = Column(String(64), unique=True, nullable=False)
    lead_id = Column(Integer, nullable=False)
    opportunity_id = Column(Integer)
    quotation_id = Column(Integer)
    line_items_json = Column(Text, default="[]")
    currency = Column(String(3), default="USD")
    total_value = Column(Float)
    advance_pct = Column(Float)
    advance_amount = Column(Float)
    advance_received_date = Column(Date)
    balance_amount = Column(Float)
    balance_due_date = Column(Date)
    balance_received_date = Column(Date)
    payment_terms = Column(String(256))
    lc_number = Column(String(128))
    incoterms = Column(String(10), default="FOB")
    shipping_port = Column(String(128))
    destination_port = Column(String(128))
    country_of_destination = Column(String(3))
    bl_number = Column(String(128))
    container_number = Column(String(64))
    production_status = Column(String(32), default="pending")
    expected_production_days = Column(Integer)
    production_start_date = Column(Date)
    production_end_date = Column(Date)
    shipment_date = Column(Date)
    delivery_date = Column(Date)
    status = Column(String(32), default="new")
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDED AI SCORING (no src imports)
# ══════════════════════════════════════════════════════════════════════════════

BRASS_HS_CODES = {"741810", "741820", "741900", "830600", "830610", "830620",
                  "691300", "691390", "940540", "940550", "630260", "630291"}
INDIA_SOURCES = {"india_export_data", "tradeindia", "indiamart", "ihgf", "volza"}
RFQ_SOURCES = {"alibaba", "global_sources", "tradekey", "ec21",
               "eworldtrade", "tradeindia", "indiamart", "made_in_china"}
INDIA_BUYER_COUNTRIES = {
    "US", "GB", "DE", "FR", "AU", "CA", "NL", "BE", "AE",
    "SA", "KW", "QA", "IT", "ES", "CH", "SE", "DK", "NO",
    "SG", "JP", "ZA", "BR",
}
BRASS_KEYWORDS = [
    "brass", "metal", "handicraft", "decor", "statue", "figurine",
    "giftware", "hotelware", "religious", "artifact", "garden decor",
    "candleholder", "lamp", "vase", "ornament", "craft", "idol",
]
IDEAL_BUYER_TYPES = {"retailer", "distributor", "wholesaler", "hospitality", "sourcing_company"}
COMPOSITE_WEIGHTS = {
    "import_activity": 0.25, "product_fit": 0.25,
    "india_import_probability": 0.20, "growth_trend": 0.15,
    "supplier_switch": 0.10, "new_importer": 0.05,
}


def _extract(buyer: Buyer) -> dict[str, Any]:
    today = date.today()
    last_import = buyer.last_import_date
    first_import = buyer.first_import_date
    recency_days = (today - last_import).days if last_import else 999
    first_import_days = (today - first_import).days if first_import else 9999
    hs_codes = json.loads(buyer.hs_codes_json or "[]")
    categories = json.loads(buyer.product_categories_json or "[]")
    data_sources = json.loads(buyer.data_sources_json or "[]")
    volume = float(buyer.estimated_annual_volume_usd or 0)
    cat_text = " ".join(str(c) for c in categories).lower()
    vol_log_norm = 0.0
    if volume > 1_000:
        vol_log_norm = min(1.0, (math.log10(volume) - 3) / (math.log10(500_000_000) - 3))
    return {
        "buyer_type": buyer.buyer_type or "unknown",
        "country_code": (buyer.country_code or "").upper(),
        "import_frequency": buyer.import_frequency or "unknown",
        "recency_days": recency_days,
        "first_import_days": first_import_days,
        "annual_volume_usd": volume,
        "vol_log_norm": vol_log_norm,
        "total_shipments": int(buyer.total_shipments or 0),
        "source_count": int(buyer.source_count or len(data_sources) or 1),
        "data_sources": data_sources,
        "india_source_count": len(set(data_sources) & INDIA_SOURCES),
        "rfq_source_count": len(set(data_sources) & RFQ_SOURCES),
        "from_india_buyer_country": (buyer.country_code or "").upper() in INDIA_BUYER_COUNTRIES,
        "hs_codes": hs_codes,
        "hs_brass_overlap": len(set(hs_codes) & BRASS_HS_CODES),
        "brass_keyword_hits": sum(1 for kw in BRASS_KEYWORDS if kw in cat_text),
        "confidence_score": float(buyer.confidence_score or 0.5),
    }


def _india_import_probability(f: dict) -> float:
    score = 20.0
    india_src = f["india_source_count"]
    score += 45 if india_src >= 3 else (35 if india_src == 2 else (22 if india_src == 1 else 0))
    score += min(18, f["hs_brass_overlap"] * 4)
    score += min(12, f["brass_keyword_hits"] * 2)
    score += {"hospitality": 9, "retailer": 7, "distributor": 8, "wholesaler": 6,
              "sourcing_company": 11, "importer": 5, "oem": 9}.get(f["buyer_type"], 0)
    if f["from_india_buyer_country"]:
        score += 5
    if f["buyer_type"] == "government":
        score -= 18
    score *= (0.85 + 0.15 * f["confidence_score"])
    return round(min(100.0, max(0.0, score)), 2)


def _supplier_switch_probability(f: dict) -> float:
    score = 12.0
    rfq = f["rfq_source_count"]
    score += 28 if rfq >= 4 else (20 if rfq >= 2 else (10 if rfq == 1 else 0))
    rec = f["recency_days"]
    score += 22 if rec > 730 else (15 if rec > 365 else (8 if rec > 180 else (3 if rec > 90 else 0)))
    sh = f["total_shipments"]
    score += 22 if sh < 5 else (14 if sh < 15 else (7 if sh < 30 else 0))
    sc = f["source_count"]
    score += 14 if sc >= 5 else (8 if sc >= 3 else (4 if sc >= 2 else 0))
    vol = f["annual_volume_usd"]
    score += 9 if vol > 20_000_000 else (6 if vol > 5_000_000 else (3 if vol > 1_000_000 else 0))
    return round(min(100.0, max(0.0, score)), 2)


def _product_fit_score(f: dict) -> float:
    score = 15.0
    score += min(38, f["hs_brass_overlap"] * 9)
    score += min(28, f["brass_keyword_hits"] * 4)
    bt = f["buyer_type"]
    score += 16 if bt in IDEAL_BUYER_TYPES else (10 if bt in {"importer", "oem"} else (7 if bt == "procurement_agency" else (2 if bt == "government" else 0)))
    vol = f["annual_volume_usd"]
    score += 5 if vol > 50_000_000 else (3 if vol > 5_000_000 else (-8 if vol < 50_000 else 0))
    score *= (0.9 + 0.1 * f["confidence_score"])
    return round(min(100.0, max(0.0, score)), 2)


def _growth_trend_score(f: dict) -> float:
    score = 35.0
    score += {"daily": 28, "weekly": 25, "monthly": 18, "quarterly": 8,
              "annual": 3, "sporadic": -6, "unknown": 0}.get(f["import_frequency"], 0)
    rec = f["recency_days"]
    score += (22 if rec < 15 else (16 if rec < 30 else (10 if rec < 90 else
             (4 if rec < 180 else (-5 if rec < 365 else (-14 if rec < 730 else -22))))))
    score += min(12, (f["source_count"] - 1) * 3)
    vol = f["annual_volume_usd"]
    score += 10 if vol > 100_000_000 else (7 if vol > 20_000_000 else (4 if vol > 5_000_000 else (2 if vol > 1_000_000 else (-5 if vol < 100_000 else 0))))
    sh = f["total_shipments"]
    score += 6 if sh > 150 else (3 if sh > 50 else 0)
    return round(min(100.0, max(0.0, score)), 2)


def _new_importer_score(f: dict) -> float:
    fd = f["first_import_days"]
    score = (100.0 if fd < 90 else (88.0 if fd < 180 else (72.0 if fd < 365 else
            (52.0 if fd < 730 else (34.0 if fd < 1095 else (20.0 if fd < 1825 else 10.0))))))
    sh = f["total_shipments"]
    score += 15 if sh < 3 else (9 if sh < 8 else (4 if sh < 20 else 0))
    if f["rfq_source_count"] >= 1:
        score += 8
    if fd > 1825 and sh > 50:
        score = min(score, 18.0)
    return round(min(100.0, max(0.0, score)), 2)


def _import_activity_score(f: dict) -> float:
    score = f["vol_log_norm"] * 30
    score += {"daily": 25, "weekly": 25, "monthly": 20, "quarterly": 12,
              "annual": 6, "sporadic": 3, "unknown": 5}.get(f["import_frequency"], 5)
    score += min(20, f["total_shipments"] * 0.12)
    score += min(15, f["source_count"] * 3)
    rec = f["recency_days"]
    score += (10 if rec < 30 else (7 if rec < 90 else (4 if rec < 180 else (2 if rec < 365 else 0))))
    return round(min(100.0, max(0.0, score)), 2)


def _score_tier(c: float) -> str:
    return "A" if c >= 80 else ("B" if c >= 65 else ("C" if c >= 50 else ("D" if c >= 35 else "F")))


def compute_score(buyer: Buyer) -> dict:
    f = _extract(buyer)
    iip = _india_import_probability(f)
    ssp = _supplier_switch_probability(f)
    pfs = _product_fit_score(f)
    gts = _growth_trend_score(f)
    nis = _new_importer_score(f)
    ias = _import_activity_score(f)
    composite = round(
        ias * COMPOSITE_WEIGHTS["import_activity"]
        + pfs * COMPOSITE_WEIGHTS["product_fit"]
        + iip * COMPOSITE_WEIGHTS["india_import_probability"]
        + gts * COMPOSITE_WEIGHTS["growth_trend"]
        + ssp * COMPOSITE_WEIGHTS["supplier_switch"]
        + nis * COMPOSITE_WEIGHTS["new_importer"],
        2,
    )
    return {
        "india_import_probability": iip,
        "supplier_switch_probability": ssp,
        "product_fit_score": pfs,
        "growth_trend_score": gts,
        "new_importer_score": nis,
        "import_activity_score": ias,
        "composite_score": composite,
        "tier": _score_tier(composite),
    }


async def score_all(db: AsyncSession) -> int:
    buyers_stmt = select(Buyer).where(Buyer.is_active == True)
    buyers = (await db.execute(buyers_stmt)).scalars().all()
    count = 0
    for b in buyers:
        scores = compute_score(b)
        existing = (await db.execute(
            select(BuyerScore).where(BuyerScore.buyer_id == b.id)
        )).scalar_one_or_none()
        if existing:
            for k, v in scores.items():
                setattr(existing, k, v)
            existing.scored_at = datetime.utcnow()
        else:
            db.add(BuyerScore(buyer_id=b.id, scored_at=datetime.utcnow(), **scores))
        count += 1
    await db.commit()
    return count


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDED CALCULATOR RATES (no src imports)
# ══════════════════════════════════════════════════════════════════════════════

_INR_PER_USD: float = 83.5

_PRODUCT_COSTS: dict[str, dict] = {
    "decorative": {"label": "Decorative Items", "hs_codes": ["830600", "830610", "830620"], "raw": 390, "mfg": 210, "fin": 110, "pkg": 30},
    "religious": {"label": "Religious & Temple Items", "hs_codes": ["830600", "691300"], "raw": 410, "mfg": 230, "fin": 85, "pkg": 28},
    "hospitality": {"label": "Hotel & Hospitality Ware", "hs_codes": ["940540", "940550", "830600"], "raw": 400, "mfg": 215, "fin": 125, "pkg": 35},
    "garden": {"label": "Garden Decor", "hs_codes": ["830600", "830620"], "raw": 365, "mfg": 185, "fin": 65, "pkg": 25},
    "gifting": {"label": "Premium Gifting", "hs_codes": ["830600", "830610"], "raw": 420, "mfg": 240, "fin": 135, "pkg": 45},
    "industrial": {"label": "Industrial / OEM Fittings", "hs_codes": ["741810", "741820", "741900"], "raw": 355, "mfg": 175, "fin": 45, "pkg": 20},
    "statues": {"label": "Statues & Sculptures", "hs_codes": ["830600", "691390"], "raw": 380, "mfg": 280, "fin": 150, "pkg": 40},
}

_FREIGHT_RATES: dict[str, dict] = {
    "US": {"fcl": 1.85, "lcl": 3.60, "air": 8.50, "days": 26, "region": "North America"},
    "CA": {"fcl": 2.00, "lcl": 3.80, "air": 9.00, "days": 28, "region": "North America"},
    "DE": {"fcl": 1.55, "lcl": 3.10, "air": 7.20, "days": 22, "region": "Europe"},
    "GB": {"fcl": 1.65, "lcl": 3.30, "air": 7.50, "days": 23, "region": "Europe"},
    "FR": {"fcl": 1.55, "lcl": 3.10, "air": 7.20, "days": 22, "region": "Europe"},
    "NL": {"fcl": 1.50, "lcl": 3.00, "air": 7.00, "days": 21, "region": "Europe"},
    "BE": {"fcl": 1.55, "lcl": 3.10, "air": 7.20, "days": 21, "region": "Europe"},
    "IT": {"fcl": 1.60, "lcl": 3.20, "air": 7.30, "days": 22, "region": "Europe"},
    "ES": {"fcl": 1.65, "lcl": 3.30, "air": 7.40, "days": 23, "region": "Europe"},
    "SE": {"fcl": 1.70, "lcl": 3.40, "air": 7.60, "days": 24, "region": "Europe"},
    "CH": {"fcl": 1.70, "lcl": 3.40, "air": 7.60, "days": 23, "region": "Europe"},
    "AE": {"fcl": 0.85, "lcl": 1.90, "air": 4.80, "days": 8,  "region": "Middle East"},
    "SA": {"fcl": 0.90, "lcl": 2.00, "air": 5.00, "days": 9,  "region": "Middle East"},
    "KW": {"fcl": 0.90, "lcl": 2.00, "air": 5.00, "days": 9,  "region": "Middle East"},
    "QA": {"fcl": 0.90, "lcl": 2.00, "air": 5.00, "days": 9,  "region": "Middle East"},
    "AU": {"fcl": 2.60, "lcl": 4.60, "air": 10.50, "days": 18, "region": "Asia Pacific"},
    "SG": {"fcl": 1.05, "lcl": 2.20, "air": 5.20, "days": 9,  "region": "Asia Pacific"},
    "JP": {"fcl": 1.55, "lcl": 3.10, "air": 7.20, "days": 14, "region": "Asia Pacific"},
    "KR": {"fcl": 1.45, "lcl": 2.90, "air": 6.80, "days": 12, "region": "Asia Pacific"},
    "BR": {"fcl": 2.80, "lcl": 5.00, "air": 11.00, "days": 32, "region": "South America"},
    "ZA": {"fcl": 2.20, "lcl": 4.20, "air": 9.50, "days": 18, "region": "Africa"},
    "_DEFAULT": {"fcl": 2.20, "lcl": 4.00, "air": 9.50, "days": 25, "region": "Other"},
}

_RODTEP = 0.034
_DRAWBACK = 0.022
_IGST = 0.10
_QUAL_INSP = 0.015
_AGENT_COMM = 0.02
_BANK_CHARGE = 0.008
_INSURANCE = 0.004
_INLAND_FREIGHT_PER_KG = 4.5
_FIXED_OVERHEAD_INR = 6_500 + 2_500 + 4_000 + 8_000  # docs + COO + fumigation + port
_TARGET_MARGIN = 0.28
_MIN_MARGIN = 0.18
_TAX_RATE = 0.25


def _calc_profitability(
    product_category: str,
    quantity_pieces: int,
    weight_kg: float,
    destination_country: str,
    shipping_mode: str = "sea_fcl",
    selling_price_usd: Optional[float] = None,
    include_lc: bool = False,
    inr_per_usd: float = _INR_PER_USD,
) -> dict:
    cc = _PRODUCT_COSTS.get(product_category)
    if not cc:
        raise ValueError(f"Unknown product_category '{product_category}'")
    fr = _FREIGHT_RATES.get(destination_country.upper(), _FREIGHT_RATES["_DEFAULT"])
    mode_key = {"sea_fcl": "fcl", "sea_lcl": "lcl", "air": "air"}.get(shipping_mode, "fcl")

    # Production cost
    prod_inr = (cc["raw"] + cc["mfg"] + cc["fin"] + cc["pkg"]) * weight_kg
    inland_inr = _INLAND_FREIGHT_PER_KG * weight_kg
    fixed_inr = _FIXED_OVERHEAD_INR + inland_inr
    fob_usd = (prod_inr + fixed_inr) / inr_per_usd

    # Variable costs
    qual_usd = fob_usd * _QUAL_INSP
    agent_usd = fob_usd * _AGENT_COMM
    bank_usd = fob_usd * (_BANK_CHARGE + (0.005 if include_lc else 0))
    freight_usd = fr[mode_key] * weight_kg

    cif_usd = fob_usd + qual_usd + agent_usd + bank_usd + freight_usd
    insurance_usd = cif_usd * _INSURANCE
    total_cost_usd = cif_usd + insurance_usd

    # Incentives
    fob_inr = fob_usd * inr_per_usd
    rodtep_inr = fob_inr * _RODTEP
    drawback_inr = fob_inr * _DRAWBACK
    igst_inr = (cc["raw"] * weight_kg) * _IGST
    total_incentives_usd = (rodtep_inr + drawback_inr + igst_inr) / inr_per_usd

    net_cost_usd = round(total_cost_usd - total_incentives_usd, 2)
    recommended_price = round(net_cost_usd / (1 - _TARGET_MARGIN), 2)
    breakeven_price = round(net_cost_usd / (1 - _MIN_MARGIN), 2)
    actual_price = selling_price_usd if selling_price_usd else recommended_price

    gross_profit = actual_price - net_cost_usd
    gross_margin = round(gross_profit / actual_price * 100, 2) if actual_price else 0
    tax = max(0, gross_profit) * _TAX_RATE
    net_earnings = round(gross_profit - tax, 2)
    net_margin = round(net_earnings / actual_price * 100, 2) if actual_price else 0
    roi = round(net_earnings / total_cost_usd * 100, 2) if total_cost_usd else 0

    per_piece_cost = round(net_cost_usd / quantity_pieces, 4) if quantity_pieces else 0
    per_piece_price = round(actual_price / quantity_pieces, 4) if quantity_pieces else 0
    per_piece_profit = round(net_earnings / quantity_pieces, 4) if quantity_pieces else 0

    viability_notes = []
    if gross_margin < _MIN_MARGIN * 100:
        viability_notes.append(f"Gross margin {gross_margin:.1f}% below minimum {_MIN_MARGIN*100:.0f}%")
    if net_earnings < 0:
        viability_notes.append("Net earnings are negative")
    if shipping_mode == "sea_fcl" and weight_kg < 500:
        viability_notes.append("< 500 kg -- consider LCL instead of FCL")

    return {
        "inputs": {
            "product_category": product_category,
            "product_label": cc["label"],
            "quantity_pieces": quantity_pieces,
            "weight_kg": weight_kg,
            "destination_country": destination_country.upper(),
            "shipping_mode": shipping_mode,
            "shipping_region": fr["region"],
            "sea_transit_days": fr["days"],
            "exchange_rate_inr_usd": inr_per_usd,
        },
        "production_costs": {
            "total_production_inr": round(prod_inr, 2),
            "total_production_usd": round(prod_inr / inr_per_usd, 2),
        },
        "export_overhead": {
            "inland_freight_inr": round(inland_inr, 2),
            "fixed_overhead_inr": round(fixed_inr, 2),
            "total_fixed_overhead_usd": round(fixed_inr / inr_per_usd, 2),
        },
        "variable_costs": {
            "fob_cost_usd": round(fob_usd, 2),
            "quality_inspection_usd": round(qual_usd, 2),
            "agent_commission_usd": round(agent_usd, 2),
            "bank_charges_usd": round(bank_usd, 2),
            "freight_usd_per_kg": fr[mode_key],
            "international_freight_usd": round(freight_usd, 2),
            "marine_insurance_usd": round(insurance_usd, 2),
        },
        "total_export_cost_usd": round(total_cost_usd, 2),
        "government_incentives": {
            "rodtep_inr": round(rodtep_inr, 2),
            "duty_drawback_inr": round(drawback_inr, 2),
            "igst_refund_inr": round(igst_inr, 2),
            "total_incentives_usd": round(total_incentives_usd, 2),
        },
        "net_cost_usd": net_cost_usd,
        "pricing": {
            "min_breakeven_price_usd": breakeven_price,
            "recommended_selling_price_usd": recommended_price,
            "actual_selling_price_usd": actual_price,
            "total_revenue_usd": actual_price,
        },
        "profitability": {
            "gross_profit_usd": round(gross_profit, 2),
            "gross_margin_pct": gross_margin,
            "income_tax_usd": round(tax, 2),
            "net_earnings_usd": net_earnings,
            "net_margin_pct": net_margin,
            "roi_pct": roi,
        },
        "per_unit": {
            "cost_per_piece_usd": per_piece_cost,
            "selling_price_per_piece_usd": per_piece_price,
            "profit_per_piece_usd": per_piece_profit,
        },
        "viability": {
            "is_viable": gross_margin >= _MIN_MARGIN * 100 and net_earnings >= 0,
            "notes": viability_notes,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# SEED DATA
# ══════════════════════════════════════════════════════════════════════════════

SEED: list[tuple] = [
    ("Pier 1 Imports", "US", "United States", "Fort Worth", "pier1.com", "retailer", "monthly", 45_000_000, "alibaba,ny_now"),
    ("Home Depot Pro Supply", "US", "United States", "Atlanta", "homedepot.com", "retailer", "monthly", 120_000_000, "volza,sam_gov"),
    ("Cost Plus World Market", "US", "United States", "Oakland", "worldmarket.com", "retailer", "monthly", 28_000_000, "import_yeti,ny_now"),
    ("TJX Companies", "US", "United States", "Framingham", "tjx.com", "wholesaler", "weekly", 95_000_000, "panjiva,volza"),
    ("Restoration Hardware", "US", "United States", "Corte Madera", "rh.com", "retailer", "monthly", 65_000_000, "volza,ny_now"),
    ("CB2 Imports", "US", "United States", "Chicago", "cb2.com", "retailer", "monthly", 42_000_000, "alibaba,ny_now"),
    ("Crate and Barrel", "US", "United States", "Northbrook", "crateandbarrel.com", "retailer", "monthly", 55_000_000, "volza,panjiva"),
    ("Anthropologie Home", "US", "United States", "Philadelphia", "anthropologie.com", "retailer", "monthly", 38_000_000, "import_yeti,ny_now"),
    ("Pottery Barn", "US", "United States", "San Francisco", "potterybarn.com", "retailer", "monthly", 88_000_000, "volza"),
    ("West Elm Imports", "US", "United States", "Brooklyn", "westelm.com", "retailer", "monthly", 52_000_000, "import_yeti"),
    ("HomeGoods Procurement", "US", "United States", "Framingham", "homegoods.com", "retailer", "weekly", 210_000_000, "datamyne,volza"),
    ("Marriott Procurement", "US", "United States", "Bethesda", "marriott.com", "hospitality", "monthly", 95_000_000, "sam_gov,ihgf"),
    ("Hilton Worldwide Supply", "US", "United States", "McLean", "hilton.com", "hospitality", "monthly", 75_000_000, "volza"),
    ("Hyatt Hotels Corp", "US", "United States", "Chicago", "hyatt.com", "hospitality", "monthly", 48_000_000, "sam_gov"),
    ("US GSA Procurement", "US", "United States", "Washington DC", "gsa.gov", "government", "quarterly", 5_000_000, "sam_gov"),
    ("Li and Fung Sourcing", "HK", "Hong Kong", "Hong Kong", "lifung.com", "sourcing_company", "weekly", 280_000_000, "alibaba,panjiva,volza"),
    ("Accent Decor USA", "US", "United States", "Atlanta", "accentdecor.com", "distributor", "monthly", 28_000_000, "ny_now,import_yeti"),
    ("Uttermost Company", "US", "United States", "Rocky Mount", "uttermost.com", "distributor", "monthly", 42_000_000, "import_yeti,tradeindia"),
    ("IMAX Corporation", "US", "United States", "Dallas", "imax-worldwide.com", "distributor", "monthly", 35_000_000, "import_yeti,tradeindia"),
    ("Zentique Inc", "US", "United States", "Duluth", "zentique.com", "distributor", "monthly", 22_000_000, "ny_now,alibaba"),
    ("John Lewis Partnership", "GB", "United Kingdom", "London", "johnlewis.com", "retailer", "weekly", 145_000_000, "volza,ambiente"),
    ("Marks Spencer Home", "GB", "United Kingdom", "London", "marksandspencer.com", "retailer", "monthly", 95_000_000, "panjiva"),
    ("Next Home", "GB", "United Kingdom", "Leicester", "next.co.uk", "retailer", "monthly", 65_000_000, "volza,ihgf"),
    ("Dunelm Group", "GB", "United Kingdom", "Syston", "dunelm.com", "retailer", "monthly", 42_000_000, "import_yeti"),
    ("InterContinental Hotels", "GB", "United Kingdom", "Windsor", "ihg.com", "hospitality", "monthly", 65_000_000, "panjiva,ihgf"),
    ("Maisons du Monde", "FR", "France", "Paris", "maisonsdumonde.com", "retailer", "monthly", 72_000_000, "maison_objet,volza"),
    ("Galeries Lafayette Home", "FR", "France", "Paris", "galerieslafayette.com", "retailer", "monthly", 55_000_000, "volza,maison_objet"),
    ("Accor Hotels Procurement", "FR", "France", "Paris", "accor.com", "hospitality", "monthly", 55_000_000, "maison_objet"),
    ("IKEA Deutschland", "DE", "Germany", "Hofheim", "ikea.de", "wholesaler", "weekly", 320_000_000, "panjiva,volza"),
    ("WestwingNow GmbH", "DE", "Germany", "Munich", "westwing.de", "retailer", "monthly", 35_000_000, "tradeindia,ihgf"),
    ("Adairs Australia", "AU", "Australia", "Melbourne", "adairs.com.au", "retailer", "monthly", 22_000_000, "ihgf,import_yeti"),
    ("Freedom Furniture", "AU", "Australia", "Sydney", "freedom.com.au", "retailer", "monthly", 35_000_000, "panjiva,volza"),
    ("HomeSense Canada", "CA", "Canada", "Toronto", "homesense.ca", "retailer", "monthly", 42_000_000, "datamyne,volza"),
    ("Home Centre UAE", "AE", "United Arab Emirates", "Dubai", "homecenteronline.com", "retailer", "monthly", 55_000_000, "volza,ihgf"),
    ("Pan Emirates Furniture", "AE", "United Arab Emirates", "Dubai", "panemirates.com", "wholesaler", "monthly", 65_000_000, "volza,panjiva"),
    ("IKEA Saudi Arabia", "SA", "Saudi Arabia", "Riyadh", "ikea.com/sa", "wholesaler", "weekly", 120_000_000, "volza"),
    ("COURTS Asia", "SG", "Singapore", "Singapore", "courts.com.sg", "retailer", "monthly", 45_000_000, "volza"),
    ("Muji Home Japan", "JP", "Japan", "Tokyo", "muji.com/jp", "retailer", "weekly", 145_000_000, "datamyne"),
    ("Loft Japan", "JP", "Japan", "Tokyo", "loft.co.jp", "retailer", "weekly", 95_000_000, "volza,panjiva"),
    ("Zara Home Spain", "ES", "Spain", "A Coruna", "zarahome.com/es", "retailer", "monthly", 72_000_000, "maison_objet"),
    ("HEMA Netherlands", "NL", "Netherlands", "Amsterdam", "hema.nl", "retailer", "monthly", 32_000_000, "ambiente,volza"),
    ("Indiska Sweden", "SE", "Sweden", "Stockholm", "indiska.com", "retailer", "monthly", 18_000_000, "ihgf,tradeindia"),
    ("Woolworths Home SA", "ZA", "South Africa", "Cape Town", "woolworths.co.za", "retailer", "monthly", 28_000_000, "ihgf"),
    ("UNDP Procurement", None, "International", "New York", "undp.org", "procurement_agency", "monthly", 8_000_000, "ungm"),
    ("Mast Industries Sourcing", "US", "United States", "New York", "mast-industries.com", "sourcing_company", "weekly", 185_000_000, "datamyne"),
    ("Intertek Buying Office", "GB", "United Kingdom", "London", "intertek.com", "sourcing_company", "monthly", 75_000_000, "volza"),
]

HS_POOL = ["741810", "741820", "741900", "830600", "830610", "940540", "691300", "830620"]
CAT_POOL = [
    "brass decor", "brass handicraft", "brass statue", "brass giftware",
    "brass hotelware", "metal home decor", "brass lamp", "brass candleholder",
    "brass vase", "brass garden decor", "religious brass artifacts", "OEM brass",
]
COUNTRIES_EXTRA = [
    ("KR", "South Korea"), ("MY", "Malaysia"), ("BE", "Belgium"),
    ("DK", "Denmark"), ("NO", "Norway"), ("CH", "Switzerland"),
    ("PL", "Poland"), ("CZ", "Czech Republic"), ("TR", "Turkey"),
    ("NG", "Nigeria"), ("KE", "Kenya"), ("AR", "Argentina"),
    ("TH", "Thailand"), ("VN", "Vietnam"), ("ID", "Indonesia"),
    ("PH", "Philippines"), ("PK", "Pakistan"), ("MX", "Mexico"),
    ("IT", "Italy"), ("BR", "Brazil"), ("KW", "Kuwait"),
    ("QA", "Qatar"), ("NZ", "New Zealand"), ("FI", "Finland"),
    ("PT", "Portugal"), ("HU", "Hungary"), ("GR", "Greece"),
    ("AT", "Austria"), ("BE", "Belgium"), ("EG", "Egypt"),
]
TYPES = ["importer", "distributor", "wholesaler", "retailer", "hospitality", "sourcing_company"]
SOURCES_POOL = ["alibaba", "tradeindia", "un_comtrade", "import_yeti", "volza", "ihgf", "panjiva", "ec21"]


def _norm(name: str) -> str:
    import re
    n = name.lower()
    n = re.sub(r"[^\w\s]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _make(company, country_code, country_name, city, domain, buyer_type, freq, volume, sources_str):
    today = date.today()
    last = today - timedelta(days=random.randint(10, 300))
    first = last - timedelta(days=random.randint(180, 1800))
    srcs = sources_str.split(",")
    return Buyer(
        uuid=str(uuid4()),
        company_name=company,
        company_name_normalized=_norm(company),
        country_code=country_code, country_name=country_name,
        city=city, website=f"https://{domain}", website_domain=domain,
        email_json=json.dumps([f"procurement@{domain.split('/')[0]}"]),
        phone_json=json.dumps([f"+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}"]),
        product_categories_json=json.dumps(random.sample(CAT_POOL, random.randint(2, 5))),
        hs_codes_json=json.dumps(random.sample(HS_POOL, random.randint(1, 4))),
        buyer_type=buyer_type, import_frequency=freq,
        estimated_annual_volume_usd=round(float(volume), 2),
        last_import_date=last, first_import_date=first,
        total_shipments=random.randint(4, 280),
        source_count=len(srcs),
        data_sources_json=json.dumps(srcs),
        confidence_score=round(random.uniform(0.65, 0.97), 4),
        is_verified=random.random() > 0.65, is_active=True,
        description=f"Leading {buyer_type} of brass and metal home decor products.",
    )


async def seed_db() -> int:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        existing = (await session.execute(select(func.count(Buyer.id)))).scalar_one()
        if existing > 0:
            return existing
    buyers = [_make(*row) for row in SEED]
    idx = 0
    while len(buyers) < 500:
        cc, cn = COUNTRIES_EXTRA[idx % len(COUNTRIES_EXTRA)]
        idx += 1
        name = f"{cn} Brass Imports {idx}"
        dom = f"brassimp{idx}.com"
        buyers.append(_make(
            name, cc, cn, "Metro City", dom,
            random.choice(TYPES),
            random.choice(["monthly", "quarterly", "annual"]),
            random.uniform(500_000, 25_000_000),
            ",".join(random.sample(SOURCES_POOL, 2)),
        ))
    async with SessionLocal() as session:
        session.add_all(buyers)
        await session.commit()
    return len(buyers)


# ══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    n = await seed_db()
    print(f"  Buyers seeded: {n}")
    async with SessionLocal() as db:
        scored = await score_all(db)
    print(f"  Lead scores computed: {scored}")
    async with SessionLocal() as db:
        opps = await _seed_growth_opportunities(db)
    print(f"  Growth opportunities seeded: {opps}")
    async with SessionLocal() as db:
        ems = await _seed_emerging_importers(db)
    print(f"  Emerging importers flagged: {ems}")
    yield


app = FastAPI(
    title="BrassExport Intelligence",
    description=(
        "**Demo mode** -- 500 buyers, AI scoring, CRM, Export Calculator, "
        "Growth Engine, Outreach, and Executive Dashboard.  \n\n"
        "### Modules\n"
        "- **Buyer Intelligence**: `/api/v1/buyers/` -- browse & search\n"
        "- **AI Scoring**: `/api/v1/dashboard/top-buyers` -- lead scores 0-100\n"
        "- **CRM**: `/api/v1/crm/leads/` -- full sales lifecycle\n"
        "- **Calculator**: `/api/v1/calculator/calculate` -- export profitability\n"
        "- **Growth Engine**: `/api/v1/growth/recommendations` -- daily top-10 buyers\n"
        "- **Outreach**: `/api/v1/outreach/generate` -- AI email generation\n"
        "- **Executive Dashboard**: `/api/v1/executive/overview` -- KPIs & forecast\n"
    ),
    version="2.0.0-demo",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _out_buyer(r: Buyer) -> dict:
    return {
        "id": r.id, "uuid": r.uuid, "company_name": r.company_name,
        "country_code": r.country_code, "country_name": r.country_name,
        "city": r.city, "website": r.website,
        "email": json.loads(r.email_json or "[]"),
        "phone": json.loads(r.phone_json or "[]"),
        "product_categories": json.loads(r.product_categories_json or "[]"),
        "hs_codes": json.loads(r.hs_codes_json or "[]"),
        "buyer_type": r.buyer_type, "import_frequency": r.import_frequency,
        "estimated_annual_volume_usd": float(r.estimated_annual_volume_usd) if r.estimated_annual_volume_usd else None,
        "last_import_date": r.last_import_date.isoformat() if r.last_import_date else None,
        "first_import_date": r.first_import_date.isoformat() if r.first_import_date else None,
        "total_shipments": r.total_shipments, "source_count": r.source_count,
        "data_sources": json.loads(r.data_sources_json or "[]"),
        "confidence_score": float(r.confidence_score) if r.confidence_score else None,
        "is_verified": bool(r.is_verified),
    }


def _out_score(b: Buyer, s: BuyerScore) -> dict:
    return {
        **_out_buyer(b),
        "composite_score": s.composite_score, "tier": s.tier,
        "india_import_probability": s.india_import_probability,
        "supplier_switch_probability": s.supplier_switch_probability,
        "product_fit_score": s.product_fit_score,
        "growth_trend_score": s.growth_trend_score,
        "new_importer_score": s.new_importer_score,
        "import_activity_score": s.import_activity_score,
    }


# ── Root / Health ─────────────────────────────────────────────────────────────
@app.get("/", tags=["root"])
async def root():
    return {"service": "BrassExport Intelligence", "version": "1.0.0-demo", "docs": "/docs"}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "mode": "demo-sqlite"}


# ══════════════════════════════════════════════════════════════════════════════
# BUYER INTELLIGENCE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/buyers/", tags=["buyers"])
async def list_buyers(
    country_code: Optional[str] = Query(None),
    buyer_type: Optional[str] = Query(None),
    min_confidence: float = Query(0.0, ge=0, le=1),
    verified_only: bool = Query(False),
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("confidence_score"), sort_order: str = Query("desc"),
):
    async with SessionLocal() as db:
        stmt = select(Buyer).where(Buyer.is_active == True)
        if country_code:
            stmt = stmt.where(Buyer.country_code == country_code.upper())
        if buyer_type:
            stmt = stmt.where(Buyer.buyer_type == buyer_type)
        if min_confidence > 0:
            stmt = stmt.where(Buyer.confidence_score >= min_confidence)
        if verified_only:
            stmt = stmt.where(Buyer.is_verified == True)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        col = getattr(Buyer, sort_by, Buyer.confidence_score)
        stmt = stmt.order_by(col.desc() if sort_order == "desc" else col.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size, "results": [_out_buyer(r) for r in rows]}


@app.get("/api/v1/buyers/{buyer_id}", tags=["buyers"])
async def get_buyer(buyer_id: int):
    async with SessionLocal() as db:
        row = await db.get(Buyer, buyer_id)
    if not row:
        raise HTTPException(404, "Buyer not found")
    return _out_buyer(row)


@app.get("/api/v1/search/", tags=["search"])
async def search(
    q: str = Query(..., min_length=2),
    country_code: Optional[str] = Query(None),
    buyer_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
):
    async with SessionLocal() as db:
        stmt = select(Buyer).where(
            Buyer.is_active == True,
            or_(Buyer.company_name.ilike(f"%{q}%"),
                Buyer.product_categories_json.ilike(f"%{q}%"),
                Buyer.country_name.ilike(f"%{q}%"),
                Buyer.buyer_type.ilike(f"%{q}%")),
        )
        if country_code:
            stmt = stmt.where(Buyer.country_code == country_code.upper())
        if buyer_type:
            stmt = stmt.where(Buyer.buyer_type == buyer_type)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(Buyer.confidence_score.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size, "results": [_out_buyer(r) for r in rows]}


@app.get("/api/v1/search/export", tags=["search"])
async def export_csv(
    country_code: Optional[str] = Query(None),
    buyer_type: Optional[str] = Query(None),
    min_confidence: float = Query(0.5),
    limit: int = Query(500, le=10_000),
):
    async with SessionLocal() as db:
        stmt = select(Buyer).where(Buyer.is_active == True, Buyer.confidence_score >= min_confidence)
        if country_code:
            stmt = stmt.where(Buyer.country_code == country_code.upper())
        if buyer_type:
            stmt = stmt.where(Buyer.buyer_type == buyer_type)
        stmt = stmt.order_by(Buyer.confidence_score.desc()).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "company_name", "country_code", "city", "website",
                     "buyer_type", "estimated_annual_volume_usd", "confidence_score"])
    for r in rows:
        writer.writerow([r.id, r.company_name, r.country_code, r.city, r.website,
                         r.buyer_type, r.estimated_annual_volume_usd, r.confidence_score])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=brass_buyers.csv"})


# ── Analytics ─────────────────────────────────────────────────────────────────
@app.get("/api/v1/analytics/overview", tags=["analytics"])
async def overview():
    async with SessionLocal() as db:
        total = (await db.execute(select(func.count(Buyer.id)).where(Buyer.is_active == True))).scalar_one()
        verified = (await db.execute(select(func.count(Buyer.id)).where(Buyer.is_active == True, Buyer.is_verified == True))).scalar_one()
        countries = (await db.execute(select(func.count(func.distinct(Buyer.country_code))).where(Buyer.is_active == True))).scalar_one()
        avg_conf = (await db.execute(select(func.avg(Buyer.confidence_score)).where(Buyer.is_active == True))).scalar_one()
        total_vol = (await db.execute(select(func.sum(Buyer.estimated_annual_volume_usd)).where(Buyer.is_active == True))).scalar_one()
        scored_count = (await db.execute(select(func.count(BuyerScore.id)))).scalar_one()
        avg_score = (await db.execute(select(func.avg(BuyerScore.composite_score)))).scalar_one()
        lead_count = (await db.execute(select(func.count(Lead.id)))).scalar_one()
    return {
        "total_buyers": total, "verified": verified, "countries": countries,
        "avg_confidence": round(float(avg_conf or 0), 4),
        "total_volume_usd": float(total_vol or 0),
        "ai_scored_buyers": scored_count,
        "avg_lead_score": round(float(avg_score or 0), 2),
        "crm_leads": lead_count,
        "data_sources": 25,
    }


@app.get("/api/v1/analytics/by-country", tags=["analytics"])
async def by_country(limit: int = Query(30)):
    async with SessionLocal() as db:
        stmt = (
            select(Buyer.country_code, Buyer.country_name,
                   func.count(Buyer.id).label("count"),
                   func.sum(Buyer.estimated_annual_volume_usd).label("vol"))
            .where(Buyer.is_active == True)
            .group_by(Buyer.country_code, Buyer.country_name)
            .order_by(func.count(Buyer.id).desc()).limit(limit)
        )
        rows = (await db.execute(stmt)).fetchall()
    return [{"country_code": r.country_code, "country_name": r.country_name,
             "buyer_count": r.count, "total_volume_usd": float(r.vol or 0)} for r in rows]


@app.get("/api/v1/analytics/by-buyer-type", tags=["analytics"])
async def by_buyer_type():
    async with SessionLocal() as db:
        total = (await db.execute(select(func.count(Buyer.id)).where(Buyer.is_active == True))).scalar_one() or 1
        rows = (await db.execute(
            select(Buyer.buyer_type, func.count(Buyer.id).label("count"))
            .where(Buyer.is_active == True).group_by(Buyer.buyer_type).order_by(func.count(Buyer.id).desc())
        )).fetchall()
    return [{"buyer_type": r.buyer_type, "count": r.count, "pct": round(r.count / total * 100, 2)} for r in rows]


# ── Scoring ───────────────────────────────────────────────────────────────────
@app.get("/api/v1/scores/{buyer_id}", tags=["scoring"])
async def get_score(buyer_id: int):
    async with SessionLocal() as db:
        b = await db.get(Buyer, buyer_id)
        if not b:
            raise HTTPException(404, "Buyer not found")
        s = (await db.execute(select(BuyerScore).where(BuyerScore.buyer_id == buyer_id))).scalar_one_or_none()
        if not s:
            raise HTTPException(404, "No score -- call POST /api/v1/scores/run")
    return _out_score(b, s)


@app.post("/api/v1/scores/run", tags=["scoring"])
async def run_scoring():
    async with SessionLocal() as db:
        count = await score_all(db)
    return {"scored": count}


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.get("/api/v1/dashboard/top-buyers", tags=["dashboard"])
async def top_buyers(limit: int = Query(50), min_composite: float = Query(55.0),
                     country_code: Optional[str] = Query(None), buyer_type: Optional[str] = Query(None)):
    async with SessionLocal() as db:
        stmt = (select(Buyer, BuyerScore).join(BuyerScore, Buyer.id == BuyerScore.buyer_id)
                .where(Buyer.is_active == True, BuyerScore.composite_score >= min_composite))
        if country_code:
            stmt = stmt.where(Buyer.country_code == country_code.upper())
        if buyer_type:
            stmt = stmt.where(Buyer.buyer_type == buyer_type)
        rows = (await db.execute(stmt.order_by(BuyerScore.composite_score.desc()).limit(limit))).all()
    return {"view": "top_buyers", "count": len(rows), "results": [_out_score(b, s) for b, s in rows]}


@app.get("/api/v1/dashboard/new-buyers", tags=["dashboard"])
async def new_buyers(limit: int = Query(50), min_new_score: float = Query(60.0),
                     country_code: Optional[str] = Query(None)):
    async with SessionLocal() as db:
        stmt = (select(Buyer, BuyerScore).join(BuyerScore, Buyer.id == BuyerScore.buyer_id)
                .where(Buyer.is_active == True, BuyerScore.new_importer_score >= min_new_score))
        if country_code:
            stmt = stmt.where(Buyer.country_code == country_code.upper())
        rows = (await db.execute(stmt.order_by(BuyerScore.new_importer_score.desc()).limit(limit))).all()
    return {"view": "new_buyers", "count": len(rows), "results": [_out_score(b, s) for b, s in rows]}


@app.get("/api/v1/dashboard/high-growth", tags=["dashboard"])
async def high_growth(limit: int = Query(50), min_growth: float = Query(60.0),
                      country_code: Optional[str] = Query(None)):
    async with SessionLocal() as db:
        stmt = (select(Buyer, BuyerScore).join(BuyerScore, Buyer.id == BuyerScore.buyer_id)
                .where(Buyer.is_active == True, BuyerScore.growth_trend_score >= min_growth))
        if country_code:
            stmt = stmt.where(Buyer.country_code == country_code.upper())
        rows = (await db.execute(stmt.order_by(BuyerScore.growth_trend_score.desc()).limit(limit))).all()
    return {"view": "high_growth", "count": len(rows), "results": [_out_score(b, s) for b, s in rows]}


@app.get("/api/v1/dashboard/untapped", tags=["dashboard"])
async def untapped(limit: int = Query(50), min_product_fit: float = Query(55.0),
                   max_india_prob: float = Query(50.0), country_code: Optional[str] = Query(None)):
    async with SessionLocal() as db:
        stmt = (select(Buyer, BuyerScore).join(BuyerScore, Buyer.id == BuyerScore.buyer_id)
                .where(Buyer.is_active == True, BuyerScore.product_fit_score >= min_product_fit,
                       BuyerScore.india_import_probability <= max_india_prob))
        if country_code:
            stmt = stmt.where(Buyer.country_code == country_code.upper())
        rows = (await db.execute(
            stmt.order_by(BuyerScore.product_fit_score.desc()).limit(limit)
        )).all()
    return {"view": "untapped", "count": len(rows), "results": [_out_score(b, s) for b, s in rows]}


# ══════════════════════════════════════════════════════════════════════════════
# CRM ROUTES
# ══════════════════════════════════════════════════════════════════════════════

def _out_lead(l: Lead) -> dict:
    return {
        "id": l.id, "uuid": l.uuid, "company_name": l.company_name,
        "country_code": l.country_code, "canonical_buyer_id": l.canonical_buyer_id,
        "contact_name": l.contact_name, "contact_email": l.contact_email,
        "contact_phone": l.contact_phone, "contact_whatsapp": l.contact_whatsapp,
        "status": l.status, "source": l.source, "priority": l.priority,
        "assigned_to": l.assigned_to,
        "estimated_value_usd": l.estimated_value_usd,
        "last_contact_date": l.last_contact_date.isoformat() if l.last_contact_date else None,
        "expected_close_date": l.expected_close_date.isoformat() if l.expected_close_date else None,
        "notes_count": l.notes_count, "interactions_count": l.interactions_count,
        "open_followups": l.open_followups,
        "created_at": l.created_at.isoformat() if l.created_at else None,
        "updated_at": l.updated_at.isoformat() if l.updated_at else None,
    }


@app.get("/api/v1/crm/leads/", tags=["CRM"])
async def list_leads(
    status: Optional[str] = Query(None), priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None), country_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
):
    async with SessionLocal() as db:
        stmt = select(Lead)
        if status:
            stmt = stmt.where(Lead.status == status)
        if priority:
            stmt = stmt.where(Lead.priority == priority)
        if assigned_to:
            stmt = stmt.where(Lead.assigned_to == assigned_to)
        if country_code:
            stmt = stmt.where(Lead.country_code == country_code.upper())
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await db.execute(stmt.order_by(Lead.updated_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "results": [_out_lead(r) for r in rows]}


@app.post("/api/v1/crm/leads/", tags=["CRM"], status_code=201)
async def create_lead(body: dict):
    async with SessionLocal() as db:
        lead = Lead(uuid=str(uuid4()), **{k: v for k, v in body.items() if hasattr(Lead, k)})
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
    return _out_lead(lead)


@app.get("/api/v1/crm/leads/{lead_id}", tags=["CRM"])
async def get_lead(lead_id: int):
    async with SessionLocal() as db:
        lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return _out_lead(lead)


@app.patch("/api/v1/crm/leads/{lead_id}", tags=["CRM"])
async def patch_lead(lead_id: int, body: dict):
    async with SessionLocal() as db:
        lead = await db.get(Lead, lead_id)
        if not lead:
            raise HTTPException(404, "Lead not found")
        for k, v in body.items():
            if hasattr(Lead, k) and k not in ("id", "uuid", "created_at"):
                setattr(lead, k, v)
        lead.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(lead)
    return _out_lead(lead)


@app.get("/api/v1/crm/leads/pipeline/summary", tags=["CRM"])
async def pipeline_summary():
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Lead.status, func.count(Lead.id).label("count"),
                   func.sum(Lead.estimated_value_usd).label("total_value"))
            .group_by(Lead.status)
        )).fetchall()
    return [{"status": r.status, "count": r.count,
             "total_value_usd": float(r.total_value or 0)} for r in rows]


# ── Contacts ──────────────────────────────────────────────────────────────────
def _out_contact(c: Contact) -> dict:
    return {
        "id": c.id, "lead_id": c.lead_id, "name": c.name, "title": c.title,
        "department": c.department, "email": c.email, "phone": c.phone,
        "whatsapp": c.whatsapp, "linkedin_url": c.linkedin_url,
        "is_primary": c.is_primary, "do_not_contact": c.do_not_contact,
        "preferred_contact_method": c.preferred_contact_method,
        "last_contacted_at": c.last_contacted_at.isoformat() if c.last_contacted_at else None,
        "notes": c.notes,
    }


@app.get("/api/v1/crm/contacts/", tags=["CRM"])
async def list_contacts(lead_id: int = Query(...)):
    async with SessionLocal() as db:
        rows = (await db.execute(select(Contact).where(Contact.lead_id == lead_id).order_by(Contact.is_primary.desc()))).scalars().all()
    return {"lead_id": lead_id, "count": len(rows), "contacts": [_out_contact(r) for r in rows]}


@app.post("/api/v1/crm/contacts/", tags=["CRM"], status_code=201)
async def create_contact(body: dict):
    async with SessionLocal() as db:
        c = Contact(**{k: v for k, v in body.items() if hasattr(Contact, k)})
        db.add(c)
        await db.commit()
        await db.refresh(c)
    return _out_contact(c)


# ── Contact History ───────────────────────────────────────────────────────────
def _out_history(h: ContactHistory) -> dict:
    return {
        "id": h.id, "lead_id": h.lead_id, "contact_id": h.contact_id,
        "interaction_type": h.interaction_type, "direction": h.direction,
        "subject": h.subject, "notes": h.notes, "outcome": h.outcome,
        "next_action": h.next_action, "duration_minutes": h.duration_minutes,
        "interacted_by": h.interacted_by,
        "interacted_at": h.interacted_at.isoformat() if h.interacted_at else None,
    }


@app.get("/api/v1/crm/history/", tags=["CRM"])
async def list_history(lead_id: int = Query(...), page: int = Query(1), page_size: int = Query(50)):
    async with SessionLocal() as db:
        stmt = select(ContactHistory).where(ContactHistory.lead_id == lead_id).order_by(ContactHistory.interacted_at.desc())
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"lead_id": lead_id, "total": total, "history": [_out_history(r) for r in rows]}


@app.post("/api/v1/crm/history/", tags=["CRM"], status_code=201)
async def log_interaction(body: dict):
    async with SessionLocal() as db:
        if "interacted_at" not in body:
            body["interacted_at"] = datetime.utcnow()
        h = ContactHistory(**{k: v for k, v in body.items() if hasattr(ContactHistory, k)})
        db.add(h)
        lead = await db.get(Lead, body.get("lead_id"))
        if lead:
            lead.interactions_count = (lead.interactions_count or 0) + 1
            lead.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(h)
    return _out_history(h)


# ── Notes ─────────────────────────────────────────────────────────────────────
def _out_note(n: Note) -> dict:
    return {"id": n.id, "lead_id": n.lead_id, "content": n.content,
            "note_type": n.note_type, "created_by": n.created_by, "is_pinned": n.is_pinned,
            "created_at": n.created_at.isoformat() if n.created_at else None}


@app.get("/api/v1/crm/notes/", tags=["CRM"])
async def list_notes(lead_id: int = Query(...), pinned_only: bool = Query(False)):
    async with SessionLocal() as db:
        stmt = select(Note).where(Note.lead_id == lead_id)
        if pinned_only:
            stmt = stmt.where(Note.is_pinned == True)
        rows = (await db.execute(stmt.order_by(Note.is_pinned.desc(), Note.created_at.desc()))).scalars().all()
    return {"lead_id": lead_id, "count": len(rows), "notes": [_out_note(r) for r in rows]}


@app.post("/api/v1/crm/notes/", tags=["CRM"], status_code=201)
async def create_note(body: dict):
    async with SessionLocal() as db:
        note = Note(**{k: v for k, v in body.items() if hasattr(Note, k)})
        db.add(note)
        lead = await db.get(Lead, body.get("lead_id"))
        if lead:
            lead.notes_count = (lead.notes_count or 0) + 1
        await db.commit()
        await db.refresh(note)
    return _out_note(note)


# ── Follow-ups ────────────────────────────────────────────────────────────────
def _out_fu(f: FollowUp) -> dict:
    return {
        "id": f.id, "lead_id": f.lead_id, "title": f.title,
        "follow_up_type": f.follow_up_type, "priority": f.priority,
        "assigned_to": f.assigned_to,
        "scheduled_at": f.scheduled_at.isoformat() if f.scheduled_at else None,
        "is_completed": f.is_completed,
        "completed_at": f.completed_at.isoformat() if f.completed_at else None,
        "outcome_notes": f.outcome_notes,
    }


@app.get("/api/v1/crm/followups/", tags=["CRM"])
async def list_followups(
    lead_id: Optional[int] = Query(None),
    is_completed: Optional[bool] = Query(None),
    assigned_to: Optional[str] = Query(None),
    page: int = Query(1), page_size: int = Query(50),
):
    async with SessionLocal() as db:
        stmt = select(FollowUp)
        if lead_id is not None:
            stmt = stmt.where(FollowUp.lead_id == lead_id)
        if is_completed is not None:
            stmt = stmt.where(FollowUp.is_completed == is_completed)
        if assigned_to:
            stmt = stmt.where(FollowUp.assigned_to == assigned_to)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await db.execute(stmt.order_by(FollowUp.scheduled_at.asc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"total": total, "page": page, "results": [_out_fu(r) for r in rows]}


@app.post("/api/v1/crm/followups/", tags=["CRM"], status_code=201)
async def create_followup(body: dict):
    async with SessionLocal() as db:
        fu = FollowUp(**{k: v for k, v in body.items() if hasattr(FollowUp, k)})
        db.add(fu)
        lead = await db.get(Lead, body.get("lead_id"))
        if lead:
            lead.open_followups = (lead.open_followups or 0) + 1
        await db.commit()
        await db.refresh(fu)
    return _out_fu(fu)


@app.post("/api/v1/crm/followups/{followup_id}/complete", tags=["CRM"])
async def complete_followup(followup_id: int, outcome_notes: Optional[str] = None):
    async with SessionLocal() as db:
        fu = await db.get(FollowUp, followup_id)
        if not fu:
            raise HTTPException(404, "Follow-up not found")
        fu.is_completed = True
        fu.completed_at = datetime.utcnow()
        if outcome_notes:
            fu.outcome_notes = outcome_notes
        lead = await db.get(Lead, fu.lead_id)
        if lead and lead.open_followups:
            lead.open_followups = max(0, lead.open_followups - 1)
        await db.commit()
        await db.refresh(fu)
    return _out_fu(fu)


# ── Opportunities ─────────────────────────────────────────────────────────────
STAGE_PROB = {"prospecting": 10, "qualification": 25, "proposal": 45,
              "negotiation": 70, "won": 100, "lost": 0}


def _out_opp(o: Opportunity) -> dict:
    return {
        "id": o.id, "uuid": o.uuid, "lead_id": o.lead_id, "title": o.title,
        "stage": o.stage, "probability_pct": o.probability_pct,
        "estimated_value_usd": o.estimated_value_usd,
        "weighted_value_usd": round((o.estimated_value_usd or 0) * (o.probability_pct or 0) / 100, 2),
        "currency": o.currency, "incoterms": o.incoterms,
        "expected_close_date": o.expected_close_date.isoformat() if o.expected_close_date else None,
        "won_at": o.won_at.isoformat() if o.won_at else None,
        "lost_reason": o.lost_reason, "assigned_to": o.assigned_to,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


@app.get("/api/v1/crm/opportunities/", tags=["CRM"])
async def list_opportunities(lead_id: Optional[int] = Query(None),
                              stage: Optional[str] = Query(None), page: int = Query(1)):
    async with SessionLocal() as db:
        stmt = select(Opportunity)
        if lead_id is not None:
            stmt = stmt.where(Opportunity.lead_id == lead_id)
        if stage:
            stmt = stmt.where(Opportunity.stage == stage)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await db.execute(stmt.order_by(Opportunity.estimated_value_usd.desc()).limit(100))).scalars().all()
    return {"total": total, "results": [_out_opp(r) for r in rows]}


@app.post("/api/v1/crm/opportunities/", tags=["CRM"], status_code=201)
async def create_opportunity(body: dict):
    async with SessionLocal() as db:
        data = {k: v for k, v in body.items() if hasattr(Opportunity, k)}
        data.setdefault("uuid", str(uuid4()))
        data.setdefault("probability_pct", STAGE_PROB.get(data.get("stage", "prospecting"), 20))
        opp = Opportunity(**data)
        db.add(opp)
        await db.commit()
        await db.refresh(opp)
    return _out_opp(opp)


@app.get("/api/v1/crm/opportunities/funnel", tags=["CRM"])
async def opp_funnel():
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Opportunity.stage, func.count(Opportunity.id).label("count"),
                   func.sum(Opportunity.estimated_value_usd).label("val"))
            .group_by(Opportunity.stage)
        )).fetchall()
    return [{"stage": r.stage, "count": r.count, "value_usd": float(r.val or 0),
             "probability": STAGE_PROB.get(r.stage, 0)} for r in rows]


# ── Samples ───────────────────────────────────────────────────────────────────
def _out_sample(s: Sample) -> dict:
    return {
        "id": s.id, "sample_number": s.sample_number, "lead_id": s.lead_id,
        "status": s.status, "courier": s.courier, "tracking_number": s.tracking_number,
        "sent_date": s.sent_date.isoformat() if s.sent_date else None,
        "delivered_date": s.delivered_date.isoformat() if s.delivered_date else None,
        "cost_usd": s.cost_usd, "paid_by_buyer": s.paid_by_buyer,
        "feedback": s.feedback, "approved_for_bulk": s.approved_for_bulk,
    }


@app.get("/api/v1/crm/samples/", tags=["CRM"])
async def list_samples(lead_id: Optional[int] = Query(None), status: Optional[str] = Query(None)):
    async with SessionLocal() as db:
        stmt = select(Sample)
        if lead_id is not None:
            stmt = stmt.where(Sample.lead_id == lead_id)
        if status:
            stmt = stmt.where(Sample.status == status)
        rows = (await db.execute(stmt.order_by(Sample.created_at.desc()))).scalars().all()
    return {"count": len(rows), "samples": [_out_sample(r) for r in rows]}


@app.post("/api/v1/crm/samples/", tags=["CRM"], status_code=201)
async def create_sample(body: dict):
    async with SessionLocal() as db:
        data = {k: v for k, v in body.items() if hasattr(Sample, k)}
        data["sample_number"] = f"SMP-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        s = Sample(**data)
        db.add(s)
        await db.commit()
        await db.refresh(s)
    return _out_sample(s)


@app.patch("/api/v1/crm/samples/{sample_id}", tags=["CRM"])
async def update_sample(sample_id: int, body: dict):
    async with SessionLocal() as db:
        s = await db.get(Sample, sample_id)
        if not s:
            raise HTTPException(404, "Sample not found")
        for k, v in body.items():
            if hasattr(Sample, k) and k not in ("id", "sample_number", "created_at"):
                setattr(s, k, v)
        s.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(s)
    return _out_sample(s)


# ── Quotations ────────────────────────────────────────────────────────────────
def _out_quot(q: Quotation) -> dict:
    return {
        "id": q.id, "quotation_number": q.quotation_number, "lead_id": q.lead_id,
        "line_items": json.loads(q.line_items_json or "[]"),
        "currency": q.currency, "total_value": q.total_value,
        "incoterms": q.incoterms, "payment_terms": q.payment_terms,
        "validity_days": q.validity_days, "delivery_weeks": q.delivery_weeks,
        "port_of_loading": q.port_of_loading, "status": q.status,
        "sent_at": q.sent_at.isoformat() if q.sent_at else None,
        "valid_until": q.valid_until.isoformat() if q.valid_until else None,
        "accepted_at": q.accepted_at.isoformat() if q.accepted_at else None,
        "profitability": json.loads(q.profitability_json or "{}"),
    }


@app.get("/api/v1/crm/quotations/", tags=["CRM"])
async def list_quotations(lead_id: Optional[int] = Query(None), status: Optional[str] = Query(None)):
    async with SessionLocal() as db:
        stmt = select(Quotation)
        if lead_id is not None:
            stmt = stmt.where(Quotation.lead_id == lead_id)
        if status:
            stmt = stmt.where(Quotation.status == status)
        rows = (await db.execute(stmt.order_by(Quotation.created_at.desc()))).scalars().all()
    return {"count": len(rows), "quotations": [_out_quot(r) for r in rows]}


@app.post("/api/v1/crm/quotations/", tags=["CRM"], status_code=201)
async def create_quotation(body: dict):
    async with SessionLocal() as db:
        data = {k: v for k, v in body.items() if hasattr(Quotation, k)}
        data["quotation_number"] = f"QT-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        if "line_items" in data:
            data["line_items_json"] = json.dumps(data.pop("line_items"))
        if "profitability" in data:
            data["profitability_json"] = json.dumps(data.pop("profitability"))
        q = Quotation(**data)
        db.add(q)
        await db.commit()
        await db.refresh(q)
    return _out_quot(q)


@app.patch("/api/v1/crm/quotations/{quot_id}", tags=["CRM"])
async def update_quotation(quot_id: int, body: dict):
    async with SessionLocal() as db:
        q = await db.get(Quotation, quot_id)
        if not q:
            raise HTTPException(404, "Quotation not found")
        for k, v in body.items():
            if k == "line_items":
                q.line_items_json = json.dumps(v)
            elif hasattr(Quotation, k) and k not in ("id", "quotation_number", "created_at"):
                setattr(q, k, v)
        if body.get("status") == "accepted" and not q.accepted_at:
            q.accepted_at = datetime.utcnow()
        q.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(q)
    return _out_quot(q)


# ── Purchase Orders ───────────────────────────────────────────────────────────
def _out_po(po: PurchaseOrder) -> dict:
    return {
        "id": po.id, "po_number": po.po_number, "our_reference": po.our_reference,
        "lead_id": po.lead_id, "currency": po.currency, "total_value": po.total_value,
        "advance_pct": po.advance_pct, "advance_amount": po.advance_amount,
        "advance_received_date": po.advance_received_date.isoformat() if po.advance_received_date else None,
        "incoterms": po.incoterms, "shipping_port": po.shipping_port,
        "destination_port": po.destination_port, "country_of_destination": po.country_of_destination,
        "bl_number": po.bl_number, "container_number": po.container_number,
        "production_status": po.production_status, "status": po.status,
        "shipment_date": po.shipment_date.isoformat() if po.shipment_date else None,
        "delivery_date": po.delivery_date.isoformat() if po.delivery_date else None,
        "notes": po.notes,
        "created_at": po.created_at.isoformat() if po.created_at else None,
    }


@app.get("/api/v1/crm/purchase-orders/", tags=["CRM"])
async def list_pos(lead_id: Optional[int] = Query(None), status: Optional[str] = Query(None)):
    async with SessionLocal() as db:
        stmt = select(PurchaseOrder)
        if lead_id is not None:
            stmt = stmt.where(PurchaseOrder.lead_id == lead_id)
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
        rows = (await db.execute(stmt.order_by(PurchaseOrder.created_at.desc()))).scalars().all()
    return {"count": len(rows), "purchase_orders": [_out_po(r) for r in rows]}


@app.post("/api/v1/crm/purchase-orders/", tags=["CRM"], status_code=201)
async def create_po(body: dict):
    async with SessionLocal() as db:
        data = {k: v for k, v in body.items() if hasattr(PurchaseOrder, k)}
        data["our_reference"] = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        if "line_items" in data:
            data["line_items_json"] = json.dumps(data.pop("line_items"))
        if data.get("advance_pct") and data.get("total_value"):
            data["advance_amount"] = round(data["total_value"] * data["advance_pct"] / 100, 2)
            data["balance_amount"] = round(data["total_value"] - data["advance_amount"], 2)
        po = PurchaseOrder(**data)
        db.add(po)
        await db.commit()
        await db.refresh(po)
    return _out_po(po)


@app.patch("/api/v1/crm/purchase-orders/{po_id}", tags=["CRM"])
async def update_po(po_id: int, body: dict):
    async with SessionLocal() as db:
        po = await db.get(PurchaseOrder, po_id)
        if not po:
            raise HTTPException(404, "PO not found")
        for k, v in body.items():
            if hasattr(PurchaseOrder, k) and k not in ("id", "our_reference", "created_at"):
                setattr(po, k, v)
        po.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(po)
    return _out_po(po)


@app.get("/api/v1/crm/stats/overview", tags=["CRM"])
async def crm_overview():
    async with SessionLocal() as db:
        leads = (await db.execute(select(func.count(Lead.id)))).scalar_one()
        by_status = (await db.execute(
            select(Lead.status, func.count(Lead.id).label("count"),
                   func.sum(Lead.estimated_value_usd).label("val"))
            .group_by(Lead.status)
        )).fetchall()
        opps = (await db.execute(select(func.count(Opportunity.id)))).scalar_one()
        pipeline_val = (await db.execute(
            select(func.sum(Opportunity.estimated_value_usd))
            .where(Opportunity.stage.in_(["proposal", "negotiation"]))
        )).scalar_one()
        samples = (await db.execute(select(func.count(Sample.id)))).scalar_one()
        quotes = (await db.execute(select(func.count(Quotation.id)))).scalar_one()
        pos = (await db.execute(select(func.count(PurchaseOrder.id)))).scalar_one()
        won_rev = (await db.execute(
            select(func.sum(PurchaseOrder.total_value)).where(PurchaseOrder.status == "delivered")
        )).scalar_one()
    return {
        "total_leads": leads,
        "total_opportunities": opps,
        "active_pipeline_usd": float(pipeline_val or 0),
        "total_samples": samples,
        "total_quotations": quotes,
        "total_purchase_orders": pos,
        "delivered_revenue_usd": float(won_rev or 0),
        "by_lead_status": [
            {"status": r.status, "count": r.count, "value_usd": float(r.val or 0)}
            for r in by_status
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# CALCULATOR ROUTES
# ══════════════════════════════════════════════════════════════════════════════

class CalcRequest(BaseModel):
    product_category: str = Field(..., description="decorative | religious | hospitality | garden | gifting | industrial | statues")
    quantity_pieces: int = Field(..., ge=1, le=1_000_000)
    weight_kg: float = Field(..., gt=0)
    destination_country: str = Field(..., min_length=2, max_length=2)
    shipping_mode: str = Field("sea_fcl", description="sea_fcl | sea_lcl | air")
    selling_price_usd: Optional[float] = Field(None, gt=0)
    include_lc: bool = False
    inr_per_usd: float = Field(83.5, gt=0)

    @field_validator("destination_country")
    @classmethod
    def _upper(cls, v): return v.upper()


@app.get("/api/v1/calculator/products", tags=["calculator"])
async def calc_products():
    return [
        {"key": k, "label": v["label"], "hs_codes": v["hs_codes"],
         "approx_cost_inr_per_kg": v["raw"] + v["mfg"] + v["fin"] + v["pkg"]}
        for k, v in _PRODUCT_COSTS.items()
    ]


@app.get("/api/v1/calculator/countries", tags=["calculator"])
async def calc_countries():
    return [
        {"country_code": cc if cc != "_DEFAULT" else "OTHER",
         "region": v["region"],
         "sea_fcl_usd_per_kg": v["fcl"], "sea_lcl_usd_per_kg": v["lcl"],
         "air_usd_per_kg": v["air"], "sea_transit_days": v["days"]}
        for cc, v in _FREIGHT_RATES.items()
    ]


@app.post("/api/v1/calculator/calculate", tags=["calculator"],
          summary="Full export cost and profitability breakdown")
async def calculate(body: CalcRequest):
    try:
        result = _calc_profitability(
            product_category=body.product_category,
            quantity_pieces=body.quantity_pieces,
            weight_kg=body.weight_kg,
            destination_country=body.destination_country,
            shipping_mode=body.shipping_mode,
            selling_price_usd=body.selling_price_usd,
            include_lc=body.include_lc,
            inr_per_usd=body.inr_per_usd,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return result


@app.post("/api/v1/calculator/compare", tags=["calculator"],
          summary="Compare sea FCL vs LCL vs air side-by-side")
async def compare_modes(body: CalcRequest):
    results = {}
    for mode in ("sea_fcl", "sea_lcl", "air"):
        try:
            r = _calc_profitability(
                product_category=body.product_category,
                quantity_pieces=body.quantity_pieces,
                weight_kg=body.weight_kg,
                destination_country=body.destination_country,
                shipping_mode=mode,
                selling_price_usd=body.selling_price_usd,
                inr_per_usd=body.inr_per_usd,
            )
            results[mode] = {
                "total_export_cost_usd": r["total_export_cost_usd"],
                "net_cost_usd": r["net_cost_usd"],
                "recommended_selling_price_usd": r["pricing"]["recommended_selling_price_usd"],
                "gross_margin_pct": r["profitability"]["gross_margin_pct"],
                "net_earnings_usd": r["profitability"]["net_earnings_usd"],
                "net_margin_pct": r["profitability"]["net_margin_pct"],
                "freight_usd": r["variable_costs"]["international_freight_usd"],
                "transit_days": r["inputs"]["sea_transit_days"],
                "is_viable": r["viability"]["is_viable"],
            }
        except Exception as e:
            results[mode] = {"error": str(e)}
    viable = [m for m, v in results.items() if v.get("is_viable")]
    best = max(viable, key=lambda m: results[m].get("net_earnings_usd", 0)) if viable else None
    return {
        "product_category": body.product_category,
        "weight_kg": body.weight_kg,
        "quantity_pieces": body.quantity_pieces,
        "destination_country": body.destination_country,
        "comparison": results,
        "recommendation": f"{best} offers the best net earnings" if best else "No viable mode found",
    }


# ══════════════════════════════════════════════════════════════════════════════
# GROWTH ENGINE MODELS (SQLite-compatible)
# ══════════════════════════════════════════════════════════════════════════════

class GrowthOpp(Base):
    __tablename__ = "growth_opportunities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    buyer_id = Column(Integer, nullable=False)
    opportunity_score = Column(Float)
    rank_position = Column(Integer)
    country_code = Column(String(3))
    buyer_type = Column(String(64))
    estimated_value_usd = Column(Float)
    india_import_probability = Column(Float)
    competitive_gap_score = Column(Float)
    market_timing_score = Column(Float)
    country_market_score = Column(Float)
    is_new_discovery = Column(Boolean, default=False)
    is_emerging = Column(Boolean, default=False)
    reasoning = Column(Text)
    market_signals_json = Column(Text, default="[]")
    status = Column(String(32), default="active")
    crm_lead_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmergingImporter(Base):
    __tablename__ = "emerging_importers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    buyer_id = Column(Integer, unique=True, nullable=False)
    months_active = Column(Integer)
    shipment_count = Column(Integer)
    annual_volume_usd = Column(Float)
    growth_velocity_score = Column(Float)
    market_timing_score = Column(Float)
    overall_score = Column(Float)
    category = Column(String(64))
    confidence = Column(String(16))
    action_recommended = Column(String(64))
    trend_json = Column(Text, default="{}")
    is_active = Column(Boolean, default=True)
    detected_at = Column(DateTime, default=datetime.utcnow)


class OutreachCampaign(Base):
    __tablename__ = "outreach_campaigns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    campaign_type = Column(String(32), default="cold_outreach")
    status = Column(String(32), default="draft")
    target_country = Column(String(3))
    target_buyer_type = Column(String(64))
    template_name = Column(String(64))
    language = Column(String(5), default="en")
    emails_sent = Column(Integer, default=0)
    emails_opened = Column(Integer, default=0)
    replies_received = Column(Integer, default=0)
    positive_replies = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class OutreachEmail(Base):
    __tablename__ = "outreach_emails"
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer)
    buyer_id = Column(Integer)
    lead_id = Column(Integer)
    to_email = Column(Text, nullable=False)
    to_name = Column(Text)
    to_company = Column(Text)
    to_country = Column(String(3))
    subject = Column(Text, nullable=False)
    body_text = Column(Text, nullable=False)
    template_name = Column(String(64))
    language = Column(String(5), default="en")
    status = Column(String(32), default="draft")
    sent_at = Column(DateTime)
    opened_at = Column(DateTime)
    open_count = Column(Integer, default=0)
    reply_received = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailReply(Base):
    __tablename__ = "email_replies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    outreach_email_id = Column(Integer)
    campaign_id = Column(Integer)
    lead_id = Column(Integer)
    from_email = Column(Text, nullable=False)
    from_name = Column(Text)
    subject = Column(Text)
    body_text = Column(Text, nullable=False)
    sentiment = Column(String(32))
    intent = Column(String(32))
    confidence_score = Column(Float)
    signals_json = Column(Text, default="{}")
    suggested_next_action = Column(String(64))
    received_at = Column(DateTime, default=datetime.utcnow)
    is_processed = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDED GROWTH RANKER + EMERGING DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

_COUNTRY_OPP: dict[str, float] = {
    "US": 85, "GB": 82, "DE": 78, "AU": 76, "CA": 74, "FR": 72,
    "NL": 70, "BE": 68, "AE": 88, "SA": 85, "KW": 80, "QA": 78,
    "IT": 66, "ES": 64, "CH": 70, "SE": 65, "SG": 75, "JP": 60,
    "ZA": 58, "BR": 45, "KR": 55, "HK": 80, "MY": 62, "TH": 58,
}
_SEASONAL: dict[int, float] = {
    1: 1.20, 2: 1.15, 3: 1.05, 4: 0.95, 5: 0.90, 6: 0.85,
    7: 0.80, 8: 0.90, 9: 1.05, 10: 1.30, 11: 1.35, 12: 1.25,
}
_TYPE_MULT: dict[str, float] = {
    "hospitality": 1.15, "sourcing_company": 1.12, "importer": 1.10,
    "distributor": 1.08, "wholesaler": 1.05, "retailer": 1.00,
    "procurement_agency": 0.90, "oem": 0.85, "government": 0.60,
}
_FREQ_SCORE: dict[str, float] = {
    "daily": 100, "weekly": 90, "monthly": 70, "quarterly": 45,
    "annual": 25, "sporadic": 15, "unknown": 30,
}


def _rank_opportunity(buyer: Buyer, score: BuyerScore) -> dict:
    month = date.today().month
    composite = score.composite_score or 0
    iip = score.india_import_probability or 0
    pfs = score.product_fit_score or 0
    gts = score.growth_trend_score or 0
    nis = score.new_importer_score or 0
    cc = (buyer.country_code or "").upper()
    btype = (buyer.buyer_type or "unknown").lower()
    vol = float(buyer.estimated_annual_volume_usd or 0)
    freq = (buyer.import_frequency or "unknown").lower()

    country_score = _COUNTRY_OPP.get(cc, 50)
    competitive_gap = min(100, max(0, pfs - iip + 30))
    seasonal = _SEASONAL.get(month, 1.0)
    freq_s = _FREQ_SCORE.get(freq, 30)
    timing = min(100, (seasonal * 60) + (freq_s * 0.40))

    vol_bonus = (20 if vol >= 100_000_000 else 15 if vol >= 20_000_000
                 else 10 if vol >= 5_000_000 else 5 if vol >= 1_000_000 else 0)

    raw = (composite * 0.38 + country_score * 0.20 + competitive_gap * 0.15
           + timing * 0.15 + gts * 0.07 + nis * 0.05) + vol_bonus
    mult = _TYPE_MULT.get(btype, 0.90)
    opp_score = round(min(100.0, max(0.0, raw * mult)), 2)

    signals = []
    if iip < 30 and pfs > 60:
        signals.append(f"Product fit {pfs:.0f}/100 but only {iip:.0f}% India import probability")
    if country_score >= 80:
        signals.append(f"{cc} is a top-tier brass export market")
    if seasonal >= 1.15:
        signals.append(f"Prime ordering season (month {month})")
    if nis > 65:
        signals.append("Newly started importing -- no supplier locked in")
    if gts > 70:
        signals.append(f"High growth trend {gts:.0f}/100")
    if vol >= 20_000_000:
        signals.append(f"Annual volume ${vol/1e6:.1f}M")
    if not signals:
        signals.append(f"Lead score {composite:.0f} qualifies for priority outreach")

    action = ("initial_contact" if iip < 25 and pfs > 55
              else "emerging_opportunity" if nis > 60
              else "initial_contact")
    template = ("emerging_importer" if nis > 60 else "initial_introduction")

    return {
        "opportunity_score": opp_score,
        "competitive_gap_score": round(competitive_gap, 2),
        "market_timing_score": round(timing, 2),
        "country_market_score": round(country_score, 2),
        "signals": signals,
        "reasoning": f"Score {opp_score:.0f}/100: " + "; ".join(signals[:2]),
        "action_type": action,
        "email_template": template,
    }


def _detect_emerging(buyer: Buyer, score: BuyerScore) -> Optional[dict]:
    first = buyer.first_import_date
    if not first:
        return None
    months = max(1, (date.today() - first).days // 30)
    if months > 30:
        return None
    shipments = int(buyer.total_shipments or 0)
    vol = float(buyer.estimated_annual_volume_usd or 0)
    gts = float(score.growth_trend_score or 0)
    nis = float(score.new_importer_score or 0)
    composite = float(score.composite_score or 0)
    if shipments < 2 or composite < 30:
        return None
    density = shipments / months
    vmult = (1.40 if months < 6 else 1.25 if months < 12 else 1.10 if months < 18 else 0.95)
    gv = round(min(100, (min(100, density * 20) * vmult + gts * 0.30 + nis * 0.20)), 2)
    seasonal = _SEASONAL.get(date.today().month, 1.0)
    timing = round(min(100, float(score.product_fit_score or 0) * seasonal), 2)
    overall = round(gv * 0.50 + timing * 0.25 + composite * 0.25, 2)
    if overall < 35:
        return None
    cat = ("new_market_entrant" if months <= 6 and density >= 1.0
           else "fast_grower" if density >= 2.0
           else "accelerating" if gts >= 70
           else "emerging")
    return {
        "months_active": months,
        "shipment_count": shipments,
        "annual_volume_usd": vol,
        "growth_velocity_score": gv,
        "market_timing_score": timing,
        "overall_score": overall,
        "category": cat,
        "confidence": ("high" if overall >= 70 else "medium" if overall >= 50 else "low"),
        "action_recommended": ("urgent_outreach" if cat == "new_market_entrant"
                               else "priority_outreach" if cat == "fast_grower"
                               else "standard_outreach"),
        "trend": {"months_active": months, "density": round(density, 2), "gts": gts},
    }


async def _seed_growth_opportunities(db: AsyncSession) -> int:
    existing = (await db.execute(select(func.count(GrowthOpp.id)))).scalar_one()
    if existing > 0:
        return existing
    buyers_stmt = (
        select(Buyer, BuyerScore)
        .join(BuyerScore, Buyer.id == BuyerScore.buyer_id)
        .where(BuyerScore.composite_score >= 45)
        .order_by(BuyerScore.composite_score.desc())
        .limit(300)
    )
    rows = (await db.execute(buyers_stmt)).all()
    count = 0
    for rank_pos, (buyer, score) in enumerate(rows, 1):
        r = _rank_opportunity(buyer, score)
        db.add(GrowthOpp(
            buyer_id=buyer.id,
            opportunity_score=r["opportunity_score"],
            rank_position=rank_pos,
            country_code=buyer.country_code,
            buyer_type=buyer.buyer_type,
            estimated_value_usd=float(buyer.estimated_annual_volume_usd or 0),
            india_import_probability=float(score.india_import_probability or 0),
            competitive_gap_score=r["competitive_gap_score"],
            market_timing_score=r["market_timing_score"],
            country_market_score=r["country_market_score"],
            is_new_discovery=rank_pos <= 50,
            reasoning=r["reasoning"],
            market_signals_json=json.dumps(r["signals"]),
            status="active",
        ))
        count += 1
    await db.commit()
    return count


async def _seed_emerging_importers(db: AsyncSession) -> int:
    existing = (await db.execute(select(func.count(EmergingImporter.id)))).scalar_one()
    if existing > 0:
        return existing
    rows = (await db.execute(
        select(Buyer, BuyerScore).join(BuyerScore, Buyer.id == BuyerScore.buyer_id)
    )).all()
    count = 0
    for buyer, score in rows:
        em = _detect_emerging(buyer, score)
        if not em:
            continue
        db.add(EmergingImporter(
            buyer_id=buyer.id,
            months_active=em["months_active"],
            shipment_count=em["shipment_count"],
            annual_volume_usd=em["annual_volume_usd"],
            growth_velocity_score=em["growth_velocity_score"],
            market_timing_score=em["market_timing_score"],
            overall_score=em["overall_score"],
            category=em["category"],
            confidence=em["confidence"],
            action_recommended=em["action_recommended"],
            trend_json=json.dumps(em["trend"]),
        ))
        count += 1
    await db.commit()
    return count


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDED EMAIL GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULT_SENDER = {
    "name": "Export Manager", "title": "Head of International Sales",
    "company": "Moradabad Brass Crafts", "email": "exports@moradabadbrass.com",
    "phone": "+91-591-2410000", "website": "https://www.moradabadbrass.com",
}
_PRICE_HINTS = {
    "large": "USD 3.50-28 per piece (FOB Mundra/JNPT)",
    "medium": "USD 5-35 per piece (FOB Mundra/JNPT)",
    "small": "USD 6-45 per piece (FOB Mundra/JNPT)",
}
_MOQ_HINTS = {
    "large": "500 pieces per design",
    "medium": "200-500 pieces per design",
    "small": "100 pieces for trial orders",
}


def _email_tier(vol: float) -> str:
    return "large" if vol >= 20_000_000 else ("medium" if vol >= 2_000_000 else "small")


def _gen_email(buyer: Buyer, template: str = "initial_introduction", sender: Optional[dict] = None) -> dict:
    s = {**_DEFAULT_SENDER, **(sender or {})}
    cats = json.loads(buyer.product_categories_json or "[]")
    cat_str = ", ".join(cats[:3]) if cats else "brass home decor and handicrafts"
    vol = float(buyer.estimated_annual_volume_usd or 0)
    tier = _email_tier(vol)
    price = _PRICE_HINTS[tier]
    moq = _MOQ_HINTS[tier]
    company = buyer.company_name or "Your Company"
    contact = buyer.company_name or "Procurement Team"
    country = buyer.country_name or "your country"

    if template == "initial_introduction":
        subject = f"Premium Brass Handicrafts from Moradabad -- Sourcing Opportunity for {company}"
        body = (
            f"Dear {contact},\n\n"
            f"I hope this message finds you well.\n\n"
            f"My name is {s['name']}, {s['title']} at {s['company']}, a leading manufacturer and exporter "
            f"of premium brass handicrafts, home decor, and religious artifacts from Moradabad, India -- "
            f"the world's brass capital with over 400 years of craft heritage.\n\n"
            f"We supply to leading buyers across {country} and believe {company}'s requirements in "
            f"{cat_str} align closely with our capabilities.\n\n"
            f"Why buyers choose Moradabad brass:\n"
            f"- Competitive FOB pricing: {price}\n"
            f"- MOQ: {moq}\n"
            f"- ISO 9001:2015 certified, custom designs, private labelling\n"
            f"- Lead time: 30-45 days for repeat orders\n"
            f"- Full export documentation with government incentives (RoDTEP + Duty Drawback)\n\n"
            f"I would love to share our catalogue and arrange a brief call.\n\n"
            f"Warm regards,\n{s['name']}\n{s['title']} | {s['company']}\n{s['email']} | {s['phone']}"
        )
    elif template == "emerging_importer":
        subject = f"Welcome to Brass Importing -- A Dedicated Partner for {company}"
        body = (
            f"Dear {contact},\n\n"
            f"Congratulations on establishing {company}'s presence in {cat_str} imports.\n\n"
            f"As a manufacturer supplying buyers across 40+ countries for over two decades, we understand "
            f"the challenges new importers face: quality consistency, documentation, and supplier accountability.\n\n"
            f"We offer new importers:\n"
            f"- Dedicated account manager available during your business hours\n"
            f"- Pre-shipment inspection reports with photographic evidence\n"
            f"- Small trial orders: {moq}\n"
            f"- Pricing: {price}\n"
            f"- WhatsApp production updates throughout manufacturing\n\n"
            f"Would you be open to a 15-minute call this week?\n\n"
            f"Warm regards,\n{s['name']}\n{s['title']} | {s['company']}\n{s['email']} | WhatsApp: {s['phone']}"
        )
    elif template == "warm_followup":
        subject = f"Following Up -- Brass Sourcing Opportunity for {company}"
        body = (
            f"Dear {contact},\n\n"
            f"I wanted to follow up on my earlier note regarding premium brass handicrafts from Moradabad.\n\n"
            f"Since my last message we have added 45 new designs curated for the {country} market -- "
            f"including trending items in {cat_str}.\n\n"
            f"Current pricing: {price}. Complimentary samples available for shortlisted designs.\n\n"
            f"Could we schedule a quick 15-minute call?\n\n"
            f"Best regards,\n{s['name']}\n{s['title']} | {s['company']}\n{s['email']}"
        )
    elif template == "sample_offer":
        subject = f"Complimentary Brass Samples for {company} -- No Obligation"
        body = (
            f"Dear {contact},\n\n"
            f"I am pleased to offer {company} a complimentary sample set -- 5-8 pieces across our "
            f"best-performing {cat_str} designs, shipped to {country} at no charge via DHL Express.\n\n"
            f"Each piece comes with specifications, HS codes, and FOB pricing.\n\n"
            f"To receive your samples, simply reply with your delivery address and preferred categories.\n\n"
            f"Best regards,\n{s['name']}\n{s['title']} | {s['company']}\n{s['email']} | {s['phone']}"
        )
    else:
        subject = f"Brass Handicraft Sourcing -- {s['company']}"
        body = f"Dear {contact},\n\nPlease find our product offering attached.\n\nBest regards,\n{s['name']}"

    return {"subject": subject, "body_text": body,
            "template": template, "to_email": json.loads(buyer.email_json or "[]")[:1],
            "personalization": {"company": company, "country": country, "categories": cat_str, "tier": tier}}


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDED REPLY CLASSIFIER
# ══════════════════════════════════════════════════════════════════════════════

import re as _re

_POS_PAT = [r"\binterested\b", r"\byes\b", r"\bsure\b", r"\bplease\b",
            r"\bwould like\b", r"\bsend.*catalogue\b", r"\bcall\b", r"\bmeeting\b"]
_NEG_PAT = [r"\bnot interested\b", r"\bno thanks\b", r"\bdo not contact\b",
            r"\bunsubscribe\b", r"\bremove.*list\b"]
_INTENT_PAT = {
    "requesting_quote": [r"\bprice\b", r"\bquotation\b", r"\bhow much\b"],
    "requesting_sample": [r"\bsample\b", r"\btest order\b", r"\btrial\b"],
    "meeting": [r"\bcall\b", r"\bvideo\b", r"\bschedule\b"],
    "interested": [r"\binterested\b", r"\btell me more\b", r"\bmore info\b"],
    "lost": [r"\bnot interested\b", r"\bcurrent supplier\b"],
    "unsubscribe": [r"\bunsubscribe\b", r"\bdo not contact\b"],
}


def _classify_reply(body: str) -> dict:
    text = body.lower()
    pos = sum(1 for p in _POS_PAT if _re.search(p, text))
    neg = sum(1 for p in _NEG_PAT if _re.search(p, text))
    sentiment = ("negative" if neg >= 2
                 else "not_interested" if neg == 1 and pos == 0
                 else "positive" if pos >= 1
                 else "neutral")
    scores = {k: sum(1 for p in pats if _re.search(p, text)) for k, pats in _INTENT_PAT.items()}
    intent = max(scores, key=lambda k: scores[k]) if any(scores.values()) else "unknown"
    if intent == "unsubscribe":
        sentiment = "negative"
    next_action = {
        "requesting_quote": "send_quotation",
        "requesting_sample": "create_sample_record",
        "meeting": "schedule_call",
        "lost": "close_lead",
        "unsubscribe": "mark_do_not_contact",
    }.get(intent, "send_warm_followup" if sentiment == "neutral" else
          "send_sample_offer" if sentiment == "positive" else "log_and_monitor")
    conf = min(0.99, 0.45 + (pos + neg) * 0.08)
    return {"sentiment": sentiment, "intent": intent,
            "confidence": round(conf, 3), "next_action": next_action}


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDED CLOSURE PROBABILITY
# ══════════════════════════════════════════════════════════════════════════════

_STAGE_BASE_PROB = {
    "prospecting": 10, "qualification": 22, "proposal": 40,
    "negotiation": 65, "won": 100, "lost": 0,
}
_STAGE_DAYS_EST = {
    "prospecting": 120, "qualification": 75, "proposal": 45,
    "negotiation": 18, "won": 0, "lost": 0,
}


def _closure_prob(opp: Opportunity) -> dict:
    stage = (opp.stage or "prospecting").lower()
    val = float(opp.estimated_value_usd or 0)
    stage_score = _STAGE_BASE_PROB.get(stage, 15)
    days_to_close = _STAGE_DAYS_EST.get(stage, 60)
    probability = min(95, max(3, float(stage_score)))
    return {
        "probability_pct": probability,
        "days_to_close_est": days_to_close,
        "weighted_value_usd": round(val * probability / 100, 2),
        "confidence_level": "medium",
    }


# ══════════════════════════════════════════════════════════════════════════════
# GROWTH ENGINE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/growth/recommendations", tags=["growth"])
async def growth_recommendations(limit: int = Query(10, le=50)):
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(GrowthOpp, Buyer, BuyerScore)
            .join(Buyer, GrowthOpp.buyer_id == Buyer.id)
            .join(BuyerScore, BuyerScore.buyer_id == Buyer.id)
            .where(GrowthOpp.status == "active")
            .order_by(GrowthOpp.opportunity_score.desc())
            .limit(limit)
        )).all()
    return {
        "run_date": date.today().isoformat(),
        "count": len(rows),
        "recommendations": [
            {
                "rank": i + 1,
                "company_name": buyer.company_name,
                "country_code": buyer.country_code,
                "buyer_type": buyer.buyer_type,
                "opportunity_score": opp.opportunity_score,
                "composite_lead_score": score.composite_score,
                "estimated_value_usd": float(buyer.estimated_annual_volume_usd or 0),
                "india_import_probability": score.india_import_probability,
                "competitive_gap_score": opp.competitive_gap_score,
                "market_timing_score": opp.market_timing_score,
                "reasoning": opp.reasoning,
                "signals": json.loads(opp.market_signals_json or "[]"),
                "action_type": "initial_contact",
                "email_template": "initial_introduction" if not opp.is_emerging else "emerging_importer",
                "canonical_id": buyer.id,
            }
            for i, (opp, buyer, score) in enumerate(rows)
        ],
    }


@app.get("/api/v1/growth/opportunities", tags=["growth"])
async def growth_opportunities(
    min_score: float = Query(45.0),
    country_code: Optional[str] = Query(None),
    buyer_type: Optional[str] = Query(None),
    is_emerging: Optional[bool] = Query(None),
    page: int = Query(1), page_size: int = Query(50),
):
    async with SessionLocal() as db:
        stmt = (
            select(GrowthOpp, Buyer)
            .join(Buyer, GrowthOpp.buyer_id == Buyer.id)
            .where(GrowthOpp.status == "active", GrowthOpp.opportunity_score >= min_score)
        )
        if country_code:
            stmt = stmt.where(GrowthOpp.country_code == country_code.upper())
        if buyer_type:
            stmt = stmt.where(GrowthOpp.buyer_type == buyer_type)
        if is_emerging is not None:
            stmt = stmt.where(GrowthOpp.is_emerging == is_emerging)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await db.execute(
            stmt.order_by(GrowthOpp.opportunity_score.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )).all()
    return {
        "total": total,
        "results": [
            {
                "id": opp.id,
                "opportunity_score": opp.opportunity_score,
                "company_name": buyer.company_name,
                "country_code": opp.country_code,
                "buyer_type": opp.buyer_type,
                "estimated_value_usd": opp.estimated_value_usd,
                "india_import_probability": opp.india_import_probability,
                "competitive_gap_score": opp.competitive_gap_score,
                "is_emerging": opp.is_emerging,
                "reasoning": opp.reasoning,
                "signals": json.loads(opp.market_signals_json or "[]"),
            }
            for opp, buyer in rows
        ],
    }


@app.get("/api/v1/growth/emerging", tags=["growth"])
async def growth_emerging(min_score: float = Query(40.0), page: int = Query(1), page_size: int = Query(50)):
    async with SessionLocal() as db:
        stmt = (
            select(EmergingImporter, Buyer)
            .join(Buyer, EmergingImporter.buyer_id == Buyer.id)
            .where(EmergingImporter.is_active == True, EmergingImporter.overall_score >= min_score)
        )
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await db.execute(
            stmt.order_by(EmergingImporter.overall_score.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )).all()
    return {
        "total": total,
        "results": [
            {
                "id": em.id,
                "company_name": buyer.company_name,
                "country_code": buyer.country_code,
                "buyer_type": buyer.buyer_type,
                "months_active": em.months_active,
                "shipment_count": em.shipment_count,
                "annual_volume_usd": em.annual_volume_usd,
                "growth_velocity_score": em.growth_velocity_score,
                "overall_score": em.overall_score,
                "category": em.category,
                "confidence": em.confidence,
                "action_recommended": em.action_recommended,
            }
            for em, buyer in rows
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# OUTREACH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/outreach/templates", tags=["outreach"])
async def list_templates():
    return [
        {"name": t, "description": d} for t, d in [
            ("initial_introduction", "First cold outreach to a new buyer"),
            ("warm_followup", "Follow-up after 10 days with no reply"),
            ("sample_offer", "Offer complimentary samples"),
            ("emerging_importer", "Targeted approach for new importers"),
            ("warm_followup", "Re-engage cold lead"),
        ]
    ]


@app.post("/api/v1/outreach/generate", tags=["outreach"])
async def generate_email(body: dict):
    buyer_id = body.get("canonical_id") or body.get("buyer_id")
    template = body.get("template_name", "initial_introduction")
    async with SessionLocal() as db:
        buyer = await db.get(Buyer, buyer_id)
        if not buyer:
            raise HTTPException(404, "Buyer not found")
    result = _gen_email(buyer, template, body.get("sender"))
    return result


@app.get("/api/v1/outreach/campaigns", tags=["outreach"])
async def list_campaigns():
    async with SessionLocal() as db:
        rows = (await db.execute(select(OutreachCampaign).order_by(OutreachCampaign.created_at.desc()))).scalars().all()
    return {"campaigns": [{"id": c.id, "name": c.name, "status": c.status,
                            "emails_sent": c.emails_sent, "replies_received": c.replies_received}
                          for c in rows]}


@app.post("/api/v1/outreach/campaigns", tags=["outreach"], status_code=201)
async def create_campaign(body: dict):
    async with SessionLocal() as db:
        c = OutreachCampaign(**{k: v for k, v in body.items() if hasattr(OutreachCampaign, k)})
        db.add(c)
        await db.commit()
        await db.refresh(c)
    return {"id": c.id, "name": c.name, "status": c.status}


@app.post("/api/v1/outreach/replies/ingest", tags=["outreach"], status_code=201)
async def ingest_reply(body: dict):
    text = body.get("body_text", "")
    result = _classify_reply(text)
    async with SessionLocal() as db:
        r = EmailReply(
            from_email=body.get("from_email", "unknown@example.com"),
            from_name=body.get("from_name"),
            subject=body.get("subject"),
            body_text=text,
            sentiment=result["sentiment"],
            intent=result["intent"],
            confidence_score=result["confidence"],
            signals_json=json.dumps({}),
            suggested_next_action=result["next_action"],
            outreach_email_id=body.get("outreach_email_id"),
            lead_id=body.get("lead_id"),
        )
        db.add(r)
        await db.commit()
        await db.refresh(r)
    return {"reply_id": r.id, **result}


@app.get("/api/v1/outreach/replies", tags=["outreach"])
async def list_replies(sentiment: Optional[str] = Query(None), page: int = Query(1)):
    async with SessionLocal() as db:
        stmt = select(EmailReply)
        if sentiment:
            stmt = stmt.where(EmailReply.sentiment == sentiment)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (await db.execute(stmt.order_by(EmailReply.created_at.desc()).offset((page - 1) * 50).limit(50))).scalars().all()
    return {"total": total, "replies": [
        {"id": r.id, "from_email": r.from_email, "sentiment": r.sentiment,
         "intent": r.intent, "next_action": r.suggested_next_action} for r in rows
    ]}


@app.get("/api/v1/outreach/stats/overview", tags=["outreach"])
async def outreach_stats():
    async with SessionLocal() as db:
        total_campaigns = (await db.execute(select(func.count(OutreachCampaign.id)))).scalar_one()
        total_emails = (await db.execute(select(func.count(OutreachEmail.id)))).scalar_one()
        total_replies = (await db.execute(select(func.count(EmailReply.id)))).scalar_one()
        positive = (await db.execute(
            select(func.count(EmailReply.id)).where(EmailReply.sentiment == "positive")
        )).scalar_one()
        by_intent = (await db.execute(
            select(EmailReply.intent, func.count(EmailReply.id).label("cnt"))
            .group_by(EmailReply.intent).order_by(func.count(EmailReply.id).desc())
        )).fetchall()
    return {
        "campaigns": total_campaigns, "emails_generated": total_emails,
        "replies": total_replies, "positive_replies": positive,
        "positive_rate_pct": round(positive / max(1, total_replies) * 100, 2),
        "by_intent": [{"intent": r.intent, "count": r.cnt} for r in by_intent],
    }


# ══════════════════════════════════════════════════════════════════════════════
# EXECUTIVE DASHBOARD ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/executive/overview", tags=["executive"])
async def exec_overview():
    async with SessionLocal() as db:
        total_buyers = (await db.execute(select(func.count(Buyer.id)).where(Buyer.is_active == True))).scalar_one()
        avg_score = (await db.execute(select(func.avg(BuyerScore.composite_score)))).scalar_one() or 0
        hot = (await db.execute(
            select(func.count(BuyerScore.id)).where(BuyerScore.tier.in_(["A", "B"]))
        )).scalar_one()
        crm_leads = (await db.execute(select(func.count(Lead.id)))).scalar_one()
        active_opps = (await db.execute(
            select(func.count(Opportunity.id)).where(Opportunity.stage.notin_(["won", "lost"]))
        )).scalar_one()
        pipeline_val = (await db.execute(
            select(func.sum(Opportunity.estimated_value_usd)).where(Opportunity.stage.notin_(["won", "lost"]))
        )).scalar_one() or 0
        growth_opps = (await db.execute(
            select(func.count(GrowthOpp.id)).where(GrowthOpp.status == "active")
        )).scalar_one()
        emerging_count = (await db.execute(
            select(func.count(EmergingImporter.id)).where(EmergingImporter.is_active == True)
        )).scalar_one()
        total_replies = (await db.execute(select(func.count(EmailReply.id)))).scalar_one()
    return {
        "generated_at": date.today().isoformat(),
        "buyer_intelligence": {
            "total_buyers": total_buyers,
            "avg_lead_score": round(float(avg_score), 2),
            "tier_a_b_buyers": hot,
            "active_growth_opportunities": growth_opps,
            "emerging_importers": emerging_count,
        },
        "crm_pipeline": {
            "total_leads": crm_leads,
            "active_opportunities": active_opps,
            "pipeline_value_usd": float(pipeline_val),
        },
        "outreach": {"total_replies": total_replies},
    }


@app.get("/api/v1/executive/country-heatmap", tags=["executive"])
async def exec_country_heatmap():
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(
                Buyer.country_code, Buyer.country_name,
                func.count(Buyer.id).label("buyer_count"),
                func.sum(Buyer.estimated_annual_volume_usd).label("vol"),
                func.avg(BuyerScore.composite_score).label("avg_score"),
            )
            .outerjoin(BuyerScore, BuyerScore.buyer_id == Buyer.id)
            .where(Buyer.is_active == True)
            .group_by(Buyer.country_code, Buyer.country_name)
            .having(func.count(Buyer.id) >= 2)
            .order_by(func.sum(Buyer.estimated_annual_volume_usd).desc())
        )).fetchall()
    heatmap = []
    for r in rows:
        cc = r.country_code or "XX"
        ms = _COUNTRY_OPP.get(cc, 50)
        avg = float(r.avg_score or 0)
        opp_index = round(ms * 0.40 + avg * 0.60, 2)
        heatmap.append({
            "country_code": cc, "country_name": r.country_name,
            "buyer_count": r.buyer_count,
            "total_volume_usd": float(r.vol or 0),
            "avg_lead_score": round(avg, 2),
            "market_opportunity_score": ms,
            "country_opportunity_index": opp_index,
        })
    heatmap.sort(key=lambda x: x["country_opportunity_index"], reverse=True)
    return {"country_count": len(heatmap), "heatmap": heatmap}


@app.get("/api/v1/executive/active-deals", tags=["executive"])
async def exec_active_deals():
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Opportunity, Lead)
            .outerjoin(Lead, Opportunity.lead_id == Lead.id)
            .where(Opportunity.stage.notin_(["won", "lost"]))
            .order_by(Opportunity.estimated_value_usd.desc())
            .limit(50)
        )).all()
    deals = []
    for opp, lead in rows:
        prob = _closure_prob(opp)
        deals.append({
            "opportunity_id": opp.id, "title": opp.title,
            "stage": opp.stage, "company": lead.company_name if lead else None,
            "estimated_value_usd": float(opp.estimated_value_usd or 0),
            "probability_pct": prob["probability_pct"],
            "weighted_value_usd": prob["weighted_value_usd"],
            "days_to_close_est": prob["days_to_close_est"],
        })
    total = sum(d["estimated_value_usd"] for d in deals)
    weighted = sum(d["weighted_value_usd"] for d in deals)
    return {"total_deals": len(deals), "total_pipeline_usd": round(total, 2),
            "weighted_pipeline_usd": round(weighted, 2), "deals": deals}


@app.get("/api/v1/executive/forecast", tags=["executive"])
async def exec_forecast(months_ahead: int = Query(6, ge=1, le=12)):
    today = date.today()
    forecasts = []
    for i in range(months_ahead):
        m = today.month + i
        y = today.year
        while m > 12:
            m -= 12
            y += 1
        month_str = f"{y}-{m:02d}"
        season = _SEASONAL.get(m, 1.0)
        async with SessionLocal() as db:
            pipeline_val = (await db.execute(
                select(func.sum(Opportunity.estimated_value_usd))
                .where(Opportunity.stage.notin_(["won", "lost"]))
            )).scalar_one() or 0
            po_val = (await db.execute(
                select(func.sum(PurchaseOrder.total_value))
                .where(PurchaseOrder.status.in_(["new", "production"]))
            )).scalar_one() or 0
        pipeline_float = float(pipeline_val) / max(1, months_ahead)
        confirmed = float(po_val) / max(1, months_ahead)
        base = (confirmed + pipeline_float * 0.35) * season
        forecasts.append({
            "month": month_str,
            "base_case_usd": round(base, 2),
            "upside_case_usd": round(base * 1.25, 2),
            "downside_case_usd": round(base * 0.75, 2),
            "confirmed_usd": round(confirmed, 2),
            "weighted_pipeline_usd": round(pipeline_float * 0.35, 2),
            "seasonal_factor": round(season, 4),
        })
    return {
        "months_ahead": months_ahead,
        "total_base_case_usd": round(sum(f["base_case_usd"] for f in forecasts), 2),
        "total_upside_usd": round(sum(f["upside_case_usd"] for f in forecasts), 2),
        "forecast": forecasts,
    }


@app.get("/api/v1/executive/pipeline-analysis", tags=["executive"])
async def exec_pipeline():
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Opportunity.stage, func.count(Opportunity.id).label("cnt"),
                   func.sum(Opportunity.estimated_value_usd).label("val"))
            .group_by(Opportunity.stage)
        )).fetchall()
        total = (await db.execute(select(func.count(Opportunity.id)))).scalar_one()
        won = next((r for r in rows if r.stage == "won"), None)
        lost = next((r for r in rows if r.stage == "lost"), None)
        closed = (won.cnt if won else 0) + (lost.cnt if lost else 0)
        win_rate = round((won.cnt / max(1, closed)) * 100, 2) if won else 0
    return {
        "total_opportunities": total,
        "win_rate_pct": win_rate,
        "won_value_usd": float(won.val or 0) if won else 0,
        "by_stage": [
            {"stage": r.stage, "count": r.cnt, "value_usd": float(r.val or 0)}
            for r in rows if r.stage not in ("won", "lost")
        ],
    }


@app.get("/api/v1/executive/buyer-heatmap", tags=["executive"])
async def exec_buyer_heatmap():
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Buyer.buyer_type, BuyerScore.tier,
                   func.count(Buyer.id).label("count"),
                   func.avg(BuyerScore.composite_score).label("avg_score"))
            .join(BuyerScore, BuyerScore.buyer_id == Buyer.id)
            .group_by(Buyer.buyer_type, BuyerScore.tier)
        )).fetchall()
    matrix: dict = {}
    for r in rows:
        bt = r.buyer_type or "unknown"
        if bt not in matrix:
            matrix[bt] = {}
        matrix[bt][r.tier] = {"count": r.count, "avg_score": round(float(r.avg_score or 0), 2)}
    return {"tiers": ["A", "B", "C", "D", "F"], "buyer_types": sorted(matrix.keys()), "matrix": matrix}


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("")
    print("=" * 72)
    print("  BrassExport Intelligence -- Autonomous Export Growth Platform")
    print("  Buyer Intel + AI Scoring + CRM + Calculator + Growth Engine")
    print("  + Outreach + Executive Dashboard")
    print("=" * 72)
    print("  Swagger UI (all endpoints)  ->  http://localhost:8000/docs")
    print("")
    print("  [Buyer Intelligence]")
    print("  Buyers                      ->  /api/v1/buyers/")
    print("  Search                      ->  /api/v1/search/?q=brass")
    print("  Analytics                   ->  /api/v1/analytics/overview")
    print("")
    print("  [AI Lead Scoring]")
    print("  Top Buyers                  ->  /api/v1/dashboard/top-buyers")
    print("  New Buyers                  ->  /api/v1/dashboard/new-buyers")
    print("  High Growth                 ->  /api/v1/dashboard/high-growth")
    print("  Untapped Markets            ->  /api/v1/dashboard/untapped")
    print("")
    print("  [Autonomous Growth Engine]")
    print("  Daily Top-10 Recs           ->  /api/v1/growth/recommendations")
    print("  Ranked Opportunities        ->  /api/v1/growth/opportunities")
    print("  Emerging Importers          ->  /api/v1/growth/emerging")
    print("")
    print("  [Outreach]")
    print("  Generate Email              ->  POST /api/v1/outreach/generate")
    print("  Ingest Reply                ->  POST /api/v1/outreach/replies/ingest")
    print("  Campaign Stats              ->  /api/v1/outreach/stats/overview")
    print("")
    print("  [Executive Dashboard]")
    print("  KPI Overview                ->  /api/v1/executive/overview")
    print("  Country Heatmap             ->  /api/v1/executive/country-heatmap")
    print("  Active Deals                ->  /api/v1/executive/active-deals")
    print("  Revenue Forecast            ->  /api/v1/executive/forecast")
    print("  Pipeline Analysis           ->  /api/v1/executive/pipeline-analysis")
    print("  Buyer Segment Matrix        ->  /api/v1/executive/buyer-heatmap")
    print("")
    print("  [CRM]")
    print("  Leads                       ->  /api/v1/crm/leads/")
    print("  CRM Overview                ->  /api/v1/crm/stats/overview")
    print("")
    print("  [Export Calculator]")
    print("  Calculate                   ->  POST /api/v1/calculator/calculate")
    print("  Compare Modes               ->  POST /api/v1/calculator/compare")
    print("")
    print("  Press Ctrl+C to stop")
    print("=" * 72)
    print("")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
