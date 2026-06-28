"""
Render a Digest ORM row + its DigestItems into HTML for email delivery.

Design mirrors the MAI News web app exactly:
  Palette  — Moss & Ember (the app default)
    bg      #f4ede1   warm linen
    ink     #1f1d18   near-black
    muted   #6b6557   warm grey
    accent  #5a6b3d   forest green
    blobs   #5a6b3d · #c66a3a · #d9a05b · #3a4a3c
    card    rgba(255,253,247,0.78) → #fffdf7 (solid for email)
  Font     — Inter Tight → system-ui fallback (web-safe)
  Brand    — "MAI news" with italic bold "news" (matches .wm-mai / .wm-news)
  Cards    — warm off-white panels, 1px border rgba(0,0,0,0.07), 12px radius
  Source   — uppercase, accent colour, small tracking (matches .dash2-source)
  Title    — 600 weight, ink colour, -0.01em tracking (matches .dash2-card-title)
  CTA      — accent-coloured "Read article →" (matches app link style)
  Footer   — ink bg with muted text, matching the dark sidebar feel

All CSS in a <style> block (Gmail, Apple Mail, Outlook 2019+).
Critical wrapper styles are also inline for Outlook 2016.
"""
from __future__ import annotations

import html as _html

from app.models import Article, Digest, DigestItem

# ── App colours (Moss & Ember palette, exact hex) ──────────────────────────
_BG      = "#f4ede1"   # warm linen — backdrop base
_INK     = "#1f1d18"   # near-black — primary text
_MUTED   = "#6b6557"   # warm grey  — secondary text, timestamps
_ACCENT  = "#5a6b3d"   # forest green — source labels, links, CTAs
_BLOB1   = "#5a6b3d"   # forest green
_BLOB2   = "#c66a3a"   # burnt sienna
_BLOB3   = "#d9a05b"   # golden amber
_BLOB4   = "#3a4a3c"   # dark moss
_CARD    = "#fffdf7"   # warm off-white — card background
_BORDER  = "rgba(0,0,0,0.07)"
_FOOTER_BG = "#1f1d18"  # ink colour → feels like the dark sidebar


def render_html(digest: Digest, items_with_articles: list[tuple[DigestItem, Article]]) -> str:
    when_long  = digest.generated_at.strftime("%A, %d %B %Y")
    when_short = digest.generated_at.strftime("%d %b %Y").upper()
    n = len(items_with_articles)
    count_label = f"{n} {'story' if n == 1 else 'stories'}"

    article_blocks = "\n".join(
        _article_block(i + 1, item, article)
        for i, (item, article) in enumerate(items_with_articles)
    )
    if not article_blocks:
        article_blocks = _empty_block()

    return _TEMPLATE.format(
        when_long=when_long,
        when_short=when_short,
        count_label=count_label,
        article_blocks=article_blocks,
        # colours (double-braced in CSS, single here for .format())
        BG=_BG, INK=_INK, MUTED=_MUTED, ACCENT=_ACCENT,
        CARD=_CARD, FOOTER_BG=_FOOTER_BG,
        BLOB1=_BLOB1, BLOB2=_BLOB2, BLOB3=_BLOB3,
    )


def render_subject(digest: Digest, item_count: int) -> str:
    when = digest.generated_at.strftime("%a %d %b")
    if item_count == 0:
        return f"MAI News | Your digest — {when}"
    return f"MAI News | {item_count} stor{'y' if item_count == 1 else 'ies'} — {when}"


# ── Per-article HTML block ──────────────────────────────────────────────────

def _article_block(rank: int, item: DigestItem, article: Article) -> str:
    title   = _esc(article.title or "(untitled)")
    url     = _esc(article.url or "#")
    source  = _esc(article.source.name if article.source else "Unknown source").upper()
    summary = _esc(item.summary or article.extract or "")
    date    = article.published_at.strftime("%-d %b %Y") if article.published_at else ""
    date_html = f' <span style="color:{_MUTED}; font-size:11px;">· {date}</span>' if date else ""

    return f"""
    <tr>
      <td class="card">
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
          <tr>
            <!-- Rank badge -->
            <td class="rank-cell" valign="top">
              <div class="rank">{rank}</div>
            </td>
            <!-- Content -->
            <td class="content-cell" valign="top">
              <p class="source-line">
                <span style="color:{_ACCENT}; font-size:10.5px; font-weight:700; letter-spacing:0.14em; text-transform:uppercase;">{source}</span>{date_html}
              </p>
              <h2 class="article-title">
                <a href="{url}" style="color:{_INK}; text-decoration:none;">{title}</a>
              </h2>
              <p class="summary">{summary}</p>
              <a href="{url}" style="color:{_ACCENT}; font-size:12.5px; font-weight:600; text-decoration:none; letter-spacing:0.02em;">Read article →</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr><td style="height:10px; background:{_BG};"></td></tr>"""


