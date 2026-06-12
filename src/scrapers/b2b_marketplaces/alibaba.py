"""
Alibaba.com buyer scraper.
Targets "Buyers" / "RFQ" sections for brass and metal decor categories.
Uses Playwright because Alibaba is heavily JS-rendered with anti-bot detection.
"""
from __future__ import annotations

import json
import re
from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

ALIBABA_RFQS = "https://rfq.alibaba.com/rfq/buyerSearch.htm"
ALIBABA_BUYERS = "https://www.alibaba.com/buyers"

CATEGORY_KEYWORDS = [
    "brass decor",
    "brass handicraft",
    "brass statue figurine",
    "brass gift items",
    "brass hotelware",
    "metal home decor",
    "brass garden ornament",
    "brass religious idol",
    "brass candlestick",
    "moradabad metal craft",
]

COUNTRY_FILTERS = [
    "United States", "United Kingdom", "Germany", "France",
    "Australia", "Canada", "Netherlands", "UAE", "Saudi Arabia",
    "Singapore", "Japan", "South Korea", "South Africa", "Brazil",
    "Italy", "Spain", "Belgium", "Switzerland", "Mexico", "Poland",
]


class AlibabaScraper(BaseScraper):
    """
    Scrapes Alibaba RFQ (Request for Quotation) board for active buyers
    of brass and metal decor products.
    """
    source_name = "alibaba"
    requires_browser = True
    requests_per_second = 0.5  # strict rate limiting required

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for keyword in CATEGORY_KEYWORDS:
            async for r in self._scrape_rfqs(keyword):
                yield r
            async for r in self._scrape_buyer_profiles(keyword):
                yield r

    async def _scrape_rfqs(self, keyword: str) -> AsyncGenerator[RawRecord, None]:
        context = await self._new_context()
        try:
            page = await context.new_page()
            url = f"{ALIBABA_RFQS}?keywords={keyword.replace(' ', '+')}&tab=rfq"
            await page.goto(url, wait_until="networkidle", timeout=60_000)
            await page.wait_for_timeout(2000)

            for _ in range(5):  # paginate up to 5 pages
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                for card in soup.select(".rfq-card, [class*='rfq-item'], .buyer-card"):
                    buyer_name = (
                        card.select_one(".company-name, .buyer-name, [class*='company']")
                    )
                    country = card.select_one(".country, [class*='location'], .flag")
                    product = card.select_one(".product-name, .title, h3")
                    quantity = card.select_one(".quantity, [class*='qty']")

                    if not buyer_name:
                        continue

                    name = buyer_name.get_text(strip=True)
                    if not name or len(name) < 3:
                        continue

                    yield RawRecord(
                        external_id=None,
                        data_source=self.source_name,
                        company_name=name,
                        country_name=country.get_text(strip=True) if country else None,
                        product_categories=[keyword],
                        product_description=product.get_text(strip=True) if product else None,
                        buyer_type="importer",
                        confidence_score=0.60,
                        raw_data={
                            "keyword": keyword,
                            "quantity": quantity.get_text(strip=True) if quantity else None,
                        },
                    )

                # Try next page
                next_btn = await page.query_selector("a.next, button.next, [class*='pagination-next']")
                if not next_btn:
                    break
                await next_btn.click()
                await page.wait_for_timeout(2000)
        except Exception as exc:
            log.error("alibaba.rfq_error", keyword=keyword, error=str(exc))
        finally:
            await context.close()

    async def _scrape_buyer_profiles(self, keyword: str) -> AsyncGenerator[RawRecord, None]:
        """Scrape Alibaba's buyer directory / sourcing requests."""
        url = f"https://www.alibaba.com/trade/search?SearchText={keyword.replace(' ', '+')}&tab=buyer"
        try:
            html = await self.browse(url, wait_for_selector=".company-name")
        except Exception as exc:
            log.error("alibaba.buyer_error", keyword=keyword, error=str(exc))
            return

        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select(".organic-list-offer, .company-list-item"):
            name_el = card.select_one(".company-name, h3")
            country_el = card.select_one(".country, .location")
            website_el = card.select_one("a[href*='alibaba.com/company']")

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
                website=website_el["href"] if website_el else None,
                product_categories=[keyword],
                buyer_type="importer",
                confidence_score=0.55,
                raw_data={"keyword": keyword, "source": "buyer_directory"},
            )
