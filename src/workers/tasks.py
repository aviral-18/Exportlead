"""
Celery task definitions.
All heavy async work is run via asyncio.run() inside synchronous Celery tasks.
"""
from __future__ import annotations

import asyncio
import logging

from celery import group, shared_task

from src.workers.celery_app import app

log = logging.getLogger(__name__)


# ── Individual scraper tasks ──────────────────────────────────────────────────

def _make_scraper_task(scraper_cls_path: str):
    """Factory that creates a Celery task for a given scraper class path."""
    @app.task(
        name=f"src.workers.tasks.scrape_{scraper_cls_path.split('.')[-1].lower()}",
        bind=True,
        max_retries=3,
        default_retry_delay=300,
        queue="ingest",
    )
    def task(self):
        from importlib import import_module
        parts = scraper_cls_path.rsplit(".", 1)
        module = import_module(parts[0])
        cls = getattr(module, parts[1])
        from src.pipeline.ingestion import run_scraper
        try:
            count = asyncio.run(run_scraper(cls))
            log.info(f"scraper={parts[1]} records={count}")
            return count
        except Exception as exc:
            log.exception(f"scraper={parts[1]} failed")
            raise self.retry(exc=exc)
    return task


@app.task(name="src.workers.tasks.run_scraper_task", queue="ingest")
def run_scraper_task(scraper_class_path: str) -> int:
    """Generic task: run any scraper by importable class path."""
    from importlib import import_module
    parts = scraper_class_path.rsplit(".", 1)
    module = import_module(parts[0])
    cls = getattr(module, parts[1])
    from src.pipeline.ingestion import run_scraper
    return asyncio.run(run_scraper(cls))


# ── Pipeline tasks ────────────────────────────────────────────────────────────

@app.task(name="src.workers.tasks.run_deduplication_task", queue="pipeline")
def run_deduplication_task(min_score: float = 0.70) -> int:
    from src.pipeline.deduplication import domain_exact_dedup, find_duplicate_candidates
    domain_count = asyncio.run(domain_exact_dedup())
    minhash_count = asyncio.run(find_duplicate_candidates(min_score=min_score))
    return domain_count + minhash_count


@app.task(name="src.workers.tasks.run_entity_resolution_task", queue="pipeline")
def run_entity_resolution_task(score_threshold: float = None) -> int:
    from src.pipeline.entity_resolution import resolve_entities
    return asyncio.run(resolve_entities(score_threshold=score_threshold))


@app.task(name="src.workers.tasks.run_full_pipeline_task", queue="pipeline")
def run_full_pipeline_task() -> dict:
    """Run all scrapers → dedup → entity resolution sequentially."""
    scraper_paths = _all_scraper_paths()
    results = {}
    for path in scraper_paths:
        try:
            count = run_scraper_task(path)
            results[path.split(".")[-1]] = count
        except Exception as exc:
            results[path.split(".")[-1]] = f"ERROR: {exc}"

    dedup_count = run_deduplication_task()
    er_count = run_entity_resolution_task()
    return {
        "scrapers": results,
        "dedup_candidates": dedup_count,
        "canonical_records": er_count,
    }


# ── Grouped scraper tasks ─────────────────────────────────────────────────────

@app.task(name="src.workers.tasks.run_all_public_scrapers", queue="ingest")
def run_all_public_scrapers() -> dict:
    """Run UN Comtrade, SAM.gov, World Bank, ADB, UNGM in parallel."""
    public = [
        "src.scrapers.trade_intelligence.un_comtrade.UnComtradeScraper",
        "src.scrapers.procurement.sam_gov.SamGovScraper",
        "src.scrapers.procurement.world_bank.WorldBankScraper",
        "src.scrapers.procurement.adb.ADBScraper",
        "src.scrapers.procurement.ungm.UNGMScraper",
        "src.scrapers.procurement.ted_europa.TEDEuropaScraper",
        "src.scrapers.trade_intelligence.india_export_data.IndiaExportDataScraper",
    ]
    results = {}
    for path in public:
        try:
            results[path.split(".")[-1]] = run_scraper_task(path)
        except Exception as exc:
            results[path.split(".")[-1]] = str(exc)
    return results


