# Feature → Endpoint Map

> Companion to [personas_and_features.md](./personas_and_features.md) (the product) and [hosting.md](./hosting.md) (where this all runs).
> Each feature (F1–F12) is mapped to the backend endpoints that implement it.
> All paths are prefixed with **`/api/v1`** (set in [backend/app/main.py:126](../backend/app/main.py#L126)).
>
> The tag taxonomy and source registry referenced below are owned by the data engineering layer: [sources.json](../sources.json) is the canonical source of truth, and [tag_discovery_report.md](../data_engineering/tag_discovery_report.md) describes how the topic clusters were derived.

---

## F1 — Employee registration

User signs in with their Microsoft identity; the backend provisions a `User` row on first login. Built against any Entra ID tenant — for development this can be a **free standalone tenant** created from [entra.microsoft.com](https://entra.microsoft.com) (no Azure subscription, no credit card; see [backend/.env.example](../backend/.env.example) for setup steps).

| Method | Path | What it does |
|---|---|---|
| `GET` | `/auth/login` | Starts the OAuth 2.0 / OIDC flow. Generates a CSRF `state` and a PKCE `code_verifier`, stashes both in HttpOnly cookies (path `/api/v1/auth`, 10-min TTL), and `302`-redirects the browser to Entra's `/authorize`. |
| `GET` | `/auth/callback` | OAuth redirect target. Verifies `state` against the cookie (constant-time compare), exchanges the auth `code` at Entra's `/token` endpoint via MSAL (which validates the ID token signature against Entra's JWKS), provisions the `User` row on first login, mints the app's own JWT, and `302`-redirects to `FRONTEND_URL/#access_token=<jwt>`. The token rides in the URL fragment so it stays out of server access logs. |
| `POST` | `/auth/dev-login` | Dev-only shortcut: provisions a deterministic dev user, seeds demo data, returns `{ access_token, token_type, expires_in, user }` as JSON. Returns `404` when `ENV != dev`. |
| `GET` | `/me` | Returns the authenticated user (id, email, display name). Requires `Authorization: Bearer <jwt>`. Used by the frontend to confirm "am I logged in?" and gate the registration vs. app shell. |

Implementation notes:

- The OAuth flow lives in [backend/app/auth/entra.py](../backend/app/auth/entra.py) (MSAL `ConfidentialClientApplication`) and is wired into the router at [backend/app/routers/auth.py](../backend/app/routers/auth.py).
- The frontend extracts the JWT from the URL fragment on load, stores it (memory or `localStorage`), removes it from the URL via `history.replaceState`, then attaches it as `Authorization: Bearer <jwt>` on every API call.
- The same `User` row shape is used regardless of which login path created it — `entra_oid` is a placeholder UUID for `/auth/dev-login` users, and the real Entra `oid` for real users.

---

## F2 — Preferences UI (topics, tags, sources, frequency, tone, length)

Reads the multi-dimensional tag taxonomy, the source registry, and the user's current preferences; writes new preferences.

| Method | Path | What it does |
|---|---|---|
| `GET` | `/topics` | Returns the **topic** dimension of the taxonomy (slug + label). Convenience subset of `/tags?dimension=topic`, kept for backwards compatibility and to drive the registration chip list. Seeded at startup ([seed.py](../backend/app/seed.py)) from [sources.json](../sources.json) `metadata.tags_taxonomy.topic`. |
| `GET` | `/tags` | Returns the **full multi-dimensional tag taxonomy** keyed by dimension: `topic`, `business`, `regulation_policy`, `regional`, `role`, `seniority`. Source of truth: [sources.json](../sources.json) `metadata.tags_taxonomy`. Cached for 24h. |
| `GET` | `/tags?dimension={d}` | Returns a single dimension only — used by preference filter chips that show one category at a time. |
| `GET` | `/sources` | Lists available sources from the registry: `id`, `name`, `category`, `source_type`, `region`, `content_quality`. Powers the source-muting picker in preferences. Optional filters: `?region=`, `?category=`. Backed by [sources.json](../sources.json). |
| `GET` | `/me/preferences` | Returns the caller's current preferences: selected topics, business tags, regulation tags, regions, role, muted sources, frequency, delivery day/hour, tone, length, language. |
| `PUT` | `/me/preferences` | Replaces the caller's preferences. Validates every tag slug against the taxonomy and every source id against the registry; rejects unknown values. |

Preferences body shape:

```json
{
  "topics": ["ai_ml", "cloud_infra"],
  "business_tags": ["ma_funding"],
  "regulation_tags": ["ai_regulation"],
  "regions": ["europe"],
  "role": "engineers",
  "muted_sources": ["mit_technology_review"],
  "frequency": "weekly",
  "delivery_day": "monday",
  "delivery_hour_local": 8,
  "tone": "technical",
  "length": "standard",
  "language": "en"
}
```

> The data engineering taxonomy's `seniority` dimension (`deep_dive` / `brief`) maps directly to the existing `length` field (`deep` / `short`). The two are kept as one field on the wire for UI continuity; the digest worker reads `length` and the summariser applies the corresponding seniority depth.

---

## F3 — Email digest generation

The digest itself is produced by a background worker (not a public endpoint). The API only exposes **reads** of past digests for end users; writes happen via direct DB access from the digest worker (D1).

The worker is triggered on a schedule by an **internal webhook** that lives under `/api/v1/internal/*`. The scheduler is **GitHub Actions cron** ([.github/workflows/digest-cron.yml](../.github/workflows/digest-cron.yml)) — free, no card needed, fires the webhook once a day.

| Method | Path | What it does |
|---|---|---|
| `GET` | `/me/digests` | Lists the caller's past digests, newest first. Cursor-paginated (`?cursor=...&limit=...`). Returns summary metadata only (id, generated_at, item_count). |
| `POST` | `/internal/run-digest-worker` | **Infrastructure-only.** Triggers one run of the digest worker. Authenticated by `Authorization: Bearer <WORKER_SHARED_SECRET>` — not a user JWT. Returns 503 when the secret is unconfigured (closed-by-default). Hidden from OpenAPI (`include_in_schema=False`) so the frontend client doesn't surface it. Called by GitHub Actions cron; idempotent — the worker skips users who already have a digest for today. |

> No public "generate digest now" endpoint at MVP — cadence is owned by the scheduler. A debug trigger can be added behind a feature flag if needed for demos.

> The worker logic lives in [backend/app/workers/digest_worker.py](../backend/app/workers/digest_worker.py); the webhook entry point is [backend/app/routers/internal.py](../backend/app/routers/internal.py).

---

## F4 — Configurable cadence (daily / weekly)

Cadence is a **field on `/me/preferences`** (`frequency: daily | weekdays | weekly`). The scheduler reads it when picking who to deliver to on a given run. No dedicated endpoint.

| Method | Path | What it does |
|---|---|---|
| `PUT` | `/me/preferences` | Same endpoint as F2 — `frequency` is part of the preferences body. |

---

## F5 — Chatbot: grounded Q&A with citations

Conversational interface for news exploration. Each user message returns an LLM answer with article citations.

| Method | Path | What it does |
|---|---|---|
| `POST` | `/me/sessions` | Creates a new chat session for the caller. Returns the session id used in subsequent message calls. |
| `GET` | `/me/sessions` | Lists the caller's chat sessions (cursor-paginated). Used for a sidebar of past conversations. |
| `GET` | `/me/sessions/{session_id}` | Returns one session with its full message history. |
| `POST` | `/me/sessions/{session_id}/messages` | Sends a user message; runs retrieval + LLM; returns the assistant reply **with citations** (each citation has `article_id`, title, source, url). This is the core grounded-answer endpoint. |
| `GET` | `/me/sessions/{session_id}/messages` | Paginated message history for a session (when the embedded history in `GET /me/sessions/{id}` would be too large). |
| `DELETE` | `/me/sessions/{session_id}` | Deletes a chat session and its messages. |

Citations resolve to articles via:

| Method | Path | What it does |
|---|---|---|
| `GET` | `/articles/{article_id}` | Returns the article (title, source, url, published_at, extract). The chatbot UI uses this to expand a citation into a preview card. |
| `GET` | `/articles/{article_id}/source` | Redirects to the **original publisher URL**. Keeps users tied to the source of truth (grounding requirement from the capstone brief). |

---

## F6 — Chatbot: follow-ups & "dig deeper"

Same endpoint as F5 — implemented via **session memory**. The server uses the session's prior messages as context for each new turn, so follow-ups like *"and what about the licensing implications?"* resolve against the previous turn.

| Method | Path | What it does |
|---|---|---|
| `POST` | `/me/sessions/{session_id}/messages` | Posting another message to the same session id continues the conversation; prior turns are included in the LLM prompt up to the context budget. |

---

## F7 — Chatbot: story comparison ("compare X vs Y")

Same endpoint as F5. The LLM is prompted with both articles' content (selected via retrieval) and asked to produce a side-by-side answer. No dedicated route — comparison is a query pattern, not a new resource.

| Method | Path | What it does |
|---|---|---|
| `POST` | `/me/sessions/{session_id}/messages` | A comparison query is just a user message whose retrieval step pulls multiple articles. Citations cover both sides. |

---

## F8 — Read the digest in-app

The email links into the web app; the app fetches the same digest content and renders it.

| Method | Path | What it does |
|---|---|---|
| `GET` | `/me/digests/{digest_id}` | Returns one digest: items (ranked), summaries, tones, and citations resolved to title/source/url. Default `?format=json` for the SPA. |
| `GET` | `/me/digests/{digest_id}?format=html` | Same digest, rendered as a minimal HTML page. Used as a fallback / for the email-mirror view. |

> Cross-user access returns **404** (not 403) — we don't leak the existence of someone else's digest id ([digests.py](../backend/app/routers/digests.py)).

---

## F9 — Preferences edit + unsubscribe

Editing prefs uses the same `PUT /me/preferences` as F2. Unsubscribe = stop receiving digests, which today means deleting the account (the worker filters out users with no row). Logout is separate and doesn't affect delivery.

| Method | Path | What it does |
|---|---|---|
| `PUT` | `/me/preferences` | Update preferences (also the path for changing cadence / muting sources). |
| `DELETE` | `/me` | Deletes the caller's account and all dependent rows (sessions, feedback, digests). Returns `204`. |
| `POST` | `/auth/logout` | Returns `204`. Bearer-token auth is stateless, so logout is the frontend forgetting its JWT; the server defensively clears any leftover oauth cookies but holds no per-user session. Does **not** unsubscribe — the user keeps receiving digests until they hit `DELETE /me`. |

---

## F10 — Feedback signal (thumbs up/down)

One signal per `(user, digest, article)`. A second POST overwrites the previous signal (idempotent).

| Method | Path | What it does |
|---|---|---|
| `POST` | `/me/digests/{digest_id}/feedback` | Records a thumbs up/down for one article inside one digest. Body: `{ article_id, signal: "up" \| "down" }`. Returns `204`. Validates that the article actually appeared in the digest so feedback can't be forged against unrelated articles. |

---

## F11 — Language selection *(post-MVP)*

No endpoint. When added, will become a field on `/me/preferences` and a parameter to the summarizer/chat prompts.

---

## F12 — Saved articles / read-later *(post-MVP)*

No endpoint. Sketch: `POST /me/saved` / `GET /me/saved` / `DELETE /me/saved/{article_id}`.

---

## Auxiliary endpoints (not feature-mapped)

| Method | Path | What it does |
|---|---|---|
| `GET` | `/health/live` | Liveness probe — returns immediately. For container orchestrator. |
| `GET` | `/health/ready` | Readiness probe — confirms DB is reachable before declaring ready. |

---

## Endpoint summary (one-liner per route)

```
GET    /api/v1/auth/login                              F1   Start SSO
GET    /api/v1/auth/callback                           F1   SSO callback — provisions user on first login
POST   /api/v1/auth/logout                             F9   Clear session cookie
POST   /api/v1/auth/dev-login                          F1   Dev shortcut (disabled in prod)

GET    /api/v1/me                                      F1   Current user
DELETE /api/v1/me                                      F9   Delete account
GET    /api/v1/me/preferences                          F2   Read preferences
PUT    /api/v1/me/preferences                          F2/F4/F9  Update preferences (topics/tags/sources/freq/tone/length)

GET    /api/v1/topics                                  F2   Topic dimension (legacy convenience)
GET    /api/v1/tags                                    F2   Full multi-dimensional tag taxonomy
GET    /api/v1/tags?dimension={d}                      F2   Single dimension (topic/business/regulation_policy/regional/role/seniority)
GET    /api/v1/sources                                 F2   Source registry (id/name/category/region/source_type)

GET    /api/v1/articles/{id}                           F5   Article detail (for citation expansion)
GET    /api/v1/articles/{id}/source                    F5   Redirect to original publisher URL

GET    /api/v1/me/digests                              F3   List past digests
GET    /api/v1/me/digests/{id}                         F8   Get one digest (?format=json|html)
POST   /api/v1/me/digests/{id}/feedback                F10  Thumbs up/down on one item

POST   /api/v1/me/sessions                             F5   Create chat session
GET    /api/v1/me/sessions                             F5   List chat sessions
GET    /api/v1/me/sessions/{id}                        F5   Get session + history
DELETE /api/v1/me/sessions/{id}                        F5   Delete session
GET    /api/v1/me/sessions/{id}/messages               F5   Paginated message history
POST   /api/v1/me/sessions/{id}/messages               F5/F6/F7  Send message — LLM answer + citations

GET    /api/v1/health/live                             —    Liveness probe
GET    /api/v1/health/ready                            —    Readiness probe

POST   /api/v1/internal/run-digest-worker              F3   [INFRA] Trigger digest worker (shared-secret auth; GH Actions cron)
```
