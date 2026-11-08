"""Sync: the Home Assistant side reports its language and time zone (docs/API.md "Sync")."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import StoresDep
from app.api.planning import SYNCED_LANGUAGE_KEY, SYNCED_TIME_ZONE_KEY, add_on_time_zone
from app.api.schemas import SyncIn, SyncOut

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("", response_model=SyncOut)
async def sync(body: SyncIn, stores: StoresDep) -> SyncOut:
    stores.settings.update(
        {SYNCED_LANGUAGE_KEY: body.language, SYNCED_TIME_ZONE_KEY: body.time_zone}
    )
    return SyncOut(
        language=body.language,
        time_zone=body.time_zone,
        timezone_mismatch=body.time_zone != add_on_time_zone(),
    )
