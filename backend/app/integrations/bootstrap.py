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
"""
from __future__ import annotations

import sys
from pathlib import Path

_PIPELINE_ROOT = (Path(__file__).resolve().parents[3] / "llm_engineering").resolve()
_INSERTED = False


def ensure_pipeline_importable() -> None:
    """Idempotent: insert `<repo_root>/llm_engineering` on sys.path."""
    global _INSERTED
    if _INSERTED:
        return
    p = str(_PIPELINE_ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)
    _INSERTED = True
