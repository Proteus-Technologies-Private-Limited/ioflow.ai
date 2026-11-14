# IOFlow application image: builds the React UI and serves it together with
# the API from one container on port 7001.
#
# Build from the repository root (docker-compose.yml does this):
#   docker build -f backend/Dockerfile -t ioflow .

# ---- Stage 1: build the frontend --------------------------------------------
FROM node:20-alpine AS ui

WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend + built UI --------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build tools for packages without wheels, plus the PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ unixodbc-dev postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Dependencies first, for layer caching
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Application code, example flows, and the built UI (served from ./static)
COPY backend/ /app/backend/
COPY flow-design-src/ /app/flow-design-src/
COPY --from=ui /ui/dist/ /app/backend/static/

# Non-root user; writable locations for logs, uploads and generated secrets
RUN useradd -m -u 1000 ioflow \
    && mkdir -p /app/logs /app/backend/uploads /var/lib/ioflow \
    && chmod +x /app/backend/docker-entrypoint.sh \
    && chown -R ioflow:ioflow /app /var/lib/ioflow
USER ioflow

EXPOSE 7001

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7001/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
CMD ["python", "run.py"]
