"""
gdelt_fetcher.py — GDELT DOC 2.0 API client for the ingestion pipeline.

GDELT is NOT an RSS feed; it is a global news index queryable via the
DOC 2.0 full-text API. This client pulls recent English-language tech
articles from the regions where our dedicated RSS sources are sparse
(LATAM, MEA, APAC, Greater China, India) and returns dicts in the SAME
shape as rss_fetcher.fetch_with_state(), so pipeline.py treats GDELT
articles exactly like RSS ones.

Free, no API key. The API is rate-limited — we sleep 6s between calls
(matching the official gdeltr2 client) and cap records per region.

Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

_GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

# Tech-relevant query fragment, OR-ed inside parens (GDELT query syntax).
_TECH_TERMS = (
    '(technology OR "artificial intelligence" OR startup OR software '
    'OR cybersecurity OR semiconductor OR fintech)'
)

# region_tag -> GDELT sourcecountry FIPS codes (sourcecountry: filters by
# where the OUTLET is based, which is what we want for regional coverage).
# Multiple countries are OR-ed by repeating the query with each; to keep
# requests low we use a representative set per region.
_REGION_COUNTRIES = {
    "Latin America":        ["BR", "MX", "AR", "CI", "CO"],   # Brazil, Mexico, Argentina, Chile, Colombia
    "Middle East & Africa": ["NI", "KE", "EG", "SF", "AE"],   # Nigeria, Kenya, Egypt, S.Africa, UAE
    "Asia Pacific":         ["ID", "VM", "TH", "RP", "MY"],   # Indonesia, Vietnam, Thailand, Philippines, Malaysia
    "Greater China":        ["CH", "TW"],                     # China, Taiwan
    "India":                ["IN"],
}

_TIMEOUT = 20.0
_MAX_PER_REGION = 20
_SLEEP_BETWEEN_CALLS = 6.0  # API rate limit — do not lower


def _parse_gdelt_date(seendate: str) -> datetime:
    """GDELT 'seendate' format: 20260601T143000Z."""
    try:
        return datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _query_region(region_tag: str, country_codes: list[str], max_records: int) -> list[dict]:
    # Build: TECH (sourcecountry:BR OR sourcecountry:MX ...) sourcelang:english
    country_clause = " OR ".join(f"sourcecountry:{c}" for c in country_codes)
    query = f"{_TECH_TERMS} ({country_clause}) sourcelang:english"
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": max_records,
        "sort": "datedesc",
        "timespan": "1d",
    }
    url = f"{_GDELT_ENDPOINT}?{urlencode(params)}"
    try:
        resp = requests.get(
            url, timeout=_TIMEOUT,
            headers={"User-Agent": "MAI-News-Bot/1.0 (capstone research project)"},
        )
        resp.raise_for_status()
        # GDELT sometimes returns empty body or HTML on throttling — guard json()
        if not resp.text.strip():
            print(f"[gdelt:{region_tag}] empty response — skipping")
            return []
        data = resp.json()
    except requests.exceptions.JSONDecodeError:
        print(f"[gdelt:{region_tag}] non-JSON response (likely throttled) — skipping")
        return []
    except Exception as exc:
        print(f"[gdelt:{region_tag}] fetch error: {exc} — skipping")
        return []

    out: list[dict] = []
    for art in data.get("articles", []):
        url_ = art.get("url", "")
        title = art.get("title", "")
        if not url_ or not title:
            continue
        pub_dt = _parse_gdelt_date(art.get("seendate", ""))
        out.append({
            "url":          url_,
            "title":        title,
            "summary":      title,  # DOC API returns no body text; title doubles as snippet
            "source_id":    "gdelt",
            "rss_feed_url": "GDELT_API",
            "category":     "Aggregator",
            "pub_date":     pub_dt.isoformat(),
            "fetched_at":   datetime.now(timezone.utc).isoformat(),
            "gdelt_region": region_tag,
        })
    print(f"[gdelt:{region_tag}] {len(out)} articles")
    return out


def fetch_gdelt(state: dict | None = None,
                max_per_region: int = _MAX_PER_REGION) -> tuple[list[dict], dict]:
    """
    Query GDELT across all underserved regions, watermark-aware.

    Args:
        state: {source_id: iso_ts}. Only the 'gdelt' key is read/written.
        max_per_region: cap on records pulled per region.

    Returns (articles, updated_state) — same contract as fetch_with_state.
    """
    state = state or {}
    last_iso = state.get("gdelt")
    last_dt = None
    if last_iso:
        try:
            last_dt = datetime.fromisoformat(last_iso)
        except ValueError:
            last_dt = None

    collected: list[dict] = []
    max_pub = last_dt

    for i, (region_tag, countries) in enumerate(_REGION_COUNTRIES.items()):
        batch = _query_region(region_tag, countries, max_per_region)
        for art in batch:
            pub_dt = datetime.fromisoformat(art["pub_date"])
            if last_dt is not None and pub_dt <= last_dt:
                continue
            collected.append(art)
            if max_pub is None or pub_dt > max_pub:
                max_pub = pub_dt
        # rate-limit politeness, but not after the final call
        if i < len(_REGION_COUNTRIES) - 1:
            time.sleep(_SLEEP_BETWEEN_CALLS)

    # de-dup by URL within this run (regions can overlap)
    seen: set[str] = set()
    deduped: list[dict] = []
    for a in collected:
        if a["url"] not in seen:
            seen.add(a["url"])
            deduped.append(a)

    updated_state = dict(state)
    if max_pub is not None:
        updated_state["gdelt"] = max_pub.isoformat()

    print(f"[gdelt] total unique new: {len(deduped)}")
    return deduped, updated_state


if __name__ == "__main__":
    arts, st = fetch_gdelt()
    print(f"\nFetched {len(arts)} GDELT articles total")
    for a in arts[:5]:
        print(f"  [{a['gdelt_region']}] {a['title'][:65]}")