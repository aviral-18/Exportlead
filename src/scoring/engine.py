"""
Batch scoring engine.
Loads canonical buyers in pages, scores each, upserts lead_scores rows.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from src.core.database import get_session
from src.core.models import CanonicalBuyer, LeadScore
from src.scoring.scorer import score_buyer

log = logging.getLogger(__name__)

PAGE_SIZE = 500


async def score_all_buyers(
    only_unscored: bool = False,
    min_confidence: float = 0.0,
) -> int:
    """
    Score every canonical buyer and upsert LeadScore rows.
    Returns the number of buyers scored.
    """
    offset = 0
    total = 0

    async with get_session() as db:
        while True:
            stmt = select(CanonicalBuyer).where(CanonicalBuyer.is_active == True)
            if min_confidence > 0:
                stmt = stmt.where(CanonicalBuyer.confidence_score >= min_confidence)
            if only_unscored:
                # exclude buyers that already have a lead_score row
                scored_ids_stmt = select(LeadScore.canonical_id)
                stmt = stmt.where(CanonicalBuyer.id.not_in(scored_ids_stmt))
            stmt = stmt.order_by(CanonicalBuyer.id).offset(offset).limit(PAGE_SIZE)

            buyers = (await db.execute(stmt)).scalars().all()
            if not buyers:
                break

            rows_to_upsert = []
            for buyer in buyers:
                try:
                    result = score_buyer(buyer)
                    rows_to_upsert.append({
                        "canonical_id": buyer.id,
                        "india_import_probability": result.india_import_probability,
                        "supplier_switch_probability": result.supplier_switch_probability,
                        "product_fit_score": result.product_fit,
                        "growth_trend_score": result.growth_trend,
                        "new_importer_score": result.new_importer,
                        "import_activity_score": result.import_activity,
                        "composite_score": result.composite,
                        "tier": result.tier,
                        "scored_at": datetime.now(timezone.utc),
                    })
                except Exception:
                    log.exception("scoring failed for canonical_id=%s", buyer.id)

            await _upsert_scores(db, rows_to_upsert)
            await db.commit()

            total += len(buyers)
            log.info("scored %d buyers (total so far: %d)", len(buyers), total)
            offset += PAGE_SIZE

    return total


async def score_single_buyer(canonical_id: int) -> dict | None:
    """Score one buyer and persist. Returns the score dict or None if not found."""
    async with get_session() as db:
        buyer = await db.get(CanonicalBuyer, canonical_id)
        if not buyer:
            return None

        result = score_buyer(buyer)
        await _upsert_scores(db, [{
            "canonical_id": canonical_id,
            "india_import_probability": result.india_import_probability,
            "supplier_switch_probability": result.supplier_switch_probability,
            "product_fit_score": result.product_fit,
            "growth_trend_score": result.growth_trend,
            "new_importer_score": result.new_importer,
            "import_activity_score": result.import_activity,
            "composite_score": result.composite,
            "tier": result.tier,
            "scored_at": datetime.now(timezone.utc),
        }])
        await db.commit()
        return result.to_dict()


async def _upsert_scores(db, rows: list[dict]) -> None:
    """INSERT ... ON CONFLICT (canonical_id) DO UPDATE via raw ORM upsert."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    if not rows:
        return

    stmt = pg_insert(LeadScore).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["canonical_id"],
        set_={
            "india_import_probability": stmt.excluded.india_import_probability,
            "supplier_switch_probability": stmt.excluded.supplier_switch_probability,
            "product_fit_score": stmt.excluded.product_fit_score,
            "growth_trend_score": stmt.excluded.growth_trend_score,
            "new_importer_score": stmt.excluded.new_importer_score,
            "import_activity_score": stmt.excluded.import_activity_score,
            "composite_score": stmt.excluded.composite_score,
            "tier": stmt.excluded.tier,
            "scored_at": stmt.excluded.scored_at,
        },
    )
    await db.execute(stmt)
