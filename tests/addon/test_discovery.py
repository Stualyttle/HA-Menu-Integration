"""Tests for the Supervisor discovery payload and retry behaviour."""

import httpx

from app.discovery import SERVICE_NAME, announce, build_discovery_payload


def test_payload_shape() -> None:
    payload = build_discovery_payload("abc-menu-planner", 8098, "tok")
    assert payload == {
        "service": SERVICE_NAME,
        "config": {"host": "abc-menu-planner", "port": 8098, "token": "tok"},
    }


async def test_announce_returns_uuid_and_sends_bearer(monkeypatch) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["json"] = request.read().decode()
        return httpx.Response(200, json={"result": "ok", "data": {"uuid": "u-1"}})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr("app.discovery.httpx.AsyncClient", client_factory)

    uuid = await announce("host-x", 8098, "tok", supervisor_token="sup", retry_delays=())
    assert uuid == "u-1"
    assert seen["auth"] == "Bearer sup"
    assert '"service": "menu_planner"' in seen["json"] or '"service":"menu_planner"' in seen["json"]


async def test_announce_gives_up_without_supervisor_token() -> None:
    assert await announce("h", 1, "t", supervisor_token="", retry_delays=()) is None
