"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from btcintel import __version__
from btcintel.api import (
    routes_cases,
    routes_chain,
    routes_cluster,
    routes_kb,
    routes_tags,
    routes_trace,
)
from btcintel.chain.budget import BudgetExceeded
from btcintel.chain.errors import NotFound, SourceError
from btcintel.chain.source import ChainSource
from btcintel.config import Settings, load_settings
from btcintel.paths import REPO_ROOT
from btcintel.runtime import open_runtime

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "[::1]")
WILDCARD_BINDS = ("0.0.0.0", "::", "")


def allowed_hosts(bind_host: str) -> list[str]:
    """Host headers the API answers. Checking them blocks DNS rebinding: without it any web page the
    analyst visits could reach this unauthenticated, local-only API through the browser."""
    if bind_host in WILDCARD_BINDS:
        return ["*"]  # deliberately exposed on every interface (the CLI warns)
    host = f"[{bind_host}]" if ":" in bind_host and not bind_host.startswith("[") else bind_host
    return list(dict.fromkeys([*LOOPBACK_HOSTS, host]))


def create_app(settings: Settings | None = None, *, chain: ChainSource | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with open_runtime(settings, chain) as state:
            app.state.rt = state
            yield

    app = FastAPI(title="btc-intel", version=__version__, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts(settings.host))
    for module in (routes_chain, routes_trace, routes_cluster, routes_tags, routes_cases, routes_kb):
        app.include_router(module.router)

    @app.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(SourceError)
    async def source_error(request: Request, exc: SourceError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc), "incomplete": True})

    @app.exception_handler(BudgetExceeded)
    async def budget(request: Request, exc: BudgetExceeded) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc), "incomplete": True})

    dist = REPO_ROOT / "web" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app
