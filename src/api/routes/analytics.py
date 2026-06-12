"""
Analytics endpoints.
GET /analytics/overview          — platform-level KPIs
GET /analytics/by-country        — buyers by country
GET /analytics/by-source         — records by data source
GET /analytics/by-buyer-type     — distribution of buyer types
GET /analytics/ingestion-runs    — ingestion run history
POST /pipeline/trigger-scraper   — trigger a specific scraper
POST /pipeline/trigger-dedup     — trigger deduplication
POST /pipeline/trigger-er        — trigger entity resolution
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.api.schemas import (
    AnalyticsByBuyerType,
    AnalyticsByCountry,
    AnalyticsBySource,
    IngestionRunOut,
    TriggerScrapeRequest,
    TriggerScrapeResponse,
)
from src.core.models import CanonicalBuyer, IngestionRun, RawBuyer

router = APIRouter(tags=["analytics"])

SCRAPER_REGISTRY = {
    "volza": "src.scrapers.trade_intelligence.volza.VolzaScraper",
    "import_yeti": "src.scrapers.trade_intelligence.import_yeti.ImportYetiScraper",
    "un_comtrade": "src.scrapers.trade_intelligence.un_comtrade.UnComtradeScraper",
    "trade_map": "src.scrapers.trade_intelligence.trade_map.TradeMapScraper",
    "export_genius": "src.scrapers.trade_intelligence.export_genius.ExportGeniusScraper",
    "datamyne": "src.scrapers.trade_intelligence.datamyne.DatamyneScraper",
    "panjiva": "src.scrapers.trade_intelligence.panjiva.PanjivaScraper",
    "india_export_data": "src.scrapers.trade_intelligence.india_export_data.IndiaExportDataScraper",
    "alibaba": "src.scrapers.b2b_marketplaces.alibaba.AlibabaScraper",
    "global_sources": "src.scrapers.b2b_marketplaces.global_sources.GlobalSourcesScraper",
    "tradekey": "src.scrapers.b2b_marketplaces.tradekey.TradeKeyScraper",
    "ec21": "src.scrapers.b2b_marketplaces.ec21.EC21Scraper",
    "eworldtrade": "src.scrapers.b2b_marketplaces.eworldtrade.EWorldTradeScraper",
    "tradeindia": "src.scrapers.b2b_marketplaces.tradeindia.TradeIndiaScraper",
    "indiamart": "src.scrapers.b2b_marketplaces.indiamart.IndiaMARTScraper",
    "made_in_china": "src.scrapers.b2b_marketplaces.made_in_china.MadeInChinaScraper",
    "sam_gov": "src.scrapers.procurement.sam_gov.SamGovScraper",
    "ted_europa": "src.scrapers.procurement.ted_europa.TEDEuropaScraper",
    "ungm": "src.scrapers.procurement.ungm.UNGMScraper",
    "world_bank": "src.scrapers.procurement.world_bank.WorldBankScraper",
    "adb": "src.scrapers.procurement.adb.ADBScraper",
    "ambiente": "src.scrapers.trade_fairs.ambiente.AmbienteScraper",
    "maison_objet": "src.scrapers.trade_fairs.maison_objet.MaisonObjetScraper",
    "ny_now": "src.scrapers.trade_fairs.ny_now.NYNowScraper",
    "ihgf": "src.scrapers.trade_fairs.ihgf.IHGFFairScraper",
}


@router.get("/analytics/overview")
async def overview(db: AsyncSession = Depends(get_db)) -> dict:
    """Platform KPIs."""
    total_raw = (await db.execute(select(func.count(RawBuyer.id)))).scalar_one()
    total_canonical = (
        await db.execute(
            select(func.count(CanonicalBuyer.id)).where(CanonicalBuyer.is_active == True)
        )
    ).scalar_one()
    total_verified = (
        await db.execute(
            select(func.count(CanonicalBuyer.id)).where(
                CanonicalBuyer.is_active == True,
                CanonicalBuyer.is_verified == True,
            )
        )
    ).scalar_one()
    total_countries = (
        await db.execute(
            select(func.count(func.distinct(CanonicalBuyer.country_code))).where(
                CanonicalBuyer.is_active == True
            )
        )
    ).scalar_one()
    avg_confidence = (
        await db.execute(
            select(func.avg(CanonicalBuyer.confidence_score)).where(
                CanonicalBuyer.is_active == True
            )
        )
    ).scalar_one()
    total_volume = (
        await db.execute(
            select(func.sum(CanonicalBuyer.estimated_annual_volume_usd)).where(
                CanonicalBuyer.is_active == True
            )
        )
    ).scalar_one()
    dedup_ratio = round(1 - (total_canonical / total_raw), 4) if total_raw else 0.0

    return {
        "total_raw_records": total_raw,
        "total_canonical_buyers": total_canonical,
        "total_verified": total_verified,
        "total_countries": total_countries,
        "avg_confidence_score": round(float(avg_confidence or 0), 4),
        "total_estimated_volume_usd": float(total_volume or 0),
        "deduplication_ratio": dedup_ratio,
    }


@router.get("/analytics/by-country", response_model=list[AnalyticsByCountry])
async def by_country(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            CanonicalBuyer.country_code,
            CanonicalBuyer.country_name,
            func.count(CanonicalBuyer.id).label("buyer_count"),
            func.avg(CanonicalBuyer.confidence_score).label("avg_confidence"),
            func.sum(CanonicalBuyer.estimated_annual_volume_usd).label("total_volume"),
        )
        .where(CanonicalBuyer.is_active == True)
        .group_by(CanonicalBuyer.country_code, CanonicalBuyer.country_name)
        .order_by(func.count(CanonicalBuyer.id).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).fetchall()
    return [
        AnalyticsByCountry(
            country_code=r.country_code,
            country_name=r.country_name,
            buyer_count=r.buyer_count,
            avg_confidence=round(float(r.avg_confidence or 0), 4),
            total_volume_usd=float(r.total_volume) if r.total_volume else None,
        )
        for r in rows
    ]


@router.get("/analytics/by-source", response_model=list[AnalyticsBySource])
async def by_source(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(
            RawBuyer.data_source,
            func.count(RawBuyer.id).label("record_count"),
            func.count(func.distinct(RawBuyer.country_code)).label("unique_countries"),
            func.avg(RawBuyer.confidence_score).label("avg_confidence"),
            func.max(RawBuyer.created_at).label("last_ingested"),
        )
        .group_by(RawBuyer.data_source)
        .order_by(func.count(RawBuyer.id).desc())
    )
    rows = (await db.execute(stmt)).fetchall()
    return [
        AnalyticsBySource(
            data_source=r.data_source,
            record_count=r.record_count,
            unique_countries=r.unique_countries,
            avg_confidence=round(float(r.avg_confidence or 0), 4),
            last_ingested=r.last_ingested,
        )
        for r in rows
    ]


@router.get("/analytics/by-buyer-type", response_model=list[AnalyticsByBuyerType])
async def by_buyer_type(db: AsyncSession = Depends(get_db)):
    total_stmt = select(func.count(CanonicalBuyer.id)).where(CanonicalBuyer.is_active == True)
    total = (await db.execute(total_stmt)).scalar_one() or 1

    stmt = (
        select(
            CanonicalBuyer.buyer_type,
            func.count(CanonicalBuyer.id).label("count"),
        )
        .where(CanonicalBuyer.is_active == True)
        .group_by(CanonicalBuyer.buyer_type)
        .order_by(func.count(CanonicalBuyer.id).desc())
    )
    rows = (await db.execute(stmt)).fetchall()
    return [
        AnalyticsByBuyerType(
            buyer_type=r.buyer_type,
            count=r.count,
            pct=round(r.count / total * 100, 2),
        )
        for r in rows
    ]


@router.get("/analytics/ingestion-runs", response_model=list[IngestionRunOut])
async def ingestion_runs(
    source: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(IngestionRun).order_by(IngestionRun.created_at.desc()).limit(limit)
    if source:
        stmt = stmt.where(IngestionRun.data_source == source)
    rows = (await db.execute(stmt)).scalars().all()
    return [IngestionRunOut.model_validate(r) for r in rows]


# ── Pipeline control ──────────────────────────────────────────────────────────

@router.post("/pipeline/trigger-scraper", response_model=TriggerScrapeResponse)
async def trigger_scraper(body: TriggerScrapeRequest) -> TriggerScrapeResponse:
    from src.workers.tasks import run_scraper_task

    scraper_path = SCRAPER_REGISTRY.get(body.scraper, body.scraper)
    task = run_scraper_task.apply_async(
        args=[scraper_path],
        priority=body.priority,
        queue="ingest",
    )
    return TriggerScrapeResponse(task_id=task.id, scraper=body.scraper)


@router.post("/pipeline/trigger-dedup")
async def trigger_dedup(min_score: float = 0.70) -> dict:
    from src.workers.tasks import run_deduplication_task

    task = run_deduplication_task.apply_async(
        kwargs={"min_score": min_score},
        queue="pipeline",
    )
    return {"task_id": task.id, "status": "queued"}


@router.post("/pipeline/trigger-entity-resolution")
async def trigger_entity_resolution(score_threshold: float = None) -> dict:
    from src.workers.tasks import run_entity_resolution_task

    task = run_entity_resolution_task.apply_async(
        kwargs={"score_threshold": score_threshold},
        queue="pipeline",
    )
    return {"task_id": task.id, "status": "queued"}


@router.post("/pipeline/trigger-full")
async def trigger_full_pipeline() -> dict:
    from src.workers.tasks import run_full_pipeline_task

    task = run_full_pipeline_task.apply_async(queue="pipeline")
    return {"task_id": task.id, "status": "queued"}
