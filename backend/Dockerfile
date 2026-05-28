# Backend container image.
#
# Targets Azure Container Apps (consumption plan) and is also runnable
# locally:
#   docker build -t tech-intel-api -f backend/Dockerfile backend/
#   docker run -p 8000:8000 --env-file backend/.env tech-intel-api
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
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformers embedding model into the image
# so the Container App can start serving requests without a multi-second
# download on first use. The model name must match settings.embedding_model
# (and the backend.app.config default).
ARG EMBEDDING_MODEL=all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

# Copy the actual application code.
COPY app/ ./app/

# Azure Container Apps and Render both honour $PORT; default to 8000
# locally. Shell form so $PORT is expanded by sh — JSON CMD does not.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
