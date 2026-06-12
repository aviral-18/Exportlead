"""
Growth-engine database models.
Tracks discovery runs, ranked opportunities, daily recommendations,
emerging importers, deal probability scores, and export forecasts.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Integer, Numeric, String, Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# Re-import from core so all models share the same metadata
from src.core.models import Base  # noqa: F811, E402


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    sources_queried: Mapped[int] = mapped_column(Integer, default=0)
    raw_records_scanned: Mapped[int] = mapped_column(Integer, default=0)
    new_buyers_found: Mapped[int] = mapped_column(Integer, default=0)
    existing_buyers_updated: Mapped[int] = mapped_column(Integer, default=0)
    scored: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_created: Mapped[int] = mapped_column(Integer, default=0)
    emerging_flagged: Mapped[int] = mapped_column(Integer, default=0)
    top_opportunity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    run_duration_seconds: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)


class GrowthOpportunity(Base):
    __tablename__ = "growth_opportunities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    discovery_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    opportunity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), index=True)
    rank_position: Mapped[Optional[int]] = mapped_column(Integer)
    country_code: Mapped[Optional[str]] = mapped_column(String(3), index=True)
    buyer_type: Mapped[Optional[str]] = mapped_column(String(64))
    estimated_value_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    india_import_probability: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    product_fit_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    competitive_gap_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    market_timing_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    country_market_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    is_new_discovery: Mapped[bool] = mapped_column(Boolean, default=False)
    is_emerging: Mapped[bool] = mapped_column(Boolean, default=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    market_signals_json: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    crm_lead_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    added_to_crm_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())


class DailyRecommendation(Base):
    __tablename__ = "daily_recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    discovery_run_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    opportunity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    composite_lead_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    key_signals_json: Mapped[Optional[str]] = mapped_column(Text)
    action_type: Mapped[Optional[str]] = mapped_column(String(32))
    email_template: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    acted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmergingImporter(Base):
    __tablename__ = "emerging_importers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    first_import_date: Mapped[Optional[str]] = mapped_column(String(10))
    months_active: Mapped[Optional[int]] = mapped_column(Integer)
    shipment_count: Mapped[Optional[int]] = mapped_column(Integer)
    annual_volume_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    growth_velocity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    market_timing_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    overall_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    category: Mapped[Optional[str]] = mapped_column(String(64))
    trend_json: Mapped[Optional[str]] = mapped_column(Text)
    action_recommended: Mapped[Optional[str]] = mapped_column(String(64))
    confidence: Mapped[Optional[str]] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    crm_lead_id: Mapped[Optional[int]] = mapped_column(BigInteger)


class DealProbabilityScore(Base):
    __tablename__ = "deal_probability_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    probability_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    confidence_level: Mapped[Optional[str]] = mapped_column(String(16))
    days_to_close_est: Mapped[Optional[int]] = mapped_column(Integer)
    expected_value_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    weighted_value_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    positive_signals_json: Mapped[Optional[str]] = mapped_column(Text)
    risk_factors_json: Mapped[Optional[str]] = mapped_column(Text)
    scoring_breakdown_json: Mapped[Optional[str]] = mapped_column(Text)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class ExportForecast(Base):
    __tablename__ = "export_forecasts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    forecast_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    base_case_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    upside_case_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    downside_case_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    confirmed_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    weighted_pipeline_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    seasonal_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    active_opportunities: Mapped[Optional[int]] = mapped_column(Integer)
    avg_close_probability: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    opportunities_json: Mapped[Optional[str]] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
