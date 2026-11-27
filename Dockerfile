# syntax=docker/dockerfile:1
# VerifyLens: FastAPI API + built React UI + headless Chromium, one container.
#
#   docker compose up -d --build        (see docker-compose.yml and DEPLOY.md)
#
# Runs ONE uvicorn process on purpose: SQLite allows one writer and the rate
# limits are in memory. Do not add --workers or run several replicas.

# ---- 1. Build the React app ------------------------------------------------
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Same origin as the API, so a relative path. The build also type-checks.
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

# ---- 2. Runtime --------------------------------------------------------------
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Same layout as the repository: /app/backend (code) and /app/frontend/dist.
WORKDIR /app/backend

# Dependencies first so code changes don't reinstall them.
COPY backend/requirements-prod.txt .
# libatomic1: needed by Playwright's bundled Node driver before it can run
# "playwright install" (not included in the slim image).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libatomic1 \
 && pip install --root-user-action=ignore -r requirements-prod.txt \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/* /root/.cache

# Unprivileged user; /data holds the database, /backups the backup copies.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin verifylens \
 && mkdir -p /data /backups \
 && chown verifylens:verifylens /data /backups

COPY backend/app/ app/
COPY backend/security/ security/
COPY backend/scripts/ scripts/
COPY --from=frontend /build/dist /app/frontend/dist

# FORWARDED_ALLOW_IPS (read by uvicorn): trust X-Forwarded-For only from this
# reverse-proxy address, so rate limits see real client IPs. See DEPLOY.md.
ENV DATABASE_PATH=/data/search_history.db \
    BACKUP_DIR=/backups \
    HEADLESS=true \
    FORWARDED_ALLOW_IPS=127.0.0.1

USER verifylens
EXPOSE 8000
# VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
