"""
SAM.gov scraper — US Federal procurement opportunities.
Public REST API: https://api.sam.gov/opportunities/v2/search
Requires SAM_GOV_API_KEY (free registration at sam.gov).
Targets brass/metal decor procurement by US government agencies.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator

import structlog

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

SAM_API = "https://api.sam.gov/opportunities/v2/search"
ENTITY_API = "https://api.sam.gov/entity-information/v3/entities"

SEARCH_KEYWORDS = [
    "brass decor", "brass handicraft", "metal decor",
    "decorative brass", "brass artifacts", "brass statues",
    "metal gifts", "brass hotelware", "decorative metalwork",
]

NAICS_CODES = [
    "339999",  # all other miscellaneous manufacturing
    "453220",  # gift novelty souvenir stores
    "423990",  # other misc durable goods merchant wholesalers
    "453920",  # art dealers
]


class SamGovScraper(BaseScraper):
    """
    Queries SAM.gov for federal procurement opportunities and past awards
    related to brass/metal decorative items.
    Identifies US government agencies and contractors as potential buyers.
    """
    source_name = "sam_gov"
    requests_per_second = 0.5  # SAM.gov enforces strict rate limits

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        if not settings.sam_gov_api_key:
            log.warning("sam_gov.no_api_key", msg="Register free at sam.gov")
            return

        # Current + past 2 years
        posted_from = (datetime.utcnow() - timedelta(days=730)).strftime("%m/%d/%Y")
        posted_to = datetime.utcnow().strftime("%m/%d/%Y")

        for keyword in SEARCH_KEYWORDS:
            async for r in self._search_opportunities(keyword, posted_from, posted_to):
                yield r

        # Also search entity registry for companies buying brass
        async for r in self._search_entities():
            yield r

    async def _search_opportunities(
        self, keyword: str, posted_from: str, posted_to: str
    ) -> AsyncGenerator[RawRecord, None]:
        params = {
            "api_key": settings.sam_gov_api_key,
            "q": keyword,
            "postedFrom": posted_from,
            "postedTo": posted_to,
            "limit": 1000,
            "offset": 0,
        }

        while True:
            try:
                resp = await self.get(SAM_API, params=params)
            except Exception as exc:
                log.error("sam_gov.opp_error", keyword=keyword, error=str(exc))
                break

            opps = resp.get("opportunitiesData", [])
            if not opps:
                break

            for opp in opps:
                agency = opp.get("fullParentPathName") or opp.get("organizationName", "")
                if not agency:
                    continue

                yield RawRecord(
                    external_id=opp.get("noticeId"),
                    data_source=self.source_name,
                    company_name=agency.split(".")[-1].strip() or agency,
                    country_code="US",
                    country_name="United States",
                    product_categories=[keyword],
                    product_description=opp.get("title"),
                    buyer_type="government",
                    confidence_score=0.90,
                    raw_data={
                        "notice_id": opp.get("noticeId"),
                        "notice_type": opp.get("type"),
                        "department": opp.get("fullParentPathName"),
                        "award_amount": opp.get("award", {}).get("amount"),
                        "posted_date": opp.get("postedDate"),
                        "response_deadline": opp.get("responseDeadLine"),
                        "set_aside": opp.get("typeOfSetAside"),
                        "naics_code": opp.get("naicsCode"),
                        "link": opp.get("uiLink"),
                    },
                )

            total = resp.get("totalRecords", 0)
            params["offset"] += 1000
            if params["offset"] >= total:
                break
            await asyncio.sleep(2)

    async def _search_entities(self) -> AsyncGenerator[RawRecord, None]:
        """Search SAM entity registry for companies with relevant NAICS codes."""
        for naics in NAICS_CODES:
            params = {
                "api_key": settings.sam_gov_api_key,
                "naicsCode": naics,
                "entityEFTIndicator": "",
                "registrationStatus": "A",
                "purposeOfRegistrationCode": "Z2,Z5",  # all awards
                "limit": 100,
                "offset": 0,
            }
            while True:
                try:
                    resp = await self.get(ENTITY_API, params=params)
                except Exception as exc:
                    log.error("sam_gov.entity_error", naics=naics, error=str(exc))
                    break

                entities = resp.get("entityData", [])
                if not entities:
                    break

                for e in entities:
                    reg = e.get("registration", {})
                    addr = reg.get("physicalAddress", {})
                    legal_name = reg.get("legalBusinessName", "")
                    if not legal_name:
                        continue

                    yield RawRecord(
                        external_id=reg.get("ueiSAM"),
                        data_source=self.source_name,
                        company_name=legal_name,
                        country_code="US",
                        country_name="United States",
                        city=addr.get("city"),
                        state_province=addr.get("stateOrProvinceCode"),
                        postal_code=addr.get("zipCode"),
                        address=addr.get("addressLine1"),
                        website=reg.get("entityURL"),
                        product_categories=[f"NAICS:{naics}"],
                        buyer_type="procurement_agency",
                        confidence_score=0.75,
                        raw_data={"naics": naics, "uei": reg.get("ueiSAM")},
                    )

                total = resp.get("totalRecords", 0)
                params["offset"] += 100
                if params["offset"] >= total:
                    break
