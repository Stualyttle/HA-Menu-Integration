"""Options and token storage. Values are read from /data at startup."""

from __future__ import annotations

import json
import logging
import os
import secrets
from pathlib import Path

LOG = logging.getLogger(__name__)

TOKEN_FILENAME = "internal_token"
OPTIONS_FILENAME = "options.json"


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def load_options(path: Path | None = None) -> dict:
    """Read the add-on options written by the Supervisor. Returns {} if missing."""
    path = path or data_dir() / OPTIONS_FILENAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_or_create_token(directory: Path | None = None) -> str:
    """Return the internal API token, creating it on first start. Never logged."""
    directory = directory or data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    token_path = directory / TOKEN_FILENAME
    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    token_path.write_text(token, encoding="utf-8")
    os.chmod(token_path, 0o600)
    LOG.info("Generated new internal API token")
    return token