def _empty_block() -> str:
    return f"""
    <tr>
      <td style="background:{_CARD}; border:1px solid {_BORDER}; border-radius:12px; padding:32px 40px; text-align:center; color:{_MUTED}; font-size:15px; font-style:italic;">
        No new stories this cycle — check back tomorrow.
      </td>
    </tr>"""


def _esc(text: str) -> str:
    return _html.escape(text)


# ── Full email template ─────────────────────────────────────────────────────
# Uses .format() — CSS braces are doubled {{ }}, template vars are single {{var}}

_TEMPLATE = """\
<!doctype html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>MAI News — {{when_long}}</title>
  <!--[if mso]>
  <noscript>
    <xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml>
  </noscript>
  <![endif]-->
  <style>
    /* ── Reset ─────────────────────────────────────── */
    body, table, td, a {{ margin:0; padding:0; border:0; }}
    body {{
      background:{BG};
      font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", "Inter Tight",
                  Helvetica, Arial, sans-serif;
      -webkit-font-smoothing:antialiased;
      color:{INK};
    }}
    img {{ border:0; line-height:100%; outline:none; display:block; }}
    table {{ border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt; }}
    a {{ color:{ACCENT}; }}

    /* ── Shell ─────────────────────────────────────── */
    .shell {{ width:100%; background:{BG}; padding:40px 16px; }}
    .container {{ max-width:600px; width:100%; margin:0 auto; }}

    /* ── Header ────────────────────────────────────── */
    .header {{
      background:{BG};
      border-top:3px solid {BLOB2};
      border-radius:14px 14px 0 0;
      padding:36px 40px 28px;
      text-align:center;
      border:1px solid {_BORDER};
      border-bottom:none;
    }}
    .wordmark {{
      font-size:32px; font-weight:400; color:{INK};
      letter-spacing:0.5px; line-height:1; margin-bottom:6px;
    }}
    .wordmark-news {{
      font-style:italic; font-weight:600; letter-spacing:-0.01em;
      font-size:0.9em; display:inline-block; transform:translateY(-0.05em);
      margin-left:4px;
    }}
    .tagline {{
      font-size:10.5px; letter-spacing:0.18em; text-transform:uppercase;
      color:{MUTED}; margin-bottom:20px;
    }}
    .header-rule {{
      width:40px; height:2px; margin:0 auto 20px;
      background:linear-gradient(90deg, {BLOB1}, {BLOB2}, {BLOB3});
      border-radius:2px;
    }}
    .header-date-pill {{
      display:inline-block;
      border:1px solid rgba(0,0,0,0.12);
      border-radius:999px;
      padding:5px 18px;
      font-size:11.5px;
      color:{MUTED};
      letter-spacing:0.06em;
      background:{CARD};
    }}

    /* ── Datebar ───────────────────────────────────── */
    .datebar {{
      background:{CARD};
      border-left:1px solid {_BORDER};
      border-right:1px solid {_BORDER};
      padding:14px 40px;
    }}
    .datebar-inner {{ display:table; width:100%; }}
    .datebar-left {{
      display:table-cell; vertical-align:middle;
      font-size:11px; color:{MUTED}; letter-spacing:0.12em; text-transform:uppercase;
    }}
    .datebar-right {{
      display:table-cell; vertical-align:middle; text-align:right;
      font-size:11px; color:{ACCENT}; letter-spacing:0.1em;
      text-transform:uppercase; font-weight:700;
    }}
    .divider {{ height:1px; background:rgba(0,0,0,0.07); margin:0; }}

    /* ── Cards wrapper ─────────────────────────────── */
    .cards-wrap {{
      background:{BG};
      padding:10px 10px 2px;
      border-left:1px solid {_BORDER};
      border-right:1px solid {_BORDER};
    }}

    /* ── Article card ──────────────────────────────── */
    .card {{
      background:{CARD};
      border:1px solid rgba(0,0,0,0.07);
      border-radius:12px;
      padding:22px 24px;
    }}
    .rank-cell {{ width:34px; padding-right:14px; }}
    .rank {{
      width:28px; height:28px; border-radius:50%;
      background:{ACCENT};
      color:{CARD}; font-size:12px; font-weight:700;
      text-align:center; line-height:28px;
    }}
    .content-cell {{ vertical-align:top; }}
    .source-line {{ margin:0 0 6px; }}
    .article-title {{
      margin:0 0 10px;
      font-size:16px; font-weight:600;
      line-height:1.35; color:{INK};
      letter-spacing:-0.01em;
    }}
    .summary {{
      margin:0 0 14px;
      font-size:13.5px; line-height:1.65;
      color:{MUTED};
    }}

    /* ── Footer ────────────────────────────────────── */
    .footer-wrap {{
      background:{BG};
      border:1px solid {_BORDER};
      border-top:none;
      border-radius:0 0 14px 14px;
      padding:2px 10px 10px;
    }}
    .footer {{
      background:{FOOTER_BG};
      border-radius:0 0 8px 8px;
      padding:28px 40px;
      text-align:center;
    }}
    .footer-wordmark {{
      font-size:16px; font-weight:400;
      color:rgba(255,253,247,0.45);
      letter-spacing:0.5px; margin-bottom:12px;
    }}
    .footer-wordmark-news {{
      font-style:italic; font-weight:600;
      color:rgba(255,253,247,0.65);
    }}
    .footer-rule {{
      width:30px; height:1px; margin:0 auto 14px;
      background:rgba(255,253,247,0.12);
    }}
    .footer-text {{
      font-size:12px; color:rgba(255,253,247,0.35); line-height:1.7;
    }}
    .footer-link {{ color:rgba(255,253,247,0.55); text-decoration:none; }}
    .footer-sep {{ color:rgba(255,253,247,0.15); margin:0 8px; }}

    /* ── Responsive ────────────────────────────────── */
    @media only screen and (max-width:480px) {{
      .header {{ padding:28px 20px 22px; }}
      .datebar {{ padding:12px 20px; }}
      .card {{ padding:18px 16px; }}
      .footer {{ padding:24px 20px; }}
      .cards-wrap {{ padding:8px 8px 2px; }}
    }}
  </style>
</head>
<body>
<!--[if mso]><table width="100%" cellpadding="0" cellspacing="0" style="background:{BG};"><tr><td align="center" style="padding:40px 16px;"><table width="600" cellpadding="0" cellspacing="0"><![endif]-->

<table class="shell" width="100%" cellpadding="0" cellspacing="0" role="presentation">
  <tr>
    <td align="center">
      <table class="container" width="600" cellpadding="0" cellspacing="0" role="presentation">

        <!-- ══ HEADER ══ -->
        <tr>
          <td class="header" style="border-top:3px solid {BLOB2};">
            <div class="wordmark">MAI<span class="wordmark-news">news</span></div>
            <div class="tagline">Your tech intelligence digest</div>
            <div class="header-rule"></div>
            <div class="header-date-pill">{when_short}</div>
          </td>
        </tr>

        <!-- ══ DATEBAR ══ -->
        <tr>
          <td class="datebar">
            <div class="datebar-inner">
              <span class="datebar-left">{when_long}</span>
              <span class="datebar-right">{count_label}</span>
            </div>
          </td>
        </tr>
        <tr><td class="divider" style="height:1px; background:rgba(0,0,0,0.07);"></td></tr>

        <!-- ══ ARTICLES ══ -->
        <tr>
          <td>
            <table class="cards-wrap" width="100%" cellpadding="0" cellspacing="0" role="presentation">
              {article_blocks}
            </table>
          </td>
        </tr>

        <!-- ══ FOOTER ══ -->
        <tr>
          <td class="footer-wrap">
            <table class="footer" width="100%" cellpadding="0" cellspacing="0" role="presentation">
              <tr>
                <td>
                  <div class="footer-wordmark">MAI <span class="footer-wordmark-news">news</span></div>
                  <div class="footer-rule"></div>
                  <div class="footer-text">
                    You're receiving this because you subscribed to MAI News.<br>
                    <a href="#" class="footer-link">Manage preferences</a>
                    <span class="footer-sep">·</span>
                    <a href="#" class="footer-link">Unsubscribe</a>
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>

<!--[if mso]></table></td></tr></table><![endif]-->
</body>
</html>"""


# Replace placeholder in template (needed because _BORDER contains special chars)
_TEMPLATE = _TEMPLATE.replace("{_BORDER}", _BORDER)
