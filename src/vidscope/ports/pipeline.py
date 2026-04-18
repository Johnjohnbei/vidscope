"""Pipeline ports: Stage contract + per-stage service Protocols.

The pipeline is a sequence of five stages (ingest → transcribe → frames →
analyze → index). Each stage is a small class that implements the
:class:`Stage` Protocol. Stages do not touch I/O directly — they receive
service Protocols (:class:`Downloader`, :class:`Transcriber`, ...) via
dependency injection and delegate the actual work to those.

Resume-from-failure
-------------------

:meth:`Stage.is_satisfied` is the mechanism that lets ``vidscope add <url>``
be safely re-runnable on a partially-succeeded video. Before executing a
stage, the runner asks ``is_satisfied(ctx)``; if ``True``, the stage is
skipped (a ``SKIPPED`` pipeline_run row is still written so operators can
see the short-circuit happened) and the runner moves on.

Execution contract
------------------

- :meth:`Stage.execute` takes a :class:`PipelineContext` and a
  :class:`~vidscope.ports.unit_of_work.UnitOfWork` that is already open
  and inside a transaction. The stage writes its domain rows through the
  unit of work's repositories. The runner commits the transaction (and
  the matching pipeline_runs row) atomically when the stage returns.
- The stage may mutate the context (e.g. the ingest stage fills
  ``media_key``, the transcribe stage fills ``transcript_id``) and
  returns a :class:`StageResult` that the runner uses to decide whether
  to proceed.
- On failure the stage raises a typed
  :class:`~vidscope.domain.errors.DomainError`. The runner catches, marks
  the pipeline_run row FAILED, and aborts the remaining stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, TypedDict, runtime_checkable

from vidscope.domain import (
    Analysis,
    Frame,
    Language,
    Mention,
    Platform,
    PlatformId,
    Transcript,
    VideoId,
)
from vidscope.ports.unit_of_work import UnitOfWork

__all__ = [
    "Analyzer",
    "ChannelEntry",
    "CreatorInfo",
    "Downloader",
    "FrameExtractor",
    "IngestOutcome",
    "PipelineContext",
    "ProbeResult",
    "ProbeStatus",
    "SearchIndex",
    "SearchResult",
    "Stage",
    "StageResult",
    "Transcriber",
]


# ---------------------------------------------------------------------------
# Pipeline context and results
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PipelineContext:
    """Mutable state carried through the pipeline for one video.

    Each stage reads from and writes to this context. The runner threads
    a single instance through all stages; stages must never replace the
    context, only mutate it in place.

    ``source_url`` is the URL the user passed to ``vidscope add``. Every
    other field is populated as stages complete.
    """

    source_url: str
    video_id: VideoId | None = None
    platform: Platform | None = None
    platform_id: PlatformId | None = None
    media_key: str | None = None
    audio_key: str | None = None
    transcript_id: int | None = None
    language: Language | None = None
    frame_ids: list[int] = field(default_factory=list)
    analysis_id: int | None = None


@dataclass(frozen=True, slots=True)
class StageResult:
    """Outcome of a single stage execution.

    ``skipped=True`` means the stage short-circuited via
    :meth:`Stage.is_satisfied` — still write a pipeline_runs row with
    status SKIPPED so operators see it happened.

    ``message`` is a short human-readable summary the CLI can display.
    """

    skipped: bool = False
    message: str = ""


# ---------------------------------------------------------------------------
# Stage protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Stage(Protocol):
    """Contract every pipeline stage implements.

    Stages are stateless singletons held by the container. They receive
    their dependencies (service Protocols, adapters) via ``__init__`` and
    expose only the two methods below.
    """

    name: str
    """Stable stage identifier. Must match one of
    :class:`~vidscope.domain.values.StageName`."""

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Return ``True`` if this stage's output already exists for the
        given context — the runner will skip execution and record a
        SKIPPED pipeline_runs row.
        """
        ...

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Perform the stage's work, mutating ``ctx`` and writing rows
        through ``uow``.

        Raises
        ------
        DomainError
            Any typed failure. The runner catches, marks the run FAILED,
            and aborts the remaining stages.
        """
        ...


# ---------------------------------------------------------------------------
# Per-stage service protocols
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Creator metadata extracted at ingest time (D-01)
# ---------------------------------------------------------------------------


class CreatorInfo(TypedDict):
    """Creator metadata carried alongside a successful ingest.

    Populated by :class:`Downloader` implementations from the yt-dlp
    ``info_dict`` without any extra network call. Consumed by
    :class:`IngestStage` to construct a :class:`~vidscope.domain.Creator`
    and upsert it via :attr:`UnitOfWork.creators` before the video row
    write (per D-04: single UoW transaction).

    Fields mirror the subset of ``ProbeResult`` that populates a
    :class:`Creator`:

    - ``platform_user_id`` comes from yt-dlp's ``uploader_id`` — the
      platform-stable id that survives renames (D-01 canonical UNIQUE key).
    - ``handle`` and ``display_name`` both come from yt-dlp's ``uploader``
      today (MAY diverge later if yt-dlp exposes a separate handle field).
    - ``profile_url`` ← ``uploader_url``
    - ``avatar_url`` ← ``uploader_thumbnail`` (first URL when yt-dlp returns a list)
    - ``follower_count`` ← ``channel_follower_count``
    - ``is_verified`` ← ``channel_verified`` / ``uploader_verified`` (rare)

    When ``Downloader`` cannot extract ``uploader_id`` (empty or absent),
    the whole :class:`CreatorInfo` is set to ``None`` on
    :attr:`IngestOutcome.creator_info` (D-02: ingest succeeds with
    ``creator_id=NULL``).
    """

    platform_user_id: str
    handle: str | None
    display_name: str | None
    profile_url: str | None
    avatar_url: str | None
    follower_count: int | None
    is_verified: bool | None


@dataclass(frozen=True, slots=True)
class IngestOutcome:
    """Result of a successful ingest operation.

    ``media_path`` is a real on-disk path produced by the downloader.
    The ingest stage copies it into :class:`MediaStorage` and discards
    the original.

    ``creator_info`` is populated when yt-dlp exposes ``uploader_id``
    (the D-01 canonical UNIQUE key on ``creators``). ``None`` is a
    legitimate outcome for compilations, playlists without a single
    uploader, and extractors that don't expose an uploader (M006 D-02:
    ingest succeeds with ``creator_id=NULL``).

    ``description``, ``hashtags``, ``mentions``, ``music_track``,
    ``music_artist`` are M007 additions (R043, R045). Every field is
    optional with a safe default so M006 callers keep working without
    modification. Per M007 D-01 the caption + music are persisted on
    the ``videos`` row directly (no side entity); per D-05 the
    hashtags and mentions land in side tables. Each field is ``None``
    / empty tuple when the platform does not expose it — NEVER a
    synthesised placeholder (per R045).
    """

    platform: Platform
    platform_id: PlatformId
    url: str
    media_path: str
    title: str | None = None
    author: str | None = None
    duration: float | None = None
    upload_date: str | None = None
    view_count: int | None = None
    creator_info: CreatorInfo | None = None
    description: str | None = None
    hashtags: tuple[str, ...] = ()
    mentions: tuple[Mention, ...] = ()
    music_track: str | None = None
    music_artist: str | None = None


@dataclass(frozen=True, slots=True)
class ChannelEntry:
    """One entry returned by :meth:`Downloader.list_channel_videos`.

    Captures just enough to deduplicate against existing videos
    (``platform_id``) and to hand off to the ingest pipeline
    (``url``). No metadata is fetched at listing time — that comes
    later in the regular download flow.
    """

    platform_id: PlatformId
    url: str


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Outcome of :meth:`Downloader.probe`.

    The probe is a metadata-only call (no media download, no transcribe,
    no DB write) used by ``vidscope cookies test`` to verify that the
    configured cookies actually authenticate against a gated platform,
    and by the M006 backfill script to recover creator metadata from
    already-ingested videos.

    Attributes
    ----------
    status:
        High-level outcome — see :class:`ProbeStatus`.
    url:
        The URL that was probed.
    detail:
        Human-readable detail. On ``ok``, the resolved title or video id.
        On any failure, a short message suitable for CLI display.
    title:
        Resolved video title when ``status == ProbeStatus.OK``, ``None``
        otherwise.
    uploader:
        yt-dlp's ``uploader`` field — the human-friendly creator name
        (e.g. "MrBeast"). ``None`` when the extractor does not expose it.
        Consumed by the M006 backfill script to populate
        ``Creator.display_name``.
    uploader_id:
        yt-dlp's ``uploader_id`` field — the platform-stable id that
        survives renames. Consumed by the M006 backfill script to
        populate ``Creator.platform_user_id`` (the canonical UNIQUE key).
    uploader_url:
        Creator profile URL. Consumed as ``Creator.profile_url``.
    channel_follower_count:
        Current follower count when yt-dlp exposes it. Consumed as
        ``Creator.follower_count`` (per D-04: scalar only, no
        time-series — M009 owns temporal data).
    uploader_thumbnail:
        Creator avatar URL (first URL if yt-dlp returns a list).
        Consumed as ``Creator.avatar_url`` (per D-05: string only,
        no image download).
    uploader_verified:
        Verified-badge flag when exposed. Not consistently populated
        across extractors — ``None`` is normal.
    """

    status: ProbeStatus
    url: str
    detail: str
    title: str | None = None
    uploader: str | None = None
    uploader_id: str | None = None
    uploader_url: str | None = None
    channel_follower_count: int | None = None
    uploader_thumbnail: str | None = None
    uploader_verified: bool | None = None


