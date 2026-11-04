"""FastAPI application factory. Internal and ingress listeners share this app."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import DATA_ROUTERS
from app.api.errors import install_error_handlers
from app.auth import TOKEN_HEADER, token_matches
from app.config import data_dir
from app.db import Stores

API_VERSION = "0.1.0"
DB_FILENAME = "menu_planner.db"


def create_app(
    *,
    require_token: bool,
    token: str | None = None,
    stores: Stores | None = None,
    db_path: Path | None = None,
) -> FastAPI:
    if require_token and not token:
        raise ValueError("require_token=True needs a token")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Injected stores belong to the caller, so they are not closed here.
        if stores is not None:
            yield
            return
        opened = Stores.open(db_path or data_dir() / DB_FILENAME)
        app.state.stores = opened
        try:
            yield
        finally:
            opened.close()

    app = FastAPI(
        title="Menu Planner",
        version=API_VERSION,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.require_token = require_token
    app.state.token = token
    if stores is not None:
        app.state.stores = stores
    install_error_handlers(app)

    async def check_token(request: Request) -> None:
        if not request.app.state.require_token:
            return
        provided = request.headers.get(TOKEN_HEADER)
        if not token_matches(provided, request.app.state.token):
            raise _Unauthorized()

    @app.exception_handler(_Unauthorized)
    async def _unauthorized_handler(_request: Request, _exc: _Unauthorized) -> JSONResponse:
        return JSONResponse({"detail": "invalid or missing token"}, status_code=401)

    @app.get("/api/health", dependencies=[Depends(check_token)])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": API_VERSION}

    for router in DATA_ROUTERS:
        app.include_router(router, dependencies=[Depends(check_token)])

    return app


class _Unauthorized(Exception):
    """Raised when the internal token is missing or wrong."""
