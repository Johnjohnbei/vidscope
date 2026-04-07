"""Media storage port.

The domain never touches the filesystem directly. Every video file, audio
file, and frame image goes through the :class:`MediaStorage` port, which
is backed today by :class:`LocalMediaStorage` (filesystem under the
configured data directory) and tomorrow, if needed, by any blob store.

Keys
----

Storage keys are slash-separated strings, cross-platform. The canonical
layout is::

    videos/{video_id}/media.{ext}
    videos/{video_id}/audio.{ext}
    videos/{video_id}/frames/{index:04d}.jpg

Adapters translate keys to physical locations. Callers never assemble paths
manually — they call :meth:`MediaStorage.build_key` helpers on the adapter
if needed, or pass keys through from prior rows stored in the DB.

Operations
----------

- :meth:`store` — copy a source file into storage under ``key``. Returns
  the key (possibly normalized). Overwrites any existing object at the
  same key atomically where possible.
- :meth:`resolve` — return a concrete :class:`Path` pointing at the stored
  object. Adapters that are not filesystem-backed must raise
  :class:`StorageError` (or expose an :meth:`open` method instead).
- :meth:`exists` — ``True`` if an object is stored under ``key``.
- :meth:`delete` — remove an object by key. Idempotent: missing keys are
  a no-op, not an error.
- :meth:`open` — return a readable binary file handle. Callers are
  responsible for closing it.
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable

__all__ = ["MediaStorage"]


@runtime_checkable
class MediaStorage(Protocol):
    """Abstract store for video media files and extracted frames.

    Implementations should be safe to call from any layer that has been
    handed the port through dependency injection. Implementations must
    translate all I/O failures into
    :class:`~vidscope.domain.errors.StorageError`.
    """

    def store(self, key: str, source_path: Path) -> str:
        """Copy ``source_path`` into storage under ``key`` and return the
        stored key.

        Raises
        ------
        StorageError
            When the copy fails for any reason (missing source, permission
            denied, disk full, etc.).
        """
        ...

    def resolve(self, key: str) -> Path:
        """Return a concrete :class:`Path` for ``key``.

        Filesystem-backed adapters return the real on-disk location. Object
        stores should raise :class:`StorageError` — callers that need byte
        access should call :meth:`open` instead.
        """
        ...

    def exists(self, key: str) -> bool:
        """Return ``True`` if ``key`` exists in storage."""
        ...

    def delete(self, key: str) -> None:
        """Remove ``key`` from storage. Idempotent: no error if missing."""
        ...

    def open(self, key: str) -> BinaryIO:
        """Return a readable binary file handle for ``key``.

        Callers must close the returned handle. Raises
        :class:`StorageError` if the key does not exist.
        """
        ...
