"""
Render a Digest ORM row + its DigestItems into HTML for email delivery.

Design language mirrors the MAI News web app:
  - Dark (#1a1a1a) outer shell
  - Warm off-white (#fffdf7) content panels
  - Amber → rose gradient header (echoes the animated blob backdrop)
  - Inter/system-font stack, tight tracking on labels
  - Article rank badges in warm amber
  - Clean card separation, source attribution, read-more links

All CSS is embedded in a <style> block in <head> (supported by Gmail,
Apple Mail, Outlook 2019+) plus critical inline styles on the outer
wrapper for Outlook 2016 and below.
"""
from __future__ import annotations

import html as _html

from app.models import Article, Digest, DigestItem


def render_html(digest: Digest, items_with_articles: list[tuple[DigestItem, Article]]) -> str:
    when_long = digest.generated_at.strftime("%A, %d %B %Y")
    when_short = digest.generated_at.strftime("%d %b %Y").upper()
    n = len(items_with_articles)
    count_label = f"{n}&nbsp;{'story' if n == 1 else 'stories'}"

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
    )


def render_subject(digest: Digest, item_count: int) -> str:
    when = digest.generated_at.strftime("%a %d %b")
    if item_count == 0:
        return f"MAI News | Your digest — {when}"
    return f"MAI News | {item_count} stor{'y' if item_count == 1 else 'ies'} — {when}"


# ── Helpers ────────────────────────────────────────────────────────────────

def _article_block(rank: int, item: DigestItem, article: Article) -> str:
    title   = _esc(article.title or "(untitled)")
    url     = _esc(article.url or "#")
    source  = _esc(article.source.name if article.source else "Unknown source")
    summary = _esc(item.summary or article.extract or "")
    date    = article.published_at.strftime("%-d %b %Y") if article.published_at else ""

    return f"""
        <tr>
          <td class="card">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td class="rank-cell">
                  <div class="rank">{rank}</div>
                </td>
                <td class="content-cell">
                  <div class="source-line">
                    <span class="source-name">{source}</span>
                    {"<span class='dot'>·</span><span class='date'>" + date + "</span>" if date else ""}
                  </div>
                  <h2 class="article-title">
                    <a href="{url}" class="article-link">{title}</a>
                  </h2>
                  <p class="summary">{summary}</p>
                  <a href="{url}" class="read-more">Read article →</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr><td class="card-gap"></td></tr>"""


def _empty_block() -> str:
    return """
        <tr>
          <td style="background:#fffdf7;border-radius:12px;padding:32px 40px;text-align:center;color:#999;font-size:15px;">
            No new stories this cycle — check back tomorrow.
          </td>
        </tr>"""


def _esc(text: str) -> str:
    return _html.escape(text)


# ── Template ───────────────────────────────────────────────────────────────

