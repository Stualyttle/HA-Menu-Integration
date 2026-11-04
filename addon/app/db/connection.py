"""SQLite connection wrapper with transactional helpers and versioned migrations."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .errors import SchemaVersionError
from .migrations import MIGRATIONS


class Database:
    """A single shared connection guarded by a re-entrant lock.

    The add-on runs two listeners in one process, so all access is serialised
    through ``_lock``. Explicit ``BEGIN IMMEDIATE`` transactions keep writes
    from two listeners from interleaving.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self.path,
            isolation_level=None,
            check_same_thread=False,
            timeout=10,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA busy_timeout = 10000")
        self._migrate()

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def query_all(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                if self._conn.in_transaction:
                    self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    @property
    def schema_version(self) -> int:
        row = self.query_one("PRAGMA user_version")
        assert row is not None
        return int(row[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _migrate(self) -> None:
        current = self.schema_version
        latest = len(MIGRATIONS)
        if current > latest:
            raise SchemaVersionError(
                f"database schema version {current} is newer than supported {latest}"
            )
        for target, migration in enumerate(MIGRATIONS[current:], start=current + 1):
            self._apply(target, migration)

    def _apply(self, target: int, migration: Callable[[sqlite3.Connection], None]) -> None:
        with self.transaction() as conn:
            migration(conn)
            conn.execute(f"PRAGMA user_version = {int(target)}")
