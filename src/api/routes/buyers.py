"""
Buyer CRUD endpoints.
GET  /buyers/           — paginated list with filters
GET  /buyers/{id}       — single canonical buyer
GET  /buyers/{id}/raw   — all raw source records for a canonical buyer
PATCH /buyers/{id}      — update verified/active flags
DELETE /buyers/{id}     — soft delete (is_active=False)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.api.schemas import BuyerSearchParams, CanonicalBuyerOut, PaginatedResponse, RawBuyerOut
from src.core.models import BuyerSourceLink, CanonicalBuyer, RawBuyer

router = APIRouter(prefix="/buyers", tags=["buyers"])


@router.get("/", response_model=PaginatedResponse)
async def list_buyers(
    country_code: Optional[str] = Query(None),
    buyer_type: Optional[str] = Query(None),
    min_confidence: float = Query(0.0, ge=0, le=1),
    verified_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("confidence_score"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CanonicalBuyer).where(CanonicalBuyer.is_active == True)

    if country_code:
        stmt = stmt.where(CanonicalBuyer.country_code == country_code.upper())
    if buyer_type:
        stmt = stmt.where(CanonicalBuyer.buyer_type == buyer_type)
    if min_confidence > 0:
        stmt = stmt.where(CanonicalBuyer.confidence_score >= min_confidence)
    if verified_only:
        stmt = stmt.where(CanonicalBuyer.is_verified == True)

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Sort
    sort_col = getattr(CanonicalBuyer, sort_by, CanonicalBuyer.confidence_score)
    stmt = stmt.order_by(
        sort_col.desc() if sort_order == "desc" else sort_col.asc()
    )

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = (await db.execute(stmt)).scalars().all()
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
        results=[CanonicalBuyerOut.model_validate(r) for r in rows],
    )


@router.get("/{buyer_id}", response_model=CanonicalBuyerOut)
async def get_buyer(buyer_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(CanonicalBuyer, buyer_id)
    if not row or not row.is_active:
        raise HTTPException(status_code=404, detail="Buyer not found")
    return CanonicalBuyerOut.model_validate(row)


@router.get("/{buyer_id}/raw", response_model=list[RawBuyerOut])
async def get_buyer_raw_records(buyer_id: int, db: AsyncSession = Depends(get_db)):
    """All raw source records that were merged into this canonical buyer."""
    stmt = (
        select(RawBuyer)
        .join(BuyerSourceLink, BuyerSourceLink.raw_buyer_id == RawBuyer.id)
        .where(BuyerSourceLink.canonical_id == buyer_id)
        .order_by(RawBuyer.confidence_score.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [RawBuyerOut.model_validate(r) for r in rows]


@router.patch("/{buyer_id}", response_model=CanonicalBuyerOut)
async def update_buyer(
    buyer_id: int,
    verified: Optional[bool] = None,
    active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(CanonicalBuyer, buyer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Buyer not found")
    if verified is not None:
        row.is_verified = verified
    if active is not None:
        row.is_active = active
    await db.flush()
    return CanonicalBuyerOut.model_validate(row)


@router.delete("/{buyer_id}", status_code=204)
async def delete_buyer(buyer_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(CanonicalBuyer, buyer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Buyer not found")
    row.is_active = False
    await db.flush()
