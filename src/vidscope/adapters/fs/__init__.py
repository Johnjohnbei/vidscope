"""Filesystem adapter package.

Provides :class:`LocalMediaStorage`, the default :class:`MediaStorage`
implementation that persists files under the configured data directory.
"""

from __future__ import annotations

from vidscope.adapters.fs.local_media_storage import LocalMediaStorage

__all__ = ["LocalMediaStorage"]
