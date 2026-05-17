# Changelog

All notable changes to this project are documented here.

---

## [2026-05-18] — Bug fixes & source registry

### Files modified

#### `data_engineering/tag_discovery.py`

**Bug 1 — Text-cleaning regex stripped all numbers and key punctuation**

The original regex `r"[^a-z\s]"` removed every character that wasn't a
lowercase letter or whitespace. This silently destroyed financial figures
(`$4.5 billion`), tech model names (`GPT-4o`, `Claude-3.7`), version strings,
and date references (`Q1 2026`) — making NER and BERTopic operate on degraded
text with meaningfully lower accuracy.

Fixed by switching to a regex that preserves digits and the characters
`$`, `.`, `-`, `%`:

```python
# before
PUNCT_NUM_RE = re.compile(r"[^a-z\s]")

# after
PUNCT_RE = re.compile(r"[^a-z0-9\s\$\.\-\%]")
```

The variable was also renamed from `PUNCT_NUM_RE` to `PUNCT_RE` and the
call-site in `clean_text()` updated to match.

---

**Bug 2 — Hardcoded `"python"` in subprocess spaCy model download**

When `en_core_web_sm` is missing, the script attempted to download it by
calling `subprocess.run(["python", ...])`. In virtual-environment and conda
setups the `python` alias is often absent or points to the wrong interpreter,
causing the download to fail silently while the subsequent `spacy.load()` call
then raises an `OSError`.

Fixed by using `sys.executable`, which always resolves to the exact Python
binary that is currently running the script:

```python
# before
subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=False)

# after
subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=False)
```

---

#### `data_engineering/rss_fetcher.py`

**Bug — Wrong module name in module docstring**

The docstring stated *"Reads RSS_FEEDS from tag_discovery.py"* but the file
actually imports `from sources import RSS_FEEDS` (line 16). This was a
misleading documentation error — not a runtime failure — but it caused
confusion when tracing which module owns the feed list.

Fixed by correcting the docstring:

```python
# before
Reads RSS_FEEDS from tag_discovery.py, fetches only entries newer than the …

# after
Reads RSS_FEEDS from sources.py, fetches only entries newer than the …
```

---

### Files added

#### `sources.json`

A 54-source pipeline source registry extracted from the capstone project
specification. Covers all 7 Microsoft geographic regions and is structured for
direct use by the ingestion and tagging pipeline.

Each source entry includes:

| Field | Description |
|---|---|
| `id` | Unique snake_case identifier used as the watermark key in `fetch_state.json` |
| `name` | Human-readable source name |
| `homepage` | Source homepage URL |
| `rss_url` | RSS feed URL (entries marked `[VERIFY]` need manual confirmation) |
| `category` | Broad topic area (`AI & Technology`, `Health AI`, `Regulation & Policy`, etc.) |
| `source_type` | `primary` (official/company) · `secondary` (journalism) · `aggregator` |
| `region` | One of the 7 Microsoft geographic regions |
| `region_tags` | Array of region-specific tags |
| `content_quality` | `full` or `excerpts` (affects downstream summarisation strategy) |
| `scrape_tier` | `breaking` (60 min) · `standard` (360 min) · `daily` (1440 min) |
| `scrape_interval_min` | Polling interval in minutes |
| `default_topic_tags` | Pre-assigned topic tags |
| `default_business_tags` | Pre-assigned business-function tags |
| `default_regulation_tags` | Pre-assigned regulation/policy tags |
| `notes` | Source-specific caveats or integration notes |

The file also embeds the full tag taxonomy under `metadata.tags_taxonomy`
covering six dimensions: `topic`, `business`, `regulation_policy`, `regional`,
`role`, and `seniority`.

Sources flagged `[VERIFY]` in `notes` have RSS URLs that could not be
confirmed at time of writing and should be tested before enabling in the
pipeline: `eu_commission_press`, `anthropic_blog`, `wamda`.