class ProbeStatus(StrEnum):
    """High-level outcomes for :class:`ProbeResult`.

    - ``OK`` — metadata fetched successfully (cookies work, or none needed)
    - ``AUTH_REQUIRED`` — server says login is required (cookies expired/missing)
    - ``NOT_FOUND`` — URL is dead or video deleted
    - ``NETWORK_ERROR`` — transient connection failure
    - ``UNSUPPORTED`` — extractor doesn't recognize the URL
    - ``ERROR`` — anything else
    """

    OK = "ok"
    AUTH_REQUIRED = "auth_required"
    NOT_FOUND = "not_found"
    NETWORK_ERROR = "network_error"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


@runtime_checkable
class Downloader(Protocol):
    """Platform-agnostic downloader.

    The default implementation in :mod:`vidscope.adapters.ytdlp` wraps
    yt-dlp. Alternate implementations (cookies-backed, private APIs)
    register under the same Protocol.
    """

    def download(self, url: str, destination_dir: str) -> IngestOutcome:
        """Download ``url`` into ``destination_dir`` and return a
        structured :class:`IngestOutcome`.

        Raises
        ------
        IngestError
            Any failure — network, parsing, platform unsupported, etc.
        """
        ...

    def list_channel_videos(
        self, url: str, *, limit: int = 10
    ) -> list[ChannelEntry]:
        """Return recent videos for a channel/account URL.

        Uses a cheap listing call (e.g. yt-dlp's extract_flat) that
        returns video IDs without downloading media. Used by the
        watchlist refresh loop to discover new videos since the last
        check.

        Parameters
        ----------
        url:
            Channel / account URL (e.g. YouTube channel, TikTok
            profile, Instagram user page).
        limit:
            Maximum number of entries to return.

        Returns
        -------
        list[ChannelEntry]
            Most recent first. Empty when the channel has no videos.

        Raises
        ------
        IngestError
            On any listing failure (unsupported platform, rate limit,
            channel not found, etc.).
        """
        ...

    def probe(self, url: str) -> ProbeResult:
        """Fetch metadata only for ``url`` without downloading media.

        Used by ``vidscope cookies test`` to verify that the configured
        cookies authenticate against a gated platform. Never raises —
        every failure is encoded in the returned :class:`ProbeResult`'s
        ``status`` field.

        Parameters
        ----------
        url:
            Video URL to probe.

        Returns
        -------
        ProbeResult
            Always returned, even on failure.
        """
        ...


