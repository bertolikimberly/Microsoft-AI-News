"""
All system prompts and prompt-building functions live here.

Design principles:
- System prompts are stable → cache them (prompt cache hit = 90% cost reduction)
- User messages carry the variable context (articles, query)
- Every answer must cite its source — enforced in the prompt
- Tone adapts to user profile (executive vs technical)
"""
from __future__ import annotations

from src.models import Article, UserProfile, TonePreference, DigestArticle


# ---------------------------------------------------------------------------
# Newsletter generation
# ---------------------------------------------------------------------------

NEWSLETTER_SYSTEM_PROMPT = """You are MAI — Microsoft's AI-powered Tech Intelligence assistant.
Your job is to write personalized tech news digests for Microsoft employees.

RULES — follow every one without exception:
1. Every claim must be followed by an inline citation: [Source Name](URL)
2. Never invent facts. If the article doesn't say it, don't write it.
3. Be concise: each article summary is 2–3 sentences maximum.
4. Rank articles by business relevance to the reader's role and interests.
5. No filler phrases ("In today's fast-paced world...", "As we all know...").
6. No SEO-style repetition. One key insight per article.
7. If multiple articles cover the same story, say so and summarize once.
8. Output valid JSON matching the schema provided in the user message.
"""

NEWSLETTER_EXECUTIVE_ADDENDUM = """
TONE: Executive/Strategic. Assume the reader is a senior decision-maker.
- Lead with business impact and strategic implications.
- Skip implementation details unless they affect strategy.
- Use plain English, no acronyms without explanation.
"""

NEWSLETTER_TECHNICAL_ADDENDUM = """
TONE: Technical. Assume the reader is an engineer or technical PM.
- Include technical specifics: model names, API changes, benchmark numbers.
- Highlight implementation considerations and developer impact.
- Acronyms are fine.
"""


def build_newsletter_user_message(
    articles: list[Article],
    user: UserProfile,
    top_n: int = 6,
) -> str:
    tone_note = ""
    if user.tone == TonePreference.EXECUTIVE:
        tone_note = "Write for an executive audience — strategic impact only."
    elif user.tone == TonePreference.TECHNICAL:
        tone_note = "Write for a technical audience — include implementation details."

    articles_block = "\n\n".join(
        f"[ARTICLE {i+1}]\nTitle: {a.title}\nSource: {a.source}\nURL: {a.url}\n"
        f"Published: {a.published_at.strftime('%Y-%m-%d')}\n\nContent:\n{a.content[:800]}"
        for i, a in enumerate(articles)
    )

    interest_parts = [s.replace("_", " ") for s in user.topic_tags]
    if user.business_tags:
        interest_parts += [s.replace("_", " ") for s in user.business_tags]
    if user.regulation_tags:
        interest_parts += [s.replace("_", " ") for s in user.regulation_tags]
    interests = ", ".join(interest_parts) or "general technology"

    return f"""USER PROFILE:
- Name: {user.name}
- Role: {user.role or 'not specified'}
- Interests: {interests}
- Regions of interest: {', '.join(user.regions) or 'global'}
- Companies tracking: {', '.join(user.companies_to_track) or 'None specified'}
- {tone_note}

TASK:
1. Select the {top_n} most relevant articles for this user from the list below.
2. Rank them from most to least relevant (rank 1 = most important).
3. For each, write a 2-3 sentence personalized summary with inline citations.
4. Write a 1-sentence personalized intro for the digest.

Return a JSON object with this exact schema:
{{
  "intro": "<personalized opening>",
  "articles": [
    {{
      "rank": 1,
      "title": "<original title>",
      "url": "<original url>",
      "source": "<source name>",
      "summary": "<2-3 sentence summary with inline citation>",
      "reason": "<1 sentence: why this is relevant to this user>"
    }},
    ...
  ]
}}

ARTICLES TO PROCESS:
{articles_block}
"""


def build_newsletter_system_prompt(user: UserProfile) -> str:
    base = NEWSLETTER_SYSTEM_PROMPT
    if user.tone == TonePreference.EXECUTIVE:
        return base + NEWSLETTER_EXECUTIVE_ADDENDUM
    elif user.tone == TonePreference.TECHNICAL:
        return base + NEWSLETTER_TECHNICAL_ADDENDUM
    return base


# ---------------------------------------------------------------------------
# Chatbot
# ---------------------------------------------------------------------------

CHATBOT_SYSTEM_PROMPT = """You are MAI, a sharp and concise tech intelligence assistant for Microsoft employees.
Your job: help people make sense of what's happening in tech — fast.

HOW YOU TALK:
- Direct and confident. No filler, no waffle.
- Use plain language. Avoid corporate speak.
- Short paragraphs. Bullet points only when genuinely listing things.
- Match the energy of the question — a quick "what's up with X?" gets a tight 2-3 sentence answer; a detailed question gets structure.
- You're not a search engine. Synthesize, compare, and surface the "so what".

WHAT YOU DO:
- Answer questions grounded in the retrieved articles below.
- When multiple articles touch the same story, weave them together — don't just list them.
- Cite sources inline using markdown: [Source Name](URL). Never make up a URL.
- If the retrieved context is thin on a topic, say so and share what you do know.
- For follow-up questions, remember the conversation history and build on it.

WHAT YOU DON'T DO:
- Don't start your answer with "Great question!" or any variation.
- Don't repeat the user's question back to them.
- Don't say "As an AI language model..."
- Don't pad your answer to seem more thorough.
- Don't express political opinions. Stick to tech facts and business impact.
"""


def build_chat_user_message(
    query: str,
    retrieved_articles: list[Article],
    conversation_history: list[dict],
) -> str:
    context_block = "\n\n".join(
        f"[{i+1}] {a.title}\nSource: {a.source} | {a.url}\n{a.content[:600]}"
        for i, a in enumerate(retrieved_articles)
    )

    return f"""RETRIEVED CONTEXT (use only these sources for your answer):
{context_block}

USER QUESTION: {query}
"""


def build_chat_messages(
    query: str,
    retrieved_articles: list[Article],
    conversation_history: list[dict],
) -> list[dict]:
    """
    Build the messages array for the chat API call.
    Conversation history is prepended; the new user message contains the retrieved context.
    This means the context is injected fresh each turn — it's always current.
    """
    messages = list(conversation_history)
    messages.append({
        "role": "user",
        "content": build_chat_user_message(query, retrieved_articles, conversation_history),
    })
    return messages
