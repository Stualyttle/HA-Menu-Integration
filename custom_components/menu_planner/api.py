"""HTTP client for the Menu Planner add-on internal API (port 8098, token protected)."""

from __future__ import annotations

from datetime import date
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT, TOKEN_HEADER


class MenuPlannerError(Exception):
    """An add-on call failed. `code` is the error envelope code or a local code."""

    def __init__(self, code: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


async def _error_from_response(response: aiohttp.ClientResponse) -> MenuPlannerError:
    """Build an error from a non-2xx response (error envelope, or the 401 `detail` body)."""
    if response.status == 401:
        return MenuPlannerError("invalid_auth", "Invalid or missing add-on token", 401)

    try:
        body = await response.json(content_type=None)
    except (aiohttp.ClientError, ValueError):
        body = None

    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return MenuPlannerError(
            str(error.get("code", "http_error")),
            str(error.get("message", f"HTTP {response.status}")),
            response.status,
        )
    return MenuPlannerError("http_error", f"HTTP {response.status}", response.status)


class MenuPlannerClient:
    """Thin proxy over the add-on API. It holds no state and adds no behaviour."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int, token: str) -> None:
        self._session = session
        self._base_url = f"http://{host}:{port}"
        self._headers = {TOKEN_HEADER: token}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                if response.status >= 400:
                    raise await _error_from_response(response)
                if response.status == 204:
                    return None
                return await response.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError) as err:
            raise MenuPlannerError(
                "cannot_connect", "Cannot reach the Menu Planner add-on"
            ) from err

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/api/health")

    async def sync(self, language: str, time_zone: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/sync", json={"language": language, "time_zone": time_zone}
        )

    async def get_menu(self, params: dict[str, str] | None = None) -> Any:
        return await self._request("GET", "/api/menu", params=params)

    async def get_menu_today(self) -> dict[str, Any]:
        return await self._request("GET", "/api/menu/today")

    async def log_eaten(self, day: date) -> Any:
        return await self._request("POST", f"/api/menu/{day.isoformat()}/eaten")

    async def get_swap_suggestions(self, day: date) -> Any:
        return await self._request("GET", f"/api/menu/{day.isoformat()}/swap")

    async def apply_swap(self, day: date, dinner_id: int) -> Any:
        return await self._request(
            "POST", f"/api/menu/{day.isoformat()}/swap", json={"dinner_id": dinner_id}
        )

    async def get_stock(self, *, unanswered_first: bool = True) -> Any:
        return await self._request(
            "GET",
            "/api/stock",
            params={"unanswered_first": "true" if unanswered_first else "false"},
        )

    async def set_stock(self, item_id: int, in_stock: bool | None) -> Any:
        return await self._request("PUT", f"/api/stock/{item_id}", json={"in_stock": in_stock})

    async def get_warnings(self) -> Any:
        return await self._request("GET", "/api/warnings")
