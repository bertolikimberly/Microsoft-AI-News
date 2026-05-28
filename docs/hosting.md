# Hosting Plan — Free-Tier Production Deploy

> What we actually deploy for the capstone — laptop-first build, free-tier hosted demo.
> See [personas_and_features.md](./personas_and_features.md) for the product, [feature_endpoints.md](./feature_endpoints.md) for the API surface.
>
> Total recurring cost: **$0** + cents-to-low-dollars in LLM tokens.

---

## 1. Stack Summary

| Piece | Provider | Plan | Free-tier limit | Why this one |
|---|---|---|---|---|
| **Backend API** ([backend/](../backend/)) | **Render** | Free Web Service | 750 hr/month total · 512 MB RAM · sleeps after 15 min idle · ~30 s cold start | Deploys from Dockerfile, HTTPS free, generous quotas. Blueprint config in [render.yaml](../render.yaml). |
| **Frontend** ([frontend/](../frontend/), Next.js) | **Vercel** | Hobby | 100 GB bandwidth/month · unlimited static deploys | Made by the Next.js team; near-zero config. |
| **PostgreSQL + pgvector** | **Neon** | Free | 0.5 GB storage · 191 compute-hr/month · auto-suspends after idle | Real Postgres, pgvector supported, no card required. |
| **LLM** | **OpenAI API** | PAYG | No free tier — set a $-cap on the dashboard | Public pricing → defensible cost-per-user in the report. Dev fallback: Ollama local. |
| **Email** | **Resend** | Free | 3 000 emails/month · 100/day | Clean SDK; sender domain must be verified in the Resend dashboard before real delivery works. |
| **Identity** | **Microsoft Entra ID** | Free standalone tenant | 50 000 monthly active users free | Real OIDC + "Sign in with Microsoft" — no Azure subscription required. |
| **Object storage** (raw HTML) | Server filesystem at MVP; **Cloudflare R2** later | R2 free tier | 10 GB storage · no egress fees | Capstone fits on Render disk; R2 reserved for scale. |
| **Cache** | In-process Python dict (MVP); **Upstash Redis** if needed | Upstash free | 10 000 commands/day | Single backend instance — Redis is over-engineering at MVP. |
| **CI / cron** | **GitHub Actions** | Free for public repos | 2 000 min/month private; unlimited public | Triggers the digest worker via `/api/v1/internal/*` (see [`WORKER_SHARED_SECRET`](../backend/.env.example)). |
| **Secrets** | `.env` locally · Render env vars in prod | — | — | No Key Vault needed; Render encrypts env vars at rest. |

---

## 2. The Shape on a Diagram

```
                       USER'S BROWSER
                              │
                              ▼
                Vercel ─── Next.js frontend
                              │
                              │ HTTPS / REST + SSE
                              ▼
                Render ─── FastAPI backend  ◄── Entra ID (sign-in)
                              │                ◄── OpenAI API (LLM)
                              │                ◄── Resend (email)
                              ▼
                    Neon (Postgres + pgvector)
```

Two hosts (Vercel + Render). Three external API providers (Entra, OpenAI, Resend). One managed database (Neon). One repo, one deploy.

---

## 3. Deploy Order (one-time setup)

| # | Step | Where | Notes |
|---|---|---|---|
| 1 | Create free Entra tenant | https://entra.microsoft.com | Steps in [backend/.env.example](../backend/.env.example) |
| 2 | Create Neon project, copy connection string | https://neon.tech | Replace `postgres://` → `postgresql+psycopg://`, keep `?sslmode=require` |
| 3 | Sign up for Resend, generate API key | https://resend.com | Verify a sending domain (or use `onboarding@resend.dev` while testing) |
| 4 | Create OpenAI API key + **set a usage cap** | https://platform.openai.com | Cap matters — accidents can be expensive |
| 5 | Push the repo to GitHub | — | Render reads `render.yaml` from the default branch |
| 6 | Render → New → Blueprint → connect repo | https://render.com | It reads [render.yaml](../render.yaml) and creates the service |
| 7 | Fill in the `sync: false` env vars in Render dashboard | Render | DB URL, Entra IDs, OpenAI/Resend keys |
| 8 | Deploy the frontend | https://vercel.com | Connect the repo, set root dir to `frontend/` |
| 9 | Set `FRONTEND_URL` + `ALLOWED_ORIGINS` in Render to the Vercel URL | Render | Re-deploys automatically |
| 10 | Update Entra App Registration redirect URI to the deployed `/auth/callback` | Entra portal | `https://tech-intel-api.onrender.com/api/v1/auth/callback` |

