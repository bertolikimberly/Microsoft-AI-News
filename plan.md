# MAI News — Project Plan & Status
**IE × Microsoft AI/ML Engineering Capstone 2026**

Last updated: 2026-06-20

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 + React 19 (localhost:3001) |
| Backend | FastAPI + SQLAlchemy + pgvector (localhost:8000 via Docker) |
| Database | Postgres 16 + pgvector (`mai-news-postgres`) |
| LLM | OpenAI gpt-4o |
| Embeddings | all-MiniLM-L6-v2 (384-dim, via sentence-transformers) |
| Auth | Passwordless magic-link; `dev-login` shortcut in dev mode |
| Infra | Docker Compose locally; Azure Container Apps target |

> **Do not push to GitHub** — `backend/.env` contains a real OpenAI key that must be rotated before any push. Azure regions are restricted to `francecentral` / `swedencentral` — use Storage static website for frontend (Azure Static Web Apps is blocked in those regions).

---

## What Is Done

### Auth & User Management
- [x] Magic-link passwordless login (email → token → redirect to `/#access_token=<jwt>`)
- [x] `dev-login` endpoint for local dev (returns JWT directly, no credentials needed)
- [x] JWT stored in `localStorage` as `mai_token`, attached as `Authorization: Bearer` to every API call
- [x] User profile: name, email, department, region
- [x] Preferences: role, region, topics, depth, delivery frequency, tone, keywords
- [x] `GET /me/preferences` + `PUT /me/preferences` persisted to Postgres
- [x] Preferences loaded from API on mount and merged into local prefs state

### Frontend — App Shell
- [x] Sidebar: Dashboard nav, Chats section, Projects/Folders section, Recents section
- [x] No horizontal scrollbar in sidebar (`overflow-x: hidden`)
- [x] Topbar breadcrumb with clickable "New chat" button
- [x] Dark/light palette system with animated blob background
- [x] Display font + news font theming
- [x] Preferences modal (topics, delivery, tone, etc.)
- [x] Toast notifications

### Frontend — Chat
- [x] SSE streaming chat (real-time token-by-token response from backend)
- [x] General chat sessions (not tied to a folder)
- [x] Folder-based chat threads
- [x] Ghost chat fix: session only created in DB on first message send, not on "New chat" click
- [x] Duplicate chat fix: `listSessions` + `getFolders` run in `Promise.all`; folder thread IDs filtered out of general Recents
- [x] `freshChatRef` pattern: ref flag bypasses React state batching for dashboard-to-chat navigation race condition
- [x] Recents section: shows last 10 items (general + folder threads), with delete buttons
- [x] Chats section: only "+ New chat" button (no duplicate thread list)
- [x] New chat screen with greeting + subtitle + 4 suggested question prompts
  - 2 prompts per row, transparent glass style, matches display font
  - Prompts drawn from user topic preferences + fallback questions
  - Subtitle: "Here's what's making news today. Ask me anything."

### Frontend — Folders / Projects
- [x] Inline folder creation in sidebar (no preferences wizard, no modal)
  - Input appears inline, Enter or checkmark to confirm, Escape or X to cancel
- [x] Folder threads (per-folder chat sessions)
- [x] Delete folder and delete thread buttons
- [x] BriefingPreview shown on new folder thread before first message
- [x] Folder preferences wizard removed (folders are now just named containers)

### Frontend — Dashboard
- [x] Dashboard page showing today's top articles
- [x] Filters by user's real topic preference slugs (passed from `prefs.topics`)
- [x] Re-fetches automatically when user preferences load from API (`topicsKey` dependency)
- [x] Falls back to all recent articles if user has no preferences saved
- [x] Featured lead story card + scrollable article list
- [x] Clicking any article sends "Tell me more about: {title}" into chat
- [x] Dashboard nav item in sidebar (top, above Chats)

### Frontend — Saved Articles
- [x] Save/unsave articles from chat cards
- [x] Saved view listing all bookmarked articles

### Backend — Articles
- [x] `GET /articles` with topic filtering, limit up to 50 (was 20 — caused dashboard 422 errors)
- [x] `GET /articles/{id}` for citation hover/expand
- [x] `GET /articles/{id}/source` redirects (302) to original URL
- [x] Article tags in `article_tags` table (multi-dimensional: topic, business, regulation_policy, regional, role)

### Backend — RAG Chat
- [x] Query embedding → pgvector cosine similarity (top_k=8)
- [x] Topic filter from user preferences applied on every retrieval
- [x] GPT-4o response with retrieved article context
- [x] Citations returned alongside streamed response

### Backend — Internal Endpoints (protected by `WORKER_SHARED_SECRET`)
- [x] `POST /api/v1/internal/run-digest-worker` — generate email digests for eligible users
- [x] `POST /api/v1/internal/run-ingest` — new this session
  - Fetches all RSS tiers (breaking, standard, daily) concurrently
  - Deduplicates with URL-hash + semantic similarity
  - Embeds and upserts into pgvector via `ArticleVectorStore`
  - Saves RSS watermarks to Postgres via `persisted_fetch_state` (survives Docker restarts)
  - Returns `{ fetched, unique, indexed }`
  - First run result: 427 fetched, 381 indexed

