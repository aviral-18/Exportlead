"""
World Bank Procurement scraper.
API: https://search.worldbank.org/api/v2/procurementnotices
Public API, no auth required.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)


class WorldBankScraper(BaseScraper):
    """
    World Bank procurement notices for handicraft / cultural / decorative items.
    Identifies development project procurement as niche buyer segment.
    """
    source_name = "world_bank"
    requests_per_second = 1.5

    SEARCH_TERMS = [
        "brass", "handicraft", "metal decor", "decorative",
        "cultural artifacts", "souvenir", "giftware",
    ]
    PAGE_SIZE = 100

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for term in self.SEARCH_TERMS:
            async for r in self._search(term):
                yield r

    async def _search(self, term: str) -> AsyncGenerator[RawRecord, None]:
        start = 0
        while True:
            try:
                resp = await self.get(
                    settings.world_bank_api_base,
                    params={
                        "qterm": term,
                        "os": start,
                        "rows": self.PAGE_SIZE,
                        "format": "json",
                        "fct": "The World Bank",
                    },
                )
            except Exception as exc:
                log.error("world_bank.error", term=term, error=str(exc))
                break

            total = int(resp.get("total", {}).get("value", 0))
            notices = resp.get("procurementnotices", {})
            if isinstance(notices, dict):
                items = list(notices.values())
            elif isinstance(notices, list):
                items = notices
            else:
                break

            if not items:
                break

            for item in items:
                borrower = item.get("borrower", "")
                country = item.get("country", "")
                project = item.get("project_name", "")
                agency = item.get("contact_organization", borrower)

                if not agency and not borrower:
                    continue
                name = agency or borrower

                yield RawRecord(
                    external_id=item.get("id"),
                    data_source=self.source_name,
                    company_name=name,
                    country_name=country,
                    product_categories=[term],
                    product_description=item.get("description") or project,
                    buyer_type="procurement_agency",
                    estimated_annual_volume_usd=self._safe_float(
                        str(item.get("contract_amount", "0")).replace(",", "")
                    ),
                    last_import_date=item.get("submission_date"),
                    confidence_score=0.80,
                    raw_data={
                        "project_id": item.get("project_id"),
                        "project_name": project,
                        "contract_type": item.get("procurement_type"),
                        "borrower": borrower,
                    },
                )

            start += self.PAGE_SIZE
            if start >= total:
                break
