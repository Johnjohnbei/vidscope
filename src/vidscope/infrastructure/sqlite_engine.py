"""SQLAlchemy Engine factory for SQLite.

This module is the single place in the codebase that constructs a raw
SQLAlchemy :class:`Engine`. Everything else (adapters, tests, container)
calls :func:`build_engine` and treats the result as opaque.

Design notes
------------

- **FK enforcement.** SQLite has foreign-key support but it is disabled
  per connection by default. We attach a ``connect`` event listener that
  runs ``PRAGMA foreign_keys=ON`` on every new connection. Without this,
  every ``ON DELETE CASCADE`` in the schema is silently ignored — a
  classic SQLite footgun.
- **WAL mode.** We also enable ``PRAGMA journal_mode=WAL`` on connect so
  concurrent reads during a write don't block. Important as soon as we
  have `vidscope add` running alongside `vidscope status` or `vidscope
  search` on the same DB.
- **future=True.** Enables SQLAlchemy 2.0 style from the engine up. All
  new code in this project uses 2.0 style exclusively.
- **No metadata creation here.** Schema creation is an adapter concern
  (``vidscope.adapters.sqlite.schema.init_db``), not an infrastructure
  concern. This module only builds an engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event

__all__ = ["build_engine"]


def build_engine(db_path: Path) -> Engine:
    """Return a SQLAlchemy Engine bound to ``db_path``.

    The engine attaches a ``connect`` listener that enables
    ``foreign_keys`` and WAL journal mode on every new connection. The
    DB file itself is created lazily by SQLite on the first write.

    Parameters
    ----------
    db_path:
        Absolute path to the SQLite database file. The parent directory
        must already exist — the engine does not create it.
    """
    engine = create_engine(f"sqlite:///{db_path}", future=True)

    @event.listens_for(engine, "connect")
    def _apply_sqlite_pragmas(
        dbapi_connection: Any, connection_record: Any
    ) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()

    return engine
