"""Repository ports.

Every persistent aggregate has its own repository Protocol. Adapters in
``vidscope.adapters.sqlite`` implement these; the pipeline, the use cases,
and the unit of work bind to these Protocols only.

Design notes
------------

- Every method takes and returns **domain entities** (from
  :mod:`vidscope.domain`), not dicts or SQL rows. Adapters are responsible
  for the translation. This keeps the rest of the codebase ignorant of the
  backing store.
- Methods that create new rows return the domain entity with its
  database-assigned id populated. This is the only way the use case gets
  the id back — it must not peek into adapter internals.
- Read methods return ``None`` on miss, never raise. "Not found" is a
  normal outcome; raising would force every caller into ``try/except``.
- List methods return lists (not generators) with an explicit ``limit``
  argument. No unbounded queries anywhere in the codebase.
- ``upsert_by_platform_id`` on :class:`VideoRepository` guarantees
  idempotent ingest: re-running ``vidscope add <url>`` on a previously
  ingested video updates the existing row instead of raising on the
  ``platform_id`` unique constraint.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from vidscope.domain import (
    Analysis,
    Creator,
    CreatorId,
    Frame,
    PipelineRun,
    Platform,
    PlatformId,
    PlatformUserId,
    RunStatus,
    StageName,
    Transcript,
    Video,
    VideoId,
    WatchedAccount,
    WatchRefresh,
)

__all__ = [
    "AnalysisRepository",
    "CreatorRepository",
    "FrameRepository",
    "PipelineRunRepository",
    "TranscriptRepository",
    "VideoRepository",
    "WatchAccountRepository",
    "WatchRefreshRepository",
]


@runtime_checkable
class VideoRepository(Protocol):
    """Persistence for :class:`~vidscope.domain.entities.Video`.

    Adapters must enforce the ``(platform, platform_id)`` unique constraint
    via :meth:`upsert_by_platform_id`.
    """

    def add(self, video: Video) -> Video:
        """Insert ``video`` and return it with ``id`` populated.

        Raises
        ------
        StorageError
            If a row with the same ``platform_id`` already exists. Callers
            that need idempotence should use :meth:`upsert_by_platform_id`.
        """
        ...

    def upsert_by_platform_id(
        self, video: Video, creator: Creator | None = None
    ) -> Video:
        """Insert ``video`` or update the existing row matching
        ``(platform, platform_id)``. Returns the resulting entity with
        ``id`` populated. Idempotent.

        When ``creator`` is provided, the repository structurally enforces
        the write-through cache on ``videos.author`` (D-03): within the
        same SQL statement, ``video.author = creator.display_name`` and
        ``video.creator_id = int(creator.id)``. Application code MUST NOT
        write ``video.author`` directly — the repository is the single
        source of truth for the cache.

        When ``creator`` is None (the default), the existing behavior is
        preserved: ``video.author`` is taken from the ``video`` argument
        as-is, ``video.creator_id`` is left untouched. This keeps M001–M005
        callers working without modification until M006/S02 wires creators
        through the ingest stage.
        """
        ...

    def get(self, video_id: VideoId) -> Video | None:
        """Return the video with ``id == video_id``, or ``None``."""
        ...

    def get_by_platform_id(
        self, platform: Platform, platform_id: PlatformId
    ) -> Video | None:
        """Return the video matching ``(platform, platform_id)`` or ``None``."""
        ...

    def list_recent(self, limit: int = 20) -> list[Video]:
        """Return the ``limit`` most recently ingested videos, newest first."""
        ...

    def list_by_creator(
        self, creator_id: CreatorId, *, limit: int = 50
    ) -> list[Video]:
        """Return up to ``limit`` videos whose ``creator_id`` FK matches
        ``creator_id``, ordered most recently ingested first.

        Returns an empty list when no videos are linked to this creator.
        Callers should resolve the creator by handle first via
        :meth:`CreatorRepository.find_by_handle`.
        """
        ...

    def count_by_creator(self, creator_id: CreatorId) -> int:
        """Return the total number of videos linked to ``creator_id``."""
        ...

    def count(self) -> int:
        """Return the total number of videos in the store."""
        ...


@runtime_checkable
class TranscriptRepository(Protocol):
    """Persistence for :class:`~vidscope.domain.entities.Transcript`."""

    def add(self, transcript: Transcript) -> Transcript:
        """Insert ``transcript`` and return it with ``id`` populated."""
        ...

    def get_for_video(self, video_id: VideoId) -> Transcript | None:
        """Return the transcript for ``video_id`` or ``None`` if not yet
        produced."""
        ...


@runtime_checkable
class FrameRepository(Protocol):
    """Persistence for :class:`~vidscope.domain.entities.Frame`."""

    def add_many(self, frames: list[Frame]) -> list[Frame]:
        """Insert every frame in ``frames`` in order and return the list
        with ``id`` populated on each. Atomic: all-or-nothing within the
        calling transaction."""
        ...

    def list_for_video(self, video_id: VideoId) -> list[Frame]:
        """Return every frame for ``video_id`` ordered by ``timestamp_ms``."""
        ...


@runtime_checkable
class AnalysisRepository(Protocol):
    """Persistence for :class:`~vidscope.domain.entities.Analysis`."""

    def add(self, analysis: Analysis) -> Analysis:
        """Insert ``analysis`` and return it with ``id`` populated."""
        ...

    def get_latest_for_video(self, video_id: VideoId) -> Analysis | None:
        """Return the most recent analysis for ``video_id`` (useful when
        multiple providers have run) or ``None``."""
        ...


@runtime_checkable
class PipelineRunRepository(Protocol):
    """Persistence for :class:`~vidscope.domain.entities.PipelineRun`.

    Pipeline-run rows are the single source of truth for "what has the
    pipeline done". :meth:`list_recent` drives ``vidscope status``.
    """

    def add(self, run: PipelineRun) -> PipelineRun:
        """Insert ``run`` and return it with ``id`` populated."""
        ...

    def update_status(
        self,
        run_id: int,
        *,
        status: RunStatus,
        finished_at: object | None = None,
        error: str | None = None,
        video_id: VideoId | None = None,
    ) -> None:
        """Mutate the row identified by ``run_id`` to reflect a terminal
        status.

        Parameters
        ----------
        run_id:
            Primary key of the ``pipeline_runs`` row to update.
        status:
            New terminal status.
        finished_at:
            Wall-clock time the stage finished. Declared as
            :class:`object` to avoid importing :class:`datetime` into
            every caller type hint; adapters accept :class:`datetime`
            values and persist them as UTC.
        error:
            Optional error message. Only set when ``status`` is FAILED.
        video_id:
            Optional video id. The ingest stage initially writes a
            pipeline_runs row with ``video_id=None`` (because the
            videos row does not exist yet), then fills in the id
            via this kwarg once the stage has persisted the video.
        """
        ...

    def latest_for_video(self, video_id: VideoId) -> PipelineRun | None:
        """Return the most recent run for ``video_id`` or ``None``."""
        ...

    def latest_by_phase(
        self, video_id: VideoId, phase: StageName
    ) -> PipelineRun | None:
        """Return the most recent run for ``(video_id, phase)`` or ``None``.

        Used by :meth:`Stage.is_satisfied` checks to decide whether a stage
        can be skipped on resume-from-failure.
        """
        ...

    def list_recent(self, limit: int = 10) -> list[PipelineRun]:
        """Return the ``limit`` most recent runs across all videos, newest
        first. Drives ``vidscope status``."""
        ...

    def count(self) -> int:
        """Return the total number of pipeline runs."""
        ...


@runtime_checkable
class WatchAccountRepository(Protocol):
    """Persistence for :class:`WatchedAccount`.

    Accounts are identified by ``(platform, handle)``; the repository
    enforces uniqueness at the DB level via a compound UNIQUE
    constraint.
    """

    def add(self, account: WatchedAccount) -> WatchedAccount:
        """Insert ``account`` and return it with ``id`` populated.

        Raises StorageError if the ``(platform, handle)`` pair already
        exists.
        """
        ...

    def get(self, account_id: int) -> WatchedAccount | None:
        """Return the account by id, or None."""
        ...

    def get_by_handle(
        self, platform: Platform, handle: str
    ) -> WatchedAccount | None:
        """Return the account matching ``(platform, handle)``, or None."""
        ...

    def list_all(self) -> list[WatchedAccount]:
        """Return every registered account, ordered by created_at asc."""
        ...

    def remove(self, account_id: int) -> None:
        """Delete the account row. No-op if the id does not exist."""
        ...

    def update_last_checked(
        self, account_id: int, *, last_checked_at: object
    ) -> None:
        """Update the last_checked_at timestamp for the account.

        ``last_checked_at`` is declared as :class:`object` to avoid
        importing :class:`datetime` into caller type hints; adapters
        accept :class:`datetime` values and persist them as UTC.
        """
        ...


@runtime_checkable
class WatchRefreshRepository(Protocol):
    """Persistence for :class:`WatchRefresh` rows.

    One row per ``vidscope watch refresh`` invocation. Drives the
    ``vidscope watch history`` command (future) and debugging.
    """

    def add(self, refresh: WatchRefresh) -> WatchRefresh:
        """Insert a refresh row and return it with ``id`` populated."""
        ...

    def list_recent(self, limit: int = 10) -> list[WatchRefresh]:
        """Return the ``limit`` most recent refreshes, newest first."""
        ...


@runtime_checkable
class CreatorRepository(Protocol):
    """Persistence for :class:`~vidscope.domain.entities.Creator`.

    Identity anchors on ``(platform, platform_user_id)`` — the
    platform-stable id that survives account renames (per D-01).
    ``creators.id`` remains a surrogate autoincrement INT PK so FKs
    and CLI arguments stay ergonomic. ``handle`` is stored but NOT
    unique — the @-name may change, and the repository upserts
    through ``platform_user_id`` only.

    Adapters must enforce the compound UNIQUE constraint on
    ``(platform, platform_user_id)`` via :meth:`upsert`.
    """

    def upsert(self, creator: Creator) -> Creator:
        """Insert ``creator`` or update the existing row matching
        ``(platform, platform_user_id)``. Returns the resulting
        entity with ``id`` populated. Idempotent.

        Fields present on ``creator`` overwrite the existing row;
        ``created_at`` and ``first_seen_at`` are preserved on update
        (archaeology), ``last_seen_at`` is refreshed.
        """
        ...

    def get(self, creator_id: CreatorId) -> Creator | None:
        """Return the creator with ``id == creator_id``, or ``None``."""
        ...

    def find_by_platform_user_id(
        self, platform: Platform, platform_user_id: PlatformUserId
    ) -> Creator | None:
        """Return the creator matching ``(platform, platform_user_id)``
        or ``None``. This is the canonical identity lookup (per D-01)."""
        ...

    def find_by_handle(
        self, platform: Platform, handle: str
    ) -> Creator | None:
        """Return the creator matching ``(platform, handle)`` or ``None``.

        Handle is non-unique across time (rename history) but unique at
        any given moment per platform. On handle collisions (shouldn't
        happen in practice because handles are platform-enforced
        unique), return the most recently seen row.
        """
        ...

    def list_by_platform(
        self, platform: Platform, *, limit: int = 50
    ) -> list[Creator]:
        """Return up to ``limit`` creators on ``platform``, most
        recently seen first."""
        ...

    def list_by_min_followers(
        self, min_count: int, *, limit: int = 50
    ) -> list[Creator]:
        """Return up to ``limit`` creators with
        ``follower_count >= min_count``, highest-follower first. Rows
        where ``follower_count IS NULL`` are excluded."""
        ...

    def count(self) -> int:
        """Return the total number of creators in the store."""
        ...
