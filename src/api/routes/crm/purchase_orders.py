"""Purchase order tracking routes."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from src.core.database import get_session
from src.crm.models import POStatus, ProductionStatus, PurchaseOrder

router = APIRouter(prefix="/purchase-orders")


class POCreate(BaseModel):
    po_number: str
    lead_id: int
    opportunity_id: Optional[int] = None
    quotation_id: Optional[int] = None
    line_items: Optional[dict] = None
    currency: str = "USD"
    total_value: Optional[float] = None
    advance_pct: Optional[float] = None
    advance_amount: Optional[float] = None
    balance_due_date: Optional[date] = None
    payment_terms: Optional[str] = None
    lc_number: Optional[str] = None
    incoterms: Optional[str] = "FOB"
    shipping_port: Optional[str] = "Nhava Sheva, India"
    destination_port: Optional[str] = None
    country_of_destination: Optional[str] = None
    expected_production_days: Optional[int] = None
    notes: Optional[str] = None


class POPatch(BaseModel):
    status: Optional[str] = None
    production_status: Optional[str] = None
    advance_received_date: Optional[date] = None
    balance_received_date: Optional[date] = None
    production_start_date: Optional[date] = None
    production_end_date: Optional[date] = None
    shipment_date: Optional[date] = None
    delivery_date: Optional[date] = None
    bl_number: Optional[str] = None
    container_number: Optional[str] = None
    lc_number: Optional[str] = None
    documents: Optional[dict] = None
    notes: Optional[str] = None


def _fmt(po: PurchaseOrder) -> dict:
    return {
        "id": po.id,
        "po_number": po.po_number,
        "our_reference": po.our_reference,
        "lead_id": po.lead_id,
        "opportunity_id": po.opportunity_id,
        "quotation_id": po.quotation_id,
        "line_items": po.line_items,
        "currency": po.currency,
        "total_value": float(po.total_value) if po.total_value else None,
        "advance_pct": float(po.advance_pct) if po.advance_pct else None,
        "advance_amount": float(po.advance_amount) if po.advance_amount else None,
        "advance_received_date": po.advance_received_date.isoformat() if po.advance_received_date else None,
        "balance_amount": float(po.balance_amount) if po.balance_amount else None,
        "balance_due_date": po.balance_due_date.isoformat() if po.balance_due_date else None,
        "balance_received_date": po.balance_received_date.isoformat() if po.balance_received_date else None,
        "payment_terms": po.payment_terms,
        "lc_number": po.lc_number,
        "incoterms": po.incoterms,
        "shipping_port": po.shipping_port,
        "destination_port": po.destination_port,
        "country_of_destination": po.country_of_destination,
        "bl_number": po.bl_number,
        "container_number": po.container_number,
        "production_status": po.production_status,
        "expected_production_days": po.expected_production_days,
        "production_start_date": po.production_start_date.isoformat() if po.production_start_date else None,
        "production_end_date": po.production_end_date.isoformat() if po.production_end_date else None,
        "shipment_date": po.shipment_date.isoformat() if po.shipment_date else None,
        "delivery_date": po.delivery_date.isoformat() if po.delivery_date else None,
        "status": po.status,
        "documents": po.documents,
        "notes": po.notes,
        "created_at": po.created_at.isoformat(),
        "updated_at": po.updated_at.isoformat(),
    }


@router.get("/", summary="List purchase orders")
async def list_pos(
    lead_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    production_status: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    async with get_session() as db:
        stmt = select(PurchaseOrder)
        if lead_id is not None:
            stmt = stmt.where(PurchaseOrder.lead_id == lead_id)
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
        if production_status:
            stmt = stmt.where(PurchaseOrder.production_status == production_status)
        if country:
            stmt = stmt.where(PurchaseOrder.country_of_destination == country.upper())
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(PurchaseOrder.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()
    return {"total": total, "page": page, "results": [_fmt(r) for r in rows]}


@router.post("/", summary="Create purchase order", status_code=201)
async def create_po(body: POCreate):
    import secrets
    async with get_session() as db:
        data = body.model_dump(exclude_none=True)
        data["our_reference"] = f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        if data.get("advance_pct") and data.get("total_value"):
            data["advance_amount"] = round(data["total_value"] * data["advance_pct"] / 100, 2)
            data["balance_amount"] = round(data["total_value"] - data["advance_amount"], 2)
        po = PurchaseOrder(**data)
        db.add(po)
        await db.commit()
        await db.refresh(po)
    return _fmt(po)


@router.get("/{po_id}", summary="Get purchase order by ID")
async def get_po(po_id: int):
    async with get_session() as db:
        po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(404, "Purchase order not found")
    return _fmt(po)


@router.patch("/{po_id}", summary="Update purchase order status / logistics")
async def patch_po(po_id: int, body: POPatch):
    async with get_session() as db:
        po = await db.get(PurchaseOrder, po_id)
        if not po:
            raise HTTPException(404, "Purchase order not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(po, k, v)
        po.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(po)
    return _fmt(po)


@router.get("/stats/overview", summary="PO pipeline overview and revenue stats")
async def po_stats():
    async with get_session() as db:
        stmt_status = (
            select(PurchaseOrder.status,
                   func.count(PurchaseOrder.id).label("count"),
                   func.sum(PurchaseOrder.total_value).label("total_value"))
            .group_by(PurchaseOrder.status)
        )
        status_rows = (await db.execute(stmt_status)).fetchall()

        stmt_prod = (
            select(PurchaseOrder.production_status,
                   func.count(PurchaseOrder.id).label("count"))
            .where(PurchaseOrder.status.not_in(["delivered", "cancelled"]))
            .group_by(PurchaseOrder.production_status)
        )
        prod_rows = (await db.execute(stmt_prod)).fetchall()

        total_revenue = (await db.execute(
            select(func.sum(PurchaseOrder.total_value)).where(
                PurchaseOrder.status == "delivered"
            )
        )).scalar_one()

        pipeline_value = (await db.execute(
            select(func.sum(PurchaseOrder.total_value)).where(
                PurchaseOrder.status.in_(["confirmed", "in_production", "shipped"])
            )
        )).scalar_one()

    return {
        "total_delivered_revenue_usd": float(total_revenue or 0),
        "active_pipeline_usd": float(pipeline_value or 0),
        "by_status": [
            {"status": r.status, "count": r.count, "value_usd": float(r.total_value or 0)}
            for r in status_rows
        ],
        "production_pipeline": [
            {"production_status": r.production_status, "count": r.count}
            for r in prod_rows
        ],
    }
