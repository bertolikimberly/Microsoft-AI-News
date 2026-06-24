"""
Make the sibling `llm_engineering/` package importable from the backend.

The LLM pipeline lives at `<repo_root>/llm_engineering/src/...` but uses
bare `src.*` imports (e.g. `from src.models import UserProfile`). The
backend runs from `<repo_root>/backend/`, so `llm_engineering/` is not on
`sys.path` by default. Call `ensure_pipeline_importable()` once before
the first `from src.* import ...` in any backend code path.

This is a deliberate runtime path tweak rather than a packaging change
because llm_engineering isn't published as a wheel yet — the two trees
share a repo, not a release.

Two layouts are supported:
  - Local dev: `<repo_root>/llm_engineering/`     — sibling of backend/
  - Docker:    `/app/llm_engineering/`            — copied in by the Dockerfile

We try each in order and use the first one that exists. The PIPELINE_ROOT
environment variable overrides both if set (handy for tests or unusual
layouts).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_CANDIDATES: tuple[Path, ...] = (
    # Local dev layout — sibling directory of backend/
    Path(__file__).resolve().parents[3] / "llm_engineering",
    # Container layout — Dockerfile COPYs llm_engineering/ to /app/llm_engineering
    Path("/app/llm_engineering"),
)
_INSERTED = False


def _resolve_pipeline_root() -> Path | None:
    """Return the first existing candidate path, or None if nothing works."""
    override = os.environ.get("PIPELINE_ROOT")
    if override:
        p = Path(override).resolve()
        return p if p.exists() else None
    for candidate in _CANDIDATES:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return None


def ensure_pipeline_importable() -> None:
    """
    Idempotent: insert the resolved llm_engineering path on sys.path.

    Raises ImportError if no candidate path resolves — caller handles it
    (digest_worker logs and skips; chat endpoint returns 503).
    """
    global _INSERTED
    if _INSERTED:
        return
    root = _resolve_pipeline_root()
    if root is None:
        raise ImportError(
            "llm_engineering/ not found. Tried: "
            + ", ".join(str(c) for c in _CANDIDATES)
            + ". Set PIPELINE_ROOT env var to override."
        )
    p = str(root)
    if p not in sys.path:
        sys.path.insert(0, p)
    _INSERTED = True
