"""
/tags — the full multi-dimensional tag taxonomy (docs/feature_endpoints F2).

Read-only, bearer-required, cacheable. Returns every tag grouped by
dimension (topic, business, regulation_policy, regional, role, seniority).
The taxonomy is seeded at startup by app.seed.seed_tags from sources.json;
this endpoint just hands it back.
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import Tag, User
from app.schemas.content import TagOut

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=dict[str, list[TagOut]])
def list_tags(
    response: Response,
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
    dimension: str | None = Query(
        default=None,
        description="Optional — return only this dimension instead of all six.",
    ),
) -> dict[str, list[TagOut]]:
    """
    Return the taxonomy as `{dimension: [{slug, label}, ...]}`.

    With `?dimension=topic` the response contains only that one key — used by
    preference screens that render a single category at a time. The taxonomy
    rarely changes, so the response is cached for 24h.
    """
    response.headers["Cache-Control"] = "private, max-age=86400"

    q = db.query(Tag)
    if dimension is not None:
        q = q.filter(Tag.dimension == dimension)
    rows = q.order_by(Tag.dimension, Tag.slug).all()

    out: dict[str, list[TagOut]] = {}
    for t in rows:
        out.setdefault(t.dimension, []).append(TagOut(slug=t.slug, label=t.label))
    return out
