"""
/sources — the news-source registry (docs/feature_endpoints F2).

Read-only, bearer-required, cacheable. Lists the curated sources that power
the source-muting picker in preferences. Rows are seeded at startup by
app.seed.seed_sources from sources.json.
"""

import json

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import Source, User
from app.schemas.content import SourceOut

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(
    response: Response,
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
    region: str | None = Query(default=None, description="Filter to sources tagged with this region."),
    category: str | None = Query(default=None, description="Filter to sources in this category."),
) -> list[SourceOut]:
    """
    List available sources, alphabetically by name. The registry rarely
    changes, so the response is cached for 24h.

    `?category=` is filtered in SQL; `?region=` is filtered in Python because
    a source's regions are stored as a JSON list, not a scalar column.
    """
    response.headers["Cache-Control"] = "private, max-age=86400"

    q = db.query(Source)
    if category is not None:
        q = q.filter(Source.category == category)
    rows = q.order_by(Source.name).all()

    out: list[SourceOut] = []
    for s in rows:
        try:
            regions = json.loads(s.region_json)
        except (TypeError, json.JSONDecodeError):
            regions = []
        if region is not None and region not in regions:
            continue
        out.append(
            SourceOut(
                id=s.id,
                name=s.name,
                category=s.category,
                source_type=s.source_type,
                region=regions,
                content_quality=s.content_quality,
            )
        )
    return out
