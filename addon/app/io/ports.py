"""Settings and template stores used by import and export.

ports.py has no Protocol for settings or the dinner template yet, so these are defined here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from app.models import ItemType


class SettingsStore(Protocol):
    async def get_settings(self) -> dict[str, Any]: ...

    async def update_settings(self, values: Mapping[str, Any]) -> None: ...


class TemplateStore(Protocol):
    async def get_template(self) -> dict[ItemType, int]: ...

    async def set_template(self, slots: Mapping[ItemType, int]) -> None: ...
