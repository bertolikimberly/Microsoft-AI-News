"""
sources.py — canonical RSS feed list for the data_engineering pipeline.
Import RSS_FEEDS from here; do not redefine elsewhere.
"""

RSS_FEEDS = [
    {"id": "mit_tech_review",      "url": "https://www.technologyreview.com/feed/",              "category": "tech"},
    {"id": "techcrunch",           "url": "https://techcrunch.com/feed/",                        "category": "tech"},
    {"id": "wired",                "url": "https://wired.com/feed/rss",                          "category": "tech"},
    {"id": "venturebeat",          "url": "https://venturebeat.com/feed/",                       "category": "tech"},
    {"id": "the_verge",            "url": "https://www.theverge.com/rss/index.xml",              "category": "tech"},
    {"id": "ars_technica_policy",  "url": "https://arstechnica.com/tech-policy/feed/",           "category": "regulation"},
    {"id": "tech_policy_press",    "url": "https://techpolicy.press/feed/",                      "category": "regulation"},
    {"id": "euractiv",             "url": "https://euractiv.com/feed",                           "category": "eu_policy"},
    {"id": "politico_eu",          "url": "https://politico.eu/feed",                            "category": "politics"},
    {"id": "eu_parliament",        "url": "https://europarl.europa.eu/rss/doc/top-20-rss.xml",  "category": "government"},
    {"id": "edpb",                 "url": "https://edpb.europa.eu/news/rss_en",                  "category": "government"},
    {"id": "bloomberg_tech",       "url": "https://feeds.bloomberg.com/technology/news.rss",     "category": "finance"},
    {"id": "economist",            "url": "https://economist.com/latest/rss.xml",                "category": "finance"},
    {"id": "sifted",               "url": "https://sifted.eu/feed",                              "category": "finance"},
    {"id": "politico_us",          "url": "https://rss.politico.com/politics-news.xml",          "category": "politics"},
    {"id": "the_local_de",         "url": "https://feeds.thelocal.com/rss/de",                   "category": "regional"},
    {"id": "the_local_fr",         "url": "https://feeds.thelocal.com/rss/fr",                   "category": "regional"},
    {"id": "the_local_es",         "url": "https://feeds.thelocal.com/rss/es",                   "category": "regional"},
    {"id": "the_local_it",         "url": "https://feeds.thelocal.com/rss/it",                   "category": "regional"},
    {"id": "the_local_se",         "url": "https://feeds.thelocal.com/rss/se",                   "category": "regional"},
    {"id": "the_local_dk",         "url": "https://feeds.thelocal.com/rss/dk",                   "category": "regional"},
    {"id": "the_local_no",         "url": "https://feeds.thelocal.com/rss/no",                   "category": "regional"},
    {"id": "the_local_at",         "url": "https://feeds.thelocal.com/rss/at",                   "category": "regional"},
    {"id": "the_local_ch",         "url": "https://feeds.thelocal.com/rss/ch",                   "category": "regional"},
    {"id": "the_recursive",        "url": "https://therecursive.com/feed",                       "category": "regional"},
]
