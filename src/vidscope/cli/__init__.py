"""VidScope command-line interface.

Thin Typer-based dispatch layer. Every subcommand is a wrapper around
a use case in :mod:`vidscope.application` — the CLI parses args, builds
a :class:`~vidscope.infrastructure.container.Container`, instantiates
the use case, calls ``execute``, and formats the typed result for
display via rich.

No business logic lives in this layer. The CLI is the only layer
allowed (together with :mod:`vidscope.infrastructure`) to reach into
the outer rings — everything else goes through the use cases.
"""

from __future__ import annotations

from vidscope.cli.app import app

__all__ = ["app"]
