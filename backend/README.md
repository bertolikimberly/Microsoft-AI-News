# Backend — Tech Intelligence Newsletter

Python / FastAPI service implementing the API surface in
[../docs/api.md](../docs/api.md) and the auth model in
[../docs/auth.md](../docs/auth.md).

## What's here

A minimal, well-commented scaffold. The structure mirrors the API design;
each file has a header comment explaining its role. Most endpoints are
stubs that return `501 Not Implemented` — they exist so the routing
contract is real and so other team members can build against it.

## Run it locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # adjust if needed
uvicorn app.main:app --reload
```

Then visit:

- http://localhost:8000/docs — interactive OpenAPI (Swagger UI)
- http://localhost:8000/api/v1/health/live — should return 200

By default the app uses a local SQLite database (`dev.db`). Tables are
created on startup. No Postgres required to boot.

## Dev login (no Entra needed)

When `ENV=dev`, you can mint a JWT for a hardcoded test user without
running through the real OAuth flow:

```bash
curl -X POST http://localhost:8000/api/v1/auth/dev-login
```

Use the returned `access_token` as `Authorization: Bearer <token>` on
subsequent requests. This endpoint is disabled when `ENV=prod`.

## Layout (read in this order)

| Path | What |
|---|---|
| `app/config.py` | Typed settings loaded from env. |
| `app/db/` | SQLAlchemy engine, session, declarative base. |
| `app/models/` | ORM tables (users, preferences). |
| `app/schemas/` | Pydantic request/response shapes (the wire format). |
| `app/auth/jwt.py` | Mint + validate our session JWT. |
| `app/auth/entra.py` | Entra ID OIDC integration (stubbed). |
| `app/deps.py` | FastAPI dependencies: DB session, `current_user`. |
| `app/errors.py` | RFC 7807 error helpers. |
| `app/routers/` | HTTP endpoints, one file per resource group. |
| `app/main.py` | App entry point — wires everything together. |

## What's intentionally NOT here yet

- Alembic migrations — tables are created via `Base.metadata.create_all`
  on startup. Swap to Alembic before any prod deploy.
- Chat / digest / article routers — those resources will be added by
  Backend Dev 2 + once data is flowing.
- Tests — add `tests/` with `pytest` once the surface stabilizes.
- Real Entra OIDC flow — `auth/entra.py` is stubbed pending app
  registration (open question AUTH-1 in docs/auth.md §13).
