"""
tag_discovery.py — RSS tag discovery pipeline
Ingests articles, runs NER + BERTopic, writes tag_discovery_report.md
"""

import os
import re
import sys
import string
from datetime import datetime
from collections import Counter, defaultdict

# ── dependency check ────────────────────────────────────────────────────────
REQUIRED = [
    "feedparser", "bs4", "nltk", "spacy", "bertopic",
    "sentence_transformers", "pandas",
]
missing = []
for pkg in REQUIRED:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)
if missing:
    print(
        "Missing dependencies. Install with:\n"
        f"  pip install {' '.join(missing)}\n"
        "Then also run:\n"
        "  python -m spacy download en_core_web_sm\n"
        "  python -m nltk.downloader stopwords"
    )
    sys.exit(1)

import feedparser
import nltk
import spacy
import pandas as pd
from bs4 import BeautifulSoup
from bertopic import BERTopic
from nltk.corpus import stopwords
from sklearn.cluster import KMeans

# Optional — used only for LLM topic naming; falls back gracefully if absent.
try:
    import anthropic as _anthropic_module
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _anthropic_module = None
    _ANTHROPIC_AVAILABLE = False

from sources import RSS_FEEDS

# ── STEP 1: ingest ───────────────────────────────────────────────────────────

def ingest_feeds(feeds):
    articles = []
    for feed_meta in feeds:
        src_id = feed_meta["id"]
        url = feed_meta["url"]
        category = feed_meta["category"]
        try:
            parsed = feedparser.parse(url)
            # feedparser doesn't raise on network errors — check bozo
            if parsed.get("bozo") and not parsed.entries:
                exc = parsed.get("bozo_exception", "unknown error")
                print(f"[{src_id}] feed error: {exc} — skipping")
                continue
            entries = parsed.entries
            count = 0
            for entry in entries:
                title = entry.get("title", "")
                summary = (
                    entry.get("summary")
                    or entry.get("content", [{}])[0].get("value", "")
                    or ""
                )
                link = entry.get("link", "")
                published = entry.get("published", entry.get("updated", ""))
                text = f"{title} {summary}".strip()
                if not text:
                    continue
                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published": published,
                    "source_id": src_id,
                    "category": category,
                    "text": text,
                })
                count += 1
            print(f"[{src_id}] fetched {count} articles")
        except Exception as exc:
            print(f"[{src_id}] failed to fetch: {exc} — skipping")
    return articles


# ── STEP 2: clean text ────────────────────────────────────────────────────────

def _ensure_stopwords():
    try:
        stopwords.words("english")
    except LookupError:
        nltk.download("stopwords", quiet=True)

def build_stopword_set():
    _ensure_stopwords()
    return set(stopwords.words("english"))

URL_RE = re.compile(r"https?://\S+|www\.\S+")
PUNCT_NUM_RE = re.compile(r"[^a-z\s]")
MULTI_SPACE_RE = re.compile(r"\s+")

def clean_text(raw: str, stop_words: set) -> str:
    # strip HTML
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ")
    text = text.lower()
    text = URL_RE.sub(" ", text)
    text = PUNCT_NUM_RE.sub(" ", text)
    text = MULTI_SPACE_RE.sub(" ", text).strip()
    tokens = [w for w in text.split() if w not in stop_words and len(w) > 2]
    return " ".join(tokens)


# ── STEP 3: NER ──────────────────────────────────────────────────────────────

# Matches residual HTML attribute fragments that slip through BeautifulSoup
# when markup is malformed — e.g. href="https://therecursive.com" appearing
# verbatim in the text and being tagged as an ORG entity by spaCy.
_HTML_ATTR_RE = re.compile(r'\w[\w-]*\s*=\s*(?:"[^"]*"|\'[^\']*\')', re.IGNORECASE)
# URL pattern for NER pre-cleaning (separate from URL_RE — this one preserves
# case because NER needs original casing to work correctly).
_URL_NER_RE = re.compile(r"https?://\S+|www\.\S+")

# Entities to drop under any spaCy label — web UI boilerplate and navigation
# text that appears verbatim in RSS summaries or leaks from HTML fragments.
_NER_BLOCKLIST_ALL: frozenset = frozenset({
    "download", "subscribe", "click", "read", "share", "follow",
    "newsletter", "continue", "cookie", "cookies", "sign up", "log in",
    "login", "sign in", "more", "next", "previous", "home", "search",
    "menu", "close", "open", "back", "comments", "reply", "like",
    "save", "print", "learn more", "see more", "view more",
    "load more", "read more", "show more",
})

