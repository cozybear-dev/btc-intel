# syntax=docker/dockerfile:1
# btc-intel: one process serving the API and the built web workbench (see compose.yaml).

FROM node:22-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1
# keep the repo layout under /app: the editable install resolves REPO_ROOT (catalog, docs/kb, web/dist) to /app
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/btcintel ./btcintel
RUN uv sync --frozen --no-dev
COPY catalog /app/catalog
COPY docs/kb /app/docs/kb
COPY --from=web /app/web/dist /app/web/dist

# uid 1000 matches the usual owner of the bind-mounted ./data
RUN useradd --uid 1000 --create-home btcintel && mkdir -p /app/data && chown btcintel:btcintel /app/data
USER btcintel
ENV PATH=/app/backend/.venv/bin:$PATH BTCINTEL_HOST=0.0.0.0 BTCINTEL_PORT=8765
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=3)"]
ENTRYPOINT ["btcintel"]
CMD ["serve"]
