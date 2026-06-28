"""
Plain article store — saves curated articles to Postgres with no vector embeddings.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models import Article as ArticleORM, ArticleTag, Source, Tag
from app.pipeline.models import Article as PipelineArticle

log = logging.getLogger(__name__)

_FALLBACK_SOURCE_ID = "src_pipeline"


class ArticleStore:
    def __init__(self, fallback_source_id: str = _FALLBACK_SOURCE_ID):
        self._fallback_source_id = fallback_source_id

    def save_articles(self, articles: list[PipelineArticle]) -> int:
        if not articles:
            return 0
        touched = 0
        with SessionLocal() as db:
            self._ensure_fallback_source(db)
            db.flush()
            valid_tags = _load_valid_tag_set(db)
            for article in articles:
                try:
                    sp = db.begin_nested()
                    if self._upsert(db, article, valid_tags):
                        touched += 1
                        sp.commit()
                    else:
                        sp.rollback()
                except Exception:
                    sp.rollback()
            db.commit()
        return touched

    def _upsert(self, db, article: PipelineArticle, valid_tags: set[tuple[str, str]]) -> bool:
        existing = db.query(ArticleORM).filter(ArticleORM.url == article.url).first()
        if existing is not None:
            if article.content and not existing.body:
                existing.body = article.content
            return False

        source_id = self._resolve_source_id(db, article.source)
        row = ArticleORM(
            id=f"art_{uuid.uuid4().hex}",
            source_id=source_id,
            title=article.title,
            url=article.url,
            published_at=_to_aware_utc(article.published_at),
            extract=article.summary or (article.content[:280] if article.content else None),
            body=article.content,
            original_language=article.original_language,
        )
        db.add(row)
        db.flush()

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
        db.add(Source(
            id=self._fallback_source_id,
            name="Pipeline (uncategorized)",
            license="rss-snippet-only",
            source_type="aggregator",
        ))
        db.flush()


def _load_valid_tag_set(db) -> set[tuple[str, str]]:
    return {(t.dimension, t.slug) for t in db.query(Tag.dimension, Tag.slug).all()}


def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
