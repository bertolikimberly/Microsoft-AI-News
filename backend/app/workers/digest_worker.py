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
from datetime import date, datetime, timezone

from sqlalchemy import func
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


def _find_eligible_users(db: Session) -> list[User]:
    """
    Users who should receive a digest today:
      - have a Preferences row,
      - aren't soft-deleted,
      - don't already have a Digest whose generated_at falls on today's UTC date.

    The full delivery_day / frequency / timezone predicate (docs §F3) lives
    here too once timezone handling lands; today we treat every user with
    preferences as eligible and rely on the idempotency check to keep the
    daily cron from double-sending.
    """
    today = datetime.now(timezone.utc).date()

    candidates = (
        db.query(User)
        .join(Preferences, Preferences.user_id == User.id)
        .filter(User.deleted_at.is_(None))
        .all()
    )

    already_done = {
        uid
        for (uid,) in db.query(Digest.user_id)
        .filter(func.date(Digest.generated_at) == today)
        .all()
    }

    return [u for u in candidates if u.id not in already_done]


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
    Instantiate the LLM pipeline once per worker run.

    Returns None and logs the reason if imports fail or required config
    (LLM API key, etc.) is missing — the webhook then reports
    `skipped_reason: pipeline_unavailable` instead of 500ing.
    """
    try:
        bootstrap.ensure_pipeline_importable()
        from src.pipeline import NewsPipeline
    except ImportError as exc:
        log.warning("digest_worker: pipeline import failed (%s)", exc)
        return None

    try:
        return NewsPipeline()
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


# `date` is imported above to keep the F3 delivery_day predicate close at hand;
# silence the linter if it's currently unreferenced.
_ = date
