"""VidScope infrastructure layer.

Composition root and environment-facing primitives: configuration,
SQLite engine factory, startup checks, and the :class:`Container` that
wires every concrete adapter to its port.

This is the outermost layer together with :mod:`vidscope.cli`. It is
the only layer allowed to import concrete adapters from
:mod:`vidscope.adapters` — every other layer binds to ports.
"""

from __future__ import annotations

from vidscope.infrastructure.config import Config, get_config, reset_config_cache
from vidscope.infrastructure.container import Container, SystemClock, build_container
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.infrastructure.startup import (
    CheckResult,
    check_ffmpeg,
    check_ytdlp,
    run_all_checks,
)

__all__ = [
    "CheckResult",
    "Config",
    "Container",
    "SystemClock",
    "build_container",
    "build_engine",
    "check_ffmpeg",
    "check_ytdlp",
    "get_config",
    "reset_config_cache",
    "run_all_checks",
]
