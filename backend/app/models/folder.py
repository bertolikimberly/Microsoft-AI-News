"""
Folder ORM tables — UserFolder, UserFolderThread.

A folder is a named, topic-filtered collection of chat threads.
UserFolderThread is a join between a folder and a ChatSession —
kept as a separate table so no existing table needs altering.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_folder_id() -> str:
    return f"fld_{uuid.uuid4().hex}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserFolder(Base):
    __tablename__ = "user_folders"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_folder_id)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    topics_json: Mapped[str] = mapped_column(Text, default="[]")
    frequency: Mapped[str] = mapped_column(String, default="daily")
    keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )

    folder_threads: Mapped[list["UserFolderThread"]] = relationship(
        back_populates="folder", cascade="all, delete-orphan"
    )


class UserFolderThread(Base):
    """Join between a folder and a ChatSession (thread)."""

    __tablename__ = "user_folder_threads"

    folder_id: Mapped[str] = mapped_column(
        String, ForeignKey("user_folders.id", ondelete="CASCADE"), primary_key=True
    )
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )

    folder: Mapped["UserFolder"] = relationship(back_populates="folder_threads")
