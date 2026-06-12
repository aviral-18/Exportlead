"""
Made-in-China.com buyer scraper — https://www.made-in-china.com
Global B2B platform; we target their buyer inquiry / sourcing request board.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

MIC_BASE = "https://www.made-in-china.com"
TERMS = [
    "brass decor", "brass handicraft", "metal handicraft",
    "brass statue", "brass gift", "brass home decor",
]


class MadeInChinaScraper(BaseScraper):
    """
    Made-in-China buyer leads / sourcing requests.
    Despite the name, has many global buyers seeking Indian crafts.
    """
    source_name = "made_in_china"
    requires_browser = True
    requests_per_second = 0.8

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for term in TERMS:
            async for r in self._search(term):
                yield r

    async def _search(self, term: str) -> AsyncGenerator[RawRecord, None]:
        context = await self._new_context()
        try:
            page_obj = await context.new_page()
            url = (
                f"{MIC_BASE}/rfq/buyer-search.do"
                f"?keyword={term.replace(' ', '+')}&countryCode=&category=metal-craft"
            )
            await page_obj.goto(url, wait_until="networkidle", timeout=45_000)

            for page_num in range(1, 11):
                html = await page_obj.content()
                soup = BeautifulSoup(html, "html.parser")

                for card in soup.select(".rfq-item, .buyer-rfq, .sourcing-request"):
                    name_el = card.select_one(".company-name, .buyer-name, h3")
                    country_el = card.select_one(".country, .buyer-country, .flag-icon")
                    product_el = card.select_one(".product-name, .subject, h4")
                    qty_el = card.select_one(".quantity, .purchase-volume")

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
                            "page": page_num,
                            "qty": qty_el.get_text(strip=True) if qty_el else None,
                        },
                    )

                next_btn = await page_obj.query_selector("a.next, .page-next")
                if not next_btn:
                    break
                await next_btn.click()
                await page_obj.wait_for_timeout(1800)
        except Exception as exc:
            log.error("made_in_china.error", term=term, error=str(exc))
        finally:
            await context.close()
