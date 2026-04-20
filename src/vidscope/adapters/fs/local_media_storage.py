"""Filesystem-backed :class:`MediaStorage`.

Keys are slash-separated strings (e.g. ``videos/42/media.mp4``). The
adapter translates them to OS paths under the configured root,
preserving the hierarchy with :class:`pathlib.Path` operations so both
forward and backward slashes work on Windows.

Design notes
------------
- Every key is validated against path traversal (``..``, absolute paths)
  before being used — the adapter refuses to read or write outside the
  configured root.
- :meth:`store` does an atomic copy: ``shutil.copy2`` into a ``.tmp``
  sidecar file then ``os.replace`` onto the target. On POSIX and on
  NTFS the ``os.replace`` call is atomic, so observers never see a
  half-written file.
- :meth:`delete` is idempotent: missing keys are a no-op, not an error,
  as the :class:`MediaStorage` contract requires.
"""

from __future__ import annotations

import contextlib
import os
import shutil
from pathlib import Path
from typing import BinaryIO

from vidscope.domain.errors import StorageError

__all__ = ["LocalMediaStorage"]


class LocalMediaStorage:
    """Filesystem implementation of :class:`MediaStorage`.

    Parameters
    ----------
    root:
        Absolute path to the directory under which keys are resolved.
        Must already exist. The infrastructure layer guarantees this by
        calling :func:`vidscope.infrastructure.config.get_config` before
        constructing the adapter.
    """

    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise StorageError(
                f"LocalMediaStorage root must be absolute, got {root!r}"
            )
        if not root.exists():
            raise StorageError(
                f"LocalMediaStorage root does not exist: {root}"
            )
        self._root = Path(os.path.realpath(root))

    # ------------------------------------------------------------------
    # MediaStorage protocol
    # ------------------------------------------------------------------

    def store(self, key: str, source_path: Path) -> str:
        """Atomically copy ``source_path`` under the key and return the
        normalized key."""
        if not source_path.exists():
            raise StorageError(
                f"cannot store: source {source_path} does not exist"
            )

        target = self._resolve_safe(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        tmp_target = target.with_suffix(target.suffix + ".tmp")
        try:
            shutil.copy2(str(source_path), str(tmp_target))
            os.replace(str(tmp_target), str(target))
        except OSError as exc:
            # Best-effort cleanup of the tmp sidecar before surfacing.
            if tmp_target.exists():
                with contextlib.suppress(OSError):
                    tmp_target.unlink()
            raise StorageError(
                f"failed to store {key!r} from {source_path}: {exc}",
                cause=exc,
            ) from exc

        return _normalize_key(key)

    def resolve(self, key: str) -> Path:
        """Return the on-disk path for ``key``. The file may or may not
        exist — callers must use :meth:`exists` to check."""
        return self._resolve_safe(key)

    def exists(self, key: str) -> bool:
        try:
            return self._resolve_safe(key).exists()
        except StorageError:
            # Invalid keys don't exist. Returning False instead of
            # raising keeps callers simple.
            return False

    def delete(self, key: str) -> None:
        """Remove the file at ``key``. Idempotent: no-op if missing."""
        try:
            target = self._resolve_safe(key)
        except StorageError:
            return
        if not target.exists():
            return
        try:
            target.unlink()
        except OSError as exc:
            raise StorageError(
                f"failed to delete {key!r}: {exc}", cause=exc
            ) from exc

    def open(self, key: str) -> BinaryIO:
        """Return a readable binary file handle for ``key``."""
        target = self._resolve_safe(key)
        if not target.exists():
            raise StorageError(f"cannot open: {key!r} does not exist")
        try:
            return target.open("rb")
        except OSError as exc:
            raise StorageError(
                f"failed to open {key!r}: {exc}", cause=exc
            ) from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_safe(self, key: str) -> Path:
        """Translate a slash-separated key to an absolute path under root.

        _normalize_key rejects absolute paths and '..' components.
        os.path.realpath is applied so that Windows MSIX junction points
        are resolved to the real filesystem location that external
        processes (ffmpeg, faster-whisper) can access.
        """
        normalized = _normalize_key(key)
        return Path(os.path.realpath(self._root / normalized))


def _normalize_key(key: str) -> str:
    """Reject absolute keys and traversal components, return the
    normalized slash-separated form."""
    if not key:
        raise StorageError("storage key must be non-empty")
    if key.startswith("/") or key.startswith("\\"):
        raise StorageError(f"storage key must be relative, got {key!r}")
    if ".." in key.replace("\\", "/").split("/"):
        raise StorageError(f"storage key must not contain '..', got {key!r}")
    # Convert any backslashes to forward slashes for the canonical form.
    return key.replace("\\", "/")
