"""
Adapter layer between backend ORM types and the LLM pipeline's Pydantic
types. Two directions:

  user_to_profile(user, prefs)              -> pipeline UserProfile (input)
  persist_digest(db, user, newsletter)      -> Digest + DigestItems + Articles (output)

Keep all backend <-> pipeline translation in this one file. The digest
worker calls these; nothing else should import from `src.*`.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.integrations.taxonomy import to_pipeline_categories
from app.models import (
    Article as ArticleORM,
    Digest as DigestORM,
    DigestItem as DigestItemORM,
    Preferences as PreferencesORM,
    Source as SourceORM,
    User as UserORM,
)

# The LLM pipeline lives in a sibling package (`llm_engineering/src/`).
# `digest_worker` is responsible for adding it to sys.path before importing
# from here; see app.integrations.bootstrap.
from src.models import (
    Article as PipelineArticle,
    DigestFrequency,
    NewsletterDigest,
    TonePreference,
    UserProfile,
)

log = logging.getLogger(__name__)


def user_to_profile(user: UserORM, prefs: PreferencesORM) -> UserProfile:
    """
    Build a pipeline UserProfile from backend User + Preferences rows.

    Topic preferences are translated via the taxonomy bridge. Business,
    regulation, region, and seniority tags are not surfaced to the pipeline
    yet — when the ranker grows to read them, extend this adapter rather
    than threading new fields through digest_worker.
    """
    topic_slugs = _safe_json_list(prefs.topics_json)
    interests = to_pipeline_categories(topic_slugs)

    return UserProfile(
        user_id=user.id,
        name=user.display_name or user.email.split("@", 1)[0],
        email=user.email,
        role=prefs.role or "",
        interests=interests,
        companies_to_track=[],  # not modelled in backend prefs yet
        tone=_tone(prefs.tone),
        digest_frequency=_frequency(prefs.frequency),
        topic_weights={},  # filled later from implicit feedback (F10)
    )


def persist_digest(
    db: Session,
    user: UserORM,
    newsletter: NewsletterDigest,
    fallback_source_id: str,
) -> DigestORM:
    """
    Turn the pipeline's in-memory NewsletterDigest into ORM rows.

    For each article in the newsletter we either reuse an existing Article
    row (matched by URL — the natural key, since pipeline IDs are sha256(url)
    and don't collide with backend's `art_<uuid>`) or insert a new one. The
    Digest + DigestItem rows are always new — duplicate-day prevention lives
    in _find_eligible_users, not here.

    `fallback_source_id` is the source row used when the pipeline doesn't
    surface enough metadata to resolve the article's source. The worker
    seeds a "pipeline" source on startup and passes its id here.

    Caller owns the commit; this function does flushes but no commit.
    """
    digest = DigestORM(user_id=user.id, generated_at=newsletter.generated_at)
    db.add(digest)
    db.flush()  # need digest.id for items below

    tone = _profile_tone(user.preferences) if user.preferences else "balanced"
    length = (user.preferences.length if user.preferences else None) or "standard"

    for entry in newsletter.articles:
        article_row = _upsert_article(db, entry.article, fallback_source_id)
        db.add(
            DigestItemORM(
                digest_id=digest.id,
                article_id=article_row.id,
                rank=entry.rank,
                summary=entry.summary,
                tone=tone,
                length=length,
                citations_json=json.dumps([]),  # citations resolved at read time (F8)
            )
        )

    return digest


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _upsert_article(
    db: Session, pipeline_article: PipelineArticle, fallback_source_id: str
) -> ArticleORM:
    """Match on URL; insert if missing. Returns the persisted ArticleORM row."""
    existing = db.query(ArticleORM).filter(ArticleORM.url == pipeline_article.url).first()
    if existing is not None:
        # Refresh body + embedding pointer if the pipeline has a fresher copy.
        if pipeline_article.content and not existing.body:
            existing.body = pipeline_article.content
        if pipeline_article.embedding_id and not existing.embedding_id:
            existing.embedding_id = pipeline_article.embedding_id
        return existing

    source_id = _resolve_source_id(db, pipeline_article.source, fallback_source_id)
    row = ArticleORM(
        source_id=source_id,
        title=pipeline_article.title,
        url=pipeline_article.url,
        author=None,
        published_at=_to_aware_utc(pipeline_article.published_at),
        extract=pipeline_article.summary or (pipeline_article.content[:280] if pipeline_article.content else None),
        body=pipeline_article.content,
        embedding_id=pipeline_article.embedding_id,
    )
    db.add(row)
    db.flush()
    return row


def _resolve_source_id(db: Session, source_name: str, fallback_source_id: str) -> str:
    """
    Match a pipeline `source` (a human name like "TechCrunch") to a backend
    Source row by `name`. Falls back to the worker's pipeline-source row
    when we can't resolve it.
    """
    if not source_name:
        return fallback_source_id
    row = db.query(SourceORM).filter(SourceORM.name == source_name).first()
    return row.id if row else fallback_source_id


def _safe_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _tone(value: str | None) -> TonePreference:
    """Backend stores tone as a free string; map to pipeline enum, defaulting to BALANCED."""
    try:
        return TonePreference(value) if value else TonePreference.BALANCED
    except ValueError:
        return TonePreference.BALANCED


def _profile_tone(prefs: PreferencesORM | None) -> str:
    return (prefs.tone if prefs and prefs.tone else "balanced")


def _frequency(value: str | None) -> DigestFrequency:
    try:
        return DigestFrequency(value) if value else DigestFrequency.WEEKLY
    except ValueError:
        return DigestFrequency.WEEKLY


def _to_aware_utc(dt: datetime) -> datetime:
    """Pipeline articles may have naive datetimes; backend columns require tz-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
