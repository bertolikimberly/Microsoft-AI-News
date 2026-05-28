"""
Digest worker — generates and persists daily digests (F3).

Triggered by the /api/v1/internal/run-digest-worker webhook, which is
itself fired on a schedule by .github/workflows/digest-cron.yml (GitHub
Actions cron — free, no card needed). The webhook authenticates with
WORKER_SHARED_SECRET; this module assumes the caller is trusted.

Flow (see docs/feature_endpoints.md F3):
  1. Find users whose frequency × delivery_day × delivery_hour_local
     makes today a delivery day, and who don't already have a digest
     for today (idempotency).
  2. For each eligible user:
       a. Build a pipeline UserProfile from their backend preferences.
       b. Run the LLM pipeline end-to-end (fetch → dedupe → rank → generate).
       c. Persist the resulting NewsletterDigest as Digest + DigestItem
          + Article rows via the integrations.llm_bridge adapter.

The LLM pipeline lives in the sibling `llm_engineering/` tree; we put it
on sys.path via integrations.bootstrap so backend code can import from
`src.*` without packaging it as a wheel.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.integrations import bootstrap
from app.models import Digest, Preferences, Source, User

log = logging.getLogger(__name__)

# Source row used for pipeline-fetched articles when we can't match a
# specific publisher in the backend `sources` table. Created once on first
# run.
_PIPELINE_SOURCE_ID = "src_pipeline"
_PIPELINE_SOURCE_NAME = "Pipeline (uncategorized)"


def run() -> dict:
    """
    Entry point called by the internal webhook.

    Returns a summary the webhook echoes back. Always returns; per-user
    failures are logged and counted but don't crash the run.
    """
    with SessionLocal() as db:
        _ensure_pipeline_source(db)
        eligible = _find_eligible_users(db)
        log.info("digest_worker: eligible users today: %d", len(eligible))

        if not eligible:
            return {"eligible_users": 0, "generated": 0, "failed": 0}

        pipeline = _build_pipeline()
        if pipeline is None:
            log.warning("digest_worker: pipeline unavailable; skipping run")
            return {"eligible_users": len(eligible), "generated": 0, "failed": 0, "skipped_reason": "pipeline_unavailable"}

        generated = 0
        failed = 0
        for user in eligible:
            try:
                _generate_for_user(db, pipeline, user)
                db.commit()
                generated += 1
            except Exception:
                log.exception("digest_worker: generation failed for user %s", user.id)
                db.rollback()
                failed += 1

        return {"eligible_users": len(eligible), "generated": generated, "failed": failed}


# ----------------------------------------------------------------------
# Eligibility
# ----------------------------------------------------------------------


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# Window after the last successful generation in which we refuse to
# generate again for the same user. 22h is enough to swallow per-user TZ
# jitter (DST transitions, near-midnight runs) without blocking the next
# scheduled cycle 24h later. Keep this strictly below the shortest
# delivery cadence (daily = 24h).
_IDEMPOTENCY_WINDOW = timedelta(hours=22)


def _find_eligible_users(db: Session) -> list[User]:
    """
    Per-user, timezone-aware eligibility predicate.

    A user is eligible right now if, evaluated in their own IANA timezone:
      1. today's weekday is a delivery day for their `frequency`
            daily     -> every day
            weekdays  -> Monday through Friday
            weekly    -> only on `delivery_day`
      2. the current local hour has reached `delivery_hour_local`
      3. they have not received a digest within `_IDEMPOTENCY_WINDOW`

    The worker is expected to run hourly (see digest-cron.yml); the hour
    check ensures we don't fire before 08:00 local, and the idempotency
    check ensures we don't fire repeatedly within the same local day.

    Soft-deleted users are excluded. Users with bad/missing timezone strings
    fall back to UTC rather than being skipped.
    """
    now_utc = datetime.now(timezone.utc)
    recent_cutoff = now_utc - _IDEMPOTENCY_WINDOW

    candidates = (
        db.query(User)
        .join(Preferences, Preferences.user_id == User.id)
        .filter(User.deleted_at.is_(None))
        .all()
    )

    recent_user_ids = {
        uid
        for (uid,) in db.query(Digest.user_id)
        .filter(Digest.generated_at >= recent_cutoff)
        .all()
    }

    eligible: list[User] = []
    for user in candidates:
        prefs = user.preferences
        if prefs is None:
            continue
        if user.id in recent_user_ids:
            continue

        local_now = _to_user_local(now_utc, prefs.timezone)

        if not _is_delivery_day(prefs.frequency, prefs.delivery_day, local_now):
            continue
        if local_now.hour < prefs.delivery_hour_local:
            continue

        eligible.append(user)

    return eligible


def _to_user_local(now_utc: datetime, tz_name: str | None) -> datetime:
    """Convert UTC to the user's local time, falling back to UTC on bad input."""
    try:
        zone = ZoneInfo(tz_name) if tz_name else ZoneInfo("UTC")
    except ZoneInfoNotFoundError:
        log.warning("digest_worker: unknown timezone %r, falling back to UTC", tz_name)
        zone = ZoneInfo("UTC")
    return now_utc.astimezone(zone)


