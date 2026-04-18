"""Domain entities for VidScope.

Every entity is a frozen dataclass with slots. They carry data and a small
amount of behavior that depends only on their own state — no I/O, no calls
to ports, no SQLAlchemy, no Typer. Any operation that would need to reach
outside the entity belongs in the pipeline, an adapter, or a use case.

The entities are intentionally slimmer than a full persistence model:

- They use ``str`` for media references (``media_key``, ``image_key``)
  instead of ``pathlib.Path`` so the domain stays filesystem-agnostic. The
  :class:`MediaStorage` port resolves a key to a concrete location.
- Timestamps are always timezone-aware ``datetime`` — naive timestamps are
  a bug waiting to happen across DST boundaries and machine timezones.
- Foreign keys are expressed as typed ids (:data:`VideoId`) not raw ints,
  so mypy catches accidental passing of the wrong key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from vidscope.domain.values import (
    ContentType,
    Language,
    Platform,
    PlatformId,
    RunStatus,
    SentimentLabel,
    StageName,
    TrackingStatus,
    VideoId,
)

__all__ = [
    "Analysis",
    "Frame",
    "PipelineRun",
    "Transcript",
    "TranscriptSegment",
    "Video",
    "VideoStats",
    "VideoTracking",
    "WatchRefresh",
    "WatchedAccount",
]


@dataclass(frozen=True, slots=True)
class Video:
    """A single video record ingested from a source platform.

    ``id`` is ``None`` until the repository persists the row; the
    repository returns a new instance with ``id`` populated.

    ``media_key`` is the opaque storage key resolved by :class:`MediaStorage`.
    ``None`` means the ingest stage has not completed yet.
    """

    platform: Platform
    platform_id: PlatformId
    url: str
    id: VideoId | None = None
    author: str | None = None
    title: str | None = None
    duration: float | None = None
    upload_date: str | None = None
    view_count: int | None = None
    media_key: str | None = None
    created_at: datetime | None = None

    def is_ingested(self) -> bool:
        """Return ``True`` once the ingest stage has stored a media file."""
        return self.media_key is not None


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """One timestamped segment of a transcript.

    All times are in seconds relative to the start of the video. ``text``
    is the raw utterance — no punctuation normalization, no lowercasing.
    """

    start: float
    end: float
    text: str

    def duration(self) -> float:
        """Return the segment's length in seconds. Never negative."""
        return max(0.0, self.end - self.start)


@dataclass(frozen=True, slots=True)
class Transcript:
    """Full transcript of a video plus its segments."""

    video_id: VideoId
    language: Language
    full_text: str
    segments: tuple[TranscriptSegment, ...] = ()
    id: int | None = None
    created_at: datetime | None = None

    def is_empty(self) -> bool:
        """Return ``True`` when the transcript carries no usable text."""
        return not self.full_text.strip()


@dataclass(frozen=True, slots=True)
class Frame:
    """One frame extracted from a video at a specific timestamp."""

    video_id: VideoId
    image_key: str
    timestamp_ms: int
    is_keyframe: bool = False
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Analysis:
    """Qualitative analysis produced by an analyzer provider.

    M010 extension: adds a score vector (5 dimensions), sentiment label,
    sponsor flag, structural content type, controlled-vocabulary verticals,
    and a natural-language reasoning field. All new fields default to
    ``None`` / ``()`` so analyses produced before M010 remain valid (D032
    additive migration).
    """

    video_id: VideoId
    provider: str
    language: Language
    keywords: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()            # freeform, preserved for compat (M001-M009)
    score: float | None = None              # overall score preserved (D032)
    summary: str | None = None
    # --- M010 additive fields (R053, R054, R055) ---
    verticals: tuple[str, ...] = ()                  # R054 controlled taxonomy slugs
    information_density: float | None = None         # R053 score vector — [0, 100]
    actionability: float | None = None               # R053 score vector — [0, 100]
    novelty: float | None = None                     # R053 score vector — [0, 100]
    production_quality: float | None = None          # R053 score vector — [0, 100]
    sentiment: SentimentLabel | None = None          # R053 sentiment label
    is_sponsored: bool | None = None                 # R053 sponsor flag (None = unknown)
    content_type: ContentType | None = None          # R053 structural content type
    reasoning: str | None = None                     # R055 2-3 sentence explanation
    id: int | None = None
    created_at: datetime | None = None

    def has_summary(self) -> bool:
        return self.summary is not None and bool(self.summary.strip())


