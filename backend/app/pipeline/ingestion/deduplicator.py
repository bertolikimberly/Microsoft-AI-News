"""
URL-based article deduplication.

Strips near-duplicate articles that arrive from multiple RSS feeds covering
the same story. Exact-URL dedup is fast and catches the vast majority of
reposts. The LLM curator (curator.py) handles thematic redundancy — two
articles covering the same story from different angles are a curator problem,
not a dedup problem.
"""
from __future__ import annotations

from app.pipeline.models import Article

# Source quality tiers — used to pick the best article when two share the
# same URL hash (shouldn't happen, but belt-and-suspenders).
_SOURCE_TIER: dict[str, int] = {
    "mit technology review": 5,
    "reuters technology": 5,
    "bloomberg technology": 5,
    "eu parliament": 5,
    "google blog": 5,
    "aws news blog": 5,
    "openai blog": 5,
    "anthropic blog": 5,
    "nvidia blog": 5,
    "github blog": 5,
    "arxiv — cs.ai": 5,
    "arxiv — cs.lg": 5,
    "techcrunch": 4,
    "wired": 4,
    "the verge": 4,
    "ars technica (tech policy)": 4,
    "politico europe": 4,
    "politico us": 4,
    "the economist": 4,
    "the register": 4,
    "venturebeat": 3,
    "euractiv": 3,
    "geekwire": 3,
    "rest of world": 3,
    "sifted": 3,
    "tech policy press": 3,
    "hacker news": 2,
}


def _source_tier(source: str) -> int:
    return _SOURCE_TIER.get(source.lower(), 1)


class ArticleDeduplicator:
    """
    Deduplicates by article ID (URL-hash). Keeps the highest-tier source
    when the same ID arrives from multiple feeds.
    """

    def deduplicate(self, articles: list[Article]) -> list[Article]:
        best: dict[str, Article] = {}
        for a in articles:
            existing = best.get(a.id)
            if existing is None or _source_tier(a.source) > _source_tier(existing.source):
                best[a.id] = a
        return list(best.values())