def _is_delivery_day(frequency: str, delivery_day: str, local_now: datetime) -> bool:
    """Today (in user-local TZ) a delivery day for this frequency?"""
    if frequency == "daily":
        return True
    weekday = local_now.weekday()  # Monday = 0
    if frequency == "weekdays":
        return weekday < 5
    if frequency == "weekly":
        try:
            return _WEEKDAYS[weekday] == delivery_day
        except IndexError:
            return False
    return False


# ----------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------


def _generate_for_user(db: Session, pipeline, user: User) -> None:
    """
    Run the pipeline for one user and persist the result.

    Imports from `app.integrations.llm_bridge` are deferred to the call
    site so a failure to import the pipeline (e.g. missing dependency)
    doesn't break the rest of the backend on app boot.
    """
    from app.integrations.llm_bridge import persist_digest, user_to_profile

    if user.preferences is None:
        log.info("digest_worker: user %s has no preferences; skipping", user.id)
        return

    profile = user_to_profile(user, user.preferences)
    newsletter = asyncio.run(pipeline.run_for_user(profile))
    persist_digest(db, user, newsletter, fallback_source_id=_PIPELINE_SOURCE_ID)


# ----------------------------------------------------------------------
# Pipeline lifecycle
# ----------------------------------------------------------------------


def _build_pipeline():
    """
    Instantiate the LLM pipeline once per worker run, wired to the backend's
    pgvector-backed vector store so embeddings and articles share one
    source of truth (Postgres `articles` table).

    Returns None and logs the reason if imports fail or required config
    (LLM API key, etc.) is missing — the webhook then reports
    `skipped_reason: pipeline_unavailable` instead of 500ing.
    """
    try:
        bootstrap.ensure_pipeline_importable()
        from src.pipeline import NewsPipeline
        from app.rag.vector_store import ArticleVectorStore
    except ImportError as exc:
        log.warning("digest_worker: pipeline import failed (%s)", exc)
        return None

    try:
        vector_store = ArticleVectorStore(fallback_source_id=_PIPELINE_SOURCE_ID)
        return NewsPipeline(vector_store=vector_store)
    except Exception:
        log.exception("digest_worker: pipeline construction failed")
        return None


def _ensure_pipeline_source(db: Session) -> None:
    """Idempotently insert the fallback Source row used when we can't match a publisher."""
    if db.get(Source, _PIPELINE_SOURCE_ID) is not None:
        return
    db.add(
        Source(
            id=_PIPELINE_SOURCE_ID,
            name=_PIPELINE_SOURCE_NAME,
            license="rss-snippet-only",
            source_type="aggregator",
        )
    )
    db.commit()


