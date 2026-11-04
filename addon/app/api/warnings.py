"""Warnings: list unresolved and mark resolved (docs/API.md "Warnings")."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import StoresDep
from app.api.schemas import WarningOut

router = APIRouter(prefix="/api/warnings", tags=["warnings"])


@router.get("", response_model=list[WarningOut])
async def list_warnings(stores: StoresDep) -> list[WarningOut]:
    return [WarningOut.from_model(w) for w in await stores.warnings.list_open()]


@router.post(
    "/{warning_id}/resolve",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def resolve_warning(warning_id: int, stores: StoresDep) -> Response:
    await stores.warnings.resolve_warning(warning_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
