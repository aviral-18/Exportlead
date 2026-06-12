"""
SQLAlchemy 2.0 models for BrassExport Intelligence.

Partitioning strategy:
  raw_buyers  — HASH on id, 32 partitions (handles 50M+ rows, ~1.5M/partition)
  canonical_buyers — unpartitioned master (est. 15–20M after dedup)
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ─── Enumerations ─────────────────────────────────────────────────────────────

class BuyerType(str, enum.Enum):
    IMPORTER = "importer"
    DISTRIBUTOR = "distributor"
    WHOLESALER = "wholesaler"
    RETAILER = "retailer"
    PROCUREMENT_AGENCY = "procurement_agency"
    HOSPITALITY = "hospitality"
    SOURCING_COMPANY = "sourcing_company"
    OEM = "oem"
    GOVERNMENT = "government"
    NGO = "ngo"
    UNKNOWN = "unknown"


class ImportFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    SPORADIC = "sporadic"
    UNKNOWN = "unknown"


class DataSource(str, enum.Enum):
    # Trade intelligence
    VOLZA = "volza"
    IMPORT_YETI = "import_yeti"
    UN_COMTRADE = "un_comtrade"
    TRADE_MAP = "trade_map"
    EXPORT_GENIUS = "export_genius"
    DATAMYNE = "datamyne"
    PANJIVA = "panjiva"
    INDIA_EXPORT_DATA = "india_export_data"
    # B2B marketplaces
    ALIBABA = "alibaba"
    GLOBAL_SOURCES = "global_sources"
    TRADEKEY = "tradekey"
    EC21 = "ec21"
    EWORLDTRADE = "eworldtrade"
    TRADEINDIA = "tradeindia"
    INDIAMART = "indiamart"
    MADE_IN_CHINA = "made_in_china"
    # Procurement
    SAM_GOV = "sam_gov"
    TED_EUROPA = "ted_europa"
    UNGM = "ungm"
    WORLD_BANK = "world_bank"
    ADB = "adb"
    # Trade fairs
    AMBIENTE = "ambiente"
    MAISON_OBJET = "maison_objet"
    NY_NOW = "ny_now"
    IHGF = "ihgf"


class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# ─── Raw buyers (partitioned) ─────────────────────────────────────────────────

class RawBuyer(Base):
    """
    Single ingest record from any source.
    Partitioned by HASH(id) with 32 partitions via DDL in migration.
    """
    __tablename__ = "raw_buyers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(512))
    data_source: Mapped[str] = mapped_column(
        Enum(DataSource, name="data_source_enum"), nullable=False, index=True
    )
    ingestion_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, index=True
    )

    # Company identity
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    company_name_normalized: Mapped[Optional[str]] = mapped_column(Text, index=True)
    company_name_tokens: Mapped[Optional[str]] = mapped_column(
        Text, comment="space-joined lowercased tokens for trigram index"
    )

    # Location
    country_code: Mapped[Optional[str]] = mapped_column(String(3), index=True)
    country_name: Mapped[Optional[str]] = mapped_column(String(128))
    state_province: Mapped[Optional[str]] = mapped_column(String(128))
    city: Mapped[Optional[str]] = mapped_column(String(128))
    postal_code: Mapped[Optional[str]] = mapped_column(String(32))
    address: Mapped[Optional[str]] = mapped_column(Text)

    # Contact
    website: Mapped[Optional[str]] = mapped_column(Text)
    website_domain: Mapped[Optional[str]] = mapped_column(String(256), index=True)
    email: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    phone: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    contact_person: Mapped[Optional[str]] = mapped_column(Text)

    # Products
    product_categories: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    hs_codes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    product_description: Mapped[Optional[str]] = mapped_column(Text)

    # Trade data
    buyer_type: Mapped[Optional[str]] = mapped_column(
        Enum(BuyerType, name="buyer_type_enum"), index=True
    )
    import_frequency: Mapped[Optional[str]] = mapped_column(
        Enum(ImportFrequency, name="import_frequency_enum")
    )
    estimated_annual_volume_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2)
    )
    volume_currency: Mapped[Optional[str]] = mapped_column(String(3))
    last_import_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    first_import_date: Mapped[Optional[date]] = mapped_column(Date)
    total_shipments: Mapped[Optional[int]] = mapped_column(Integer)
    total_suppliers: Mapped[Optional[int]] = mapped_column(Integer)

    # Quality
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), default=Decimal("0.5")
    )
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    canonical_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)

    # Raw payload
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Housekeeping
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_raw_buyers_source_external",
            "data_source",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index(
            "ix_raw_buyers_country_type",
            "country_code",
            "buyer_type",
        ),
        Index(
            "ix_raw_buyers_name_trgm",
            "company_name_normalized",
            postgresql_using="gin",
            postgresql_ops={"company_name_normalized": "gin_trgm_ops"},
        ),
        Index(
            "ix_raw_buyers_hs_codes_gin",
            "hs_codes",
            postgresql_using="gin",
        ),
        Index(
            "ix_raw_buyers_categories_gin",
            "product_categories",
            postgresql_using="gin",
        ),
        Index("ix_raw_buyers_last_import", "last_import_date"),
        {"postgresql_partition_by": "HASH (id)"},
    )


# ─── Canonical / deduplicated master records ──────────────────────────────────

class CanonicalBuyer(Base):
    __tablename__ = "canonical_buyers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        default=lambda: str(uuid4()),
        unique=True,
        index=True,
    )

    # Best-known identity (merged from raw records)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    company_name_normalized: Mapped[Optional[str]] = mapped_column(Text, index=True)
    trade_name: Mapped[Optional[str]] = mapped_column(Text)

    country_code: Mapped[Optional[str]] = mapped_column(String(3), index=True)
    country_name: Mapped[Optional[str]] = mapped_column(String(128))
    state_province: Mapped[Optional[str]] = mapped_column(String(128))
    city: Mapped[Optional[str]] = mapped_column(String(128))
    address: Mapped[Optional[str]] = mapped_column(Text)

    website: Mapped[Optional[str]] = mapped_column(Text)
    website_domain: Mapped[Optional[str]] = mapped_column(String(256), unique=True)
    email: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    phone: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))

    product_categories: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    hs_codes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))

    buyer_type: Mapped[Optional[str]] = mapped_column(
        Enum(BuyerType, name="buyer_type_enum"), index=True
    )
    import_frequency: Mapped[Optional[str]] = mapped_column(
        Enum(ImportFrequency, name="import_frequency_enum")
    )
    estimated_annual_volume_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2)
    )
    last_import_date: Mapped[Optional[date]] = mapped_column(Date)
    first_import_date: Mapped[Optional[date]] = mapped_column(Date)
    total_shipments: Mapped[Optional[int]] = mapped_column(Integer)

    # Aggregated data
    source_count: Mapped[int] = mapped_column(Integer, default=1)
    data_sources: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), default=Decimal("0.5")
    )

    # Enrichment flags
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    annual_revenue_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    founded_year: Mapped[Optional[int]] = mapped_column(SmallInteger)

    extra: Mapped[Optional[dict]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_canonical_name_trgm",
            "company_name_normalized",
            postgresql_using="gin",
            postgresql_ops={"company_name_normalized": "gin_trgm_ops"},
        ),
        Index(
            "ix_canonical_hs_codes_gin",
            "hs_codes",
            postgresql_using="gin",
        ),
        Index("ix_canonical_country_type", "country_code", "buyer_type"),
        Index("ix_canonical_confidence", "confidence_score"),
    )


# ─── Source → canonical links ─────────────────────────────────────────────────

class BuyerSourceLink(Base):
    __tablename__ = "buyer_source_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    raw_buyer_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    data_source: Mapped[str] = mapped_column(String(64), nullable=False)
    match_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("canonical_id", "raw_buyer_id", name="uq_link_canonical_raw"),
    )


# ─── Dedup candidates ─────────────────────────────────────────────────────────

class DedupCandidate(Base):
    """Pairs of raw_buyer IDs that are candidates for merging."""
    __tablename__ = "dedup_candidates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_a: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    id_b: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name_similarity: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    domain_match: Mapped[bool] = mapped_column(Boolean, default=False)
    country_match: Mapped[bool] = mapped_column(Boolean, default=False)
    combined_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_match: Mapped[Optional[bool]] = mapped_column(Boolean)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("id_a", "id_b", name="uq_dedup_pair"),
        Index("ix_dedup_combined_score", "combined_score"),
        Index("ix_dedup_unresolved", "resolved", postgresql_where=text("resolved = false")),
    )


# ─── Ingestion run tracking ───────────────────────────────────────────────────

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    data_source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum(IngestionStatus, name="ingestion_status_enum"),
        default=IngestionStatus.PENDING,
        index=True,
    )
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    run_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ─── Scraper checkpoints (resumable pagination) ───────────────────────────────

class ScraperCheckpoint(Base):
    __tablename__ = "scraper_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data_source: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    checkpoint_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    last_successful_page: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ─── AI Lead Scores ───────────────────────────────────────────────────────────

class LeadScore(Base):
    """
    One row per canonical buyer. Upserted by the scoring engine.
    All dimension scores are 0-100 floats; composite is the weighted sum.
    """
    __tablename__ = "lead_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, index=True
    )

    # Six scoring dimensions
    india_import_probability: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    supplier_switch_probability: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    product_fit_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    growth_trend_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    new_importer_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    import_activity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))

    # Composite 0-100
    composite_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), index=True)

    # Letter tier: A / B / C / D / F
    tier: Mapped[Optional[str]] = mapped_column(String(1), index=True)

    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_lead_scores_composite", "composite_score"),
        Index("ix_lead_scores_india_prob", "india_import_probability"),
        Index("ix_lead_scores_growth", "growth_trend_score"),
        Index("ix_lead_scores_new_importer", "new_importer_score"),
        Index("ix_lead_scores_tier", "tier"),
    )
