"""
Deduplication pipeline using MinHash LSH for scalable candidate generation.

Strategy:
  1. Block by (country_code, first_char_of_name) to limit comparisons
  2. Use MinHash + LSH to find approximate near-duplicates in O(n) time
  3. Score each candidate pair on: name similarity, domain, country, hs_codes
  4. Write candidates to dedup_candidates table for entity resolution
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

from datasketch import MinHash, MinHashLSH
from rapidfuzz import fuzz
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_session
from src.core.models import DedupCandidate, RawBuyer

log = logging.getLogger(__name__)

# MinHash params — tune for precision/recall trade-off
NUM_PERM = 128       # higher = more accurate, more memory
LSH_THRESHOLD = 0.5  # Jaccard similarity threshold for LSH buckets


@dataclass
class CandidatePair:
    id_a: int
    id_b: int
    name_similarity: float
    domain_match: bool
    country_match: bool
    combined_score: float


def _shingles(text: str, k: int = 3) -> set[str]:
    """k-gram character shingles for MinHash."""
    if len(text) < k:
        return {text}
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def _build_minhash(text: str) -> MinHash:
    m = MinHash(num_perm=NUM_PERM)
    for shingle in _shingles(text):
        m.update(shingle.encode("utf-8"))
    return m


def _score_pair(
    name_a: str,
    name_b: str,
    domain_a: Optional[str],
    domain_b: Optional[str],
    country_a: Optional[str],
    country_b: Optional[str],
    hs_a: Optional[list[str]],
    hs_b: Optional[list[str]],
) -> tuple[float, bool, bool]:
    """Returns (combined_score, domain_match, country_match)."""
    name_sim = fuzz.token_sort_ratio(name_a, name_b) / 100.0

    domain_match = bool(
        domain_a and domain_b and domain_a.lower() == domain_b.lower()
    )
    country_match = bool(
        country_a and country_b and country_a.upper() == country_b.upper()
    )

    # HS code overlap (Jaccard)
    hs_sim = 0.0
    if hs_a and hs_b:
        set_a, set_b = set(hs_a), set(hs_b)
        hs_sim = len(set_a & set_b) / len(set_a | set_b) if (set_a | set_b) else 0.0

    # Weighted scoring
    score = (
        name_sim * 0.50
        + (0.30 if domain_match else 0.0)
        + (0.15 if country_match else 0.0)
        + hs_sim * 0.05
    )
    return score, domain_match, country_match


async def find_duplicate_candidates(
    batch_size: int = 5000,
    min_score: float = 0.70,
) -> int:
    """
    Full deduplication pass over raw_buyers.
    Returns total candidate pairs written.
    """
    total_written = 0
    lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)

    async with get_session() as session:
        # Stream all non-duplicate records ordered by country+name for blocking
        offset = 0
        records: list[tuple[int, str, Optional[str], Optional[str], Optional[list[str]]]] = []

        while True:
            stmt = (
                select(
                    RawBuyer.id,
                    RawBuyer.company_name_normalized,
                    RawBuyer.website_domain,
                    RawBuyer.country_code,
                    RawBuyer.hs_codes,
                )
                .where(RawBuyer.is_duplicate == False)
                .order_by(RawBuyer.id)
                .limit(batch_size)
                .offset(offset)
            )
            rows = (await session.execute(stmt)).fetchall()
            if not rows:
                break
            records.extend(rows)
            offset += batch_size
            log.info(f"dedup: loaded {len(records)} records")

    log.info(f"dedup: total records to process = {len(records)}")

    # Build LSH index
    id_to_record: dict[str, tuple] = {}
    for rec in records:
        rid, name, domain, country, hs = rec
        if not name:
            continue
        key = str(rid)
        mh = _build_minhash(name)
        try:
            lsh.insert(key, mh)
        except ValueError:
            pass  # duplicate key — skip
        id_to_record[key] = rec

    # Find candidate pairs
    candidate_pairs: list[CandidatePair] = []
    seen_pairs: set[tuple[int, int]] = set()

    for rec in records:
        rid, name, domain, country, hs = rec
        if not name:
            continue
        mh = _build_minhash(name)
        try:
            neighbours = lsh.query(mh)
        except Exception:
            continue

        for neighbour_key in neighbours:
            neighbour_id = int(neighbour_key)
            if neighbour_id == rid:
                continue
            pair = (min(rid, neighbour_id), max(rid, neighbour_id))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            nrec = id_to_record.get(str(neighbour_id))
            if not nrec:
                continue
            _, n2, d2, c2, h2 = nrec

            score, dom_match, ctr_match = _score_pair(
                name, n2, domain, d2, country, c2, hs, h2
            )
            if score >= min_score:
                candidate_pairs.append(
                    CandidatePair(
                        id_a=pair[0],
                        id_b=pair[1],
                        name_similarity=round(fuzz.token_sort_ratio(name, n2) / 100, 4),
                        domain_match=dom_match,
                        country_match=ctr_match,
                        combined_score=round(score, 4),
                    )
                )

    log.info(f"dedup: found {len(candidate_pairs)} candidate pairs")

    # Write to DB in batches
    WRITE_BATCH = 1000
    async with get_session() as session:
        for i in range(0, len(candidate_pairs), WRITE_BATCH):
            batch = candidate_pairs[i : i + WRITE_BATCH]
            objs = [
                DedupCandidate(
                    id_a=p.id_a,
                    id_b=p.id_b,
                    name_similarity=p.name_similarity,
                    domain_match=p.domain_match,
                    country_match=p.country_match,
                    combined_score=p.combined_score,
                )
                for p in batch
            ]
            session.add_all(objs)
            await session.flush()
            total_written += len(batch)

    log.info(f"dedup: wrote {total_written} candidates to DB")
    return total_written


async def domain_exact_dedup() -> int:
    """
    Fast pass: mark exact domain duplicates.
    Two records with the same website_domain (and neither already canonical)
    are near-certain duplicates.
    Returns count of pairs added.
    """
    sql = text("""
        INSERT INTO dedup_candidates (id_a, id_b, domain_match, country_match,
                                      name_similarity, combined_score)
        SELECT
            a.id, b.id,
            TRUE,
            (a.country_code = b.country_code),
            similarity(a.company_name_normalized, b.company_name_normalized),
            0.95
        FROM raw_buyers a
        JOIN raw_buyers b
            ON a.website_domain = b.website_domain
           AND a.id < b.id
           AND a.is_duplicate = FALSE
           AND b.is_duplicate = FALSE
           AND a.website_domain IS NOT NULL
        ON CONFLICT (id_a, id_b) DO UPDATE
            SET combined_score = GREATEST(dedup_candidates.combined_score, 0.95),
                domain_match = TRUE
    """)
    async with get_session() as session:
        result = await session.execute(sql)
        count = result.rowcount
    log.info(f"domain_dedup: {count} pairs")
    return count
