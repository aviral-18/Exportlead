"""
UNGM scraper — United Nations Global Marketplace.
https://www.ungm.org/Public/Notice
Targets UN procurement tenders for decorative / handicraft items.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

UNGM_BASE = "https://www.ungm.org"
UNGM_NOTICES = f"{UNGM_BASE}/Public/Notice"

SEARCH_TERMS = [
    "brass", "metal decor", "handicraft", "decorative",
    "artifacts", "giftware", "souvenirs",
]

# UN Agency codes
UN_AGENCIES = {
    "UNDP": "United Nations Development Programme",
    "UNICEF": "United Nations Children's Fund",
    "WHO": "World Health Organization",
    "WFP": "World Food Programme",
    "UNHCR": "United Nations High Commissioner for Refugees",
    "UNESCO": "United Nations Educational, Scientific and Cultural Organization",
    "UNOPS": "United Nations Office for Project Services",
    "UN WOMEN": "United Nations Entity for Gender Equality",
    "UNFPA": "United Nations Population Fund",
    "ITC": "International Trade Centre",
}


class UNGMScraper(BaseScraper):
    """
    Scrapes UNGM public tender notices for handicraft / decorative items.
    Identifies UN agencies as high-value institutional buyers.
    """
    source_name = "ungm"
    requires_browser = False
    requests_per_second = 0.8

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        if not settings.ungm_scrape_enabled:
            return

        for term in SEARCH_TERMS:
            async for r in self._search(term):
                yield r

    async def _search(self, term: str) -> AsyncGenerator[RawRecord, None]:
        page = 1
        while True:
            params = {
                "keywords": term,
                "pageIndex": page,
                "pageSize": 50,
                "NoticeType": "0",  # 0=all
            }
            try:
                html = await self.get(
                    f"{UNGM_NOTICES}/SearchNotices",
                    params=params,
                    json_response=False,
                )
            except Exception as exc:
                log.error("ungm.error", term=term, error=str(exc))
                break

            soup = BeautifulSoup(html, "html.parser")
            rows = soup.select("table.tableNotices tbody tr, .notice-row")
            if not rows:
                break

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue

                ref = cells[0].get_text(strip=True)
                title = cells[1].get_text(strip=True)
                agency = cells[2].get_text(strip=True)
                deadline = cells[3].get_text(strip=True)

                if not agency:
                    continue

                agency_full = UN_AGENCIES.get(agency.upper(), agency)

                yield RawRecord(
                    external_id=ref,
                    data_source=self.source_name,
                    company_name=agency_full,
                    country_code=None,  # UN agencies are international
                    country_name="International",
                    product_categories=[term],
                    product_description=title,
                    buyer_type="procurement_agency",
                    confidence_score=0.88,
                    raw_data={
                        "ref": ref,
                        "title": title,
                        "agency": agency,
                        "deadline": deadline,
                    },
                )

            # UNGM typically shows up to 200 results per search
            if len(rows) < 50:
                break
            page += 1
