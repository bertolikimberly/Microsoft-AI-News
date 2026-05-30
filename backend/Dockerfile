# Backend container image.
#
# Targets Azure Container Apps (consumption plan) and is also runnable
# locally. **Build context must be the repo root**, not the backend dir,
# because the image needs the sibling `llm_engineering/` tree and
# `sources.json` for the digest worker to import the pipeline:
#
#   docker build -t tech-intel-api -f backend/Dockerfile .
#   docker run -p 8000:8000 --env-file backend/.env tech-intel-api
#
# (The GitHub Actions workflow `.github/workflows/deploy-backend.yml`
# sets `context: .` for the same reason.)
#
# The root Dockerfile at the repo root is for the data engineering
# Jupyter environment — separate concern.

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

# Install Python deps first so the layer is cached when only code changes.
# Both requirements files are installed into the same image — the backend's
# digest worker imports the pipeline directly, so they share one venv.
WORKDIR /app
COPY backend/requirements.txt ./backend-requirements.txt
COPY llm_engineering/requirements.txt ./pipeline-requirements.txt
RUN pip install --no-cache-dir -r backend-requirements.txt -r pipeline-requirements.txt

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

# Copy the actual application code.
#   - backend/app  → /app/app             (FastAPI app)
#   - llm_engineering → /app/llm_engineering (pipeline imported via bootstrap)
#   - sources.json → /app/sources.json    (read by seed_tags + source registry)
COPY backend/app/ ./app/
COPY llm_engineering/ ./llm_engineering/
COPY sources.json ./sources.json

# Azure Container Apps and Render both honour $PORT; default to 8000
# locally. Shell form so $PORT is expanded by sh — JSON CMD does not.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
