"""
Ambiente (Frankfurt) exhibitor/visitor scraper.
https://ambiente.messefrankfurt.com
World's largest consumer goods fair — key venue for brass/gift buyers.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

AMBIENTE_BASE = "https://ambiente.messefrankfurt.com"

# Ambiente product segments relevant to brass/metal decor
SEGMENTS = [
    "giving",       # gifts & decorative
    "living",       # home & garden decor
    "working",      # office accessories
    "dining",       # tableware / hotelware
]


class AmbienteScraper(BaseScraper):
    """
    Scrapes Ambiente exhibitor and buyer profiles.
    Focus on buyers/visitors in the Giving and Living segments.
    """
    source_name = "ambiente"
    requires_browser = True
    requests_per_second = 0.6

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for segment in SEGMENTS:
            async for r in self._scrape_exhibitors(segment):
                yield r
            async for r in self._scrape_buyers(segment):
                yield r

    async def _scrape_exhibitors(self, segment: str) -> AsyncGenerator[RawRecord, None]:
        """Exhibitors often are also buyers from other manufacturers."""
        url = (
            f"{AMBIENTE_BASE}/en/for-visitors/product-groups/{segment}/"
            "?page=1&perPage=100&region=all&country=all"
        )
        try:
            html = await self.browse(url, wait_for_selector=".exhibitor-list")
        except Exception as exc:
            log.error("ambiente.exhibitor_error", segment=segment, error=str(exc))
            return

        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select(".exhibitor-card, .company-card"):
            name_el = card.select_one(".company-name, h3")
            country_el = card.select_one(".country, .location")
            website_el = card.select_one("a.website, a[href*='http']")
            product_el = card.select_one(".products, .categories")

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
                product_categories=[
                    segment,
                    product_el.get_text(strip=True) if product_el else "trade fair buyer",
                ],
                buyer_type="importer",
                confidence_score=0.72,
                raw_data={"fair": "ambiente", "segment": segment, "type": "exhibitor"},
            )

    async def _scrape_buyers(self, segment: str) -> AsyncGenerator[RawRecord, None]:
        """Official buyer program attendees (pre-registered buyers)."""
        url = (
            f"{AMBIENTE_BASE}/en/trade-fair/buyers-programme/"
            f"?segment={segment}"
        )
        try:
            html = await self.browse(url)
        except Exception as exc:
            log.error("ambiente.buyer_error", segment=segment, error=str(exc))
            return

        soup = BeautifulSoup(html, "html.parser")
        for item in soup.select(".buyer-item, .participant-item"):
            name_el = item.select_one(".company, h3, .name")
            country_el = item.select_one(".country, .origin")
            type_el = item.select_one(".buyer-type, .company-type")

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
                product_categories=[segment],
                buyer_type=self._map_buyer_type(
                    type_el.get_text(strip=True) if type_el else ""
                ),
                confidence_score=0.78,
                raw_data={"fair": "ambiente", "segment": segment, "type": "buyer_programme"},
            )

    @staticmethod
    def _map_buyer_type(text: str) -> str:
        text = text.lower()
        if "wholesale" in text or "distributor" in text:
            return "distributor"
        if "retail" in text:
            return "retailer"
        if "hotel" in text or "hospitality" in text:
            return "hospitality"
        if "sourcing" in text or "buying office" in text:
            return "sourcing_company"
        return "importer"
