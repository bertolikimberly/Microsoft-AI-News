"""
sources.py — canonical RSS feed list for the data_engineering pipeline.
Import RSS_FEEDS from here; do not redefine elsewhere.

Fields
------
id          Unique snake_case key — used as the watermark key in fetch_state.json.
url         RSS feed URL.
category    Broad topic area used for NER source-attribution and BERTopic labels.
enabled     If False, rss_fetcher skips the source entirely but preserves its
            watermark so it can be re-enabled without re-ingesting old articles.
            Defaults to True when absent.
tier        Content-relevance tier for the personalization ranker:
              "primary"    — Microsoft-owned, official regulator, or top-tier
                             tech journalism (default when absent)
              "secondary"  — Broad-scope sources with mixed relevance; ranker
                             weights their articles lower

Disabled sources (enabled=False)
---------------------------------
- politico_us        General US politics feed; produced NYC mayoral-race and
                     state-budget articles — zero relevance to Microsoft/tech.
- the_local_*  (×9) Expat lifestyle news for EU countries; topics were public
                     holidays, Eurovision, health outbreaks — not tech content.
All are preserved here so watermarks survive and the sources can be re-enabled
by setting enabled=True without any other changes.

Secondary-tier sources (enabled, but ranked lower)
---------------------------------------------------
- euractiv      Broad EU-politics feed; relevant for AI Act / DMA / DSA but
                also publishes unrelated Brussels politics.
- politico_eu   Same tradeoff — EU competition and tech-policy coverage mixed
                with general EU political news.
"""

RSS_FEEDS = [
    # ── Tech journalism ───────────────────────────────────────────────────────
    {"id": "mit_tech_review",     "url": "https://www.technologyreview.com/feed/",                             "category": "tech"},
    {"id": "techcrunch",          "url": "https://techcrunch.com/feed/",                                       "category": "tech"},
    {"id": "wired",               "url": "https://wired.com/feed/rss",                                         "category": "tech"},
    {"id": "venturebeat",         "url": "https://venturebeat.com/feed/",                                      "category": "tech"},
    {"id": "the_verge",           "url": "https://www.theverge.com/rss/index.xml",                             "category": "tech"},
    {"id": "the_verge_ai",        "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",  "category": "tech"},

    # ── Microsoft primary sources ─────────────────────────────────────────────
    {"id": "ms_tech_community",   "url": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=MicrosoftLearnBlog", "category": "microsoft"},
    {"id": "azure_blog",          "url": "https://azure.microsoft.com/en-us/blog/feed/",                       "category": "microsoft"},
    {"id": "ms_research",         "url": "https://www.microsoft.com/en-us/research/blog/feed/",                "category": "microsoft"},

    # ── Regulation & policy ───────────────────────────────────────────────────
    {"id": "ars_technica_policy", "url": "https://arstechnica.com/tech-policy/feed/",                          "category": "regulation"},
    {"id": "tech_policy_press",   "url": "https://techpolicy.press/feed/",                                     "category": "regulation"},
    {"id": "euractiv",            "url": "https://euractiv.com/feed",                                          "category": "eu_policy",  "tier": "secondary"},
    {"id": "politico_eu",         "url": "https://politico.eu/feed",                                           "category": "politics",   "tier": "secondary"},
    {"id": "eu_parliament",       "url": "https://europarl.europa.eu/rss/doc/top-20-rss.xml",                  "category": "government"},
    {"id": "edpb",                "url": "https://edpb.europa.eu/news/rss_en",                                 "category": "government"},

    # ── Finance & business ────────────────────────────────────────────────────
    {"id": "bloomberg_tech",      "url": "https://feeds.bloomberg.com/technology/news.rss",                    "category": "finance"},
    {"id": "economist",           "url": "https://economist.com/latest/rss.xml",                               "category": "finance"},
    {"id": "sifted",              "url": "https://sifted.eu/feed",                                             "category": "finance"},

    # ── Regional tech ─────────────────────────────────────────────────────────
    {"id": "the_recursive",       "url": "https://therecursive.com/feed",                                      "category": "regional"},

    # ── Disabled: general US politics (off-topic for Microsoft/tech) ──────────
    {"id": "politico_us",         "url": "https://rss.politico.com/politics-news.xml",                         "category": "politics",   "enabled": False},

    # ── Disabled: expat lifestyle news (off-topic for Microsoft/tech) ─────────
    {"id": "the_local_de",        "url": "https://feeds.thelocal.com/rss/de",                                  "category": "regional",   "enabled": False},
    {"id": "the_local_fr",        "url": "https://feeds.thelocal.com/rss/fr",                                  "category": "regional",   "enabled": False},
    {"id": "the_local_es",        "url": "https://feeds.thelocal.com/rss/es",                                  "category": "regional",   "enabled": False},
    {"id": "the_local_it",        "url": "https://feeds.thelocal.com/rss/it",                                  "category": "regional",   "enabled": False},
    {"id": "the_local_se",        "url": "https://feeds.thelocal.com/rss/se",                                  "category": "regional",   "enabled": False},
    {"id": "the_local_dk",        "url": "https://feeds.thelocal.com/rss/dk",                                  "category": "regional",   "enabled": False},
    {"id": "the_local_no",        "url": "https://feeds.thelocal.com/rss/no",                                  "category": "regional",   "enabled": False},
    {"id": "the_local_at",        "url": "https://feeds.thelocal.com/rss/at",                                  "category": "regional",   "enabled": False},
    {"id": "the_local_ch",        "url": "https://feeds.thelocal.com/rss/ch",                                  "category": "regional",   "enabled": False},
]
