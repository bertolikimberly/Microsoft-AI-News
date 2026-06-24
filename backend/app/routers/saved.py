"""
/me/saved — user's bookmarked articles.

GET  /me/saved               → list saved articles, newest first
POST /me/saved               → save an article (idempotent)
DELETE /me/saved/{article_id} → un-save an article
"""

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.errors import problem
from app.models import Article, User
from app.models.content import UserSavedArticle
from app.routers.articles import _to_out
from app.schemas.content import ArticleOut

router = APIRouter(prefix="/me/saved", tags=["saved"])


class _SaveIn(BaseModel):
    article_id: str


@router.get("", response_model=list[ArticleOut])
def list_saved(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ArticleOut]:
    rows = (
        db.query(UserSavedArticle)
        .filter(UserSavedArticle.user_id == user.id)
        .order_by(UserSavedArticle.saved_at.desc())
        .all()
    )
    return [_to_out(row.article) for row in rows]


@router.post("", response_model=ArticleOut, status_code=status.HTTP_201_CREATED)
def save_article(
    body: _SaveIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ArticleOut:
    article = db.get(Article, body.article_id)
    if article is None:
        raise problem(status=404, title="Article not found")

    existing = db.get(UserSavedArticle, (user.id, body.article_id))
    if existing is None:
        db.add(UserSavedArticle(user_id=user.id, article_id=body.article_id))
        db.commit()
        db.refresh(article)

    return _to_out(article)


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def unsave_article(
    article_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    row = db.get(UserSavedArticle, (user.id, article_id))
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
