"""Shared FastAPI dependencies: the stores from app state and the planning window."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, Request

from app.db import Stores


def get_stores(request: Request) -> Stores:
    return request.app.state.stores  # type: ignore[no-any-return]


StoresDep = Annotated[Stores, Depends(get_stores)]


def local_today() -> date:
    """Today in the add-on time zone.

    Uses the TZ environment variable until the integration's sync supplies a zone.
    """
    zone: ZoneInfo | None = None
    name = os.environ.get("TZ")
    if name:
        try:
            zone = ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            zone = None
    return datetime.now(zone).date()


def planning_window(stores: Stores) -> tuple[date, date]:
    """Inclusive [today, today + window_days - 1]."""
    start = local_today()
    window_days = int(stores.settings.get_all()["window_days"])
    return start, start + timedelta(days=window_days - 1)
