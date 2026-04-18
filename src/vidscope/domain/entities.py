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
    "FrameText",
    "Hashtag",
    "Link",
    "Mention",
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

    ``description``, ``music_track``, ``music_artist`` carry the raw
    platform caption verbatim and the music identification reported by
    the platform (per M007 D-01). Stored as direct columns on the
    ``videos`` table — no ``VideoMetadata`` side entity exists (D-01
    rejects the side-entity alternative so ``vidscope show`` reads
    every caption/music field in a single row fetch, zero JOIN). All
    three fields are ``None`` when the platform does not expose them;
    they are NEVER populated with a synthesised placeholder (per R045).
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
    creator_id: CreatorId | None = None
    description: str | None = None
    music_track: str | None = None
    music_artist: str | None = None

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


@dataclass(frozen=True, slots=True)
class Hashtag:
    """A hashtag attached to a video (e.g. ``"cooking"`` for ``#Cooking``).

    Stored in a side table keyed by ``(video_id, tag)`` — the same
    canonical pattern as :class:`Creator` (per M007 D-05). ``tag`` is
    the canonical lowercase form WITHOUT the leading ``#`` (per
    D-04: ``#Coding`` and ``#coding`` must match exactly after
    canonicalisation). The adapter that inserts the row (M007/S01
    ``HashtagRepositorySQLite``) is the single place responsible for
    applying ``tag.lower().lstrip("#")`` — the dataclass itself
    preserves whatever value the caller passes so tests and fixtures
    can construct instances deterministically.

    ``id`` is ``None`` until the repository persists the row; the
    repository returns a new instance with ``id`` populated.
    """

    video_id: VideoId
    tag: str
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Mention:
    """An ``@handle`` mention extracted from a video's description.

    Stored in a side table keyed by ``(video_id, handle)`` — same side-
    table pattern as :class:`Hashtag` (per M007 D-05). ``handle`` is
    the canonical lowercase form WITHOUT the leading ``@`` (per D-04
    exact-match facet). ``platform`` is optional: when the mention
    syntax unambiguously identifies a platform (e.g. a TikTok-only
    handle pattern) the extractor MAY populate it; otherwise ``None``
    is legitimate. Per D-03, no ``creator_id`` FK is stored — the
    Mention↔Creator linkage is derivable via JOIN at query time and
    is deliberately deferred to M011. This keeps ingest free of any
    extra DB lookups per mention.

    ``id`` is ``None`` until the repository persists the row; the
    repository returns a new instance with ``id`` populated.
    """

    video_id: VideoId
    handle: str
    platform: Platform | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Link:
    """A URL extracted from a video's text surfaces (description,
    transcript, OCR).

    Stored in a side table keyed by ``(video_id, normalized_url, source)``.
    ``url`` is the raw string as captured by the extractor (strip
    trailing punctuation but preserve the original case and query
    params). ``normalized_url`` is the deduplication key: lowercase
    scheme+host, strip ``utm_*`` query params, strip fragment, sorted
    query params (see M007/S02 ``URLNormalizer``). Per M007 D-02, no
    HEAD resolver runs at ingest — short URLs (t.co, bit.ly) are
    stored as-is and resolved later if and when M008/M011 adds that
    capability.

    ``source`` identifies where the URL was found: ``"description"``
    for captions captured at ingest, ``"transcript"`` for URLs
    surfaced in the transcript after TranscribeStage, and ``"ocr"``
    reserved for M008/S02 (OCR-sourced on-screen URLs). ``position_ms``
    is populated for transcript/OCR sources when a timestamp is
    available; ``None`` for caption-sourced URLs.

    ``id`` is ``None`` until the repository persists the row.
    """

    video_id: VideoId
    url: str
    normalized_url: str
    source: str
    position_ms: int | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class FrameText:
    """A block of OCR-extracted text for a single frame (M008/R047).

    Stored in the ``frame_texts`` side table keyed by ``(frame_id,
    id)`` with FK cascade on both ``frames.id`` and ``videos.id``.
    ``video_id`` is denormalised on the row (also present via
    ``frames.video_id``) so the FTS5 ``frame_texts_fts`` virtual
    table can filter by ``video_id`` without a JOIN — same pattern
    as the existing ``search_index`` table.

    ``confidence`` is the OCR engine's score in ``[0.0, 1.0]``;
    rows below the engine's min_confidence threshold (default 0.5)
    are discarded before insertion — the dataclass itself does not
    validate the range (responsibility of the adapter — pattern
    mirrors :class:`Hashtag` which does not canonicalise).

    ``bbox`` is an optional JSON-serialised string of the 4 corner
    points ``[[x1,y1], ..., [x4,y4]]`` from RapidOCR. Stored for
    potential future visualisation; NOT exposed in CLI/MCP v1. The
    dataclass holds it opaquely as ``str | None``.

    ``id`` is ``None`` until the repository persists the row; the
    repository returns a new instance with ``id`` populated.
    """

    video_id: VideoId
    frame_id: int
    text: str
    confidence: float
    bbox: str | None = None
    id: int | None = None
    created_at: datetime | None = None
