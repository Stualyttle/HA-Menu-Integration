"""Shared fixtures for the Menu Planner integration tests.

The add-on is replaced by aiohttp mocks registered through `aioclient_mock`, so no
network access is needed. Every route the integration calls is registered here.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from custom_components.menu_planner.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

HOST = "192.168.1.10"
PORT = 8098
TOKEN = "s3cret-token"
BASE = f"http://{HOST}:{PORT}"
ENTRY_DATA = {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN}

FROZEN_NOW = "2026-05-01 12:00:00+00:00"
TODAY = "2026-05-01"
TOMORROW = "2026-05-02"

DINNER_TODAY = {
    "date": TODAY,
    "status": "planned",
    "dinner": {
        "id": 7,
        "items": [
            {"id": 1, "name": "Pasta", "type": "main"},
            {"id": 2, "name": "Salad", "type": "side"},
        ],
    },
    "kcal": 650,
    "balance": 120,
    "replaced_reason": None,
    "warnings": [],
}

DINNER_TOMORROW = {
    "date": TOMORROW,
    "status": "pinned",
    "dinner": {"id": 9, "items": [{"id": 3, "name": "Soup", "type": "main"}]},
    "kcal": 400,
    "balance": -30,
    "replaced_reason": None,
    "warnings": ["low_protein"],
}

WARNINGS = [{"id": 5, "code": "low_protein", "date": TOMORROW, "resolved": False}]

STOCK = [
    {"id": 3, "name": "Milk", "in_stock": False},
    {"id": 4, "name": "Rice", "in_stock": True},
    {"id": 5, "name": "Flour", "in_stock": False},
]


def envelope(code: str, message: str) -> dict[str, Any]:
    """Build an add-on error envelope."""
    return {"error": {"code": code, "message": message, "details": None}}


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow HA to load the custom_components/menu_planner package."""


_MENU_RANGE_RE = re.compile(rf"^{re.escape(BASE)}/api/menu(\?.*)?$")
_STOCK_RE = re.compile(rf"^{re.escape(BASE)}/api/stock\?")
_STOCK_ITEM_RE = re.compile(rf"^{re.escape(BASE)}/api/stock/\d+$")
_EATEN_RE = re.compile(rf"^{re.escape(BASE)}/api/menu/[^/]+/eaten$")
_SWAP_RE = re.compile(rf"^{re.escape(BASE)}/api/menu/[^/]+/swap$")


def register_addon(mocker: AiohttpClientMocker, **overrides: dict[str, Any]) -> None:
    """Register every add-on route the integration calls.

    ``overrides`` maps a route key (sync, menu_today, menu_range, warnings, stock, swap,
    swap_apply, eaten, stock_set) to aioclient_mock kwargs such as ``{"status": 409,
    "json": ...}``. The first matching route wins, so call ``mocker.clear_requests()``
    before re-registering a route in a test.
    """
    routes: dict[str, tuple[str, Any, dict[str, Any]]] = {
        "sync": ("post", f"{BASE}/api/sync", {"json": {"timezone_mismatch": False}}),
        "menu_today": ("get", f"{BASE}/api/menu/today", {"json": DINNER_TODAY}),
        "menu_range": (
            "get",
            _MENU_RANGE_RE,
            {"json": {"days": [DINNER_TODAY, DINNER_TOMORROW]}},
        ),
        "warnings": ("get", f"{BASE}/api/warnings", {"json": WARNINGS}),
        "stock": ("get", _STOCK_RE, {"json": STOCK}),
        "swap": ("get", _SWAP_RE, {"json": {"suggestions": [{"dinner_id": 9}]}}),
        "swap_apply": ("post", _SWAP_RE, {"json": {}}),
        "eaten": ("post", _EATEN_RE, {"json": {}}),
        "stock_set": ("put", _STOCK_ITEM_RE, {"json": {}}),
    }
    for key, (method, url, defaults) in routes.items():
        kwargs = {**defaults, **overrides.get(key, {})}
        mocker.request(method.upper(), url, **kwargs)


@pytest.fixture
def addon(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Register happy-path add-on routes."""
    register_addon(aioclient_mock)
    return aioclient_mock


@pytest.fixture
def frozen_now(freezer) -> None:
    """Freeze the clock so 'today' and 'tomorrow' are deterministic."""
    freezer.move_to(FROZEN_NOW)


async def async_setup_entry_for_test(hass: HomeAssistant) -> MockConfigEntry:
    """Create and set up a Menu Planner entry against the mocked add-on."""
    entry = MockConfigEntry(domain=DOMAIN, data=dict(ENTRY_DATA), unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
