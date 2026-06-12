"""
Entity resolution pipeline — Union-Find clustering of dedup candidates.

Algorithm:
  1. Load all high-confidence dedup_candidates (score >= threshold)
  2. Apply Union-Find to cluster connected components
  3. For each cluster, elect a canonical record (most complete data)
  4. Write canonical_buyers, update raw_buyers.canonical_id, create links
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Optional

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_session
from src.core.models import BuyerSourceLink, CanonicalBuyer, DedupCandidate, RawBuyer

log = logging.getLogger(__name__)


# ─── Union-Find ───────────────────────────────────────────────────────────────

class UnionFind:
    def __init__(self) -> None:
        self._parent: dict[int, int] = {}
        self._rank: dict[int, int] = defaultdict(int)

    def find(self, x: int) -> int:
        if x not in self._parent:
            self._parent[x] = x
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])  # path compression
        return self._parent[x]

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self._rank[rx] < self._rank[ry]:
            rx, ry = ry, rx
        self._parent[ry] = rx
        if self._rank[rx] == self._rank[ry]:
            self._rank[rx] += 1

    def clusters(self) -> dict[int, list[int]]:
        groups: dict[int, list[int]] = defaultdict(list)
        for node in self._parent:
            groups[self.find(node)].append(node)
        return dict(groups)


# ─── Canonical record election ────────────────────────────────────────────────

def _score_completeness(rec: RawBuyer) -> float:
    """Higher score = more complete data → preferred as canonical."""
    score = 0.0
    if rec.website:
        score += 2.0
    if rec.email:
        score += 1.5
    if rec.phone:
        score += 1.0
    if rec.address:
        score += 0.8
    if rec.product_categories:
        score += 0.5
    if rec.hs_codes:
        score += 0.5
    if rec.estimated_annual_volume_usd:
        score += 0.5
    if rec.last_import_date:
        score += 0.3
    if rec.total_shipments:
        score += 0.3
    score += float(rec.confidence_score or 0) * 2.0
    return score


def _merge_records(records: list[RawBuyer]) -> dict:
    """Merge a cluster of records into one canonical dict."""
    # Sort by completeness descending; the primary record donates most fields
    records = sorted(records, key=_score_completeness, reverse=True)
    primary = records[0]

    # Merge list fields (emails, phones, categories, hs_codes) across all
    all_emails: set[str] = set()
    all_phones: set[str] = set()
    all_categories: set[str] = set()
    all_hs: set[str] = set()
    all_sources: set[str] = set()
    min_import = None
    max_import = None
    total_ship = 0

    for r in records:
        if r.email:
            all_emails.update(r.email)
        if r.phone:
            all_phones.update(r.phone)
        if r.product_categories:
            all_categories.update(r.product_categories)
        if r.hs_codes:
            all_hs.update(r.hs_codes)
        all_sources.add(r.data_source)
        if r.first_import_date:
            if min_import is None or r.first_import_date < min_import:
                min_import = r.first_import_date
        if r.last_import_date:
            if max_import is None or r.last_import_date > max_import:
                max_import = r.last_import_date
        if r.total_shipments:
            total_ship = max(total_ship, r.total_shipments)

    # Best volume estimate: take maximum across sources
    volumes = [
        r.estimated_annual_volume_usd
        for r in records
        if r.estimated_annual_volume_usd
    ]
    best_volume = max(volumes) if volumes else None

    # Confidence = weighted average
    conf_scores = [float(r.confidence_score) for r in records if r.confidence_score]
    avg_confidence = sum(conf_scores) / len(conf_scores) if conf_scores else 0.5
    # Boost by source diversity
    source_boost = min(0.1, (len(all_sources) - 1) * 0.02)
    final_confidence = min(0.99, avg_confidence + source_boost)

    return {
        "company_name": primary.company_name,
        "company_name_normalized": primary.company_name_normalized,
        "country_code": primary.country_code,
        "country_name": primary.country_name,
        "state_province": primary.state_province,
        "city": primary.city,
        "address": primary.address,
        "website": primary.website,
        "website_domain": primary.website_domain,
        "email": list(all_emails)[:10],
        "phone": list(all_phones)[:5],
        "product_categories": list(all_categories)[:50],
        "hs_codes": list(all_hs)[:20],
        "buyer_type": primary.buyer_type,
        "import_frequency": primary.import_frequency,
        "estimated_annual_volume_usd": best_volume,
        "last_import_date": max_import,
        "first_import_date": min_import,
        "total_shipments": total_ship or None,
        "source_count": len(records),
        "data_sources": list(all_sources),
        "confidence_score": round(final_confidence, 4),
    }


# ─── Main pipeline ────────────────────────────────────────────────────────────

async def resolve_entities(
    score_threshold: float = None,
    batch_size: int = 10_000,
) -> int:
    """
    Run full entity resolution pass.
    Returns number of canonical records created / updated.
    """
    threshold = score_threshold or settings.dedup_threshold
    log.info(f"entity_resolution: threshold={threshold}")

    # Step 1: Load candidate pairs
    uf = UnionFind()
    async with get_session() as session:
        offset = 0
        while True:
            stmt = (
                select(DedupCandidate.id_a, DedupCandidate.id_b)
                .where(
                    DedupCandidate.combined_score >= threshold,
                    DedupCandidate.resolved == False,
                )
                .limit(batch_size)
                .offset(offset)
            )
            pairs = (await session.execute(stmt)).fetchall()
            if not pairs:
                break
            for id_a, id_b in pairs:
                uf.union(id_a, id_b)
            offset += batch_size
        log.info(f"entity_resolution: loaded pairs, offset={offset}")

    clusters = uf.clusters()
    # Include singletons (records not in any cluster)
    log.info(f"entity_resolution: {len(clusters)} clusters to process")

    total_canonical = 0
    CLUSTER_BATCH = 200  # process 200 clusters at a time

    cluster_items = list(clusters.items())
    for start in range(0, len(cluster_items), CLUSTER_BATCH):
        chunk = cluster_items[start : start + CLUSTER_BATCH]
        # Load all raw records for this chunk
        all_ids = [rid for _, members in chunk for rid in members]

        async with get_session() as session:
            stmt = select(RawBuyer).where(RawBuyer.id.in_(all_ids))
            raw_rows = (await session.execute(stmt)).scalars().all()
            id_to_raw = {r.id: r for r in raw_rows}

            for root_id, member_ids in chunk:
                members = [id_to_raw[mid] for mid in member_ids if mid in id_to_raw]
                if not members:
                    continue

                merged = _merge_records(members)

                # Upsert canonical record (match on website_domain or company_name+country)
                canonical = await _upsert_canonical(session, merged)
                canonical_id = canonical.id

                # Link all raw records to canonical
                for raw in members:
                    link = BuyerSourceLink(
                        canonical_id=canonical_id,
                        raw_buyer_id=raw.id,
                        data_source=raw.data_source,
                        match_confidence=raw.confidence_score,
                    )
                    session.add(link)

                # Mark raw records
                await session.execute(
                    update(RawBuyer)
                    .where(RawBuyer.id.in_([r.id for r in members]))
                    .values(
                        canonical_id=canonical_id,
                        is_duplicate=(
                            # Only the primary (highest completeness) is not a dup
                            True
                        ),
                    )
                )
                # Un-mark the primary
                primary_id = sorted(
                    members, key=_score_completeness, reverse=True
                )[0].id
                await session.execute(
                    update(RawBuyer)
                    .where(RawBuyer.id == primary_id)
                    .values(is_duplicate=False, canonical_id=canonical_id)
                )

                # Mark candidate pairs as resolved
                await session.execute(
                    update(DedupCandidate)
                    .where(
                        DedupCandidate.id_a.in_(member_ids),
                        DedupCandidate.id_b.in_(member_ids),
                    )
                    .values(resolved=True, is_match=True)
                )
                total_canonical += 1

            await session.flush()

    log.info(f"entity_resolution: created/updated {total_canonical} canonical records")
    return total_canonical


async def _upsert_canonical(session: AsyncSession, data: dict) -> CanonicalBuyer:
    """Find existing canonical record or create new one."""
    # Try by website_domain first (most reliable)
    if data.get("website_domain"):
        stmt = select(CanonicalBuyer).where(
            CanonicalBuyer.website_domain == data["website_domain"]
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            # Update fields
            for k, v in data.items():
                if v is not None and hasattr(existing, k):
                    setattr(existing, k, v)
            return existing

    # Try by normalised name + country
    if data.get("company_name_normalized") and data.get("country_code"):
        stmt = select(CanonicalBuyer).where(
            CanonicalBuyer.company_name_normalized == data["company_name_normalized"],
            CanonicalBuyer.country_code == data["country_code"],
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            for k, v in data.items():
                if v is not None and hasattr(existing, k):
                    setattr(existing, k, v)
            return existing

    # Create new
    canonical = CanonicalBuyer(**{k: v for k, v in data.items() if hasattr(CanonicalBuyer, k)})
    session.add(canonical)
    await session.flush()
    return canonical
