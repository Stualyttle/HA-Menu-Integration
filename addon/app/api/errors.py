"""Error envelope and exception handlers shared by every data router.

Every error body has the shape ``{"error": {"code", "message", "details"}}`` (docs/API.md).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.db import DuplicateNameError, NotFoundError
from app.domain.errors import DayNotEditableError, PlannerConfigError, SwapRejectedError

_HTTP_CODES: dict[int, str] = {
    400: "validation_error",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "infeasible",
    500: "internal_error",
}


class ApiError(Exception):
    """An error with a stable code, rendered in the standard envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _respond(status_code: int, code: str, message: str, details: dict[str, Any] | None = None):
    return JSONResponse(error_body(code, message, details), status_code=status_code)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return _respond(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(NotFoundError)
    async def _not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        return _respond(404, "not_found", str(exc))

    @app.exception_handler(DuplicateNameError)
    async def _duplicate(_request: Request, exc: DuplicateNameError) -> JSONResponse:
        return _respond(409, "duplicate_name", str(exc))

    @app.exception_handler(PlannerConfigError)
    async def _planner_config(_request: Request, exc: PlannerConfigError) -> JSONResponse:
        return _respond(400, "validation_error", str(exc))

    @app.exception_handler(DayNotEditableError)
    async def _day_not_editable(_request: Request, exc: DayNotEditableError) -> JSONResponse:
        return _respond(409, "conflict", str(exc))

    @app.exception_handler(SwapRejectedError)
    async def _swap_rejected(_request: Request, exc: SwapRejectedError) -> JSONResponse:
        return _respond(409, "conflict", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in exc.errors()
        ]
        return _respond(400, "validation_error", "invalid request", {"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return _respond(exc.status_code, code, str(exc.detail))
