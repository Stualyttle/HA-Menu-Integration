"""Websocket commands proxy to the add-on and pass its errors through."""

from __future__ import annotations

from custom_components.menu_planner import async_setup
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from .conftest import (
    BASE,
    DINNER_TODAY,
    STOCK,
    TODAY,
    WARNINGS,
    async_setup_entry_for_test,
    envelope,
    register_addon,
)


async def _ws(hass: HomeAssistant, hass_ws_client: WebSocketGenerator, payload: dict) -> dict:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(payload)
    return await client.receive_json()


async def test_today_returns_add_on_payload(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, addon: AiohttpClientMocker
) -> None:
    await async_setup_entry_for_test(hass)

    msg = await _ws(hass, hass_ws_client, {"type": "menu_planner/today"})

    assert msg["success"] is True
    assert msg["result"] == DINNER_TODAY


async def test_stock_defaults_unanswered_first(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, addon: AiohttpClientMocker
) -> None:
    await async_setup_entry_for_test(hass)

    msg = await _ws(hass, hass_ws_client, {"type": "menu_planner/stock"})

    assert msg["success"] is True
    assert msg["result"] == STOCK
    stock_calls = [c for c in addon.mock_calls if "/api/stock?" in str(c[1])]
    assert stock_calls
    assert "unanswered_first=true" in str(stock_calls[-1][1]).lower()


async def test_window_returns_days_with_warnings(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, addon: AiohttpClientMocker
) -> None:
    await async_setup_entry_for_test(hass)

    msg = await _ws(hass, hass_ws_client, {"type": "menu_planner/window"})

    assert msg["success"] is True
    assert msg["result"]["days"][0] == DINNER_TODAY
    assert msg["result"]["days"][1]["warnings"] == [WARNINGS[0]["code"]]


async def test_window_passes_from_and_to(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, addon: AiohttpClientMocker
) -> None:
    await async_setup_entry_for_test(hass)

    msg = await _ws(
        hass,
        hass_ws_client,
        {"type": "menu_planner/window", "from": "2026-05-01", "to": "2026-05-07"},
    )

    assert msg["success"] is True
    window_calls = [c for c in addon.mock_calls if "/api/menu?" in str(c[1])]
    url = str(window_calls[-1][1])
    assert "from=2026-05-01" in url
    assert "to=2026-05-07" in url


async def test_stock_set_puts_and_returns_result(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, addon: AiohttpClientMocker
) -> None:
    await async_setup_entry_for_test(hass)

    msg = await _ws(
        hass,
        hass_ws_client,
        {"type": "menu_planner/stock/set", "item_id": 3, "in_stock": True},
    )

    assert msg["success"] is True
    put_calls = [c for c in addon.mock_calls if c[0].upper() == "PUT"]
    assert len(put_calls) == 1
    assert str(put_calls[0][1]) == f"{BASE}/api/stock/3"
    assert put_calls[0][2] == {"in_stock": True}


async def test_eaten_posts_to_date(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, addon: AiohttpClientMocker
) -> None:
    await async_setup_entry_for_test(hass)

    msg = await _ws(hass, hass_ws_client, {"type": "menu_planner/eaten", "date": TODAY})

    assert msg["success"] is True
    assert any(
        c[0].upper() == "POST" and str(c[1]) == f"{BASE}/api/menu/{TODAY}/eaten"
        for c in addon.mock_calls
    )


async def test_swap_suggestions_returns_add_on_payload(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, addon: AiohttpClientMocker
) -> None:
    await async_setup_entry_for_test(hass)

    msg = await _ws(
        hass,
        hass_ws_client,
        {"type": "menu_planner/swap/suggestions", "date": TODAY},
    )

    assert msg["success"] is True
    assert msg["result"] == {"suggestions": [{"dinner_id": 9}]}


async def test_swap_apply_posts_dinner_id(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, addon: AiohttpClientMocker
) -> None:
    await async_setup_entry_for_test(hass)

    msg = await _ws(
        hass,
        hass_ws_client,
        {"type": "menu_planner/swap/apply", "date": TODAY, "dinner_id": 9},
    )

    assert msg["success"] is True
    post_calls = [c for c in addon.mock_calls if c[0].upper() == "POST"]
    swap_calls = [c for c in post_calls if str(c[1]) == f"{BASE}/api/menu/{TODAY}/swap"]
    assert len(swap_calls) == 1
    assert swap_calls[0][2] == {"dinner_id": 9}


async def test_add_on_error_code_is_passed_through(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    register_addon(
        aioclient_mock,
        swap_apply={"status": 409, "json": envelope("conflict", "Day is locked")},
    )
    await async_setup_entry_for_test(hass)

    msg = await _ws(
        hass,
        hass_ws_client,
        {"type": "menu_planner/swap/apply", "date": TODAY, "dinner_id": 9},
    )

    assert msg["success"] is False
    assert msg["error"]["code"] == "conflict"
    assert msg["error"]["message"] == "Day is locked"


async def test_not_loaded_error_when_no_entry(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    assert await async_setup(hass, {})

    msg = await _ws(hass, hass_ws_client, {"type": "menu_planner/today"})

    assert msg["success"] is False
    assert msg["error"]["code"] == "not_loaded"


async def test_invalid_payload_is_rejected(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, addon: AiohttpClientMocker
) -> None:
    await async_setup_entry_for_test(hass)

    msg = await _ws(
        hass,
        hass_ws_client,
        {"type": "menu_planner/stock/set", "item_id": -4},
    )

    assert msg["success"] is False
    assert msg["error"]["code"] == "invalid_format"
    assert not [c for c in addon.mock_calls if c[0].upper() == "PUT"]


_TOMORROW_DAY = {
    "date": "2026-05-02",
    "status": "pinned",
    "dinner": {"id": 9, "items": [{"id": 3, "name": "Soup", "type": "main"}]},
    "kcal": 400,
    "balance": -30,
    "replaced_reason": None,
    "warnings": ["low_protein"],
}
