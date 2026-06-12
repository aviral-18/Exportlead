"""
TradeKey.com buyer scraper — https://www.tradekey.com
B2B marketplace focused on South Asia / Middle East buyers.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

TRADEKEY_BASE = "https://www.tradekey.com"
SEARCH_TERMS = [
    "brass handicraft", "brass decor", "metal craft",
    "brass gift items", "brass figurines", "brass statues",
]


class TradeKeyScraper(BaseScraper):
    source_name = "tradekey"
    requires_browser = True
    requests_per_second = 1.0

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for term in SEARCH_TERMS:
            async for r in self._search(term):
                yield r

    async def _search(self, term: str) -> AsyncGenerator[RawRecord, None]:
        url = f"{TRADEKEY_BASE}/buyers/{term.replace(' ', '-')}.html"
        try:
            html = await self.browse(url, wait_for_selector=".buyer-list")
        except Exception as exc:
            log.error("tradekey.error", term=term, error=str(exc))
            return

        soup = BeautifulSoup(html, "html.parser")
        for item in soup.select(".buyer-item, .rfq-item, .lead-item"):
            name_el = item.select_one(".company, .buyer-name, h3")
            country_el = item.select_one(".country, .location")
            qty_el = item.select_one(".quantity, .qty-required")
            product_el = item.select_one(".product-name, .product")

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
                product_description=product_el.get_text(strip=True) if product_el else None,
                buyer_type="importer",
                confidence_score=0.55,
                raw_data={
                    "term": term,
                    "quantity": qty_el.get_text(strip=True) if qty_el else None,
                },
            )
