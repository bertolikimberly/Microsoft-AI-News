"""
rss_fetcher.py — incremental RSS ingestion with per-source watermarks.

Reads RSS_FEEDS from sources.py, fetches only entries newer than the
last successful poll for each source, and persists per-source watermarks
to fetch_state.json so reruns never re-ingest the same article twice.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import feedparser

from sources import RSS_FEEDS

STATE_FILE = Path(__file__).parent / "fetch_state.json"


# ── helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _struct_time_to_dt(struct_t) -> datetime:
    """feedparser gives UTC time.struct_time; convert to aware datetime."""
    return datetime(*struct_t[:6], tzinfo=timezone.utc)


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _entry_pub_dt(entry):
    """
    Return (pub_datetime_utc, used_fallback).
    used_fallback=True when the entry had no parseable published_parsed
    or updated_parsed and current time was substituted.
    """
    pp = entry.get("published_parsed") or entry.get("updated_parsed")
    if pp:
        return _struct_time_to_dt(pp), False
    return datetime.now(timezone.utc), True


def _extract_summary(entry) -> str:
    if entry.get("summary"):
        return entry.get("summary", "")
    content = entry.get("content")
    if content and isinstance(content, list) and content:
        return content[0].get("value", "") or ""
    return ""


# ── state I/O ────────────────────────────────────────────────────────────────

def load_state(feeds) -> dict:
    """
    Load fetch_state.json or return defaults (None per source).
    On corruption: warn and reset to defaults.
    """
    defaults = {f["id"]: None for f in feeds}
    if not STATE_FILE.exists():
        return defaults
    try:
        with STATE_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("state file is not a JSON object")
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"[WARN] fetch_state.json corrupted ({exc}) — resetting")
        return defaults

    # add any newly-added feeds that aren't in the saved state
    for src_id in defaults:
        data.setdefault(src_id, None)
    return data


def save_state(state: dict) -> None:
    """Atomic write: temp file + replace, so a crash mid-write can't corrupt."""
    tmp = STATE_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    tmp.replace(STATE_FILE)


# ── main fetch ───────────────────────────────────────────────────────────────

def fetch_new_articles():
    """
    Poll every feed in RSS_FEEDS. Return a list of normalized dicts for
    entries published after each source's last watermark.
    """
    state = load_state(RSS_FEEDS)
    new_articles = []

    for feed_meta in RSS_FEEDS:
        src_id = feed_meta["id"]
        url = feed_meta["url"]
        category = feed_meta["category"]
        last_fetched_at = state.get(src_id)
        last_dt = _parse_iso(last_fetched_at)
        last_display = last_fetched_at or "never"

        try:
            parsed = feedparser.parse(url)
        except Exception as exc:
            print(f"[{src_id}] fetch error: {exc} — skipping")
            continue

        if parsed.get("bozo") and not parsed.entries:
            exc = parsed.get("bozo_exception", "unknown error")
            print(f"[{src_id}] feed error: {exc} — skipping")
            continue

        source_new = []
        max_pub_dt = last_dt

        for entry in parsed.entries:
            pub_dt, used_fallback = _entry_pub_dt(entry)
            if used_fallback:
                print(
                    f"[{src_id}] WARN: entry missing published_parsed "
                    f"({entry.get('link', '<no link>')}) — using current time"
                )

            # incremental filter: drop entries we've already seen
            if last_dt is not None and pub_dt <= last_dt:
                continue

            source_new.append({
                "url": entry.get("link", ""),
                "title": entry.get("title", ""),
                "summary": _extract_summary(entry),
                "source_id": src_id,
                "category": category,
                "pub_date": pub_dt.isoformat(),
                "fetched_at": _now_iso(),
            })

            if max_pub_dt is None or pub_dt > max_pub_dt:
                max_pub_dt = pub_dt

        print(f"[{src_id}] {len(source_new)} new articles since {last_display}")
        new_articles.extend(source_new)

        # bump watermark to most recent pub_date seen this source, persist now
        if max_pub_dt is not None:
            state[src_id] = max_pub_dt.isoformat()
        save_state(state)

    return new_articles


# ── CLI entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("RSS fetcher — incremental ingestion")
    print("=" * 60)
    articles = fetch_new_articles()

    print()
    print("=" * 60)
    print(f"Total new articles: {len(articles)}")
    print("=" * 60)

    by_source = {}
    for art in articles:
        by_source[art["source_id"]] = by_source.get(art["source_id"], 0) + 1

    if by_source:
        print("Breakdown by source:")
        for src_id, count in sorted(by_source.items(), key=lambda kv: -kv[1]):
            print(f"  {src_id:<24} {count}")
    else:
        print("(no new articles this run)")
