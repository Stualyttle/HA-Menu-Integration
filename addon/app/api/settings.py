"""Settings and dinner template (docs/API.md "Settings, import, export")."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import StoresDep
from app.api.schemas import BalanceTargets, SettingsIn, SettingsOut, TemplateIn
from app.db import Stores
from app.domain.config import Template
from app.models import ItemType

router = APIRouter(tags=["settings"])


def _settings_out(stores: Stores) -> SettingsOut:
    values = stores.settings.get_all()
    return SettingsOut(
        window_days=int(values["window_days"]),
        household_size=int(values["household_size"]),
        repeat_gap_days=int(values["repeat_gap_days"]),
        balance_targets=BalanceTargets(**values["balance_targets"]),
        language=values["language"],
    )


@router.get("/api/settings", response_model=SettingsOut)
async def get_settings(stores: StoresDep) -> SettingsOut:
    return _settings_out(stores)


@router.put("/api/settings", response_model=SettingsOut)
async def update_settings(body: SettingsIn, stores: StoresDep) -> SettingsOut:
    changes: dict[str, object] = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if changes:
        stores.settings.update(changes)
    return _settings_out(stores)


@router.get("/api/template", response_model=TemplateIn)
async def get_template(stores: StoresDep) -> TemplateIn:
    return TemplateIn(**stores.template.get())


@router.put("/api/template", response_model=TemplateIn)
async def update_template(body: TemplateIn, stores: StoresDep) -> TemplateIn:
    counts = body.model_dump()
    Template({ItemType(slot): count for slot, count in counts.items()})
    stores.template.set(counts)
    return TemplateIn(**stores.template.get())
