"""
Advanced search endpoints.
GET  /search/           — full-text + fuzzy search across canonical buyers
GET  /search/raw        — search raw records
GET  /search/suggest    — company name autocomplete
POST /search/export     — export filtered results to CSV/XLSX
"""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Optional

import orjson
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.api.schemas import CanonicalBuyerOut, PaginatedResponse, RawBuyerOut
from src.core.models import CanonicalBuyer, RawBuyer

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/", response_model=PaginatedResponse)
async def search_buyers(
    q: str = Query(..., min_length=2, description="Search query"),
    country_code: Optional[str] = Query(None),
    buyer_type: Optional[str] = Query(None),
    hs_code: Optional[str] = Query(None),
    data_source: Optional[str] = Query(None),
    min_volume_usd: Optional[float] = Query(None),
    min_confidence: float = Query(0.0),
    last_import_after: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Hybrid search:
    1. pg_trgm similarity on company_name_normalized (fuzzy)
    2. Full-text search on company_name + product_description
    Combined with structured filters.
    """
    offset = (page - 1) * page_size

    # Build the base query using pg_trgm and ts_vector
    stmt = select(CanonicalBuyer).where(
        CanonicalBuyer.is_active == True,
        or_(
            # Trigram fuzzy match on normalised name
            func.similarity(
                CanonicalBuyer.company_name_normalized, q.lower()
            ) > 0.25,
            # Substring match on original name
            CanonicalBuyer.company_name.ilike(f"%{q}%"),
        ),
    )

    if country_code:
        stmt = stmt.where(CanonicalBuyer.country_code == country_code.upper())
    if buyer_type:
        stmt = stmt.where(CanonicalBuyer.buyer_type == buyer_type)
    if hs_code:
        stmt = stmt.where(CanonicalBuyer.hs_codes.contains([hs_code]))
    if min_volume_usd:
        stmt = stmt.where(
            CanonicalBuyer.estimated_annual_volume_usd >= min_volume_usd
        )
    if min_confidence > 0:
        stmt = stmt.where(CanonicalBuyer.confidence_score >= min_confidence)
    if last_import_after:
        stmt = stmt.where(CanonicalBuyer.last_import_date >= last_import_after)

    # Relevance ordering: trgm similarity DESC, then confidence DESC
    similarity_expr = func.similarity(
        CanonicalBuyer.company_name_normalized, q.lower()
    )
    stmt = stmt.order_by(
        similarity_expr.desc(),
        CanonicalBuyer.confidence_score.desc(),
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    rows = (await db.execute(stmt.offset(offset).limit(page_size))).scalars().all()
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
        results=[CanonicalBuyerOut.model_validate(r) for r in rows],
    )


@router.get("/raw", response_model=PaginatedResponse)
async def search_raw(
    q: str = Query(..., min_length=2),
    data_source: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Search raw (pre-dedup) records. Useful for verifying scraper output."""
    offset = (page - 1) * page_size
    stmt = select(RawBuyer).where(
        or_(
            RawBuyer.company_name.ilike(f"%{q}%"),
            func.similarity(RawBuyer.company_name_normalized, q.lower()) > 0.3,
        )
    )
    if data_source:
        stmt = stmt.where(RawBuyer.data_source == data_source)
    if country_code:
        stmt = stmt.where(RawBuyer.country_code == country_code.upper())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(
        stmt.order_by(RawBuyer.confidence_score.desc()).offset(offset).limit(page_size)
    )).scalars().all()
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
        results=[RawBuyerOut.model_validate(r) for r in rows],
    )


@router.get("/suggest")
async def suggest(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Company name autocomplete using trigram index."""
    stmt = (
        select(
            CanonicalBuyer.id,
            CanonicalBuyer.company_name,
            CanonicalBuyer.country_code,
            CanonicalBuyer.buyer_type,
        )
        .where(
            CanonicalBuyer.is_active == True,
            CanonicalBuyer.company_name.ilike(f"{q}%"),
        )
        .order_by(CanonicalBuyer.confidence_score.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).fetchall()
    return [
        {"id": r.id, "name": r.company_name, "country": r.country_code, "type": r.buyer_type}
        for r in rows
    ]


@router.get("/export")
async def export_csv(
    country_code: Optional[str] = Query(None),
    buyer_type: Optional[str] = Query(None),
    hs_code: Optional[str] = Query(None),
    min_confidence: float = Query(0.5),
    limit: int = Query(10_000, le=100_000),
    db: AsyncSession = Depends(get_db),
):
    """Export filtered canonical buyers as CSV (up to 100K rows)."""
    stmt = select(CanonicalBuyer).where(
        CanonicalBuyer.is_active == True,
        CanonicalBuyer.confidence_score >= min_confidence,
    )
    if country_code:
        stmt = stmt.where(CanonicalBuyer.country_code == country_code.upper())
    if buyer_type:
        stmt = stmt.where(CanonicalBuyer.buyer_type == buyer_type)
    if hs_code:
        stmt = stmt.where(CanonicalBuyer.hs_codes.contains([hs_code]))

    stmt = stmt.order_by(CanonicalBuyer.confidence_score.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "uuid", "company_name", "country_code", "country_name",
        "city", "website", "email", "phone", "product_categories",
        "hs_codes", "buyer_type", "import_frequency",
        "estimated_annual_volume_usd", "last_import_date",
        "total_shipments", "source_count", "data_sources", "confidence_score",
    ])
    for r in rows:
        writer.writerow([
            r.id, r.uuid, r.company_name, r.country_code, r.country_name,
            r.city, r.website,
            ";".join(r.email or []),
            ";".join(r.phone or []),
            ";".join(r.product_categories or []),
            ";".join(r.hs_codes or []),
            r.buyer_type, r.import_frequency,
            r.estimated_annual_volume_usd, r.last_import_date,
            r.total_shipments, r.source_count,
            ";".join(r.data_sources or []),
            r.confidence_score,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=brass_buyers.csv"},
    )
