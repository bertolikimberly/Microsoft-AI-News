"""
pgvector-backed article store.

Replaces the standalone ChromaDB implementation from llm_engineering with
a backend-owned store that writes embeddings into the same `articles`
table the rest of the backend reads from. The article row is the source
of truth; the vector column is just another field on it.

Interface matches the LLM pipeline's expectations (index_articles +
retrieve), so it can be passed in via `NewsPipeline(vector_store=...)`
without changing pipeline orchestration.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sentence_transformers import SentenceTransformer
from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal
from app.integrations.taxonomy import to_pipeline_categories
from app.models import Article as ArticleORM
from app.models import ArticleTag, Source

# These come from the sibling llm_engineering tree; importing this module
# implies the integrations bootstrap has already run (see
# app.integrations.__init__).
from src.models import Article as PipelineArticle
from src.models import TechCategory

log = logging.getLogger(__name__)


class ArticleVectorStore:
    """
    pgvector-backed implementation. API-compatible with the Chroma version
    in llm_engineering/src/rag/vector_store.py so the pipeline can swap
    transparently.

    Each `index_articles` call upserts pipeline articles into the backend
    `articles` table and writes their embedding into the same row.
    `retrieve` runs cosine-distance KNN via `<=>` against that column.
    """

    def __init__(self, fallback_source_id: str = "src_pipeline"):
        # Lazy-load the encoder — it pulls a multi-hundred-MB model on
        # first construction and we don't want to pay that cost in tests
        # or whenever the backend boots.
        self._encoder: SentenceTransformer | None = None
        self._fallback_source_id = fallback_source_id

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_articles(self, articles: list[PipelineArticle]) -> int:
        """
        Upsert articles + embeddings. Returns the number of articles that
        were either newly inserted or had a missing embedding filled in.

        Matches existing rows by URL — pipeline article IDs (sha256(url))
        don't collide with backend's `art_<uuid>`, so URL is the natural
        join key here.
        """
        if not articles:
            return 0

        texts = [self._embed_text(a) for a in articles]
        embeddings = self._encode(texts)

        touched = 0
        with SessionLocal() as db:
            self._ensure_fallback_source(db)
            for article, embedding in zip(articles, embeddings):
                if self._upsert(db, article, embedding):
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
        category_filter: list[TechCategory] | None = None,
    ) -> list[tuple[PipelineArticle, float]]:
        """
        Return (article, cosine_similarity) pairs, highest similarity first.

        category_filter limits to articles tagged with any of the given
        TechCategory values (translated to backend `topic` tags via the
        taxonomy bridge).
        """
        query_embedding = self._encode([query])[0]

        with SessionLocal() as db:
            stmt = (
                select(
                    ArticleORM,
                    ArticleORM.embedding.cosine_distance(query_embedding).label("distance"),
                )
                .where(ArticleORM.embedding.is_not(None))
            )

            if category_filter:
                from app.integrations.taxonomy import to_topic_slugs, TOPIC_DIMENSION

                slugs = to_topic_slugs(category_filter)
                if slugs:
                    stmt = stmt.where(
                        ArticleORM.id.in_(
                            select(ArticleTag.article_id).where(
                                ArticleTag.dimension == TOPIC_DIMENSION,
                                ArticleTag.slug.in_(slugs),
                            )
                        )
                    )

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
        self, db, article: PipelineArticle, embedding: list[float]
    ) -> bool:
        """
        Insert-or-update one pipeline article into `articles`. Returns True
        if the row was created or the embedding was newly written.
        """
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
        db.add(
            ArticleORM(
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
        )
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


def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _orm_to_pipeline(row: ArticleORM) -> PipelineArticle:
    """Reconstruct a pipeline Article from an ORM row for return to callers."""
    topic_slugs = [t.slug for t in row.tags if t.dimension == "topic"]
    categories = to_pipeline_categories(topic_slugs) or [TechCategory.OTHER]
    return PipelineArticle(
        id=row.id,
        url=row.url,
        title=row.title,
        source=row.source.name if row.source else "",
        published_at=row.published_at,
        content=row.body or row.extract or "",
        summary=row.extract,
        categories=categories,
        source_type=row.source.source_type if row.source else "secondary",
    )
