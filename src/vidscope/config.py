"""Backward-compatibility shim for ``vidscope.config``.

The runtime configuration now lives in
:mod:`vidscope.infrastructure.config`. This module re-exports the public
names so any legacy import keeps working, but emits a
:class:`DeprecationWarning` to push callers toward the correct layer.

New code must import from ``vidscope.infrastructure.config`` directly.
"""

from __future__ import annotations

import warnings

from vidscope.infrastructure.config import Config, get_config, reset_config_cache

warnings.warn(
    "`vidscope.config` is a compatibility shim. "
    "Import `vidscope.infrastructure.config` instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Config", "get_config", "reset_config_cache"]
