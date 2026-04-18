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
    Collection,
    ContentType,
    Frame,
    PipelineRun,
    Platform,
    PlatformId,
    RunStatus,
    StageName,
    Tag,
    TrackingStatus,
    Transcript,
    Video,
    VideoId,
    VideoStats,
    VideoTracking,
    WatchedAccount,
    WatchRefresh,
)

__all__ = [
    "AnalysisRepository",
    "CollectionRepository",
    "FrameRepository",
    "PipelineRunRepository",
    "TagRepository",
    "TranscriptRepository",
    "VideoRepository",
    "VideoStatsRepository",
    "VideoTrackingRepository",
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

    def list_by_author(
        self, platform: Platform, handle: str, *, limit: int = 1000
    ) -> list[Video]:
        """Return videos whose ``author`` matches ``handle`` on ``platform``.

        Used by :class:`RefreshStatsForWatchlistUseCase` (M009/S03) to list
        all known videos for a watched account without a creator_id FK.
        Capped at ``limit`` (default 1000) to avoid unbounded scans.
        """
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

    def list_by_filters(
        self,
        *,
        content_type: ContentType | None = None,
        min_actionability: float | None = None,
        is_sponsored: bool | None = None,
        limit: int = 1000,
    ) -> list[VideoId]:
        """Return video ids whose LATEST analysis matches every non-None filter.

        The match semantics:

        - ``content_type``: latest analysis.content_type equals the given enum.
          NULL stored values are excluded.
        - ``min_actionability``: latest analysis.actionability is not NULL AND >= the given float.
        - ``is_sponsored``: latest analysis.is_sponsored strictly equals the bool. NULL excluded.

        Filters are combined with AND. Missing filters (``None``) are ignored.
        Videos with no analysis row at all are excluded from the result.
        ``limit`` caps the number of video ids returned (default 1000) to
        avoid unbounded scans. Results ordered by analysis.created_at DESC.
        """
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
class VideoStatsRepository(Protocol):
    """Append-only persistence for :class:`VideoStats` snapshots.

    Each row represents one point-in-time measurement of engagement
    counters. Rows are never updated — new measurements create new rows.
    The UNIQUE constraint on ``(video_id, captured_at)`` at second
    resolution silently ignores duplicate probes within the same second
    (D-01, D031 append-only invariant).
    """

    def append(self, stats: VideoStats) -> VideoStats:
        """Insert ``stats`` and return it with ``id`` populated.

        If a row with the same ``(video_id, captured_at)`` already exists,
        the insert is silently ignored (ON CONFLICT DO NOTHING) and the
        original row is returned. This keeps the operation idempotent.
        """
        ...

    def list_for_video(self, video_id: VideoId, *, limit: int = 100) -> list[VideoStats]:
        """Return up to ``limit`` snapshots for ``video_id``, oldest first.

        Ordered by ``captured_at`` ascending so callers can directly feed
        the result to :func:`~vidscope.domain.metrics.views_velocity_24h`.
        """
        ...

    def latest_for_video(self, video_id: VideoId) -> VideoStats | None:
        """Return the most recent snapshot for ``video_id``, or ``None``."""
        ...

    def has_any_for_video(self, video_id: VideoId) -> bool:
        """Return ``True`` if at least one snapshot exists for ``video_id``."""
        ...

    def list_videos_with_min_snapshots(
        self, min_snapshots: int = 2, *, limit: int = 200
    ) -> list[VideoId]:
        """Return ids of videos that have at least ``min_snapshots`` rows.

        Used by the velocity-computation use case (S04) to identify
        videos eligible for trend analysis.
        """
        ...

    def rank_candidates_by_delta(
        self,
        *,
        since: "datetime",
        platform: "Platform | None" = None,
        limit: int = 100,
    ) -> list[VideoId]:
        """Return video_ids sorted by SQL-approximated view-delta on the window.

        Applies GROUP BY video_id + HAVING count >= 2 + LIMIT at the SQL
        level per D-04 scalability. The use case then computes the exact
        metrics on the returned subset via metrics.py pure-domain functions.

        Parameters
        ----------
        since:
            Cutoff datetime — only snapshots at or after this timestamp
            are included in the delta computation.
        platform:
            Optional filter. When provided, only videos belonging to that
            platform are returned. The join is done in SQL (not Python).
        limit:
            Maximum number of candidate video_ids to return. Applied at
            the SQL level (D-04) so no full table scan in Python.

        Returns
        -------
        list[VideoId]
            Video ids ordered by approximate view delta descending (largest
            growth first). May be smaller than ``limit`` when fewer videos
            qualify.
        """
        ...


@runtime_checkable
class VideoTrackingRepository(Protocol):
    """Persistence for :class:`VideoTracking` rows (M011/R056).

    One row per video — UNIQUE on ``video_id``. ``upsert`` is the only
    write method: creating and updating share the same signature, so
    callers don't need to decide between INSERT/UPDATE (D1 M011 RESEARCH).
    """

    def upsert(self, tracking: VideoTracking) -> VideoTracking:
        """Insert or update the tracking row for ``tracking.video_id``.

        Uses ``ON CONFLICT(video_id) DO UPDATE`` so a second call for the
        same ``video_id`` atomically replaces ``status``, ``starred``,
        ``notes``, and ``updated_at``. Returns the persisted entity with
        ``id``, ``created_at``, ``updated_at`` populated.
        """
        ...

    def get_for_video(self, video_id: VideoId) -> VideoTracking | None:
        """Return the tracking row for ``video_id`` or ``None`` if absent.

        Sparse table semantics: absence means "no user workflow yet",
        not "implicit new status".
        """
        ...

    def list_by_status(
        self, status: TrackingStatus, *, limit: int = 1000
    ) -> list[VideoTracking]:
        """Return every tracking row whose ``status`` equals ``status``.

        Ordered by ``updated_at DESC`` (most recent first). Capped at
        ``limit`` (default 1000) to avoid unbounded scans.
        """
        ...

    def list_starred(self, *, limit: int = 1000) -> list[VideoTracking]:
        """Return every tracking row with ``starred=True``.

        Ordered by ``updated_at DESC``. Capped at ``limit`` (default 1000).
        """
        ...


@runtime_checkable
class TagRepository(Protocol):
    """Persistence for :class:`Tag` rows + many-to-many ``tag_assignments``.

    Tag names are normalised to lowercase-stripped in this layer
    (D3 M011 RESEARCH). UNIQUE(name) at DB level prevents duplicates.
    """

    def get_or_create(self, name: str) -> Tag:
        """Return the :class:`Tag` row for ``name`` (lowercased, stripped).

        Creates the row if it does not exist. Raises ``StorageError`` if
        ``name`` is empty after stripping.
        """
        ...

    def get_by_name(self, name: str) -> Tag | None:
        """Return the :class:`Tag` matching ``name`` (lowercased) or ``None``."""
        ...

    def list_all(self, *, limit: int = 1000) -> list[Tag]:
        """Return every tag ordered by ``name`` ascending."""
        ...

    def list_for_video(self, video_id: VideoId) -> list[Tag]:
        """Return tags assigned to ``video_id``, ordered by name ascending."""
        ...

    def assign(self, video_id: VideoId, tag_id: int) -> None:
        """Assign ``tag_id`` to ``video_id``. Idempotent — re-assigning is a no-op."""
        ...

    def unassign(self, video_id: VideoId, tag_id: int) -> None:
        """Remove the assignment if present. No-op if absent."""
        ...

    def list_video_ids_for_tag(
        self, name: str, *, limit: int = 1000
    ) -> list[VideoId]:
        """Return every video_id tagged with ``name`` (lowercased).

        Used by :class:`SearchVideosUseCase` in S03 to compute the tag
        facet intersection set.
        """
        ...


@runtime_checkable
class CollectionRepository(Protocol):
    """Persistence for :class:`Collection` + many-to-many ``collection_items``."""

    def create(self, name: str) -> Collection:
        """Create a new collection. Raises ``StorageError`` if the name
        already exists (UNIQUE violation). Name is case-preserved (D3)."""
        ...

    def get_by_name(self, name: str) -> Collection | None:
        """Return the :class:`Collection` matching ``name`` exactly or ``None``."""
        ...

    def list_all(self, *, limit: int = 1000) -> list[Collection]:
        """Return every collection ordered by ``name`` ascending."""
        ...

    def add_video(self, collection_id: int, video_id: VideoId) -> None:
        """Add ``video_id`` to the collection. Idempotent — re-adding is a no-op."""
        ...

    def remove_video(self, collection_id: int, video_id: VideoId) -> None:
        """Remove the membership if present. No-op if absent."""
        ...

    def list_videos(
        self, collection_id: int, *, limit: int = 1000
    ) -> list[VideoId]:
        """Return video_ids in the collection, ordered by membership
        created_at descending (most-recently-added first)."""
        ...

    def list_collections_for_video(self, video_id: VideoId) -> list[Collection]:
        """Return collections containing ``video_id`` ordered by name asc."""
        ...

    def list_video_ids_for_collection(
        self, name: str, *, limit: int = 1000
    ) -> list[VideoId]:
        """Return every video_id in the collection named ``name``.

        Used by :class:`SearchVideosUseCase` in S03 for the collection facet.
        """
        ...
