"""Entry point. Runs the internal (token) and ingress (no token) listeners in one process."""

from __future__ import annotations

import asyncio
import logging
import os
import socket

import uvicorn

from app.config import load_options, load_or_create_token
from app.discovery import announce
from app.main import create_app

INTERNAL_PORT = 8098
INGRESS_PORT = 8099
BIND_HOST = "0.0.0.0"  # Container network only; the port is not published on the host.


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _own_host() -> str:
    """Hostname other add-ons and Core use to reach this container."""
    return os.environ.get("HOSTNAME") or socket.gethostname()


async def _serve() -> None:
    options = load_options()
    _setup_logging(options.get("log_level", os.environ.get("LOG_LEVEL", "info")))
    log = logging.getLogger("menu_planner")

    token = load_or_create_token()

    internal_app = create_app(require_token=True, token=token)
    ingress_app = create_app(require_token=False)

    internal = uvicorn.Server(
        uvicorn.Config(internal_app, host=BIND_HOST, port=INTERNAL_PORT, log_config=None)
    )
    ingress = uvicorn.Server(
        uvicorn.Config(ingress_app, host=BIND_HOST, port=INGRESS_PORT, log_config=None)
    )

    async def _announce_when_ready() -> None:
        while not internal.started:
            await asyncio.sleep(0.2)
        await announce(_own_host(), INTERNAL_PORT, token)

    log.info("Listening: internal %d (token), ingress %d", INTERNAL_PORT, INGRESS_PORT)
    await asyncio.gather(internal.serve(), ingress.serve(), _announce_when_ready())


def run() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    run()