# AI product / browser names that spaCy routinely misclassifies as PERSON.
# Blocked only from the PERSON label — they can still surface as ORG or PRODUCT.
_NER_BLOCKLIST_PERSON: frozenset = frozenset({
    "claude", "gpt", "gpt-4", "gpt-4o", "copilot", "gemini",
    "chatgpt", "dall-e", "dall·e", "midjourney", "llama", "mistral",
    "sora", "bard", "chrome", "firefox", "safari", "edge", "opera",
})


def _clean_for_ner(raw: str) -> str:
    """
    Prepare text for spaCy NER.

    Strips HTML tags, URLs, and attribute fragments while preserving case
    and punctuation — both are required for accurate entity recognition.
    BeautifulSoup handles well-formed markup; the extra regex pass removes
    attribute strings (href="...", src="...") that survive in malformed HTML.
    """
    text = BeautifulSoup(raw, "html.parser").get_text(separator=" ")
    text = _URL_NER_RE.sub(" ", text)
    text = _HTML_ATTR_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


# Short abbreviations that are meaningful signals and must survive the < 3
# character length filter (geopolitical bodies, financial regulators, alliances).
_NER_SHORT_ALLOWLIST: frozenset = frozenset({
    "eu", "us", "uk", "un", "nato", "who", "imf", "sec", "uae", "gcc",
})


def _is_blocked_entity(name: str, label: str) -> bool:
    """
    Return True if this entity should be filtered before counting.

    Checks in order:
      1. Fewer than 3 characters — too short to be meaningful,
         unless the name is in _NER_SHORT_ALLOWLIST
      2. Name is in the all-labels blocklist (web UI / navigation noise)
      3. Label is PERSON and name is a known AI product or browser name
    """
    lower = name.lower()
    if len(name) < 3 and lower not in _NER_SHORT_ALLOWLIST:
        return True
    if lower in _NER_BLOCKLIST_ALL:
        return True
    if label == "PERSON" and lower in _NER_BLOCKLIST_PERSON:
        return True
    return False


ENTITY_TYPES = {"ORG", "PERSON", "GPE", "LAW", "PRODUCT", "EVENT"}

def run_ner(articles, nlp):
    print("[NER] running named entity recognition ...")
    entity_counts = {etype: Counter() for etype in ENTITY_TYPES}
    # also track per-entity which source categories it appears in
    entity_sources = {etype: defaultdict(Counter) for etype in ENTITY_TYPES}

    for art in articles:
        # Strip HTML/URLs/attributes before NER so spaCy never sees raw markup.
        # clean_text() (used for BERTopic) also strips HTML but lowercases first,
        # which destroys the casing spaCy needs for entity recognition.
        ner_text = _clean_for_ner(art["text"])[:100_000]
        doc = nlp(ner_text)
        entities = []
        for ent in doc.ents:
            if ent.label_ not in ENTITY_TYPES:
                continue
            name = ent.text.strip()
            if _is_blocked_entity(name, ent.label_):
                continue
            entities.append({"text": name, "label": ent.label_})
            entity_counts[ent.label_][name] += 1
            entity_sources[ent.label_][name][art["category"]] += 1
        art["entities"] = entities

    print("[NER] done")
    return entity_counts, entity_sources


def top_entities_with_source(counter, source_map, n):
    results = []
    for name, count in counter.most_common(n):
        top_src = source_map[name].most_common(1)[0][0]
        results.append({"entity": name, "count": count, "top_source": top_src})
    return results


# ── STEP 4: BERTopic ─────────────────────────────────────────────────────────

