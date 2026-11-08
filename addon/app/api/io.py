"""Import and export of the planner data as a versioned JSON document (docs/API.md "Import/export").

The domain services in app.io own validation and merge rules; this module only adapts the
synchronous settings and template stores to the async ports and maps errors to the envelope.
Secrets (usda_api_key) never appear in the export.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body
from pydantic import BaseModel

from app.api.deps import StoresDep
from app.api.errors import ApiError
from app.db import Stores
from app.domain.errors import PlannerConfigError
from app.io.export import ExportService
from app.io.importer import ImportService
from app.io.schema import ImportValidationError
from app.models import ItemType

router = APIRouter(prefix="/api", tags=["import-export"])


class ImportIn(BaseModel):
    document: dict[str, Any]
    include_settings: bool = False
    include_history: bool = False


class ImportPreviewOut(BaseModel):
    added: dict[str, int]
    skipped: dict[str, int]
    settings_available: bool


class _SettingsAdapter:
    """Async view of the synchronous settings store; secrets are not returned by get_all."""

    def __init__(self, stores: Stores) -> None:
        self._stores = stores

    async def get_settings(self) -> dict[str, Any]:
        return self._stores.settings.get_all()

    async def update_settings(self, values: dict[str, Any]) -> None:
        self._stores.settings.update(dict(values))


class _TemplateAdapter:
    """Async view of the synchronous template store, keyed by ItemType."""

    def __init__(self, stores: Stores) -> None:
        self._stores = stores

    async def get_template(self) -> dict[ItemType, int]:
        return {ItemType(key): value for key, value in self._stores.template.get().items()}

    async def set_template(self, counts: dict[ItemType, int]) -> None:
        self._stores.template.set({key.value: value for key, value in counts.items()})


def _exporter(stores: Stores) -> ExportService:
    return ExportService(
        stores.items,
        stores.categories,
        stores.rules,
        stores.nutrition,
        _TemplateAdapter(stores),
        _SettingsAdapter(stores),
    )


def _importer(stores: Stores) -> ImportService:
    return ImportService(
        stores.items,
        stores.categories,
        stores.rules,
        stores.nutrition,
        _TemplateAdapter(stores),
        _SettingsAdapter(stores),
    )


def _validation_error(exc: ImportValidationError) -> ApiError:
    return ApiError(
        400,
        "validation_error",
        "import document is invalid",
        {"errors": exc.errors},
    )


@router.get("/export")
async def export_data(stores: StoresDep) -> dict[str, Any]:
    return await _exporter(stores).export()


@router.post("/import/preview", response_model=ImportPreviewOut)
async def preview_import(
    stores: StoresDep, document: Annotated[dict[str, Any], Body()]
) -> dict[str, Any]:
    """Validates the document and reports what an import would add or skip. Writes nothing."""
    try:
        preview = await _importer(stores).preview(document)
    except ImportValidationError as exc:
        raise _validation_error(exc) from exc
    except PlannerConfigError as exc:
        raise ApiError(400, "validation_error", str(exc)) from exc
    return preview.as_dict()


@router.post("/import", response_model=ImportPreviewOut)
async def import_data(body: ImportIn, stores: StoresDep) -> dict[str, Any]:
    """Merges the document into existing data. Existing records are skipped, never overwritten."""
    if body.include_history:
        raise ApiError(400, "unsupported", "importing history is not supported")
    try:
        preview = await _importer(stores).apply(
            body.document,
            include_settings=body.include_settings,
        )
    except ImportValidationError as exc:
        raise _validation_error(exc) from exc
    except PlannerConfigError as exc:
        raise ApiError(400, "validation_error", str(exc)) from exc
    return preview.as_dict()
