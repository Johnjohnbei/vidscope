"""Ingest a video from a URL.

The primary user-facing operation. In S02 this is a real implementation
backed by a :class:`PipelineRunner` that runs the registered stages
(currently :class:`IngestStage` only; S03-S06 add transcribe, frames,
analyze, index).

Design notes
------------

- The use case knows nothing about yt-dlp, SQLAlchemy, or the concrete
  stages. It receives a :class:`PipelineRunner` via constructor
  injection and calls ``runner.run(ctx)``.
- The use case is stateless. Every ``execute()`` call builds a fresh
  :class:`PipelineContext` and passes it through the runner.
- Error translation happens here, not in the runner: the runner
  returns a :class:`RunResult` with a success flag and stage outcomes;
  the use case maps that to the typed :class:`IngestResult` DTO the
  CLI displays.
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import MediaType, Platform, PlatformId, RunStatus, VideoId
from vidscope.pipeline import PipelineRunner
from vidscope.ports import PipelineContext, UnitOfWorkFactory

__all__ = ["IngestResult", "IngestVideoUseCase"]


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Outcome of an ingest invocation.

    ``status`` is the terminal :class:`RunStatus` of the overall ingest
    run (OK, FAILED, or PENDING for edge cases like empty URL).
    ``message`` is a short human-readable summary the CLI prints.

    The video-identifying fields are populated on success:

    - ``video_id``: DB id of the persisted row
    - ``platform``: detected platform
    - ``platform_id``: canonical platform-assigned id
    - ``title``: video title from the downloader
    - ``author``: uploader / channel name
    - ``duration``: length in seconds

    ``run_id`` is the id of the first ``pipeline_runs`` row written so
    callers can correlate with ``vidscope status``.
    """

    status: RunStatus
    message: str
    url: str
    run_id: int | None = None
    video_id: VideoId | None = None
    platform: Platform | None = None
    platform_id: PlatformId | None = None
    title: str | None = None
    author: str | None = None
    duration: float | None = None
    media_type: MediaType | None = None


class IngestVideoUseCase:
    """Ingest a single video URL through the pipeline runner.

    Parameters
    ----------
    unit_of_work_factory:
        Factory producing a fresh :class:`UnitOfWork`. Used by the
        use case to read the persisted video row after the runner
        completes (a small extra query that lets us return enriched
        metadata in the result).
    pipeline_runner:
        :class:`PipelineRunner` with every stage already registered.
        The container builds this; callers inject it.
    """

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        pipeline_runner: PipelineRunner,
    ) -> None:
        self._uow_factory = unit_of_work_factory
        self._runner = pipeline_runner

    def execute(self, url: str) -> IngestResult:
        """Run the ingest pipeline for ``url`` and return a typed result.

        The runner persists every stage's pipeline_runs row
        transactionally. On success we re-read the video row to
        populate the result with metadata (title, author, duration).

        Empty or whitespace URLs return FAILED without invoking the
        runner.
        """
        cleaned_url = url.strip() if url else ""
        if not cleaned_url:
            return IngestResult(
                status=RunStatus.FAILED,
                message="url is empty",
                url=url or "",
            )

        ctx = PipelineContext(source_url=cleaned_url)
        run_result = self._runner.run(ctx)

        # Pull the first stage's run_id for correlation with status
        first_run_id = (
            run_result.outcomes[0].run_id if run_result.outcomes else None
        )

        if not run_result.success:
            # Find the failing outcome to surface its error message.
            # `error` is Optional on StageOutcome so we coalesce to a
            # non-None string before building the result.
            failed_outcome = next(
                (o for o in run_result.outcomes if o.error is not None),
                None,
            )
            if failed_outcome is not None and failed_outcome.error is not None:
                message = failed_outcome.error
            else:
                message = (
                    f"pipeline failed at stage {run_result.failed_at!r}"
                )
            return IngestResult(
                status=RunStatus.FAILED,
                message=message,
                url=cleaned_url,
                run_id=first_run_id,
            )

        # Success path — read back the persisted video so the CLI can
        # display a rich result (title, author, duration).
        video_id = ctx.video_id
        title: str | None = None
        author: str | None = None
        duration: float | None = None
        media_type: MediaType | None = None

        if video_id is not None:
            with self._uow_factory() as uow:
                video = uow.videos.get(video_id)
                if video is not None:
                    title = video.title
                    author = video.author
                    duration = video.duration
                    media_type = video.media_type

        message = (
            f"ingested {ctx.platform.value if ctx.platform else '?'}"
            f"/{ctx.platform_id or '?'}"
        )
        if title:
            message += f" — {title}"

        return IngestResult(
            status=RunStatus.OK,
            message=message,
            url=cleaned_url,
            run_id=first_run_id,
            video_id=video_id,
            platform=ctx.platform,
            platform_id=ctx.platform_id,
            title=title,
            author=author,
            duration=duration,
            media_type=media_type,
        )