@app.task(name="src.workers.tasks.run_b2b_scrapers", queue="ingest")
def run_b2b_scrapers() -> dict:
    b2b = [
        "src.scrapers.b2b_marketplaces.tradeindia.TradeIndiaScraper",
        "src.scrapers.b2b_marketplaces.indiamart.IndiaMARTScraper",
        "src.scrapers.b2b_marketplaces.alibaba.AlibabaScraper",
        "src.scrapers.b2b_marketplaces.global_sources.GlobalSourcesScraper",
        "src.scrapers.b2b_marketplaces.tradekey.TradeKeyScraper",
        "src.scrapers.b2b_marketplaces.ec21.EC21Scraper",
        "src.scrapers.b2b_marketplaces.eworldtrade.EWorldTradeScraper",
        "src.scrapers.b2b_marketplaces.made_in_china.MadeInChinaScraper",
    ]
    results = {}
    for path in b2b:
        try:
            results[path.split(".")[-1]] = run_scraper_task(path)
        except Exception as exc:
            results[path.split(".")[-1]] = str(exc)
    return results


@app.task(name="src.workers.tasks.run_trade_fair_scrapers", queue="ingest")
def run_trade_fair_scrapers() -> dict:
    fairs = [
        "src.scrapers.trade_fairs.ihgf.IHGFFairScraper",
        "src.scrapers.trade_fairs.ambiente.AmbienteScraper",
        "src.scrapers.trade_fairs.maison_objet.MaisonObjetScraper",
        "src.scrapers.trade_fairs.ny_now.NYNowScraper",
    ]
    results = {}
    for path in fairs:
        try:
            results[path.split(".")[-1]] = run_scraper_task(path)
        except Exception as exc:
            results[path.split(".")[-1]] = str(exc)
    return results


@app.task(name="src.workers.tasks.run_commercial_scrapers", queue="ingest")
def run_commercial_scrapers() -> dict:
    """Commercial scrapers — only run if API keys are configured."""
    from src.core.config import settings
    commercial = []
    if settings.volza_api_key:
        commercial.append("src.scrapers.trade_intelligence.volza.VolzaScraper")
    if settings.import_yeti_api_key or settings.import_yeti_session_cookie:
        commercial.append("src.scrapers.trade_intelligence.import_yeti.ImportYetiScraper")
    if settings.export_genius_api_key or settings.export_genius_username:
        commercial.append("src.scrapers.trade_intelligence.export_genius.ExportGeniusScraper")
    if settings.datamyne_username:
        commercial.append("src.scrapers.trade_intelligence.datamyne.DatamyneScraper")
    if settings.panjiva_api_key:
        commercial.append("src.scrapers.trade_intelligence.panjiva.PanjivaScraper")
    if settings.trade_map_username:
        commercial.append("src.scrapers.trade_intelligence.trade_map.TradeMapScraper")

    results = {}
    for path in commercial:
        try:
            results[path.split(".")[-1]] = run_scraper_task(path)
        except Exception as exc:
            results[path.split(".")[-1]] = str(exc)
    return results


@app.task(name="src.workers.tasks.score_buyers_task", queue="pipeline")
def score_buyers_task(only_unscored: bool = False, min_confidence: float = 0.0) -> int:
    """Score all canonical buyers and upsert lead_scores rows."""
    from src.scoring.engine import score_all_buyers
    return asyncio.run(score_all_buyers(only_unscored=only_unscored, min_confidence=min_confidence))


# ── Growth engine tasks ───────────────────────────────────────────────────────

@app.task(name="src.workers.tasks.run_daily_discovery_task", queue="pipeline")
def run_daily_discovery_task() -> dict:
    """Daily buyer discovery: scan new shipments, score, rank, build top-10."""
    from src.growth.discovery import run_daily_discovery
    return asyncio.run(run_daily_discovery())


@app.task(name="src.workers.tasks.build_recommendations_task", queue="pipeline")
def build_recommendations_task(run_id: int | None = None, top_n: int = 10) -> int:
    """Build or refresh daily top-N buyer recommendations."""
    from src.growth.recommender import build_recommendations
    recs = asyncio.run(build_recommendations(run_id=run_id, top_n=top_n))
    return len(recs)


