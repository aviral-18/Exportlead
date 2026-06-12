"""
Export profitability calculator API.

POST /api/v1/calculator/calculate   — full cost + margin breakdown
GET  /api/v1/calculator/products    — list available product categories
GET  /api/v1/calculator/countries   — list supported destination countries
POST /api/v1/calculator/compare     — compare up to 4 shipping modes / countries
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/calculator", tags=["calculator"])


class CalculateRequest(BaseModel):
    product_category: str = Field(..., description="decorative | religious | hospitality | garden | gifting | industrial | statues")
    quantity_pieces: int = Field(..., ge=1, le=1_000_000)
    weight_kg: float = Field(..., gt=0, le=50_000)
    destination_country: str = Field(..., min_length=2, max_length=2, description="ISO-3166 alpha-2, e.g. US, DE, AE")
    shipping_mode: str = Field("sea_fcl", description="sea_fcl | sea_lcl | air")
    selling_price_usd: Optional[float] = Field(None, gt=0, description="Override total selling price (leave None to auto-price at target margin)")
    include_lc: bool = Field(False, description="Add LC charges to bank fees")
    inr_per_usd: float = Field(83.5, gt=0, description="Exchange rate override")

    @field_validator("shipping_mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        if v not in ("sea_fcl", "sea_lcl", "air"):
            raise ValueError("shipping_mode must be sea_fcl, sea_lcl, or air")
        return v

    @field_validator("destination_country")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class CompareRequest(BaseModel):
    product_category: str
    quantity_pieces: int = Field(..., ge=1)
    weight_kg: float = Field(..., gt=0)
    destination_country: str = Field(..., min_length=2, max_length=2)
    selling_price_usd: Optional[float] = None
    inr_per_usd: float = 83.5

    @field_validator("destination_country")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


@router.get("/products", summary="List available product categories")
async def list_products():
    from src.calculator.rates import PRODUCT_COSTS
    return [
        {
            "key": k,
            "label": v["label"],
            "hs_codes": v["hs_codes"],
            "approx_cost_inr_per_kg": round(
                v["raw_material_inr_kg"] + v["manufacturing_inr_kg"]
                + v["finishing_inr_kg"] + v["packaging_inr_kg"], 0
            ),
        }
        for k, v in PRODUCT_COSTS.items()
    ]


@router.get("/countries", summary="List destination countries with freight rates")
async def list_countries():
    from src.calculator.rates import FREIGHT_RATES
    return [
        {
            "country_code": cc if cc != "_DEFAULT" else "OTHER",
            "region": v["region"],
            "sea_fcl_usd_per_kg": v["fcl"],
            "sea_lcl_usd_per_kg": v["lcl"],
            "air_usd_per_kg": v["air"],
            "sea_transit_days": v["sea_days"],
        }
        for cc, v in FREIGHT_RATES.items()
    ]


@router.post("/calculate", summary="Full export cost and profitability calculation")
async def calculate(body: CalculateRequest):
    from src.calculator.costs import calculate as _calc, to_dict
    try:
        result = _calc(
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
    return to_dict(result)


@router.post("/compare", summary="Compare all 3 shipping modes side-by-side")
async def compare_modes(body: CompareRequest):
    from src.calculator.costs import calculate as _calc, to_dict
    results = {}
    for mode in ("sea_fcl", "sea_lcl", "air"):
        try:
            r = _calc(
                product_category=body.product_category,
                quantity_pieces=body.quantity_pieces,
                weight_kg=body.weight_kg,
                destination_country=body.destination_country,
                shipping_mode=mode,
                selling_price_usd=body.selling_price_usd,
                inr_per_usd=body.inr_per_usd,
            )
            results[mode] = {
                "total_export_cost_usd": r.total_export_cost_usd,
                "net_cost_usd": r.net_cost_usd,
                "recommended_selling_price_usd": r.recommended_selling_price_usd,
                "gross_margin_pct": r.gross_margin_pct,
                "net_earnings_usd": r.net_earnings_usd,
                "net_margin_pct": r.net_margin_pct,
                "freight_usd": r.international_freight_usd,
                "transit_days": r.sea_transit_days if mode != "air" else 3,
                "is_viable": r.is_viable,
                "notes": r.viability_notes,
            }
        except Exception as e:
            results[mode] = {"error": str(e)}
    return {
        "product_category": body.product_category,
        "weight_kg": body.weight_kg,
        "quantity_pieces": body.quantity_pieces,
        "destination_country": body.destination_country,
        "comparison": results,
        "recommendation": _recommend_mode(results),
    }


def _recommend_mode(comparison: dict) -> str:
    viable = [m for m, v in comparison.items() if v.get("is_viable")]
    if not viable:
        return "No viable shipping mode found at current prices"
    best = max(viable, key=lambda m: comparison[m].get("net_earnings_usd", 0))
    return f"{best} offers the best net earnings"
