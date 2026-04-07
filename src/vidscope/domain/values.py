"""Value objects and enumerations for the VidScope domain.

This module is the innermost layer of the application: pure Python, stdlib
only, no project imports, no third-party runtime deps. Everything here must
be safe to import from any other layer without pulling in I/O, databases,
or external libraries.

Design rules
------------
- Enums use explicit string values so they can be persisted without
  translation tables and round-trip through JSON unchanged.
- ``NewType`` aliases carry semantic intent through the type checker without
  runtime cost: ``VideoId`` is an ``int``, ``PlatformId`` is a ``str``, but
  passing one where the other is expected is a mypy error.
- ``slots=True`` on dataclasses keeps memory small and prevents accidental
  attribute creation — frozen-by-default would be ideal but the stdlib
  doesn't let us combine ``slots=True`` with frozen on 3.12 for inherited
  dataclasses, so frozen is declared per-entity in ``entities.py``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import NewType

__all__ = [
    "Language",
    "Platform",
    "PlatformId",
    "RunStatus",
    "StageName",
    "VideoId",
]


VideoId = NewType("VideoId", int)
"""Database-assigned primary key for a :class:`Video`. Opaque to callers."""

PlatformId = NewType("PlatformId", str)
"""Platform-assigned stable identifier (e.g. YouTube video id, TikTok aweme
id). Combined with :class:`Platform` it is globally unique across sources."""


class Platform(StrEnum):
    """Source platform a video was ingested from.

    The string values are the canonical names used in the database and on
    the wire. New platforms are added by extending this enum — every code
    path that switches on ``Platform`` is then forced by the type checker
    to handle the new case.
    """

    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class Language(StrEnum):
    """Detected spoken language of a transcript.

    Limited to languages the default analyzer is validated against. Unknown
    or unsupported languages map to :attr:`UNKNOWN` rather than raising —
    the analyzer can still run its language-agnostic signals.
    """

    FRENCH = "fr"
    ENGLISH = "en"
    UNKNOWN = "unknown"


class StageName(StrEnum):
    """Discrete stage of the ingestion pipeline.

    Each stage writes exactly one :class:`PipelineRun` row. The order of
    this enum declaration is the canonical execution order.
    """

    INGEST = "ingest"
    TRANSCRIBE = "transcribe"
    FRAMES = "frames"
    ANALYZE = "analyze"
    INDEX = "index"


class RunStatus(StrEnum):
    """Lifecycle state of a single :class:`PipelineRun`.

    Transitions (enforced by :class:`vidscope.pipeline.runner.PipelineRunner`):

    - ``PENDING`` → ``RUNNING``: stage started executing
    - ``RUNNING`` → ``OK``: stage finished successfully
    - ``RUNNING`` → ``FAILED``: stage raised a typed domain error
    - ``PENDING``/``RUNNING`` → ``SKIPPED``: stage's ``is_satisfied`` check
      returned ``True`` so the stage was short-circuited (resume-from-failure)
    """

    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"