_TEMPLATE = """\
<!doctype html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>MAI News — {when_long}</title>
  <style>
    /* ── Reset ────────────────────────── */
    body, table, td, a {{ margin:0; padding:0; border:0; }}
    body {{ background:#1a1a1a; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Inter Tight",Helvetica,Arial,sans-serif; -webkit-font-smoothing:antialiased; }}
    img {{ border:0; line-height:100%; outline:0; text-decoration:none; display:block; }}
    table {{ border-collapse:collapse; mso-table-lspace:0; mso-table-rspace:0; }}

    /* ── Outer shell ──────────────────── */
    .shell {{ width:100%; background:#1a1a1a; padding:40px 16px; }}
    .container {{ max-width:600px; width:100%; margin:0 auto; }}

    /* ── Header ───────────────────────── */
    .header {{
      background: linear-gradient(135deg, #e8a045 0%, #d4656a 45%, #a855a8 100%);
      border-radius:16px 16px 0 0;
      padding:36px 40px 32px;
      text-align:center;
    }}
    .wordmark {{
      font-size:30px; font-weight:400; color:#fffdf7;
      letter-spacing:0.5px; line-height:1; margin-bottom:8px;
    }}
    .wordmark strong {{ font-weight:600; font-style:italic; }}
    .tagline {{
      font-size:11px; letter-spacing:0.15em; text-transform:uppercase;
      color:rgba(255,253,247,0.75); margin-bottom:20px;
    }}
    .header-meta {{
      display:inline-block;
      background:rgba(255,253,247,0.18);
      border:1px solid rgba(255,253,247,0.28);
      border-radius:999px;
      padding:5px 16px;
      font-size:12px;
      color:rgba(255,253,247,0.9);
      letter-spacing:0.05em;
    }}

    /* ── Date bar ─────────────────────── */
    .datebar {{
      background:#fffdf7;
      border-left:1px solid rgba(0,0,0,0.06);
      border-right:1px solid rgba(0,0,0,0.06);
      padding:16px 40px;
    }}
    .datebar-inner {{
      display:table; width:100%;
    }}
    .datebar-date {{
      display:table-cell; vertical-align:middle;
      font-size:11px; color:#999; letter-spacing:0.12em; text-transform:uppercase;
    }}
    .datebar-count {{
      display:table-cell; vertical-align:middle; text-align:right;
      font-size:11px; color:#c9a96e; letter-spacing:0.08em; text-transform:uppercase; font-weight:600;
    }}
    .divider {{ height:1px; background:rgba(0,0,0,0.06); margin: 0 40px; }}

    /* ── Article cards ────────────────── */
    .cards-wrap {{ background:#f0ede6; padding:8px 8px 0; }}
    .card {{
      background:#fffdf7;
      border-radius:12px;
      padding:24px 28px;
    }}
    .card-gap {{ height:8px; background:#f0ede6; }}
    .rank-cell {{ width:36px; vertical-align:top; padding-right:16px; padding-top:2px; }}
    .rank {{
      width:28px; height:28px; border-radius:50%;
      background:linear-gradient(135deg, #e8a045, #d4656a);
      color:#fff; font-size:12px; font-weight:700;
      text-align:center; line-height:28px;
    }}
    .content-cell {{ vertical-align:top; }}
    .source-line {{ margin-bottom:6px; }}
    .source-name {{
      font-size:11px; font-weight:600; letter-spacing:0.1em;
      text-transform:uppercase; color:#c9a96e;
    }}
    .dot {{ color:#ccc; margin:0 6px; font-size:11px; }}
    .date {{ font-size:11px; color:#aaa; }}
    .article-title {{
      margin:0 0 10px; font-size:16.5px; font-weight:600;
      line-height:1.35; color:#1a1a1a; letter-spacing:-0.01em;
    }}
    .article-link {{ color:#1a1a1a; text-decoration:none; }}
    .article-link:hover {{ text-decoration:underline; }}
    .summary {{
      margin:0 0 14px; font-size:14px; line-height:1.65;
      color:#4a4a4a;
    }}
    .read-more {{
      display:inline-block; font-size:12.5px; font-weight:600;
      color:#c9a96e; text-decoration:none; letter-spacing:0.02em;
    }}
    .read-more:hover {{ text-decoration:underline; }}

    /* ── Footer ───────────────────────── */
    .footer-wrap {{ background:#f0ede6; padding:0 8px 8px; }}
    .footer {{
      background:#242424;
      border-radius:0 0 12px 12px;
      padding:28px 40px;
      text-align:center;
    }}
    .footer-brand {{
      font-size:14px; font-weight:400; color:rgba(255,253,247,0.5);
      letter-spacing:0.5px; margin-bottom:12px;
    }}
    .footer-brand strong {{ font-weight:600; font-style:italic; color:rgba(255,253,247,0.7); }}
    .footer-text {{
      font-size:12px; color:#666; line-height:1.7;
    }}
    .footer-link {{ color:#c9a96e; text-decoration:none; }}
    .footer-link:hover {{ text-decoration:underline; }}
    .footer-sep {{ color:#444; margin:0 8px; }}

    /* ── Responsive ───────────────────── */
    @media only screen and (max-width: 480px) {{
      .header {{ padding:28px 24px 24px; }}
      .datebar {{ padding:14px 24px; }}
      .card {{ padding:20px 18px; }}
      .footer {{ padding:24px; }}
      .rank-cell {{ width:30px; padding-right:12px; }}
    }}
  </style>
</head>
<body>
<!--[if mso]>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#1a1a1a;">
<tr><td align="center" style="padding:40px 16px;">
<table width="600" cellpadding="0" cellspacing="0">
<![endif]-->

<table class="shell" width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td align="center">
      <table class="container" width="600" cellpadding="0" cellspacing="0">

        <!-- HEADER -->
        <tr>
          <td class="header">
            <div class="wordmark">MAI <strong>news</strong></div>
            <div class="tagline">Tech Intelligence · Personalised for you</div>
            <div class="header-meta">{when_short}</div>
          </td>
        </tr>

        <!-- DATE BAR -->
        <tr>
          <td class="datebar">
            <div class="datebar-inner">
              <span class="datebar-date">{when_long}</span>
              <span class="datebar-count">{count_label}</span>
            </div>
          </td>
        </tr>
        <tr><td class="divider"></td></tr>

        <!-- ARTICLES -->
        <tr>
          <td>
            <table class="cards-wrap" width="100%" cellpadding="0" cellspacing="0">
              {article_blocks}
            </table>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td>
            <table class="footer-wrap" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td class="footer">
                  <div class="footer-brand">MAI <strong>news</strong></div>
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

<!--[if mso]>
</table></td></tr></table>
<![endif]-->
</body>
</html>"""
