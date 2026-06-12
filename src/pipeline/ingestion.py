"""
Ingestion pipeline — orchestrates scraping → normalisation → DB insert.
Handles:
  - Upsert logic (external_id → skip or update)
  - Batch insert with conflict handling
  - Progress tracking via IngestionRun
  - Checkpoint save/restore for resumable scraping
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator, Type

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.config import settings
from src.core.database import get_session
from src.core.models import IngestionRun, IngestionStatus, RawBuyer, ScraperCheckpoint
from src.pipeline.normalization import normalise_record
from src.scrapers.base import BaseScraper, RawRecord

log = logging.getLogger(__name__)


async def run_scraper(scraper_cls: Type[BaseScraper]) -> int:
    """
    Run a single scraper end-to-end.
    Returns number of records inserted/updated.
    """
    scraper = scraper_cls()
    source_name = scraper.source_name

    # Create run record
    async with get_session() as session:
        run = IngestionRun(
            data_source=source_name,
            status=IngestionStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        session.add(run)
        await session.flush()
        run_id = run.id

    log.info(f"ingestion.start source={source_name} run_id={run_id}")
    records_fetched = 0
    records_inserted = 0
    records_updated = 0
    records_skipped = 0
    error_msg = None

    try:
        buffer: list[dict] = []
        async with scraper:
            async for raw in scraper.scrape():
                records_fetched += 1
                normalised = _to_dict(raw, run_id)
                normalise_record(normalised)
                buffer.append(normalised)

                if len(buffer) >= settings.batch_size:
                    ins, upd, skp = await _flush_buffer(buffer, source_name)
                    records_inserted += ins
                    records_updated += upd
                    records_skipped += skp
                    buffer.clear()
                    log.info(
                        f"ingestion.progress source={source_name} "
                        f"fetched={records_fetched} inserted={records_inserted}"
                    )

        # Flush remainder
        if buffer:
            ins, upd, skp = await _flush_buffer(buffer, source_name)
            records_inserted += ins
            records_updated += upd
            records_skipped += skp

        status = IngestionStatus.COMPLETED
    except Exception as exc:
        error_msg = str(exc)
        status = IngestionStatus.FAILED
        log.exception(f"ingestion.failed source={source_name}", exc_info=exc)

    # Update run
    async with get_session() as session:
        await session.execute(
            update(IngestionRun)
            .where(IngestionRun.id == run_id)
            .values(
                status=status,
                records_fetched=records_fetched,
                records_inserted=records_inserted,
                records_updated=records_updated,
                records_skipped=records_skipped,
                error_message=error_msg,
                completed_at=datetime.utcnow(),
            )
        )

    log.info(
        f"ingestion.complete source={source_name} status={status.value} "
        f"inserted={records_inserted} updated={records_updated}"
    )
    return records_inserted + records_updated


async def _flush_buffer(
    buffer: list[dict], source_name: str
) -> tuple[int, int, int]:
    """Upsert a batch of records. Returns (inserted, updated, skipped)."""
    inserted = 0
    updated = 0
    skipped = 0

    async with get_session() as session:
        for rec in buffer:
            ext_id = rec.get("external_id")
            if ext_id:
                # Check if record already exists
                stmt = select(RawBuyer).where(
                    RawBuyer.data_source == source_name,
                    RawBuyer.external_id == ext_id,
                )
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing:
                    # Update meaningful fields
                    for field in (
                        "last_import_date", "estimated_annual_volume_usd",
                        "total_shipments", "confidence_score",
                        "product_categories", "hs_codes", "raw_data",
                    ):
                        val = rec.get(field)
                        if val is not None:
                            setattr(existing, field, val)
                    updated += 1
                    continue

            # Insert new
            obj = RawBuyer(**{k: v for k, v in rec.items() if hasattr(RawBuyer, k) and v is not None})
            session.add(obj)
            inserted += 1

        await session.flush()

    return inserted, updated, skipped


def _to_dict(record: RawRecord, run_id: int) -> dict:
    return {
        "external_id": record.external_id,
        "data_source": record.data_source,
        "ingestion_run_id": run_id,
        "company_name": record.company_name,
        "country_code": record.country_code,
        "country_name": record.country_name,
        "state_province": record.state_province,
        "city": record.city,
        "postal_code": record.postal_code,
        "address": record.address,
        "website": record.website,
        "email": record.email or [],
        "phone": record.phone or [],
        "contact_person": record.contact_person,
        "product_categories": record.product_categories or [],
        "hs_codes": record.hs_codes or [],
        "product_description": record.product_description,
        "buyer_type": record.buyer_type,
        "import_frequency": record.import_frequency,
        "estimated_annual_volume_usd": record.estimated_annual_volume_usd,
        "volume_currency": record.volume_currency,
        "last_import_date": record.last_import_date,
        "first_import_date": record.first_import_date,
        "total_shipments": record.total_shipments,
        "total_suppliers": record.total_suppliers,
        "confidence_score": record.confidence_score,
        "raw_data": record.raw_data or {},
    }


# ─── Checkpoint helpers ───────────────────────────────────────────────────────

async def save_checkpoint(source: str, data: dict) -> None:
    async with get_session() as session:
        stmt = (
            pg_insert(ScraperCheckpoint)
            .values(data_source=source, checkpoint_data=data)
            .on_conflict_do_update(
                index_elements=["data_source"],
                set_={"checkpoint_data": data},
            )
        )
        await session.execute(stmt)


async def load_checkpoint(source: str) -> dict:
    async with get_session() as session:
        stmt = select(ScraperCheckpoint).where(
            ScraperCheckpoint.data_source == source
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        return row.checkpoint_data if row else {}
