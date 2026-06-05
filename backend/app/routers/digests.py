"""
/me/digests/* — past-digest list + feedback (docs/feature_endpoints F3, F6).

This router is read-only on digests themselves — writes happen from the
digest worker (D1) via direct DB access, not the public API.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.errors import problem
from app.models import Digest, DigestItem, Feedback, User
from app.pagination import Page, PageInfo, decode_cursor, encode_cursor
from app.schemas.digest import DigestSummary, FeedbackIn

router = APIRouter(prefix="/me/digests", tags=["digests"])


@router.get("", response_model=Page[DigestSummary])
def list_digests(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> Page[DigestSummary]:
    """
    List past digests for the caller, newest first.

    Cursor pagination: cursor encodes the last seen digest ID; we paginate
    by `(generated_at DESC, id DESC)` but since ULID-ish IDs are roughly
    sortable, the cursor on `id` is good enough at MVP.
    """
    after_id = decode_cursor(cursor)

    q = (
        db.query(
            Digest.id,
            Digest.generated_at,
            func.count(DigestItem.id).label("item_count"),
        )
        .outerjoin(DigestItem, DigestItem.digest_id == Digest.id)
        .filter(Digest.user_id == user.id)
        .group_by(Digest.id)
        .order_by(desc(Digest.generated_at), desc(Digest.id))
    )

    if after_id:
        # Find the cursor row's `generated_at` so we can resume strictly past it.
        anchor = db.query(Digest.generated_at).filter(Digest.id == after_id).first()
        if anchor is not None:
            q = q.filter(
                (Digest.generated_at < anchor[0])
                | ((Digest.generated_at == anchor[0]) & (Digest.id < after_id))
            )

    rows = q.limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    data = [
        DigestSummary(id=r.id, generated_at=r.generated_at, item_count=r.item_count or 0)
        for r in rows
    ]
    next_cursor = encode_cursor(rows[-1].id) if has_more and rows else None
    return Page(data=data, page=PageInfo(next_cursor=next_cursor, limit=limit))


@router.post("/{digest_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def post_feedback(
    digest_id: str,
    body: FeedbackIn,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """
    Record a thumbs up/down on one item.

    Idempotent on `(user, digest, article)`: a second POST overwrites the
    previous signal. Returns 204 — frontend already has the value it sent.
    """
    digest = db.get(Digest, digest_id)
    if digest is None or digest.user_id != user.id:
        raise problem(status=404, title="Digest not found")

    # Confirm the article appears in this digest, so we can't be tricked
    # into recording feedback against an article from someone else's digest.
    item_match = (
        db.query(DigestItem.id)
        .filter(DigestItem.digest_id == digest_id, DigestItem.article_id == body.article_id)
        .first()
    )
    if item_match is None:
        raise problem(
            status=422,
            title="Article not in digest",
            detail=f"article_id {body.article_id} is not part of digest {digest_id}",
        )

    existing = (
        db.query(Feedback)
        .filter(
            Feedback.user_id == user.id,
            Feedback.digest_id == digest_id,
            Feedback.article_id == body.article_id,
        )
        .first()
    )
    if existing is not None:
        existing.signal = body.signal
        existing.created_at = datetime.now(timezone.utc)
    else:
        db.add(
            Feedback(
                user_id=user.id,
                digest_id=digest_id,
                article_id=body.article_id,
                signal=body.signal,
            )
        )
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
