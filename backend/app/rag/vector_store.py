"""
pgvector-backed article store.

Replaces the standalone ChromaDB implementation from llm_engineering with
a backend-owned store that writes embeddings into the same `articles`
table the rest of the backend reads from. The article row is the source
of truth; the vector column is just another field on it.

Interface matches the LLM pipeline's expectations (index_articles +
retrieve), so it can be passed in via `NewsPipeline(vector_store=...)`
without changing pipeline orchestration. Filtering uses the backend's
multi-dimensional (dimension, slug) tag vocabulary directly — no flat
category translation.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sentence_transformers import SentenceTransformer
from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal
from app.models import Article as ArticleORM
from app.models import ArticleTag, Source, Tag

# These come from the sibling llm_engineering tree; importing this module
# implies the integrations bootstrap has already run.
from src.models import Article as PipelineArticle

log = logging.getLogger(__name__)


class ArticleVectorStore:
    """
    pgvector-backed implementation. API-compatible with the Chroma version
    in llm_engineering/src/rag/vector_store.py so the pipeline can swap
    transparently.

    `retrieve` accepts an optional `topic_filter: list[str]` of topic-tag
    slugs to constrain results; pass any dimension's slugs via the more
    general `tag_filter: list[tuple[dimension, slug]]` if you need
    cross-dimensional filtering.
    """

    def __init__(self, fallback_source_id: str = "src_pipeline"):
        self._encoder: SentenceTransformer | None = None
        self._fallback_source_id = fallback_source_id

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_articles(self, articles: list[PipelineArticle]) -> int:
        if not articles:
            return 0

        texts = [self._embed_text(a) for a in articles]
        embeddings = self._encode(texts)

        touched = 0
        with SessionLocal() as db:
            self._ensure_fallback_source(db)
            valid_tags = self._load_valid_tag_set(db)
            for article, embedding in zip(articles, embeddings):
                if self._upsert(db, article, embedding, valid_tags):
                    touched += 1
            db.commit()
        return touched

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        topic_filter: list[str] | None = None,
        tag_filter: list[tuple[str, str]] | None = None,
    ) -> list[tuple[PipelineArticle, float]]:
        """
        Return (article, cosine_similarity) pairs, highest similarity first.

        `topic_filter` limits to articles tagged with any of the given
        topic-dimension slugs. `tag_filter` is the general form —
        list of (dimension, slug) pairs joined as OR.
        """
        query_embedding = self._encode([query])[0]

        # Normalise filters into a single (dimension, slug) list.
        pairs: list[tuple[str, str]] = list(tag_filter or [])
        if topic_filter:
            pairs.extend(("topic", slug) for slug in topic_filter)

        with SessionLocal() as db:
            stmt = (
                select(
                    ArticleORM,
                    ArticleORM.embedding.cosine_distance(query_embedding).label("distance"),
                )
                .where(ArticleORM.embedding.is_not(None))
            )

            if pairs:
                # Match if any (dimension, slug) pair tags the article.
                # We can't easily express an OR-of-AND-pairs in a single IN,
                # so we group by dimension and use IN per group.
                from collections import defaultdict
                grouped: dict[str, list[str]] = defaultdict(list)
                for dim, slug in pairs:
                    grouped[dim].append(slug)

                clauses = []
                for dim, slugs in grouped.items():
                    clauses.append(
                        select(ArticleTag.article_id).where(
                            ArticleTag.dimension == dim,
                            ArticleTag.slug.in_(slugs),
                        )
                    )
                # Articles matching any group.
                from sqlalchemy import union
                stmt = stmt.where(ArticleORM.id.in_(union(*clauses)))

            stmt = stmt.order_by("distance").limit(top_k)

            results: list[tuple[PipelineArticle, float]] = []
            for row, distance in db.execute(stmt).all():
                similarity = round(1.0 - float(distance), 4)
                results.append((_orm_to_pipeline(row), similarity))
            return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if self._encoder is None:
            self._encoder = SentenceTransformer(settings.embedding_model)
        return self._encoder.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

    @staticmethod
    def _embed_text(article: PipelineArticle) -> str:
        return f"{article.title}\n\n{(article.content or '')[:1500]}"

    def _upsert(
        self,
        db,
        article: PipelineArticle,
        embedding: list[float],
        valid_tags: set[tuple[str, str]],
    ) -> bool:
        existing = (
            db.query(ArticleORM)
            .filter(ArticleORM.url == article.url)
            .first()
        )
        if existing is not None:
            changed = False
            if existing.embedding is None:
                existing.embedding = embedding
                changed = True
            if article.content and not existing.body:
                existing.body = article.content
                changed = True
            return changed

        source_id = self._resolve_source_id(db, article.source)
        row = ArticleORM(
            id=f"art_{uuid.uuid4().hex}",
            source_id=source_id,
            title=article.title,
            url=article.url,
            author=None,
            published_at=_to_aware_utc(article.published_at),
            extract=article.summary or (article.content[:280] if article.content else None),
            body=article.content,
            embedding=embedding,
        )
        db.add(row)
        db.flush()

        # Persist multi-dim tags, dropping anything outside the seeded taxonomy.
        for dimension, slugs in (
            ("topic", article.topic_tags),
            ("business", article.business_tags),
            ("regulation_policy", article.regulation_tags),
            ("regional", article.regions),
        ):
            for slug in slugs:
                if (dimension, slug) not in valid_tags:
                    continue
                db.add(ArticleTag(article_id=row.id, dimension=dimension, slug=slug))

        return True

    def _resolve_source_id(self, db, source_name: str) -> str:
        if not source_name:
            return self._fallback_source_id
        row = db.query(Source).filter(Source.name == source_name).first()
        return row.id if row else self._fallback_source_id

    def _ensure_fallback_source(self, db) -> None:
        if db.get(Source, self._fallback_source_id) is not None:
            return
        db.add(
            Source(
                id=self._fallback_source_id,
                name="Pipeline (uncategorized)",
                license="rss-snippet-only",
                source_type="aggregator",
            )
        )
        db.flush()

    @staticmethod
    def _load_valid_tag_set(db) -> set[tuple[str, str]]:
        return {(t.dimension, t.slug) for t in db.query(Tag.dimension, Tag.slug).all()}


def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _orm_to_pipeline(row: ArticleORM) -> PipelineArticle:
    """Reconstruct a pipeline Article from an ORM row for return to callers."""
    by_dim: dict[str, list[str]] = {}
    for t in row.tags:
        by_dim.setdefault(t.dimension, []).append(t.slug)
    return PipelineArticle(
        id=row.id,
        url=row.url,
        title=row.title,
        source=row.source.name if row.source else "",
        published_at=row.published_at,
        content=row.body or row.extract or "",
        summary=row.extract,
        topic_tags=by_dim.get("topic", []),
        business_tags=by_dim.get("business", []),
        regulation_tags=by_dim.get("regulation_policy", []),
        regions=by_dim.get("regional", []),
        source_type=row.source.source_type if row.source else "secondary",
    )
