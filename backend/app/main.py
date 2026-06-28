"""
FastAPI application entry point.

Wires routers under `/api/v1/...` (per docs/api.md §1 versioning decision),
sets up exception handlers, and creates DB tables on startup so the app
boots from scratch with no manual schema step.

Run locally:

    uvicorn app.main:app --reload

OpenAPI docs at http://localhost:8000/docs once running.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

# Importing `app.models` registers all ORM classes on `Base.metadata`,
# so `create_all` below sees every table. Without this import the tables
# don't get created.
from app import models  # noqa: F401
from app.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine  # noqa: F401 (engine used by create_all)
from app.errors import PROBLEM_CONTENT_TYPE, problem_response
from app.routers import articles as articles_router
from app.routers import auth as auth_router
from app.routers import digests as digests_router
from app.routers import health as health_router
from app.routers import internal as internal_router
from app.routers import me as me_router
from app.routers import folders as folders_router
from app.routers import saved as saved_router
from app.routers import sessions as sessions_router
from app.routers import sources as sources_router
from app.routers import tags as tags_router
from app.seed import seed_sources, seed_tags


async def _daily_ingest_loop():
    """Runs the ingest pipeline once per day at 6 AM UTC."""
    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=6, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        log.info("daily ingest scheduled in %.0f seconds (next run: %s)", wait_seconds, next_run.isoformat())
        await asyncio.sleep(wait_seconds)
        try:
            from app.workers import ingest_worker
            log.info("daily ingest starting")
            result = ingest_worker.run()
            log.info("daily ingest complete: %s", result)
        except Exception:
            log.exception("daily ingest task failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_tags(db)
        seed_sources(db)

    task = asyncio.create_task(_daily_ingest_loop())
    yield
    task.cancel()


app = FastAPI(
    title="Tech Intelligence Newsletter API",
    version="0.1.0",
    lifespan=lifespan,
)


# ─── CORS ─────────────────────────────────────────────────────────────────
# Dev: permit common frontend dev-server origins so FE1 can hit the API
# from `npm run dev` without proxy setup.
# Prod: only the origins in ALLOWED_ORIGINS env var (the Vercel deployment URL).
_DEV_ORIGINS = [
    "http://localhost:3000",   # Next.js default
    "http://localhost:3001",   # Next.js fallback when 3000 is taken
    "http://localhost:5173",   # Vite default
    "http://localhost:4173",   # Vite preview
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:5173",
]
_origins = _DEV_ORIGINS if settings.is_dev else settings.allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Idempotency-Key"],
)


# ─── Exception handlers ───────────────────────────────────────────────────
# Make every error a proper RFC 7807 response (docs/api.md §1).


@app.exception_handler(HTTPException)
async def http_exception_handler(_request, exc: HTTPException):
    """
    Convert FastAPI's HTTPException into an RFC 7807 body.

    `app.errors.problem(...)` returns HTTPException with a dict in `detail`;
    we just need to set the right content type and pass it through.
    """
    body = exc.detail if isinstance(exc.detail, dict) else {
        "type": "about:blank",
        "title": str(exc.detail),
        "status": exc.status_code,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        media_type=PROBLEM_CONTENT_TYPE,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc: RequestValidationError):
    """
    Pydantic validation failures → 422 problem doc.

    We surface the underlying errors so frontend can target offending fields.
    """
    return problem_response(
        status=422,
        title="Validation failed",
        detail=str(exc.errors()),
    )


# ─── Router wiring ────────────────────────────────────────────────────────
# All routers live under /api/v1 (docs/api.md §1 versioning).

API_PREFIX = "/api/v1"

app.include_router(health_router.router, prefix=API_PREFIX)
app.include_router(auth_router.router, prefix=API_PREFIX)
app.include_router(me_router.router, prefix=API_PREFIX)
app.include_router(tags_router.router, prefix=API_PREFIX)
app.include_router(sources_router.router, prefix=API_PREFIX)
app.include_router(articles_router.router, prefix=API_PREFIX)
app.include_router(digests_router.router, prefix=API_PREFIX)
app.include_router(folders_router.router, prefix=API_PREFIX)
app.include_router(saved_router.router, prefix=API_PREFIX)
app.include_router(sessions_router.router, prefix=API_PREFIX)
app.include_router(internal_router.router, prefix=API_PREFIX)