---

## 4. Cost Model

**Recurring infra:** $0/month.

**Variable (LLM tokens):**
- Article summary cached across users (keyed by `article_id` + `length` + `tone`) — ~$0.003 per article on `gpt-4o-mini`.
- Chat: ~$0.01–0.05 per conversation on `gpt-4o`.
- Embeddings: **$0** — sentence-transformers runs in-process (CPU).

**Demo-scale estimate:** 100 users, weekly digest, 10 chat conversations/user/month → roughly **$5–15/month** in LLM tokens. Easily within an OpenAI hard cap.

---

## 5. Known Trade-offs

| Concern | Reality | Mitigation |
|---|---|---|
| Render free tier sleeps after 15 min idle | First request after sleep is ~30 s | Ping `/api/v1/health/live` every 10 min from a free cron service; or upgrade to Render Starter ($7/mo) for the demo |
| Neon auto-suspends idle compute | Reconnect adds latency | SQLAlchemy's `pool_pre_ping=True` (already on — see [backend/app/db/session.py](../backend/app/db/session.py)) handles it |
| OpenAI tokens cost real money | Capstone-scale demo is cents, but a bug could spike | Hard $-cap on the OpenAI account + per-route rate limits in the API |
| Vercel + Render + Neon default to US regions | Latency for EU users; GDPR data-residency flag for the report | Render `region: frankfurt`, Neon EU region, Vercel functions in EU — all free; configure if a real EU user is in scope |
| No SLA on any free tier | Service outages possible | Acceptable for a capstone; mention in the report |
| File storage on Render disk is ephemeral | Container restart loses files | Move raw-HTML storage to R2 before any real article archive matters |

---

## 6. Migration Path Back to Azure (for the report)

The report can position this deployment as "the free-tier equivalent of an Azure-native build." Every piece swaps at the adapter / connection-string layer — application code (FastAPI, SQLAlchemy, the OAuth flow) is unchanged.

| This deployment | Azure equivalent | Effort to swap |
|---|---|---|
| Render | Azure Container Apps | new Dockerfile target + connection strings |
| Vercel | Azure Static Web Apps | rebuild + redeploy |
| Neon | Azure PostgreSQL Flexible Server | connection string |
| Free Entra tenant | Microsoft corporate Entra tenant | App Registration in the corporate directory; same OIDC code |
| OpenAI direct | Azure OpenAI Service | endpoint + auth header (SDK largely compatible) |
| Resend | Azure Communication Services | swap email-client adapter |
| GitHub Actions cron | Container Apps Job (cron) | rewrite the workflow as a job spec |
| `.env` / Render env vars | Azure Key Vault | adapter only |

---

## 7. What's Already in the Code for This

| File | What it does |
|---|---|
| [backend/Dockerfile](../backend/Dockerfile) | Builds the Python 3.12 image Render deploys |
| [render.yaml](../render.yaml) | Blueprint — Render reads this and provisions everything |
| [backend/.env.example](../backend/.env.example) | Full env-var reference with per-service setup steps |
| [backend/app/config.py](../backend/app/config.py) | Typed settings (incl. `allowed_origins`, `openai_api_key`, `resend_api_key`) |
| [backend/app/main.py](../backend/app/main.py) | CORS now reads `allowed_origins` in prod |

---

## 8. Open Questions

| # | Question | Owner |
|---|---|---|
| HOST-1 | Region — Oregon (default in render.yaml) or Frankfurt for EU latency? | Backend Dev 1 |
| HOST-2 | Keep Render free + cold-start pinger, or pay $7/mo for the demo? | Team |
| HOST-3 | Custom domain (cosmetic) or stay on `*.onrender.com` / `*.vercel.app`? | Backend Dev 1 |
| HOST-4 | When to switch raw-HTML storage from local disk to Cloudflare R2 | Data Engineer 1 |