def _name_topic_with_llm(keywords: list) -> str:
    """
    Ask claude-haiku-4-5 to return a clean 2-3 word label for a BERTopic cluster.
    Falls back to joining the top-2 keywords (title-cased) on any error or if
    the anthropic package / ANTHROPIC_API_KEY is not available.
    """
    fallback = " ".join(keywords[:2]).title()

    if not _ANTHROPIC_AVAILABLE:
        return fallback
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return fallback

    kw_str = ", ".join(keywords[:5])
    try:
        client = _anthropic_module.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=16,
            messages=[{
                "role": "user",
                "content": (
                    "You label topic clusters for a Microsoft tech intelligence newsletter.\n"
                    f"BERTopic keywords: {kw_str}\n"
                    "Return a clean 2-3 word label for a Microsoft tech audience. "
                    "Examples: 'AI Policy', 'Azure Infrastructure', 'European Regulation', "
                    "'Cybersecurity Threats', 'Cloud Computing'.\n"
                    "Reply with ONLY the label — no explanation, no trailing punctuation."
                ),
            }],
        )
        label = message.content[0].text.strip().strip(".")
        if label and len(label.split()) <= 5:
            return label
        return fallback
    except Exception as exc:
        print(f"[BERTopic] LLM naming failed ({exc!r}) — using keyword fallback")
        return fallback


def run_bertopic(articles):
    texts = [a["cleaned_text"] for a in articles]
    print("[BERTopic] fitting model... (this may take 2–3 minutes)")
    topic_model = BERTopic(
        hdbscan_model=KMeans(n_clusters=15, random_state=42),
        calculate_probabilities=False,
        verbose=True
    )
    topics, _ = topic_model.fit_transform(texts)

    # attach topic assignment to each article
    for i, art in enumerate(articles):
        art["topic_id"] = topics[i]

    # build topic info
    topic_info = topic_model.get_topic_info()
    # topic_info columns: Topic, Count, Name, Representation (list of (word, score))
    # filter out -1 (outlier topic)
    topic_info = topic_info[topic_info["Topic"] != -1]

    topic_results = []
    for _, row in topic_info.head(15).iterrows():
        tid = int(row["Topic"])
        count = int(row["Count"])
        # get top 10 keywords
        topic_words = topic_model.get_topic(tid)
        if not topic_words:
            keywords = []
        else:
            keywords = [w for w, _ in topic_words[:10]]

        # which categories appear in this topic
        cat_counter = Counter(
            a["category"] for a in articles if a["topic_id"] == tid
        )
        total = sum(cat_counter.values()) or 1
        dominant = ", ".join(
            f"{cat}({round(c/total*100)}%)"
            for cat, c in cat_counter.most_common()
        )

        label = _name_topic_with_llm(keywords)
        topic_results.append({
            "topic_id": tid,
            "label": label,
            "keywords": keywords,
            "article_count": count,
            "dominant_categories": dominant,
            "cat_counter": cat_counter,
        })

    print(f"[BERTopic] found {len(topic_results)} topics (excl. outliers)")
    return topic_results


# ── STEP 5: cross-source overlap ─────────────────────────────────────────────

def build_cross_source_overlap(topic_results, top_n=10):
    rows = []
    for tr in topic_results[:top_n]:
        cat_counter = tr["cat_counter"]
        total = sum(cat_counter.values()) or 1
        breakdown = " + ".join(
            f"{cat}({round(c/total*100)}%)"
            for cat, c in cat_counter.most_common()
        )
        rows.append({
            "topic_id": tr["topic_id"],
            "keywords_preview": ", ".join(tr["keywords"][:5]),
            "breakdown": breakdown,
            "num_categories": len(cat_counter),
        })
    return rows


# ── STEP 6: report ────────────────────────────────────────────────────────────

