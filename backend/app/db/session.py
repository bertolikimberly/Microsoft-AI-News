"""
Database engine + session factory.

`engine` is the connection pool — created once per process.
`SessionLocal` is the factory used to mint per-request sessions; see
app/deps.py for the FastAPI dependency that hands them out.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings


# One engine per process; it owns the connection pool. `pool_pre_ping` cheaply
# verifies each connection is alive before it leaves the pool, which masks
# transient drops from Azure Postgres / Neon idle-timeout behaviour.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


# A session represents a unit of work / a transaction. We don't autoflush
# (we control when SQL goes out) and don't expire instances after commit
# (so attribute access after commit doesn't trigger a re-fetch).
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
