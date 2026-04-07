"""Concrete adapter implementations.

Each sub-package under :mod:`vidscope.adapters` implements one or more
:mod:`vidscope.ports` Protocols against a specific external system:

- ``sqlite``: persistence via SQLAlchemy Core over SQLite
- ``fs``: filesystem-backed :class:`MediaStorage`
- future slices add ``ytdlp``, ``whisper``, ``ffmpeg``, ``heuristic``

Adapters are instantiated exclusively by
:mod:`vidscope.infrastructure.container`. import-linter forbids any
other layer from importing from this package.
"""

from __future__ import annotations