def _md_table(headers, rows):
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def generate_report(articles, entity_counts, entity_sources, topic_results, overlap_rows):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source_count = len({a["source_id"] for a in articles})
    n_articles = len(articles)

    lines = []
    lines.append("# Tag Discovery Report")
    lines.append(f"\nGenerated: {now}")
    lines.append(f"Articles analysed: {n_articles}")
    lines.append(f"Sources: {source_count}")

    # ── named entities ────────────────────────────────────────────────────────
    lines.append("\n## Top Named Entities")

    lines.append("\n### Organisations (Top 30)")
    orgs = top_entities_with_source(entity_counts["ORG"], entity_sources["ORG"], 30)
    lines.append(_md_table(
        ["Entity", "Count", "Most frequent in"],
        [[r["entity"], r["count"], r["top_source"]] for r in orgs],
    ))

    lines.append("\n### People (Top 20)")
    people = top_entities_with_source(entity_counts["PERSON"], entity_sources["PERSON"], 20)
    lines.append(_md_table(
        ["Entity", "Count", "Most frequent in"],
        [[r["entity"], r["count"], r["top_source"]] for r in people],
    ))

    lines.append("\n### Locations (Top 20)")
    locs = top_entities_with_source(entity_counts["GPE"], entity_sources["GPE"], 20)
    lines.append(_md_table(
        ["Entity", "Count", "Most frequent in"],
        [[r["entity"], r["count"], r["top_source"]] for r in locs],
    ))

    lines.append("\n### Regulations / Laws (Top 15)")
    laws = top_entities_with_source(entity_counts["LAW"], entity_sources["LAW"], 15)
    if laws:
        lines.append(_md_table(
            ["Entity", "Count", "Most frequent in"],
            [[r["entity"], r["count"], r["top_source"]] for r in laws],
        ))
    else:
        lines.append("_No LAW entities detected in this corpus._")

    # ── topic clusters ────────────────────────────────────────────────────────
    lines.append("\n## Discovered Topic Clusters (BERTopic)")
    lines.append(_md_table(
        ["Topic ID", "Label", "Top Keywords", "Article Count", "Dominant Categories"],
        [
            [
                tr["topic_id"],
                tr["label"],
                ", ".join(tr["keywords"]),
                tr["article_count"],
                tr["dominant_categories"],
            ]
            for tr in topic_results
        ],
    ))

    # ── cross-source overlap ──────────────────────────────────────────────────
    lines.append("\n## Cross-Source Overlap")
    lines.append(
        "How the top 10 topics distribute across source categories "
        "(shows which tags will be useful across multiple pipelines):\n"
    )
    for row in overlap_rows:
        kw = row["keywords_preview"]
        lines.append(f"**Topic {row['topic_id']}** ({kw}): {row['breakdown']}")

    # ── suggested tag candidates ──────────────────────────────────────────────
    lines.append("\n## Suggested Tag Candidates")

    # Qualify: > 20 articles AND present in >= 2 source categories
    qualified = [
        tr for tr in topic_results
        if tr["article_count"] > 20 and len(tr["cat_counter"]) >= 2
    ]
    # Derive a short candidate name from top 2 keywords
    candidates = []
    for tr in qualified:
        candidates.append((tr["label"], tr["article_count"], len(tr["cat_counter"])))

    # Deduplicate by name, keep highest article count
    seen = {}
    for name, cnt, cats in candidates:
        if name not in seen or cnt > seen[name][0]:
            seen[name] = (cnt, cats)
    # Sort by article count desc, take top 12
    sorted_candidates = sorted(seen.items(), key=lambda x: -x[1][0])[:12]

    n_candidates = len(sorted_candidates)
    lines.append(
        f"Based on the above, the following {n_candidates} themes appear consistently "
        "across sources and could form the tag taxonomy:\n"
    )
    for i, (name, (cnt, cats)) in enumerate(sorted_candidates, 1):
        lines.append(f"{i}. {name}  _(~{cnt} articles, {cats} source categories)_")

    if n_candidates < 8:
        lines.append(
            "\n_Note: fewer than 8 candidates qualified (>20 articles, ≥2 categories). "
            "Consider lowering thresholds or fetching more articles._"
        )

    lines.append("\n## Next Step")
    lines.append(
        "These candidates must be reviewed and approved by the full team "
        "before being implemented as tags in the pipeline."
    )

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    # Step 1 — ingest
    print("=" * 60)
    print("STEP 1 — ingesting RSS feeds")
    print("=" * 60)
    articles = ingest_feeds(RSS_FEEDS)
    print(f"\nTotal articles collected: {len(articles)}")

    if not articles:
        print("No articles collected — cannot continue.")
        sys.exit(1)

    # Step 2 — clean
    print("\n" + "=" * 60)
    print("STEP 2 — cleaning text")
    print("=" * 60)
    stop_words = build_stopword_set()
    for art in articles:
        art["cleaned_text"] = clean_text(art["text"], stop_words)
    # Drop articles whose cleaned text is too short to be useful
    articles = [a for a in articles if len(a["cleaned_text"].split()) >= 5]
    print(f"Articles after cleaning: {len(articles)}")

    # Step 3 — NER
    print("\n" + "=" * 60)
    print("STEP 3 — named entity recognition (spaCy)")
    print("=" * 60)
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        import subprocess
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=False)
        nlp = spacy.load("en_core_web_sm")
    entity_counts, entity_sources = run_ner(articles, nlp)

    # Step 4 — BERTopic
    print("\n" + "=" * 60)
    print("STEP 4 — topic discovery (BERTopic)")
    print("=" * 60)
    topic_results = run_bertopic(articles)

    # Step 5 — cross-source overlap
    print("\n" + "=" * 60)
    print("STEP 5 — cross-source overlap")
    print("=" * 60)
    overlap_rows = build_cross_source_overlap(topic_results, top_n=10)
    print(f"Built overlap table for {len(overlap_rows)} topics")

    # Step 6 — report
    print("\n" + "=" * 60)
    print("STEP 6 — generating report")
    print("=" * 60)
    report = generate_report(articles, entity_counts, entity_sources, topic_results, overlap_rows)
    out_path = "tag_discovery_report.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to: {out_path}")
    print("Done.")


