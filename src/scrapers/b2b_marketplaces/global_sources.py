"""
Global Sources buyer scraper — https://www.globalsources.com
Targets the buyer directory and sourcing requests for brass/metal products.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

GS_BASE = "https://www.globalsources.com"
SEARCH_TERMS = [
    "brass decor", "brass handicraft", "metal home decor",
    "brass gift", "brass statues", "brass artifacts",
]


class GlobalSourcesScraper(BaseScraper):
    source_name = "global_sources"
    requires_browser = True
    requests_per_second = 0.8

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for term in SEARCH_TERMS:
            async for r in self._search_buyers(term):
                yield r

    async def _search_buyers(self, term: str) -> AsyncGenerator[RawRecord, None]:
        context = await self._new_context()
        try:
            page = await context.new_page()
            url = (
                f"{GS_BASE}/trade-shows/buyers?searchKeyword={term.replace(' ', '+')}"
                "&buyerType=buyer&productCategory=metalCrafts"
            )
            await page.goto(url, wait_until="networkidle", timeout=45_000)
            await page.wait_for_timeout(1500)

            for _ in range(8):
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                for card in soup.select(".buyer-card, .company-item, [class*='buyer-info']"):
                    name_el = card.select_one(".company-name, .buyer-name, h3, h4")
                    country_el = card.select_one(".country, .location, [class*='flag']")
                    product_el = card.select_one(".product-interest, .sourcing-product")
                    volume_el = card.select_one(".annual-purchase, .purchase-volume")

                    if not name_el:
                        continue
                    name = name_el.get_text(strip=True)
                    if not name or len(name) < 3:
                        continue

                    yield RawRecord(
                        external_id=None,
                        data_source=self.source_name,
                        company_name=name,
                        country_name=country_el.get_text(strip=True) if country_el else None,
                        product_categories=[
                            product_el.get_text(strip=True) if product_el else term
                        ],
                        buyer_type="importer",
                        estimated_annual_volume_usd=self._parse_volume(
                            volume_el.get_text(strip=True) if volume_el else ""
                        ),
                        confidence_score=0.62,
                        raw_data={"term": term},
                    )

                next_btn = await page.query_selector("a.next-page, .pagination .next")
                if not next_btn:
                    break
                await next_btn.click()
                await page.wait_for_timeout(2000)
        except Exception as exc:
            log.error("global_sources.error", term=term, error=str(exc))
        finally:
            await context.close()

    @staticmethod
    def _parse_volume(text: str) -> float | None:
        """Parse strings like '$1M - $5M' or 'USD 500K' to float."""
        if not text:
            return None
        text = text.upper().replace(",", "").replace("$", "").replace("USD", "").strip()
        multiplier = 1
        if "M" in text:
            multiplier = 1_000_000
            text = text.replace("M", "")
        elif "K" in text:
            multiplier = 1_000
            text = text.replace("K", "")
        try:
            parts = text.split("-")
            return float(parts[0].strip()) * multiplier
        except (ValueError, IndexError):
            return None
