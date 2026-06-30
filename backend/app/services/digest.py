"""
Digest service — newsletter persistence and user profile construction.

Thin orchestration layer so the digest worker and future routes import
from a clean services namespace instead of the integrations grab-bag.
"""
from __future__ import annotations

from app.integrations.llm_bridge import persist_digest, user_to_profile

__all__ = ["persist_digest", "user_to_profile"]