### Data Pipeline (`llm_engineering/`)
- [x] `RSSFetcher` with per-source watermark-based incremental fetch
- [x] `fetch_by_tier(tier)` — fetch all sources in a tier without needing a user profile
- [x] `ArticleDeduplicator`: URL-hash dedup + semantic similarity clustering (threshold 0.88)
- [x] Source registry (`sources.json`): 40+ sources across 3 tiers
- [x] `ArticleVectorStore`: embed + upsert into pgvector, writes multi-dim tags to `article_tags`
- [x] Fetch state persistence: watermarks stored in `KvState` Postgres table, survive container restarts

---

## Database State (as of 2026-06-20)

| Metric | Value |
|---|---|
| Total articles | 562 |
| Date range | 2024-01-19 to 2026-06-20 |
| Article tag rows | 1,851 |

Topic distribution in `article_tags`:

| Slug | Count |
|---|---|
| `artificial_intelligence_ml` | 341 |
| `software_development` | 119 |
| `cloud_infrastructure` | 106 |
| `hardware_chips` | 81 |
| `cybersecurity` | 60 |
| `health_biotech` | 40 |
| `metaverse_xr` | 20 |
| `quantum_computing` | 20 |

---

## What's Next

### High Priority

- [ ] **GitHub Actions cron for auto-ingest**
  The `POST /internal/run-ingest` endpoint is ready. Needs `.github/workflows/ingest-cron.yml` on a schedule (e.g. every 6 hours), calling the endpoint with `WORKER_SHARED_SECRET` from a repo secret. Do not push anything until the OpenAI key is rotated.

- [ ] **Rotate the OpenAI API key**
  The key in `backend/.env` is real. Revoke at platform.openai.com, generate a new one, store only in `backend/.env` (gitignored). Replace both `.env.example` files with a placeholder.

- [ ] **Set `FETCH_STATE_PATH` for production**
  Defaults to `/tmp/fetch_state.json` which evaporates on container restart. For Azure Container Apps, set this env var to a stable path the `persisted_fetch_state` wrapper can use. The Postgres-backed bridge is already in place — just needs the env var wired in the deploy config.

### Medium Priority

- [ ] Verify end-to-end RAG chat with the freshly indexed articles — confirm citations render and topic filtering is working for users with real preferences
- [ ] Dashboard topic chips / badges on article cards for visual context
- [ ] Dashboard "refresh" button to re-fetch without a full page reload
- [ ] Wire the email input in AuthGate to `POST /auth/email/request-login` (magic-link backend is fully built, frontend form still calls `dev-login` regardless of input)

### Lower Priority / Future

- [ ] Azure deployment: Container Apps (backend) + Storage static website (frontend, francecentral or swedencentral — Static Web Apps unavailable in those regions)
- [ ] Email digest end-to-end test (`WORKER_SHARED_SECRET` is set; needs `ACS_CONNECTION_STRING` for actual delivery)
- [ ] Alembic migrations (replace `create_all` at startup before any prod schema changes)
- [ ] Rate limiting on LLM chat endpoint (slowapi, ~20 req/min per user)
- [ ] Article click-through logging (future ranking signal)

---

## Bugs Fixed This Session

| Bug | Root cause | Fix |
|---|---|---|
| Dashboard showed no articles | Backend `le=20` limit rejected `limit=24` with 422; error swallowed silently by `.catch(() => {})` | Raised backend limit to `le=50` |
| Dashboard showed no articles even after limit fix | Initial `prefs.topics` had wrong placeholder slugs (`ai_ml`, `cloud`, `cyber`) — none exist in DB taxonomy | Changed initial `prefs.topics` to `[]` so first load is unfiltered |
| Dashboard didn't update when real prefs loaded | `useEffect` in `DashboardView` had empty `[]` dep array — never re-ran after API prefs arrived | Added `topicsKey` (joined topics string) as dependency |
| Dashboard not filtered by user preferences | `DashboardView` had no access to prefs; `App.tsx` never passed topics down | Added `userTopics` prop to `DashboardView`, passed `prefs.topics` from `App.tsx` |

---

## How to Run Locally

```bash
# 1. Copy env and fill in your OpenAI key
cp backend/.env.example backend/.env
# edit backend/.env: set OPENAI_API_KEY

# 2. Start Postgres + API
docker compose up -d

# 3. Ingest fresh articles into pgvector
curl -X POST http://localhost:8000/api/v1/internal/run-ingest \
  -H "Authorization: Bearer local-dev-test-secret-123"

# 4. Start the frontend
cd frontend && npm install && npm run dev

# 5. Open http://localhost:3001
# Sign in — any email/password works in dev mode
```

Backend code changes require a rebuild: `docker compose up --build api -d`

---

## Key Constraints

- No GitHub push until OpenAI key is rotated
- Backend is a baked Docker image — Python changes need `docker compose up --build api -d`
- Azure regions: francecentral / swedencentral only — Static Web Apps unavailable
- `WORKER_SHARED_SECRET` in `backend/.env` is `local-dev-test-secret-123` for local dev — change before any real deployment
