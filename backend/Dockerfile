# Backend container image.
#
# Build context must be the repo root so `sources.json` is accessible:
#
#   docker build -t tech-intel-api -f backend/Dockerfile .
#   docker run -p 8000:8000 --env-file backend/.env tech-intel-api
#
# (The GitHub Actions workflow `.github/workflows/deploy-backend.yml`
# sets `context: .` for the same reason.)
#
# The LLM pipeline is now part of backend/app/pipeline/ — no separate
# llm_engineering/ directory needs to be copied into the image.

FROM python:3.12-slim

# Don't write .pyc files; flush stdout immediately so log streams see
# output in real time. HF_HOME pins the sentence-transformers cache to a
# location we can pre-populate at build time so cold starts on Container
# Apps don't have to download ~80MB on first request.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache \
    TRANSFORMERS_OFFLINE=0

# System deps. `libpq` is required by psycopg at runtime; `curl` is handy
# for healthchecks and ad-hoc debugging.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformers embedding model into the image
# so the Container App can start serving requests without a multi-second
# download on first use. The model name must match settings.embedding_model
# (and the backend.app.config default).
#
# DISABLED: this step is brutally slow (~15 min) when cross-building amd64
# from an Apple Silicon Mac under emulation. Re-enable when builds run on
# native amd64 (e.g. via the GitHub Actions workflow at
# .github/workflows/deploy-backend.yml, which uses an ubuntu-latest runner).
# Without pre-download, the first request after scale-from-zero pays a
# ~5-10s model download cost; subsequent requests are unaffected.
# ARG EMBEDDING_MODEL=all-MiniLM-L6-v2
# RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

# Copy the application code.
#   - backend/app  → /app/app             (FastAPI app, includes pipeline/)
#   - sources.json → /app/sources.json    (read by seed_tags + source registry)
COPY backend/app/ ./app/
COPY sources.json ./sources.json

# Azure Container Apps and Render both honour $PORT; default to 8000
# locally. Shell form so $PORT is expanded by sh — JSON CMD does not.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
