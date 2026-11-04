"""Supervisor discovery: announce the internal endpoint so the integration can find the add-on."""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

LOG = logging.getLogger(__name__)

SUPERVISOR_URL = "http://supervisor"
DISCOVERY_PATH = "/discovery"
SERVICE_NAME = "menu_planner"
RETRY_DELAYS = (2, 5, 15, 30)


def build_discovery_payload(host: str, port: int, token: str) -> dict:
    return {
        "service": SERVICE_NAME,
        "config": {"host": host, "port": port, "token": token},
    }


async def announce(
    host: str,
    port: int,
    token: str,
    *,
    supervisor_url: str = SUPERVISOR_URL,
    supervisor_token: str | None = None,
    retry_delays: tuple[float, ...] = RETRY_DELAYS,
) -> str | None:
    """POST discovery to the Supervisor. Returns the discovery uuid, or None if it gave up."""
    supervisor_token = supervisor_token or os.environ.get("SUPERVISOR_TOKEN", "")
    if not supervisor_token:
        LOG.warning("SUPERVISOR_TOKEN not set; skipping discovery")
        return None

    payload = build_discovery_payload(host, port, token)
    headers = {"Authorization": f"Bearer {supervisor_token}"}
    attempts = (0, *retry_delays)

    async with httpx.AsyncClient(base_url=supervisor_url, timeout=10) as client:
        for attempt, delay in enumerate(attempts, start=1):
            if delay:
                await asyncio.sleep(delay)
            try:
                response = await client.post(DISCOVERY_PATH, json=payload, headers=headers)
                response.raise_for_status()
                uuid = response.json().get("data", {}).get("uuid")
                LOG.info("Discovery announced to Home Assistant (attempt %d)", attempt)
                return uuid
            except (httpx.HTTPError, ValueError) as err:
                LOG.warning("Discovery attempt %d failed: %s", attempt, err)
    LOG.error("Discovery gave up after %d attempts", len(attempts))
    return None
