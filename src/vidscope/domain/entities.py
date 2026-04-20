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
    CreatorId,
    Language,
    MediaType,
    Platform,
    PlatformId,
    PlatformUserId,
    RunStatus,
    SentimentLabel,
    StageName,
    TrackingStatus,
    VideoId,
)

__all__ = [
    "Analysis",
    "Collection",
    "Creator",
    "Frame",
    "FrameText",
    "Hashtag",
    "Link",
    "Mention",
    "PipelineRun",
    "Tag",
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
    creator_id: "CreatorId | None" = None
    music_track: str | None = None
    music_artist: str | None = None
    description: str | None = None
    thumbnail_key: str | None = None
    content_shape: str | None = None
    media_type: MediaType = MediaType.VIDEO
    hashtags: tuple[str, ...] = ()
    mentions: tuple[str, ...] = ()
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


@dataclass(frozen=True, slots=True)
class Tag:
    """User tag applied to videos (M011/S02/R057).

    Tags are a global namespace (no per-user scoping — R032 single-user
    tool). ``name`` is always lowercase-stripped by the repository on
    insert/lookup (D3 M011 RESEARCH). Uniqueness enforced at the DB
    level by UNIQUE(name).
    """

    name: str
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Collection:
    """User-curated collection of videos (M011/S02/R057).

    Collections are named groupings (e.g. "Concurrents Shopify").
    Unlike :class:`Tag`, collection ``name`` is case-preserved — two
    collections with different casing are distinct rows.
    """

    name: str
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Creator:
    """A content creator identified by a platform-scoped user id (M006).

    ``platform_user_id`` is the stable, platform-assigned identifier
    (YouTube ``UC_...``, TikTok numeric id, Instagram user id).
    ``handle`` and ``display_name`` come from yt-dlp's ``uploader``
    field — they can change over time and are refreshed on every ingest.
    ``is_orphan=True`` means the creator row was synthesised from a
    video's ``author`` field without a verified platform user id.
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


@dataclass(frozen=True, slots=True)
class FrameText:
    """One OCR-extracted text line from a video frame (M008).

    ``confidence`` is the engine's score in ``[0.0, 1.0]``.
    ``bbox`` is an opaque JSON string of the 4 corner points or ``None``
    when the engine does not expose bounding boxes.
    ``video_id`` is ``None`` until persisted; ``id`` is ``None`` until
    the repository assigns it.
    """

    video_id: VideoId
    frame_id: int
    text: str
    confidence: float
    bbox: str | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Hashtag:
    """A hashtag extracted from a video's metadata tags (M007).

    ``tag`` is stored in canonical form (lowercase, no leading ``#``)
    by the repository. Uniqueness enforced at ``(video_id, tag)`` level
    by ``HashtagRepository.replace_for_video``.
    """

    video_id: VideoId
    tag: str
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Link:
    """A URL extracted from a video's description or transcript (M007).

    ``normalized_url`` is the canonical form used for deduplication.
    ``source`` identifies where the link came from (``"description"`` or
    ``"transcript"``). ``position_ms`` is the timestamp in the
    transcript where the link appeared, or ``None`` for description links.
    """

    video_id: VideoId
    url: str
    normalized_url: str
    source: str
    position_ms: int | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Mention:
    """A @handle mention extracted from a video's description (M007).

    ``handle`` is lowercase-stripped (no leading ``@``).
    ``platform`` is ``None`` when the mention's platform cannot be
    inferred from context — the repository fills it in later via
    creator resolution.
    ``video_id=VideoId(0)`` is used as a placeholder before the video
    row exists (e.g. in the downloader extraction helpers).
    """

    video_id: VideoId
    handle: str
    platform: Platform | None = None
    id: int | None = None
    created_at: datetime | None = None