def _run_ner_sample_test():
    """
    Sanity-check the NER pre-cleaning and entity filter against inputs that
    produced garbage in the previous tag_discovery_report.md.
    Run with: python tag_discovery.py --test-ner
    """
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        print("[test-ner] ERROR: en_core_web_sm not installed.")
        print("  Run: python -m spacy download en_core_web_sm")
        return

    SAMPLES = [
        # Raw HTML with href attribute — was producing the ORG entity
        # 'href="https://therecursive.com' in the previous run.
        (
            "regional",
            'CEE Tech Roundup <a href="https://therecursive.com/cee-roundup">Read more</a>. '
            "OpenAI and Google announced new models. Download the app now. "
            "Claude scored highest on the benchmark.",
        ),
        # AI assistant names misclassified as PERSON; web UI verbs.
        (
            "tech",
            "Microsoft Copilot and Claude from Anthropic both support GPT-4o. "
            "Sam Altman and Satya Nadella spoke at the summit. "
            "Subscribe to follow our newsletter. Share this article.",
        ),
        # Short entities (EU, US) and navigation words.
        (
            "regulation",
            "EU AI Act passed. US and UK lawmakers met in DC. "
            "Click here to read the full text. The GDPR applies across Europe.",
        ),
    ]

    print("\n" + "=" * 60)
    print("NER SAMPLE TEST")
    print("=" * 60)
    for category, raw_text in SAMPLES:
        cleaned = _clean_for_ner(raw_text)
        print(f"\nInput:   {raw_text}")
        print(f"Cleaned: {cleaned}")
        doc = nlp(cleaned)
        kept, blocked = [], []
        for ent in doc.ents:
            if ent.label_ not in ENTITY_TYPES:
                continue
            name = ent.text.strip()
            if _is_blocked_entity(name, ent.label_):
                blocked.append(f"{name!r} [{ent.label_}]")
            else:
                kept.append(f"{name!r} [{ent.label_}]")
        print(f"  KEPT:    {kept if kept else ['(none)']}")
        print(f"  BLOCKED: {blocked if blocked else ['(none)']}")
    print()


def _run_topic_naming_test():
    """
    Sanity-check _name_topic_with_llm against sample BERTopic keyword sets.
    Run with: python tag_discovery.py --test-topics
    """
    SAMPLE_CLUSTERS = [
        ["china", "trade", "tariff", "import", "export"],
        ["regulation", "eu", "ai", "act", "compliance"],
        ["azure", "cloud", "microsoft", "infrastructure", "service"],
        ["security", "breach", "data", "attack", "vulnerability"],
        ["musk", "elon", "twitter", "tesla", "spacex"],
        ["gpu", "nvidia", "chip", "compute", "semiconductor"],
        ["copilot", "openai", "model", "language", "generative"],
    ]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    mode = "LLM (claude-haiku-4-5)" if (_ANTHROPIC_AVAILABLE and api_key) else "keyword fallback"

    print("\n" + "=" * 60)
    print(f"TOPIC NAMING TEST  [{mode}]")
    print("=" * 60)
    for kws in SAMPLE_CLUSTERS:
        fallback = " ".join(kws[:2]).title()
        label = _name_topic_with_llm(kws)
        flag = "" if label != fallback else "  [fallback]"
        print(f"  keywords : {', '.join(kws)}")
        print(f"  label    : {label}{flag}")
        print()


if __name__ == "__main__":
    if "--test-ner" in sys.argv:
        _run_ner_sample_test()
    elif "--test-topics" in sys.argv:
        _run_topic_naming_test()
    else:
        main()
