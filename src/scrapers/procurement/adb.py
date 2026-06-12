"""
Asian Development Bank (ADB) procurement scraper.
https://www.adb.org/projects
Public procurement notices — no auth required.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

ADB_BASE = "https://www.adb.org"
ADB_PROJECTS = f"{ADB_BASE}/projects"
ADB_TENDERS = f"{ADB_BASE}/projects/tenders/procurement"

SEARCH_TERMS = [
    "handicraft", "brass", "metal goods", "decorative", "cultural",
]

# Countries where ADB operates (potential hospitality/govt buyers)
ADB_COUNTRIES = [
    "IN", "SG", "JP", "AU", "MY", "PH", "TH", "VN", "ID",
    "PK", "BD", "LK", "NP", "KH", "MM", "LA",
]


class ADBScraper(BaseScraper):
    """
    ADB procurement tenders for decorative / handicraft / cultural items.
    Identifies development project procurement buyers in Asia-Pacific.
    """
    source_name = "adb"
    requires_browser = False
    requests_per_second = 1.0

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for term in SEARCH_TERMS:
            async for r in self._search_tenders(term):
                yield r

    async def _search_tenders(self, term: str) -> AsyncGenerator[RawRecord, None]:
        page = 0
        while True:
            url = (
                f"{ADB_TENDERS}"
                f"?keywords={term.replace(' ', '+')}"
                f"&page={page}"
                f"&procurement_type=goods"
            )
            try:
                html = await self.get(url, json_response=False)
            except Exception as exc:
                log.error("adb.error", term=term, error=str(exc))
                break

            soup = BeautifulSoup(html, "html.parser")
            rows = soup.select("table.views-table tbody tr, .tender-item")
            if not rows:
                break

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue

                title = cells[0].get_text(strip=True)
                country_cell = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                borrower_cell = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                amount_cell = cells[3].get_text(strip=True) if len(cells) > 3 else ""

                if not borrower_cell and not title:
                    continue

                yield RawRecord(
                    external_id=None,
                    data_source=self.source_name,
                    company_name=borrower_cell or f"ADB Project - {country_cell}",
                    country_name=country_cell,
                    product_categories=[term],
                    product_description=title,
                    buyer_type="procurement_agency",
                    estimated_annual_volume_usd=self._parse_amount(amount_cell),
                    confidence_score=0.78,
                    raw_data={
                        "term": term,
                        "page": page,
                        "title": title,
                        "country": country_cell,
                    },
                )

            pager = soup.select_one(".pager-next a, a.next")
            if not pager:
                break
            page += 1

    @staticmethod
    def _parse_amount(text: str) -> float | None:
        if not text:
            return None
        clean = text.replace("$", "").replace(",", "").replace("USD", "").strip()
        mult = 1
        if "million" in clean.lower() or "M" in clean:
            mult = 1_000_000
            clean = clean.lower().replace("million", "").replace("m", "").strip()
        try:
            return float(clean.split()[0]) * mult
        except (ValueError, IndexError):
            return None
