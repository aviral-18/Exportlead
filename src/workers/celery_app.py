"""
Celery application configuration.
Two queues:
  - ingest   : runs individual scrapers (high concurrency, I/O bound)
  - pipeline : runs dedup / entity resolution (lower concurrency, CPU bound)
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.core.config import settings

app = Celery("brass_export")

app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Queues
    task_default_queue="ingest",
    task_routes={
        "src.workers.tasks.run_scraper_task": {"queue": "ingest"},
        "src.workers.tasks.run_deduplication_task": {"queue": "pipeline"},
        "src.workers.tasks.run_entity_resolution_task": {"queue": "pipeline"},
        "src.workers.tasks.run_full_pipeline_task": {"queue": "pipeline"},
        "src.workers.tasks.score_buyers_task": {"queue": "pipeline"},
        # Growth engine
        "src.workers.tasks.run_daily_discovery_task": {"queue": "pipeline"},
        "src.workers.tasks.build_recommendations_task": {"queue": "pipeline"},
        "src.workers.tasks.detect_emerging_importers_task": {"queue": "pipeline"},
        "src.workers.tasks.build_export_forecast_task": {"queue": "pipeline"},
        "src.workers.tasks.score_deal_probabilities_task": {"queue": "pipeline"},
    },
    # Concurrency / reliability
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_soft_time_limit=3600,   # 1h soft limit
    task_time_limit=7200,        # 2h hard limit
    # Result expiry
    result_expires=86400,
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# ── Periodic schedules ────────────────────────────────────────────────────────
app.conf.beat_schedule = {
    # Run all public API scrapers daily at 02:00 UTC
    "daily-public-scrapers": {
        "task": "src.workers.tasks.run_all_public_scrapers",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "ingest"},
    },
    # Run B2B marketplace scrapers every 3 days at 03:00 UTC
    "b2b-scrapers": {
        "task": "src.workers.tasks.run_b2b_scrapers",
        "schedule": crontab(hour=3, minute=0, day_of_week="*/3"),
        "options": {"queue": "ingest"},
    },
    # Trade fair scrapers weekly (fairs update monthly)
    "trade-fair-scrapers": {
        "task": "src.workers.tasks.run_trade_fair_scrapers",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),  # Sunday
        "options": {"queue": "ingest"},
    },
    # Deduplication daily at 06:00 UTC (after ingestion)
    "daily-dedup": {
        "task": "src.workers.tasks.run_deduplication_task",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "pipeline"},
    },
    # Entity resolution daily at 07:00 UTC
    "daily-entity-resolution": {
        "task": "src.workers.tasks.run_entity_resolution_task",
        "schedule": crontab(hour=7, minute=0),
        "options": {"queue": "pipeline"},
    },
    # AI lead scoring daily at 08:00 UTC (after entity resolution)
    "daily-lead-scoring": {
        "task": "src.workers.tasks.score_buyers_task",
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "pipeline"},
    },
    # Daily buyer discovery at 09:00 UTC (after scoring)
    "daily-discovery": {
        "task": "src.workers.tasks.run_daily_discovery_task",
        "schedule": crontab(hour=9, minute=0),
        "options": {"queue": "pipeline"},
    },
    # Build daily top-10 recommendations at 09:30 UTC
    "daily-recommendations": {
        "task": "src.workers.tasks.build_recommendations_task",
        "schedule": crontab(hour=9, minute=30),
        "options": {"queue": "pipeline"},
    },
    # Detect emerging importers daily at 10:00 UTC
    "daily-emerging-importers": {
        "task": "src.workers.tasks.detect_emerging_importers_task",
        "schedule": crontab(hour=10, minute=0),
        "options": {"queue": "pipeline"},
    },
    # Score deal closure probabilities daily at 10:30 UTC
    "daily-deal-probabilities": {
        "task": "src.workers.tasks.score_deal_probabilities_task",
        "schedule": crontab(hour=10, minute=30),
        "options": {"queue": "pipeline"},
    },
    # Rebuild export forecast daily at 11:00 UTC
    "daily-export-forecast": {
        "task": "src.workers.tasks.build_export_forecast_task",
        "schedule": crontab(hour=11, minute=0),
        "options": {"queue": "pipeline"},
    },
}
