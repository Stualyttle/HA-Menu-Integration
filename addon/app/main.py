"""FastAPI application factory. Internal and ingress listeners share this app."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth import TOKEN_HEADER, token_matches

API_VERSION = "0.1.0"


def create_app(*, require_token: bool, token: str | None = None) -> FastAPI:
    if require_token and not token:
        raise ValueError("require_token=True needs a token")

    app = FastAPI(title="Menu Planner", version=API_VERSION, docs_url=None, redoc_url=None)
    app.state.require_token = require_token
    app.state.token = token

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

    return app


class _Unauthorized(Exception):
    """Raised when the internal token is missing or wrong."""
