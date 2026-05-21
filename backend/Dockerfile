# Backend container image.
#
# Used by Render for the deployed API (via render.yaml at the repo root).
# Also runnable locally:
#   docker build -t tech-intel-api -f backend/Dockerfile backend/
#   docker run -p 8000:8000 --env-file backend/.env tech-intel-api
#
# The root Dockerfile at the repo root is for the data engineering
# Jupyter environment — separate concern.

FROM python:3.12-slim

# Don't write .pyc files; flush stdout immediately so Render's log stream
# sees output in real time.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps. `libpq` is required by psycopg at runtime; `curl` is handy
# for the healthcheck.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first so the layer is cached when only code changes.
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application code.
COPY app/ ./app/

# Render injects PORT at runtime; default to 8000 for local docker run.
# Shell form so $PORT is expanded by sh — JSON CMD doesn't expand env vars.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