@dataclass(frozen=True, slots=True)
class PipelineRun:
    """A single stage-invocation record.

    Rows of this kind are written by :class:`PipelineRunner` at the start
    and end of every stage. ``status`` transitions from ``PENDING`` or
    ``RUNNING`` to ``OK``/``FAILED``/``SKIPPED``.

    ``video_id`` is optional because the first invocation of the ingest
    stage happens before the video row exists. In that case ``source_url``
    carries the URL the user passed to ``vidscope add``.
    """

    phase: StageName
    status: RunStatus
    started_at: datetime
    id: int | None = None
    video_id: VideoId | None = None
    source_url: str | None = None
    finished_at: datetime | None = None
    error: str | None = None
    retry_count: int = 0

    def duration(self) -> timedelta | None:
        """Elapsed wall-clock time, or ``None`` if the run has not finished."""
        if self.finished_at is None:
            return None
        return self.finished_at - self.started_at

    def is_terminal(self) -> bool:
        """Return ``True`` when the run has reached a final status."""
        return self.status in (RunStatus.OK, RunStatus.FAILED, RunStatus.SKIPPED)


@dataclass(frozen=True, slots=True)
class WatchedAccount:
    """A public account (Instagram/TikTok/YouTube) registered for
    periodic refresh.

    ``handle`` is the canonical account identifier within a platform
    (e.g. ``"@tiktok"``, a YouTube channel name, an Instagram
    username). It is unique per platform — the repository enforces
    this via a UNIQUE constraint.
    """

    platform: Platform
    handle: str
    url: str
    id: int | None = None
    created_at: datetime | None = None
    last_checked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WatchRefresh:
    """A single invocation of ``vidscope watch refresh``.

    One row per refresh call. Captures how many accounts were checked,
    how many new videos were ingested, and any errors encountered
    (one entry per account failure, not per stage failure).
    """

    started_at: datetime
    accounts_checked: int
    new_videos_ingested: int
    errors: tuple[str, ...] = ()
    id: int | None = None
    finished_at: datetime | None = None

    def duration(self) -> timedelta | None:
        if self.finished_at is None:
            return None
        return self.finished_at - self.started_at


@dataclass(frozen=True, slots=True)
class VideoStats:
    """A single stats snapshot for a video at a specific point in time.

    Snapshots are append-only — one row per ``(video_id, captured_at)``
    pair. The ``captured_at`` timestamp is truncated to the second
    (microsecond=0) so that duplicate probes within the same second are
    silently ignored at the DB level (UNIQUE constraint + ON CONFLICT DO
    NOTHING).

    All five counter fields are ``int | None``. ``None`` means the
    platform did not return that metric — it must never be confused with
    ``0`` (D-03). Callers must check ``is None`` explicitly before
    comparing against zero.
    """

    video_id: VideoId
    captured_at: datetime  # UTC-aware, resolution = second (D-01)
    view_count: int | None = None
    like_count: int | None = None
    repost_count: int | None = None  # yt-dlp field name (D-02), NOT share_count
    comment_count: int | None = None
    save_count: int | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class VideoTracking:
    """User workflow overlay for a single video (M011/R056).

    One row per video — UNIQUE on ``video_id``. The table is independent
    of ``videos`` (D033 immutable videos). Re-ingesting a video leaves
    the ``video_tracking`` row untouched — that's the pipeline neutrality
    invariant.

    Fields
    ------
    video_id:
        FK to ``videos.id`` with ON DELETE CASCADE.
    status:
        Current workflow label. Typical flow: new -> reviewed ->
        saved|actioned|ignored -> archived. Any transition is legal.
    starred:
        Independent of ``status`` — user may star any row.
    notes:
        Free-text note. ``None`` means "no note set" (distinct from
        ``""`` which means "note was explicitly cleared").
    """

    video_id: VideoId
    status: TrackingStatus
    starred: bool = False
    notes: str | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