@runtime_checkable
class Transcriber(Protocol):
    """Speech-to-text transcriber.

    The default implementation in :mod:`vidscope.adapters.whisper` wraps
    faster-whisper. Alternate implementations (cloud transcription APIs)
    register under the same Protocol.
    """

    def transcribe(self, media_path: str) -> Transcript:
        """Transcribe the audio track of ``media_path`` and return a
        :class:`Transcript` with ``video_id`` left as a placeholder —
        the stage fills it in before persisting.

        Raises
        ------
        TranscriptionError
            Any failure during transcription.
        """
        ...


@runtime_checkable
class FrameExtractor(Protocol):
    """Video frame extractor.

    The default implementation in :mod:`vidscope.adapters.ffmpeg` shells
    out to ffmpeg. The contract intentionally hides the binary from
    callers.
    """

    def extract_frames(
        self,
        media_path: str,
        output_dir: str,
        *,
        max_frames: int = 30,
    ) -> list[Frame]:
        """Extract up to ``max_frames`` frames from ``media_path`` and
        write them into ``output_dir``. Returns :class:`Frame` instances
        with ``video_id`` left as a placeholder.

        Raises
        ------
        FrameExtractionError
            Any failure — binary missing, input corrupt, disk full.
        """
        ...


@runtime_checkable
class Analyzer(Protocol):
    """Qualitative analyzer producing an :class:`Analysis` from a
    :class:`Transcript`.

    The default implementation in :mod:`vidscope.adapters.heuristic` is
    pure Python. LLM-backed implementations (NVIDIA, Groq, OpenAI) ship
    in M004 and register under the same Protocol.
    """

    @property
    def provider_name(self) -> str:
        """Stable identifier written to :attr:`Analysis.provider`."""
        ...

    def analyze(self, transcript: Transcript) -> Analysis:
        """Analyze ``transcript`` and return an :class:`Analysis` with
        ``video_id`` copied from the transcript's ``video_id``.

        Raises
        ------
        AnalysisError
            Any failure — provider unreachable, malformed response, etc.
        """
        ...


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One hit from :class:`SearchIndex.search`.

    ``rank`` is adapter-specific (SQLite FTS5 uses ``bm25()``); callers
    use it only for ordering. ``source`` identifies which piece of the
    video produced the hit (transcript, analysis summary, title, etc.).
    """

    video_id: VideoId
    source: str
    snippet: str
    rank: float


@runtime_checkable
class SearchIndex(Protocol):
    """Full-text search index over transcripts and analyses.

    The default implementation in :mod:`vidscope.adapters.sqlite` wraps
    a FTS5 virtual table. Alternate implementations (OpenSearch, Meili)
    register under the same Protocol.
    """

    def index_transcript(self, transcript: Transcript) -> None:
        """Insert a transcript into the index. Idempotent per
        (video_id, source='transcript') pair."""
        ...

    def index_analysis(self, analysis: Analysis) -> None:
        """Insert an analysis summary into the index. Idempotent per
        (video_id, source='analysis_summary') pair."""
        ...

    def search(self, query: str, *, limit: int = 20) -> list[SearchResult]:
        """Return the top ``limit`` hits for ``query``, ordered by rank."""
        ...
