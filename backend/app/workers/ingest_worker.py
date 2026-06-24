"""
Ingest worker — fetches articles from all RSS sources and indexes them
into pgvector without generating digests.

Triggered by POST /api/v1/internal/run-ingest (see routers/internal.py).
Designed to run without a user context: pulls from every source across
all scrape tiers (breaking / standard / daily).

Will later be automated via a GitHub Actions cron schedule that calls
the endpoint with WORKER_SHARED_SECRET.

Flow:
  1. Restore RSS watermark state from Postgres to disk.
  2. Fetch all sources across all tiers concurrently.
  3. Deduplicate (URL-hash + semantic similarity).
  4. Embed and upsert into pgvector via ArticleVectorStore.
  5. Save updated watermarks back to Postgres.
"""
from __future__ import annotations

import asyncio
import logging

from app.db.session import SessionLocal
from app.integrations import bootstrap
from app.integrations.fetch_state import persisted_fetch_state

log = logging.getLogger(__name__)

_PIPELINE_SOURCE_ID = "src_pipeline"
_PIPELINE_SOURCE_NAME = "Pipeline (uncategorized)"
_ALL_TIERS = ("breaking", "standard", "daily")


def run() -> dict:
    """
    Entry point called by the internal webhook.
    Returns a summary dict the endpoint echoes back.
    """
    built = _build_components()
    if built is None:
        log.warning("ingest_worker: pipeline unavailable; skipping run")
        return {"fetched": 0, "unique": 0, "indexed": 0, "skipped_reason": "pipeline_unavailable"}

    fetcher, deduplicator, vector_store = built

    with SessionLocal() as db:
        _ensure_pipeline_source(db)
        with persisted_fetch_state(db):
            all_articles = asyncio.run(_fetch_all_tiers(fetcher))

    log.info("ingest_worker: fetched %d raw articles across all tiers", len(all_articles))

    if not all_articles:
        return {"fetched": 0, "unique": 0, "indexed": 0}

    unique = deduplicator.deduplicate(all_articles)
    log.info("ingest_worker: %d unique articles after deduplication", len(unique))

    try:
        indexed = vector_store.index_articles(unique)
    except Exception:
        log.exception("ingest_worker: indexing step failed")
        indexed = 0

    log.info("ingest_worker: indexed %d articles into pgvector", indexed)
    return {"fetched": len(all_articles), "unique": len(unique), "indexed": indexed}


async def _fetch_all_tiers(fetcher) -> list:
    """Fetch all tiers concurrently, merging and deduplicating by article ID."""
    batches = await asyncio.gather(*[fetcher.fetch_by_tier(tier) for tier in _ALL_TIERS])
    seen: set[str] = set()
    articles = []
    for batch in batches:
        for a in batch:
            if a.id not in seen:
                seen.add(a.id)
                articles.append(a)
    return articles


def _build_components():
    """
    Instantiate the fetcher, deduplicator, and vector store.
    Returns (fetcher, deduplicator, vector_store) or None on failure.
    """
    try:
        bootstrap.ensure_pipeline_importable()
        from src.ingestion.fetcher import RSSFetcher
        from src.ingestion.deduplicator import ArticleDeduplicator
        from app.rag.vector_store import ArticleVectorStore
    except ImportError as exc:
        log.warning("ingest_worker: import failed (%s)", exc)
        return None

    try:
        fetcher = RSSFetcher()
        deduplicator = ArticleDeduplicator()
        vector_store = ArticleVectorStore(fallback_source_id=_PIPELINE_SOURCE_ID)
        return fetcher, deduplicator, vector_store
    except Exception:
        log.exception("ingest_worker: component construction failed")
        return None


def _ensure_pipeline_source(db) -> None:
    """Idempotently insert the fallback Source row used for uncategorised articles."""
    from app.models import Source
    if db.get(Source, _PIPELINE_SOURCE_ID) is not None:
        return
    db.add(Source(
        id=_PIPELINE_SOURCE_ID,
        name=_PIPELINE_SOURCE_NAME,
        license="rss-snippet-only",
        source_type="aggregator",
    ))
    db.commit()
