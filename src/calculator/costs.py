"""
Export profitability calculator engine.

Computes a full landed-cost breakdown and margin analysis for a brass
export shipment from Moradabad to any destination country.

All monetary values in USD unless suffixed _inr.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from src.calculator.rates import (
    BANK_CHARGE_RATE, CERTIFICATE_ORIGIN_INR, DUTY_DRAWBACK_RATE,
    EXPORT_AGENT_COMMISSION, EXPORT_DOC_COST_INR, FREIGHT_RATES,
    FUMIGATION_INR, IGST_REFUND_RATE, INLAND_FREIGHT_INR_PER_KG,
    INR_PER_USD, MARINE_INSURANCE_RATE, MIN_GROSS_MARGIN,
    PORT_HANDLING_INR, PRODUCT_COSTS, QUALITY_INSPECTION_RATE,
    RODTEP_RATE, DUTY_DRAWBACK_RATE, TARGET_GROSS_MARGIN, INCOME_TAX_RATE,
)


@dataclass
class CostBreakdown:
    # ── Inputs ────────────────────────────────────────────────────────────────
    product_category: str
    quantity_pieces: int
    weight_kg: float
    destination_country: str
    shipping_mode: str          # sea_fcl | sea_lcl | air
    include_lc: bool = False    # LC adds extra bank charges
    selling_price_usd: Optional[float] = None  # override if known

    # ── Derived (filled by calculate()) ──────────────────────────────────────
    product_label: str = ""
    inr_per_usd: float = INR_PER_USD

    # Production costs (INR)
    raw_material_cost_inr: float = 0
    manufacturing_cost_inr: float = 0
    finishing_cost_inr: float = 0
    packaging_cost_inr: float = 0
    total_production_cost_inr: float = 0
    total_production_cost_usd: float = 0

    # Export overhead (INR)
    inland_freight_inr: float = 0
    export_docs_inr: float = 0
    certificate_origin_inr: float = 0
    fumigation_inr: float = 0
    port_handling_inr: float = 0
    total_fixed_overhead_inr: float = 0
    total_fixed_overhead_usd: float = 0

    # FOB value
    fob_cost_usd: float = 0

    # Variable export costs (% of FOB)
    quality_inspection_usd: float = 0
    agent_commission_usd: float = 0
    bank_charges_usd: float = 0

    # International freight
    freight_rate_usd_per_kg: float = 0
    international_freight_usd: float = 0
    marine_insurance_usd: float = 0

    # CIF value
    cif_cost_usd: float = 0

    # Total export cost (CIF basis)
    total_export_cost_usd: float = 0

    # Duty / tax incentives (INR, then converted)
    rodtep_benefit_inr: float = 0
    duty_drawback_inr: float = 0
    igst_refund_inr: float = 0
    total_incentives_inr: float = 0
    total_incentives_usd: float = 0

    # Net cost after incentives
    net_cost_usd: float = 0
    net_cost_inr_per_kg: float = 0

    # Pricing & profitability
    recommended_selling_price_usd: float = 0
    min_breakeven_price_usd: float = 0
    actual_selling_price_usd: float = 0
    revenue_usd: float = 0

    gross_profit_usd: float = 0
    gross_margin_pct: float = 0
    net_profit_before_tax_usd: float = 0
    income_tax_usd: float = 0
    net_earnings_usd: float = 0
    net_margin_pct: float = 0
    roi_pct: float = 0

    # Per-unit metrics
    cost_per_piece_usd: float = 0
    selling_price_per_piece_usd: float = 0
    profit_per_piece_usd: float = 0

    # Freight details
    sea_transit_days: int = 0
    shipping_region: str = ""
    is_viable: bool = True
    viability_notes: list[str] = field(default_factory=list)


def calculate(
    product_category: str,
    quantity_pieces: int,
    weight_kg: float,
    destination_country: str,
    shipping_mode: str = "sea_fcl",
    selling_price_usd: Optional[float] = None,
    include_lc: bool = False,
    inr_per_usd: float = INR_PER_USD,
) -> CostBreakdown:
    """
    Full export cost and profitability calculation.

    Args:
        product_category: key from PRODUCT_COSTS
        quantity_pieces:  number of pieces in the shipment
        weight_kg:        gross weight in kg
        destination_country: ISO-3166 alpha-2 country code
        shipping_mode:    sea_fcl | sea_lcl | air
        selling_price_usd: override per-unit selling price; None = auto-price at target margin
        include_lc:       adds LC charges to bank fees
        inr_per_usd:      exchange rate override
    """
    result = CostBreakdown(
        product_category=product_category,
        quantity_pieces=quantity_pieces,
        weight_kg=weight_kg,
        destination_country=destination_country.upper(),
        shipping_mode=shipping_mode,
        include_lc=include_lc,
        selling_price_usd=selling_price_usd,
        inr_per_usd=inr_per_usd,
    )

    cc = PRODUCT_COSTS.get(product_category)
    if not cc:
        raise ValueError(f"Unknown product_category '{product_category}'. "
                         f"Valid: {list(PRODUCT_COSTS.keys())}")
    result.product_label = cc["label"]

    fr = FREIGHT_RATES.get(destination_country.upper(), FREIGHT_RATES["_DEFAULT"])
    result.shipping_region = fr["region"]
    result.sea_transit_days = fr["sea_days"]

    # ── 1. Production cost ────────────────────────────────────────────────────
    result.raw_material_cost_inr = cc["raw_material_inr_kg"] * weight_kg
    result.manufacturing_cost_inr = cc["manufacturing_inr_kg"] * weight_kg
    result.finishing_cost_inr = cc["finishing_inr_kg"] * weight_kg
    result.packaging_cost_inr = cc["packaging_inr_kg"] * weight_kg
    result.total_production_cost_inr = (
        result.raw_material_cost_inr + result.manufacturing_cost_inr
        + result.finishing_cost_inr + result.packaging_cost_inr
    )
    result.total_production_cost_usd = result.total_production_cost_inr / inr_per_usd

    # ── 2. Fixed export overhead ──────────────────────────────────────────────
    result.inland_freight_inr = INLAND_FREIGHT_INR_PER_KG * weight_kg
    result.export_docs_inr = EXPORT_DOC_COST_INR
    result.certificate_origin_inr = CERTIFICATE_ORIGIN_INR
    result.fumigation_inr = FUMIGATION_INR
    result.port_handling_inr = PORT_HANDLING_INR
    result.total_fixed_overhead_inr = (
        result.inland_freight_inr + result.export_docs_inr
        + result.certificate_origin_inr + result.fumigation_inr
        + result.port_handling_inr
    )
    result.total_fixed_overhead_usd = result.total_fixed_overhead_inr / inr_per_usd

    # ── 3. FOB cost ───────────────────────────────────────────────────────────
    result.fob_cost_usd = result.total_production_cost_usd + result.total_fixed_overhead_usd

    # ── 4. Variable export costs ──────────────────────────────────────────────
    result.quality_inspection_usd = result.fob_cost_usd * QUALITY_INSPECTION_RATE
    result.agent_commission_usd = result.fob_cost_usd * EXPORT_AGENT_COMMISSION
    bank_rate = BANK_CHARGE_RATE + (0.005 if include_lc else 0)
    result.bank_charges_usd = result.fob_cost_usd * bank_rate

    # ── 5. International freight ──────────────────────────────────────────────
    mode_key = {"sea_fcl": "fcl", "sea_lcl": "lcl", "air": "air"}.get(shipping_mode, "fcl")
    result.freight_rate_usd_per_kg = fr[mode_key]
    result.international_freight_usd = result.freight_rate_usd_per_kg * weight_kg

    # ── 6. CIF cost ───────────────────────────────────────────────────────────
    result.cif_cost_usd = (
        result.fob_cost_usd
        + result.quality_inspection_usd
        + result.agent_commission_usd
        + result.bank_charges_usd
        + result.international_freight_usd
    )
    result.marine_insurance_usd = result.cif_cost_usd * MARINE_INSURANCE_RATE
    result.cif_cost_usd += result.marine_insurance_usd
    result.total_export_cost_usd = result.cif_cost_usd

    # ── 7. Government incentives ──────────────────────────────────────────────
    fob_inr = result.fob_cost_usd * inr_per_usd
    result.rodtep_benefit_inr = fob_inr * RODTEP_RATE
    result.duty_drawback_inr = fob_inr * DUTY_DRAWBACK_RATE
    result.igst_refund_inr = result.raw_material_cost_inr * IGST_REFUND_RATE
    result.total_incentives_inr = (
        result.rodtep_benefit_inr
        + result.duty_drawback_inr
        + result.igst_refund_inr
    )
    result.total_incentives_usd = result.total_incentives_inr / inr_per_usd

    # ── 8. Net cost after incentives ──────────────────────────────────────────
    result.net_cost_usd = result.total_export_cost_usd - result.total_incentives_usd
    result.net_cost_inr_per_kg = (result.net_cost_usd * inr_per_usd) / weight_kg if weight_kg else 0

    # ── 9. Breakeven & recommended selling price ──────────────────────────────
    result.min_breakeven_price_usd = result.net_cost_usd / (1 - MIN_GROSS_MARGIN)
    result.recommended_selling_price_usd = result.net_cost_usd / (1 - TARGET_GROSS_MARGIN)

    if selling_price_usd is not None:
        result.actual_selling_price_usd = selling_price_usd
    else:
        result.actual_selling_price_usd = result.recommended_selling_price_usd

    # ── 10. P&L ───────────────────────────────────────────────────────────────
    result.revenue_usd = result.actual_selling_price_usd
    result.gross_profit_usd = result.revenue_usd - result.net_cost_usd
    result.gross_margin_pct = (
        result.gross_profit_usd / result.revenue_usd * 100 if result.revenue_usd else 0
    )

    result.net_profit_before_tax_usd = result.gross_profit_usd
    result.income_tax_usd = max(0, result.net_profit_before_tax_usd) * INCOME_TAX_RATE
    result.net_earnings_usd = result.net_profit_before_tax_usd - result.income_tax_usd
    result.net_margin_pct = (
        result.net_earnings_usd / result.revenue_usd * 100 if result.revenue_usd else 0
    )
    result.roi_pct = (
        result.net_earnings_usd / result.total_export_cost_usd * 100
        if result.total_export_cost_usd else 0
    )

    # ── 11. Per-unit metrics ──────────────────────────────────────────────────
    if quantity_pieces > 0:
        result.cost_per_piece_usd = result.net_cost_usd / quantity_pieces
        result.selling_price_per_piece_usd = result.actual_selling_price_usd / quantity_pieces
        result.profit_per_piece_usd = result.net_earnings_usd / quantity_pieces

    # ── 12. Viability check ───────────────────────────────────────────────────
    if result.gross_margin_pct < MIN_GROSS_MARGIN * 100:
        result.is_viable = False
        result.viability_notes.append(
            f"Gross margin {result.gross_margin_pct:.1f}% is below minimum {MIN_GROSS_MARGIN*100:.0f}%"
        )
    if result.net_earnings_usd < 0:
        result.is_viable = False
        result.viability_notes.append("Net earnings are negative — loss-making shipment")
    if shipping_mode == "air" and result.gross_margin_pct < 35:
        result.viability_notes.append(
            "Air freight — margin below 35% may not justify the freight premium"
        )
    if weight_kg < 500 and shipping_mode == "sea_fcl":
        result.viability_notes.append(
            "< 500 kg — consider sea_lcl or consolidation instead of full container"
        )

    # Round all floats
    _round_result(result)
    return result


def _round_result(r: CostBreakdown, ndigits: int = 2) -> None:
    for attr, val in r.__dict__.items():
        if isinstance(val, float):
            setattr(r, attr, round(val, ndigits))


def to_dict(r: CostBreakdown) -> dict:
    """Serialise a CostBreakdown for the API response."""
    return {
        "inputs": {
            "product_category": r.product_category,
            "product_label": r.product_label,
            "quantity_pieces": r.quantity_pieces,
            "weight_kg": r.weight_kg,
            "destination_country": r.destination_country,
            "shipping_mode": r.shipping_mode,
            "shipping_region": r.shipping_region,
            "sea_transit_days": r.sea_transit_days,
            "include_lc": r.include_lc,
            "exchange_rate_inr_usd": r.inr_per_usd,
        },
        "production_costs": {
            "raw_material_inr": r.raw_material_cost_inr,
            "manufacturing_inr": r.manufacturing_cost_inr,
            "finishing_inr": r.finishing_cost_inr,
            "packaging_inr": r.packaging_cost_inr,
            "total_production_inr": r.total_production_cost_inr,
            "total_production_usd": r.total_production_cost_usd,
        },
        "export_overhead": {
            "inland_freight_inr": r.inland_freight_inr,
            "export_docs_inr": r.export_docs_inr,
            "certificate_origin_inr": r.certificate_origin_inr,
            "fumigation_inr": r.fumigation_inr,
            "port_handling_inr": r.port_handling_inr,
            "total_fixed_overhead_inr": r.total_fixed_overhead_inr,
            "total_fixed_overhead_usd": r.total_fixed_overhead_usd,
        },
        "variable_costs": {
            "fob_cost_usd": r.fob_cost_usd,
            "quality_inspection_usd": r.quality_inspection_usd,
            "agent_commission_usd": r.agent_commission_usd,
            "bank_charges_usd": r.bank_charges_usd,
            "freight_rate_usd_per_kg": r.freight_rate_usd_per_kg,
            "international_freight_usd": r.international_freight_usd,
            "marine_insurance_usd": r.marine_insurance_usd,
            "cif_cost_usd": r.cif_cost_usd,
        },
        "total_export_cost_usd": r.total_export_cost_usd,
        "government_incentives": {
            "rodtep_benefit_inr": r.rodtep_benefit_inr,
            "duty_drawback_inr": r.duty_drawback_inr,
            "igst_refund_inr": r.igst_refund_inr,
            "total_incentives_inr": r.total_incentives_inr,
            "total_incentives_usd": r.total_incentives_usd,
        },
        "net_cost_usd": r.net_cost_usd,
        "net_cost_inr_per_kg": r.net_cost_inr_per_kg,
        "pricing": {
            "min_breakeven_price_usd": r.min_breakeven_price_usd,
            "recommended_selling_price_usd": r.recommended_selling_price_usd,
            "actual_selling_price_usd": r.actual_selling_price_usd,
            "total_revenue_usd": r.revenue_usd,
        },
        "profitability": {
            "gross_profit_usd": r.gross_profit_usd,
            "gross_margin_pct": r.gross_margin_pct,
            "net_profit_before_tax_usd": r.net_profit_before_tax_usd,
            "income_tax_usd": r.income_tax_usd,
            "net_earnings_usd": r.net_earnings_usd,
            "net_margin_pct": r.net_margin_pct,
            "roi_pct": r.roi_pct,
        },
        "per_unit": {
            "cost_per_piece_usd": r.cost_per_piece_usd,
            "selling_price_per_piece_usd": r.selling_price_per_piece_usd,
            "profit_per_piece_usd": r.profit_per_piece_usd,
        },
        "viability": {
            "is_viable": r.is_viable,
            "notes": r.viability_notes,
        },
    }
