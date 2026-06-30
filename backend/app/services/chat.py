"""
Chat service — RAG-powered streaming and non-streaming chat.

Thin orchestration layer between the sessions router and the pipeline.
All LLM I/O, vector retrieval, and citation resolution live here so
routers stay focused on HTTP concerns.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.integrations.llm_bridge import chat_reply, stream_chat_reply
from app.models import Preferences as PreferencesORM, User as UserORM

__all__ = ["chat_reply", "stream_chat_reply"]
