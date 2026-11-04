"""SQLite persistence layer (Phase 2, owner A)."""

from .connection import Database
from .errors import DuplicateNameError, NotFoundError, SchemaVersionError
from .stores import Stores

__all__ = [
    "Database",
    "DuplicateNameError",
    "NotFoundError",
    "SchemaVersionError",
    "Stores",
]
