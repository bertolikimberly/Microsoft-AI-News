# MAI News

AI-powered tech intelligence platform for IE × Microsoft AI/ML Engineering Capstone 2026.

Ingests articles from 40+ curated RSS sources, deduplicates and indexes them with pgvector embeddings, and delivers a RAG-powered chat interface personalised by role, region, and topic interests.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 + React 19 + Tailwind (port 3001) |
| Backend API | FastAPI + SQLAlchemy + pgvector (port 8000, Docker) |
| Database | Postgres 16 + pgvector (`mai-news-postgres`) |
| LLM | OpenAI GPT-4o |
| Embeddings | `all-MiniLM-L6-v2` 384-dim via sentence-transformers |
| Auth | Passwordless magic-link + `dev-login` shortcut for local dev |
| Deploy target | Docker locally · Azure Container Apps (backend) · Azure Storage static website (frontend) |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Node 20+
- An OpenAI API key (each team member uses their own)

---

## Local setup

### 1. Clone and configure

```bash
git clone <repo-url>
cd Microsoft-AI-News

cp backend/.env.example backend/.env
# Open backend/.env and set OPENAI_API_KEY to your own key.
# Everything else is pre-filled for local dev — leave it as-is.
```

### 2. Start Postgres + API

```bash
docker compose up -d
```

First time or after any Python/dependency change:

```bash
docker compose up --build -d
```

Tables and seed data (tags, sources) are created automatically on first boot.

Verify it's healthy:

```bash
curl http://localhost:8000/api/v1/health/ready
# → {"status":"ok","checks":{"db":"ok"}}
```

### 3. Ingest articles

Pulls from all RSS sources, deduplicates, embeds, and writes to pgvector:

```bash
curl -X POST http://localhost:8000/api/v1/internal/run-ingest \
  -H "Authorization: Bearer local-dev-test-secret-123"
# → {"fetched": 427, "unique": 381, "indexed": 381}
```

Only needed on first run or to refresh stale data. The DB persists across `docker compose` restarts.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at **http://localhost:3001** (falls back to 3000 if 3001 is taken).

### 5. Sign in

Click **Sign in** — any email/password works in dev mode. The `dev-login` endpoint creates a fixed test user (`dev.user@microsoft.com`) and returns a JWT. No real credentials needed.

---

## What is built and working

| Feature | Status |
|---|---|
| Dev login (any email/password) | ✅ |
| SSE streaming chat with GPT-4o | ✅ |
| RAG retrieval (pgvector cosine similarity, top 8 chunks) | ✅ |
| Topic filtering in RAG from user preferences | ✅ |
| Citations returned alongside streamed response | ✅ |
| User preferences (role, region, topics, tone, depth) | ✅ |
| Dashboard with today's top articles | ✅ |
| Dashboard filters by user topic preferences | ✅ |
| Clicking article → chat "Tell me more about {title}" | ✅ |
| General chat sessions | ✅ |
| Folder-based chat threads (named containers) | ✅ |
| Save / unsave articles from chat cards | ✅ |
| Saved articles view | ✅ |
| RSS ingestion pipeline (watermark-based, incremental) | ✅ |
| Deduplication (URL-hash + semantic similarity 0.88) | ✅ |
| Multi-dimension article tagging (topic/business/region/role) | ✅ |
| Internal ingest endpoint (`POST /internal/run-ingest`) | ✅ |
| Internal digest endpoint (`POST /internal/run-digest-worker`) | ✅ |

---

## Architecture

```
frontend/ (Next.js, port 3001)
  src/components/        — App, AuthGate, chat/*, dashboard/*, news/*, saved/*
  src/lib/api.ts         — typed fetch + SSE client
        │
        │ HTTP / SSE
        ▼
backend/app/ (FastAPI, port 8000)
  routers/               — sessions, articles, auth, me, internal, saved, folders
  integrations/          — llm_bridge (adapts pipeline to API layer)
  workers/               — ingest_worker, digest_worker
        │
        │ Python imports
        ▼
llm_engineering/src/
  ingestion/             — RSSFetcher, ArticleDeduplicator, ArticleVectorStore
  llm/                   — chatbot (RAG), client, prompts
  config/settings.py     — pydantic-settings (reads backend/.env)
        │
        │ SQL + pgvector
        ▼
Postgres 16 + pgvector (port 5432, Docker)
```

---

## Key API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/dev-login` | Dev login — returns JWT |
| `GET` | `/api/v1/health/ready` | Health check |
| `GET/PUT` | `/api/v1/me/preferences` | Read / write user preferences |
| `GET` | `/api/v1/articles` | List articles (supports `?topics=ai&limit=50`) |
| `POST` | `/api/v1/me/sessions` | Create chat session |
| `POST` | `/api/v1/me/sessions/{id}/messages` | Send message (SSE stream) |
| `POST` | `/api/v1/internal/run-ingest` | Trigger RSS ingest (requires `WORKER_SHARED_SECRET`) |
| `POST` | `/api/v1/internal/run-digest-worker` | Trigger email digest (requires `WORKER_SHARED_SECRET`) |

Interactive docs at **http://localhost:8000/docs**.

---

## Environment variables

All config lives in `backend/.env`. Copy from `backend/.env.example`.

| Variable | Local default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | — | **Required. Your own key.** |
| `DATABASE_URL` | pre-filled | Points to Docker Postgres |
| `ENV` | `dev` | `dev` enables dev-login and relaxed CORS |
| `JWT_SECRET` | `dev-only-change-me-in-prod` | Change in prod |
| `WORKER_SHARED_SECRET` | `local-dev-test-secret-123` | For local ingest/digest calls |
| `ENTRA_*` | blank | Leave blank — dev-login works without OAuth |
| `ACS_*` / `RESEND_*` | blank | Leave blank — emails skipped gracefully |

---

## Useful commands

```bash
# Tail API logs
docker logs mai-news-api -f

# Rebuild API after Python/dependency changes
docker compose up --build api -d

# Stop everything (keeps DB data)
docker compose down

# Wipe DB and start fresh
docker compose down -v && docker compose up -d
```

---

## Azure deployment notes

- Restricted to **francecentral** or **swedencentral** regions.
- **Azure Static Web Apps is not available** in those regions — use **Storage static website** for the frontend instead.
- Backend targets Azure Container Apps.

---

## Team

IE × Microsoft AI/ML Engineering Capstone — 2026