@app.task(name="src.workers.tasks.detect_emerging_importers_task", queue="pipeline")
def detect_emerging_importers_task() -> int:
    """Scan all scored buyers and flag emerging importers."""
    from src.growth.emerging import detect
    from src.core.database import get_session
    from src.core.models import CanonicalBuyer, LeadScore
    from src.growth.models import EmergingImporter
    from sqlalchemy import select

    async def _run():
        count = 0
        async with get_session() as session:
            rows = (await session.execute(
                select(CanonicalBuyer, LeadScore)
                .join(LeadScore, LeadScore.canonical_id == CanonicalBuyer.id)
                .where(CanonicalBuyer.is_active.is_(True))
            )).all()
            for buyer, ls in rows:
                signal = detect(buyer, ls)
                if not signal:
                    continue
                existing = (await session.execute(
                    select(EmergingImporter).where(EmergingImporter.canonical_id == buyer.id)
                )).scalar_one_or_none()
                if not existing:
                    import json
                    session.add(EmergingImporter(
                        canonical_id=buyer.id,
                        months_active=signal.months_active,
                        shipment_count=signal.shipment_count,
                        annual_volume_usd=signal.annual_volume_usd,
                        growth_velocity_score=signal.growth_velocity_score,
                        market_timing_score=signal.market_timing_score,
                        overall_score=signal.overall_score,
                        category=signal.category,
                        confidence=signal.confidence,
                        action_recommended=signal.action_recommended,
                        trend_json=json.dumps(signal.trend),
                    ))
                    count += 1
            await session.commit()
        return count

    return asyncio.run(_run())


@app.task(name="src.workers.tasks.build_export_forecast_task", queue="pipeline")
def build_export_forecast_task(months_ahead: int = 6) -> int:
    """Generate or refresh the 6-month export revenue forecast."""
    from src.growth.forecast import build_forecast
    forecasts = asyncio.run(build_forecast(months_ahead=months_ahead))
    return len(forecasts)


@app.task(name="src.workers.tasks.score_deal_probabilities_task", queue="pipeline")
def score_deal_probabilities_task() -> int:
    """Score closure probability for all active CRM opportunities."""
    from src.core.database import get_session
    from src.crm.models import Opportunity
    from src.growth.models import DealProbabilityScore
    from src.intelligence.closure import score_opportunity
    from sqlalchemy import select, update
    import json

    async def _run():
        count = 0
        async with get_session() as session:
            opps = (await session.execute(
                select(Opportunity).where(Opportunity.stage.notin_(["won", "lost"]))
            )).scalars().all()
            # Expire old scores
            await session.execute(
                update(DealProbabilityScore).values(is_current=False)
            )
            for opp in opps:
                result = await score_opportunity(opp)
                session.add(DealProbabilityScore(
                    opportunity_id=opp.id,
                    lead_id=opp.lead_id,
                    probability_pct=result.probability_pct,
                    confidence_level=result.confidence_level,
                    days_to_close_est=result.days_to_close_est,
                    expected_value_usd=result.expected_value_usd,
                    weighted_value_usd=result.weighted_value_usd,
                    positive_signals_json=json.dumps(result.positive_signals),
                    risk_factors_json=json.dumps(result.risk_factors),
                    scoring_breakdown_json=json.dumps(result.scoring_breakdown),
                    is_current=True,
                ))
                count += 1
            await session.commit()
        return count

    return asyncio.run(_run())


def _all_scraper_paths() -> list[str]:
    return [
        "src.scrapers.trade_intelligence.un_comtrade.UnComtradeScraper",
        "src.scrapers.trade_intelligence.india_export_data.IndiaExportDataScraper",
        "src.scrapers.procurement.sam_gov.SamGovScraper",
        "src.scrapers.procurement.world_bank.WorldBankScraper",
        "src.scrapers.procurement.adb.ADBScraper",
        "src.scrapers.procurement.ungm.UNGMScraper",
        "src.scrapers.procurement.ted_europa.TEDEuropaScraper",
        "src.scrapers.b2b_marketplaces.tradeindia.TradeIndiaScraper",
        "src.scrapers.b2b_marketplaces.indiamart.IndiaMARTScraper",
        "src.scrapers.b2b_marketplaces.alibaba.AlibabaScraper",
        "src.scrapers.b2b_marketplaces.global_sources.GlobalSourcesScraper",
        "src.scrapers.b2b_marketplaces.tradekey.TradeKeyScraper",
        "src.scrapers.b2b_marketplaces.ec21.EC21Scraper",
        "src.scrapers.b2b_marketplaces.eworldtrade.EWorldTradeScraper",
        "src.scrapers.b2b_marketplaces.made_in_china.MadeInChinaScraper",
        "src.scrapers.trade_fairs.ihgf.IHGFFairScraper",
        "src.scrapers.trade_fairs.ambiente.AmbienteScraper",
        "src.scrapers.trade_fairs.maison_objet.MaisonObjetScraper",
        "src.scrapers.trade_fairs.ny_now.NYNowScraper",
    ]
