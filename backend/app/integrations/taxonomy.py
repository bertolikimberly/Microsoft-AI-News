"""
Taxonomy bridge between the backend's multi-dimensional Tag system and the
LLM pipeline's single-dimensional TechCategory enum.

The pipeline thinks in 10 broad `TechCategory` values; the backend stores
fine-grained `(dimension, slug)` tag pairs (see app.seed.tag_slug). When
we ferry articles and user preferences across that boundary we collapse
both directions through these maps.

The mapping is intentionally lossy:
  - TechCategory.STARTUPS conceptually belongs in `business`, but the user
    chose "Map TechCategory -> topic tags", so we fold it into the closest
    topic where reasonable, or drop it.
  - When no topic tag is a clean match (OTHER), we omit.

Keep this file authoritative. The pipeline never reads backend tags
directly, and the backend never reads TechCategory directly — they go
through `to_pipeline_categories` / `from_pipeline_category` only.
"""
from __future__ import annotations

from src.models import TechCategory


# TechCategory -> backend topic slug (see app.seed.tag_slug for derivation
# from sources.json labels).
_CATEGORY_TO_TOPIC_SLUG: dict[TechCategory, str] = {
    TechCategory.AI_ML: "artificial_intelligence_ml",
    TechCategory.CLOUD: "cloud_infrastructure",
    TechCategory.SECURITY: "cybersecurity",
    TechCategory.DEVELOPER_TOOLS: "software_development",
    TechCategory.HARDWARE: "hardware_chips",
    TechCategory.ENTERPRISE_SOFTWARE: "software_development",
    TechCategory.OPEN_SOURCE: "software_development",
    TechCategory.STARTUPS: "software_development",
    TechCategory.POLICY_REGULATION: "data_privacy",
    # OTHER intentionally absent — no clean topic match.
}

# Reverse lookup. Multiple categories collapse to the same slug
# (e.g. DEVELOPER_TOOLS, ENTERPRISE_SOFTWARE, OPEN_SOURCE all map to
# software_development); when going slug -> category we pick the most
# representative one.
_TOPIC_SLUG_TO_CATEGORY: dict[str, TechCategory] = {
    "artificial_intelligence_ml": TechCategory.AI_ML,
    "cloud_infrastructure": TechCategory.CLOUD,
    "cybersecurity": TechCategory.SECURITY,
    "software_development": TechCategory.DEVELOPER_TOOLS,
    "hardware_chips": TechCategory.HARDWARE,
    "data_privacy": TechCategory.POLICY_REGULATION,
}

TOPIC_DIMENSION = "topic"


def to_topic_slugs(categories: list[TechCategory]) -> list[str]:
    """Pipeline categories -> backend topic tag slugs (deduplicated)."""
    out: list[str] = []
    seen: set[str] = set()
    for c in categories:
        slug = _CATEGORY_TO_TOPIC_SLUG.get(c)
        if slug and slug not in seen:
            out.append(slug)
            seen.add(slug)
    return out


def to_pipeline_categories(topic_slugs: list[str]) -> list[TechCategory]:
    """Backend topic tag slugs -> pipeline categories (deduplicated, OTHER for unknowns dropped)."""
    out: list[TechCategory] = []
    seen: set[TechCategory] = set()
    for slug in topic_slugs:
        cat = _TOPIC_SLUG_TO_CATEGORY.get(slug)
        if cat and cat not in seen:
            out.append(cat)
            seen.add(cat)
    return out
