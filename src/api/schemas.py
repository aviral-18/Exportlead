"""Pydantic schemas for the API layer."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class BuyerBase(BaseModel):
    company_name: str
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    state_province: Optional[str] = None
    city: Optional[str] = None
    website: Optional[str] = None
    product_categories: Optional[list[str]] = []
    hs_codes: Optional[list[str]] = []
    buyer_type: Optional[str] = None
    import_frequency: Optional[str] = None
    estimated_annual_volume_usd: Optional[Decimal] = None
    last_import_date: Optional[date] = None
    confidence_score: Optional[Decimal] = None


class RawBuyerOut(BuyerBase):
    id: int
    external_id: Optional[str] = None
    data_source: str
    email: Optional[list[str]] = []
    phone: Optional[list[str]] = []
    address: Optional[str] = None
    total_shipments: Optional[int] = None
    is_duplicate: bool
    canonical_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CanonicalBuyerOut(BuyerBase):
    id: int
    uuid: str
    trade_name: Optional[str] = None
    email: Optional[list[str]] = []
    phone: Optional[list[str]] = []
    address: Optional[str] = None
    total_shipments: Optional[int] = None
    source_count: int
    data_sources: Optional[list[str]] = []
    is_verified: bool
    is_active: bool
    linkedin_url: Optional[str] = None
    description: Optional[str] = None
    first_import_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BuyerSearchParams(BaseModel):
    q: Optional[str] = Field(None, description="Full-text / fuzzy search query")
    country_code: Optional[str] = Field(None, description="ISO-3166 alpha-2")
    buyer_type: Optional[str] = None
    data_source: Optional[str] = None
    hs_code: Optional[str] = Field(None, description="Filter by HS code prefix")
    min_volume_usd: Optional[float] = None
    max_volume_usd: Optional[float] = None
    min_confidence: float = Field(0.0, ge=0, le=1)
    last_import_after: Optional[date] = None
    verified_only: bool = False
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=500)
    sort_by: str = Field("confidence_score", description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    results: list


class AnalyticsByCountry(BaseModel):
    country_code: Optional[str]
    country_name: Optional[str]
    buyer_count: int
    avg_confidence: float
    total_volume_usd: Optional[float]


class AnalyticsBySource(BaseModel):
    data_source: str
    record_count: int
    unique_countries: int
    avg_confidence: float
    last_ingested: Optional[datetime]


class AnalyticsByBuyerType(BaseModel):
    buyer_type: Optional[str]
    count: int
    pct: float


class IngestionRunOut(BaseModel):
    id: int
    data_source: str
    status: str
    records_fetched: int
    records_inserted: int
    records_updated: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TriggerScrapeRequest(BaseModel):
    scraper: str = Field(..., description="Scraper class path or short name")
    priority: int = Field(5, ge=1, le=10)


class TriggerScrapeResponse(BaseModel):
    task_id: str
    scraper: str
    status: str = "queued"
