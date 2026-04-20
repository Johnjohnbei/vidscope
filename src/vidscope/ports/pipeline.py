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
    MediaType,
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


class CreatorInfo(TypedDict):
    """Creator metadata extracted from a yt-dlp info_dict (M006/S02-P01).

    All fields except ``platform_user_id`` are optional — yt-dlp does not
    always expose them. ``platform_user_id`` is always a non-empty string
    when a ``CreatorInfo`` is present (callers should never create one
    without it).
    """

    platform_user_id: str
    handle: str | None
    display_name: str | None
    profile_url: str | None
    avatar_url: str | None
    follower_count: int | None
    is_verified: bool | None


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
    media_type: MediaType | None = None
    carousel_item_keys: list[str] = field(default_factory=list)


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


@dataclass(frozen=True, slots=True)
class IngestOutcome:
    """Result of a successful ingest operation.

    ``media_path`` is a real on-disk path produced by the downloader.
    The ingest stage copies it into :class:`MediaStorage` and discards
    the original.
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
    media_type: MediaType = MediaType.VIDEO
    carousel_items: tuple[str, ...] = ()


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
    configured cookies actually authenticate against a gated platform.

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
