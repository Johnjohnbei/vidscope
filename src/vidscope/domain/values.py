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
    "CollectionName",
    "ContentShape",
    "ContentType",
    "CreatorId",
    "Language",
    "MediaType",
    "Platform",
    "PlatformId",
    "PlatformUserId",
    "RunStatus",
    "SentimentLabel",
    "StageName",
    "TagName",
    "TrackingStatus",
    "VideoId",
]


VideoId = NewType("VideoId", int)
"""Database-assigned primary key for a :class:`Video`. Opaque to callers."""

PlatformId = NewType("PlatformId", str)
"""Platform-assigned stable identifier (e.g. YouTube video id, TikTok aweme
id). Combined with :class:`Platform` it is globally unique across sources."""

CreatorId = NewType("CreatorId", int)
"""Database-assigned primary key for a :class:`Creator`."""

PlatformUserId = NewType("PlatformUserId", str)
"""Platform-assigned stable user identifier (e.g. YouTube channel id ``UC_...``,
TikTok numeric id). Combined with :class:`Platform` it is globally unique."""

TagName = NewType("TagName", str)
"""Lowercase, stripped tag name. Normalisation enforced by the
TagRepository.get_or_create. Using NewType keeps the value distinct
from arbitrary str at the type-checker level (D3 M011 RESEARCH)."""

CollectionName = NewType("CollectionName", str)
"""User-facing collection name. Case-preserved (D3 M011 RESEARCH) —
unlike TagName, the DB stores "Concurrents" and "concurrents" as
distinct rows."""


class MediaType(StrEnum):
    """Physical media type of a post as determined at ingest time.

    Assigned by the downloader (M0XX) and carried through the pipeline
    so stages can branch without inspecting file extensions.

    - VIDEO  : standard audio+video container (.mp4, .webm, …)
    - IMAGE  : single static image (.jpg, .png, .webp, …)
    - CAROUSEL : multi-image or mixed-media post (Instagram sidecar)
    """

    VIDEO = "video"
    IMAGE = "image"
    CAROUSEL = "carousel"


class ContentShape(StrEnum):
    """Visual composition of a video based on face-count analysis (M008/R049).

    Assigned by :func:`~vidscope.pipeline.stages.visual_intelligence.classify_content_shape`.
    """

    UNKNOWN = "unknown"
    BROLL = "broll"
    TALKING_HEAD = "talking_head"
    MIXED = "mixed"


class ContentType(StrEnum):
    """Structural content type of a short-form video.

    Assigned by the analyzer layer (M010). UNKNOWN is a legitimate
    default — callers must not treat ``None`` and UNKNOWN as the same:
    ``None`` = pre-M010 analysis, ``UNKNOWN`` = M010 analyzer could not
    decide between the typed options.
    """

    TUTORIAL = "tutorial"
    REVIEW = "review"
    VLOG = "vlog"
    NEWS = "news"
    STORY = "story"
    OPINION = "opinion"
    COMEDY = "comedy"
    EDUCATIONAL = "educational"
    PROMO = "promo"
    UNKNOWN = "unknown"


class SentimentLabel(StrEnum):
    """Whole-video sentiment label (not per-sentence — explicitly out of
    scope per M010 ROADMAP).
    """

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class TrackingStatus(StrEnum):
    """User-assigned workflow status for a single video (M011/R056).

    Stored in the ``video_tracking`` table (separate from the immutable
    ``videos`` table per D033). Typical user flow:

        new -> reviewed -> saved|actioned|ignored -> archived

    No state machine is enforced — any transition is legal (D2 of M011
    RESEARCH, R032 single-user tool). The status is a label, not a gate.
    """

    NEW = "new"
    REVIEWED = "reviewed"
    SAVED = "saved"
    ACTIONED = "actioned"
    IGNORED = "ignored"
    ARCHIVED = "archived"


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
    STATS = "stats"
    METADATA_EXTRACT = "metadata_extract"
    VISUAL_INTELLIGENCE = "visual_intelligence"


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
