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
    CreatorId,
    Language,
    Platform,
    PlatformId,
    PlatformUserId,
    RunStatus,
    StageName,
    VideoId,
)

__all__ = [
    "Analysis",
    "Creator",
    "Frame",
    "PipelineRun",
    "Transcript",
    "TranscriptSegment",
    "Video",
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
    """Qualitative analysis produced by an analyzer provider."""

    video_id: VideoId
    provider: str
    language: Language
    keywords: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    score: float | None = None
    summary: str | None = None
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
class Creator:
    """A content creator — the person/account that uploaded a video.

    Identity anchors on ``(platform, platform_user_id)`` — the
    platform-issued stable id (yt-dlp's ``uploader_id``) that survives
    account renames (per D-01). ``handle`` is the human-facing @-name
    which MAY change; the repository preserves rename history by
    updating the row in place. ``id`` is a surrogate autoincrement
    populated by the repository on upsert.

    ``is_orphan`` is set to ``True`` by the backfill script when
    re-probing yt-dlp returns NOT_FOUND or AUTH_REQUIRED: every video
    still gets an FK populated, no data is lost, and the flag
    surfaces later in listings (per D-02). ``avatar_url`` is a URL
    string only — no image download, no MediaStorage write (per D-05).
    ``follower_count`` is the current scalar value only — temporal
    engagement lives in M009's ``video_stats`` / future
    ``creator_stats`` (per D-04).
    """

    platform: Platform
    platform_user_id: PlatformUserId
    id: CreatorId | None = None
    handle: str | None = None
    display_name: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None
    follower_count: int | None = None
    is_verified: bool | None = None
    is_orphan: bool = False
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime | None = None
