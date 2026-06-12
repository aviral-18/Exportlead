"""eWorldTrade.com buyer scraper — https://www.eworldtrade.com"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

EWT_BASE = "https://www.eworldtrade.com"
TERMS = ["brass decor", "brass handicraft", "metal decor", "brass gift"]


class EWorldTradeScraper(BaseScraper):
    source_name = "eworldtrade"
    requires_browser = True
    requests_per_second = 1.0

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for term in TERMS:
            url = f"{EWT_BASE}/trade-leads/buy/{term.replace(' ', '-')}/"
            try:
                html = await self.browse(url, wait_for_selector=".trade-leads-list")
            except Exception as exc:
                log.error("eworldtrade.error", term=term, error=str(exc))
                continue

            soup = BeautifulSoup(html, "html.parser")
            for lead in soup.select(".trade-lead-item, .lead-card"):
                name_el = lead.select_one(".company-name, .buyer-company, h3")
                country_el = lead.select_one(".country, .location")
                qty_el = lead.select_one(".quantity, .qty")

                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name:
                    continue

                yield RawRecord(
                    external_id=None,
                    data_source=self.source_name,
                    company_name=name,
                    country_name=country_el.get_text(strip=True) if country_el else None,
                    product_categories=[term],
                    buyer_type="importer",
                    confidence_score=0.52,
                    raw_data={"term": term, "qty": qty_el.get_text(strip=True) if qty_el else None},
                )
