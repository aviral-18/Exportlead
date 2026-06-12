"""
Abstract base scraper with:
  - Async HTTP via aiohttp
  - Per-domain rate limiting (aiolimiter token bucket)
  - Exponential back-off retries (tenacity)
  - Proxy rotation
  - Playwright browser for JS-heavy pages
  - Structured logging
  - Checkpoint persistence
"""
from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
from urllib.parse import urlparse

import aiohttp
import structlog
from aiolimiter import AsyncLimiter
from fake_useragent import UserAgent
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import settings

log = structlog.get_logger(__name__)

_ua = UserAgent()


@dataclass
class RawRecord:
    """Normalised container returned by every scraper."""
    external_id: Optional[str]
    data_source: str
    company_name: str
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    state_province: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    email: Optional[list[str]] = field(default_factory=list)
    phone: Optional[list[str]] = field(default_factory=list)
    contact_person: Optional[str] = None
    product_categories: Optional[list[str]] = field(default_factory=list)
    hs_codes: Optional[list[str]] = field(default_factory=list)
    product_description: Optional[str] = None
    buyer_type: Optional[str] = None
    import_frequency: Optional[str] = None
    estimated_annual_volume_usd: Optional[float] = None
    volume_currency: Optional[str] = None
    last_import_date: Optional[str] = None   # ISO date string
    first_import_date: Optional[str] = None
    total_shipments: Optional[int] = None
    total_suppliers: Optional[int] = None
    confidence_score: float = 0.5
    raw_data: Optional[dict] = field(default_factory=dict)


class ProxyRotator:
    """Round-robin proxy rotation with optional BrightData support."""

    def __init__(self) -> None:
        self._proxies: list[str] = []
        self._idx = 0
        self._lock = asyncio.Lock()
        self._load()

    def _load(self) -> None:
        if settings.brightdata_scraping_browser_url:
            self._proxies = [settings.brightdata_scraping_browser_url]
            return
        if settings.proxy_url:
            self._proxies = [settings.proxy_url]
            return
        if settings.proxy_list_file:
            path = Path(settings.proxy_list_file)
            if path.exists():
                self._proxies = [
                    line.strip()
                    for line in path.read_text().splitlines()
                    if line.strip()
                ]

    async def next(self) -> Optional[str]:
        if not self._proxies:
            return None
        async with self._lock:
            proxy = self._proxies[self._idx % len(self._proxies)]
            self._idx += 1
        return proxy


_proxy_rotator = ProxyRotator()

# Per-domain rate limiters — shared across all scraper instances
_rate_limiters: dict[str, AsyncLimiter] = {}
_rl_lock = asyncio.Lock()


async def _get_limiter(domain: str, rps: float) -> AsyncLimiter:
    async with _rl_lock:
        if domain not in _rate_limiters:
            _rate_limiters[domain] = AsyncLimiter(max_rate=rps, time_period=1)
        return _rate_limiters[domain]


class BaseScraper(ABC):
    """
    Subclass and implement:
      source_name  — DataSource enum value string
      scrape()     — async generator yielding RawRecord
    """

    source_name: str
    requests_per_second: float = settings.requests_per_second
    max_retries: int = 5
    retry_min_wait: float = 2.0
    retry_max_wait: float = 60.0

    # Set True for sites that require JS execution
    requires_browser: bool = False

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._log = structlog.get_logger(self.__class__.__name__)

    # ── Session management ────────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "User-Agent": _ua.random,
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
            connector = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=4,
                ssl=False,
            )
            self._session = aiohttp.ClientSession(
                headers=headers,
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=60, connect=15),
            )
        return self._session

    async def _get_browser(self) -> Browser:
        if self._browser is None:
            self._playwright = await async_playwright().start()
            proxy_url = await _proxy_rotator.next()
            launch_kwargs: dict[str, Any] = {
                "headless": settings.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            }
            if proxy_url:
                launch_kwargs["proxy"] = {"server": proxy_url}
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        return self._browser

    async def _new_context(self) -> BrowserContext:
        browser = await self._get_browser()
        return await browser.new_context(
            user_agent=_ua.random,
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )

    # ── Core HTTP helpers ─────────────────────────────────────────────────────

    async def get(
        self,
        url: str,
        *,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        json_response: bool = True,
    ) -> Any:
        domain = urlparse(url).netloc
        limiter = await _get_limiter(domain, self.requests_per_second)

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(
                (aiohttp.ClientError, asyncio.TimeoutError, Exception)
            ),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self.retry_min_wait,
                max=self.retry_max_wait,
            ),
            reraise=True,
        ):
            with attempt:
                async with limiter:
                    session = await self._get_session()
                    proxy = await _proxy_rotator.next()
                    resp = await session.get(
                        url,
                        params=params,
                        headers=headers,
                        proxy=proxy,
                    )
                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", "60"))
                        self._log.warning(
                            "rate_limited", url=url, retry_after=retry_after
                        )
                        await asyncio.sleep(retry_after + random.uniform(1, 5))
                        raise aiohttp.ClientError("rate limited")
                    resp.raise_for_status()
                    if json_response:
                        return await resp.json(content_type=None)
                    return await resp.text()

    async def post(
        self,
        url: str,
        *,
        data: Optional[dict] = None,
        json: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> Any:
        domain = urlparse(url).netloc
        limiter = await _get_limiter(domain, self.requests_per_second)

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(min=self.retry_min_wait, max=self.retry_max_wait),
            reraise=True,
        ):
            with attempt:
                async with limiter:
                    session = await self._get_session()
                    proxy = await _proxy_rotator.next()
                    resp = await session.post(
                        url,
                        data=data,
                        json=json,
                        headers=headers,
                        proxy=proxy,
                    )
                    if resp.status == 429:
                        await asyncio.sleep(
                            int(resp.headers.get("Retry-After", "60"))
                            + random.uniform(1, 5)
                        )
                        raise aiohttp.ClientError("rate limited")
                    resp.raise_for_status()
                    return await resp.json(content_type=None)

    async def browse(
        self, url: str, *, wait_for_selector: Optional[str] = None
    ) -> str:
        """Fetch a JS-rendered page via Playwright and return its HTML."""
        context = await self._new_context()
        try:
            page: Page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=45_000)
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=15_000)
            await asyncio.sleep(random.uniform(0.5, 2.0))
            return await page.content()
        finally:
            await context.close()

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        """Yield RawRecord instances. Must be an async generator."""
        ...  # pragma: no cover

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def __aenter__(self) -> "BaseScraper":
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    # ── Utility ───────────────────────────────────────────────────────────────

    def _safe_float(self, value: Any, default: Optional[float] = None) -> Optional[float]:
        try:
            return float(str(value).replace(",", "").strip())
        except (ValueError, TypeError):
            return default

    def _safe_int(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        try:
            return int(str(value).replace(",", "").strip())
        except (ValueError, TypeError):
            return default
