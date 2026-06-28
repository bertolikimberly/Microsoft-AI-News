"""
RSS-based news fetcher.

Two-step content pipeline:
  1. feedparser parses the RSS feed → title, url, published_date, excerpt
  2. For sources with content_quality="excerpts", trafilatura fetches and
     extracts the full article body — it strips boilerplate (nav, ads, footers)
     far more reliably than a raw BeautifulSoup paragraph scrape.

arXiv feeds are high-volume — a keyword relevance filter is applied before returning.

Incremental ingestion: per-source watermarks are persisted to a JSON file so
reruns never re-ingest the same article twice. The file path is configurable
via FETCH_STATE_PATH; the backend wraps each run with a Postgres-backed
restore/save (see backend/app/integrations/fetch_state.py) so state survives
Container Apps scale-to-zero restarts.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import certifi
import feedparser
import trafilatura
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

# feedparser and trafilatura use urllib/httpx which both respect SSL_CERT_FILE.
# On macOS with Homebrew Python the system trust store isn't wired automatically,
# so we point both at certifi's bundle at import time.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from app.pipeline.models import Article, UserProfile
from app.pipeline.ingestion.source_registry import Source, get_sources_for_user, load_sources

_ARXIV_KEYWORDS = {
    "llm", "large language model", "transformer", "foundation model",
    "generative ai", "diffusion", "neural", "reinforcement learning",
    "multimodal", "agent", "rag", "retrieval", "fine-tun",
    "model context protocol", "mcp", "tool use", "tool calling",
    "agentic", "code generation", "code llm", "coding agent",
    "instruction tuning", "prompt", "chain-of-thought", "reasoning model",
}



def _state_file_path() -> Path:
    """
    Where the watermark state lives. Set FETCH_STATE_PATH on the container
    to point at a path the backend brackets with restore/save (so state
    survives Container Apps cold starts). Defaults to the original location
    next to the package for local dev.
    """
    override = os.environ.get("FETCH_STATE_PATH")
    if override:
        return Path(override)
    return Path(__file__).parent.parent.parent / "data" / "fetch_state.json"


_STATE_FILE = _state_file_path()


# ---------------------------------------------------------------------------
# Watermark state (mirrors data_engineering/rss_fetcher.py pattern)
# ---------------------------------------------------------------------------

def _load_state(source_ids: list[str]) -> dict[str, datetime | None]:
    defaults: dict[str, datetime | None] = {sid: None for sid in source_ids}
    if not _STATE_FILE.exists():
        return defaults
    try:
        raw = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("state file is not a JSON object")
    except (json.JSONDecodeError, ValueError, OSError):
        return defaults
    result = dict(defaults)
    for sid, iso in raw.items():
        if iso:
            try:
                result[sid] = datetime.fromisoformat(iso)
            except ValueError:
                pass
    return result


def _save_state(state: dict[str, datetime | None]) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_FILE.with_suffix(".json.tmp")
    serialized = {k: v.isoformat() if v else None for k, v in state.items()}
    tmp.write_text(json.dumps(serialized, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(_STATE_FILE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _parse_date(entry: dict) -> datetime:
    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _entry_to_text(entry: dict) -> str:
    for field in ("content", "summary", "description"):
        val = entry.get(field)
        if isinstance(val, list) and val:
            return BeautifulSoup(val[0].get("value", ""), "html.parser").get_text(" ", strip=True)
        if isinstance(val, str) and val:
            return BeautifulSoup(val, "html.parser").get_text(" ", strip=True)
    return ""


def _is_arxiv_relevant(title: str, abstract: str) -> bool:
    text = f"{title} {abstract}".lower()
    return any(kw in text for kw in _ARXIV_KEYWORDS)


def _detect_and_translate(text: str, title: str = "") -> tuple[str, str]:
    """
    Detect the language of the text and translate to English if non-English.
    Returns (translated_text, detected_language_code).
    Falls back to original text on any error.
    """
    if not text or len(text) < 40:
        return text, "en"
    try:
        from langdetect import detect, LangDetectException
        lang = detect(text[:400])
    except Exception:
        return text, "unknown"

    if lang == "en":
        return text, "en"

    try:
        from deep_translator import GoogleTranslator
        # Translate up to 4000 chars (API limit per call)
        translated = GoogleTranslator(source=lang, target="en").translate(text[:4000])
        return translated or text, lang
    except Exception:
        return text, lang


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4))
async def _fetch_full_body(url: str, timeout: float = 10.0) -> str:
    """
    Fetch and extract the main article text from a URL using trafilatura.
    Trafilatura is specifically designed for news article extraction and handles
    boilerplate removal (nav, ads, footers) far more reliably than BeautifulSoup
    paragraph scraping.
    """
    try:
        loop = asyncio.get_event_loop()
        downloaded = await loop.run_in_executor(
            None,
            lambda: trafilatura.fetch_url(
                url,
                config=trafilatura.settings.use_config(),
            ),
        )
        if not downloaded:
            return ""
        text = trafilatura.extract(
            downloaded,
            favor_recall=True,
            include_comments=False,
            include_tables=False,
        ) or ""
        return text[:4000]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

class RSSFetcher:
    """
    Fetches articles from RSS feeds defined in config/sources.json.
    Persists per-source watermarks to data/fetch_state.json so each run
    only processes articles newer than the last successful poll.
    """

    async def fetch_source(
        self,
        source: Source,
        max_articles: int = 20,
        since: datetime | None = None,
    ) -> list[Article]:
        """Parse one RSS feed and return Article objects newer than `since`."""
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, source.rss_url)

        entries = feed.entries[:max_articles]
        articles: list[Article] = []
        full_fetch_tasks: list[tuple[int, str]] = []

        for entry in entries:
            url = entry.get("link", "")
            if not url:
                continue

            title = html.unescape(entry.get("title", "No title"))
            content = _entry_to_text(entry)
            published_at = _parse_date(entry)

            # Incremental filter
            if since is not None and published_at <= since:
                continue

            if source.id.startswith("arxiv") and not _is_arxiv_relevant(title, content):
                continue

            # Detect language and translate non-English content to English.
            translated_content, lang = _detect_and_translate(content, title)
            article = Article(
                id=_make_id(url),
                url=url,
                title=title,
                source=source.name,
                published_at=published_at,
                content=translated_content,
                topic_tags=source.topic_tags,
                business_tags=source.business_tags,
                regulation_tags=source.regulation_tags,
                regions=source.regions,
                source_type=source.source_type,
                original_language=lang,
            )
            articles.append(article)

            if len(content) < 400:
                full_fetch_tasks.append((len(articles) - 1, url))

        if full_fetch_tasks:
            sem = asyncio.Semaphore(5)

            async def bounded_fetch(idx: int, url: str):
                async with sem:
                    body = await _fetch_full_body(url)
                    if body:
                        articles[idx].content = body

            await asyncio.gather(*[bounded_fetch(i, u) for i, u in full_fetch_tasks])

        return articles

    async def fetch_for_user(
        self,
        user: UserProfile,
        tiers: list[str] | None = None,
        max_per_source: int = 15,
        incremental: bool = True,
    ) -> list[Article]:
        """
        Fetch articles from all sources relevant to this user.
        When incremental=True, only articles newer than each source's last watermark
        are returned, and watermarks are updated on success.
        """
        sources = get_sources_for_user(user)
        if tiers:
            sources = [s for s in sources if s.scrape_tier in tiers]

        state = _load_state([s.id for s in sources]) if incremental else {s.id: None for s in sources}
        sem = asyncio.Semaphore(10)
        new_watermarks: dict[str, datetime] = {}

        async def fetch_one(source: Source) -> list[Article]:
            async with sem:
                try:
                    since = state.get(source.id)
                    articles = await self.fetch_source(source, max_per_source, since=since)
                    if articles:
                        new_watermarks[source.id] = max(a.published_at for a in articles)
                    return articles
                except Exception:
                    return []

        results = await asyncio.gather(*[fetch_one(s) for s in sources])

        if incremental and new_watermarks:
            updated = {**{k: v for k, v in state.items()}, **new_watermarks}
            _save_state(updated)

        all_articles: list[Article] = []
        seen_ids: set[str] = set()
        for batch in results:
            for a in batch:
                if a.id not in seen_ids:
                    seen_ids.add(a.id)
                    all_articles.append(a)

        return all_articles

    async def fetch_by_tier(
        self,
        tier: str,
        max_per_source: int = 20,
        incremental: bool = True,
    ) -> list[Article]:
        """Fetch all sources for a given scrape tier (for scheduled jobs)."""
        from app.pipeline.ingestion.source_registry import get_sources_for_tier
        sources = get_sources_for_tier(tier)

        state = _load_state([s.id for s in sources]) if incremental else {s.id: None for s in sources}
        sem = asyncio.Semaphore(10)
        new_watermarks: dict[str, datetime] = {}

        async def fetch_one(source: Source) -> list[Article]:
            async with sem:
                try:
                    since = state.get(source.id)
                    articles = await self.fetch_source(source, max_per_source, since=since)
                    if articles:
                        new_watermarks[source.id] = max(a.published_at for a in articles)
                    return articles
                except Exception:
                    return []

        results = await asyncio.gather(*[fetch_one(s) for s in sources])

        if incremental and new_watermarks:
            updated = {**{k: v for k, v in state.items()}, **new_watermarks}
            _save_state(updated)

        articles: list[Article] = []
        seen: set[str] = set()
        for batch in results:
            for a in batch:
                if a.id not in seen:
                    seen.add(a.id)
                    articles.append(a)
        return articles
