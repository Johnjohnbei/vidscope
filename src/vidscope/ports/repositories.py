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
    Frame,
    PipelineRun,
    Platform,
    PlatformId,
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

    def upsert_by_platform_id(self, video: Video) -> Video:
        """Insert ``video`` or update the existing row matching
        ``(platform, platform_id)``. Returns the resulting entity with
        ``id`` populated. Idempotent."""
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
