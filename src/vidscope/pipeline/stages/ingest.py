"""IngestStage — first stage of the pipeline.

Orchestrates three ports to turn a URL into a persisted
:class:`~vidscope.domain.entities.Video`:

1. :class:`~vidscope.ports.pipeline.Downloader` — downloads the media
   and returns metadata (title, author, duration, platform_id, etc.).
2. :class:`~vidscope.ports.storage.MediaStorage` — copies the
   downloaded file into long-term storage under a stable key.
3. :class:`~vidscope.ports.repositories.VideoRepository` — upserts
   the videos row atomically with the rest of the stage execution.

The stage knows nothing about yt-dlp, the filesystem layout, or
SQLAlchemy. It sees three Protocols and the pipeline context. That
means when yt-dlp breaks or we swap to S3 storage, this file doesn't
change.

Idempotence strategy
--------------------

:meth:`is_satisfied` always returns ``False`` in S02. The database
enforces idempotence via ``videos.platform_id`` UNIQUE + upsert — so
re-running ``vidscope add <url>`` re-downloads the media (yt-dlp
caches help a bit) but never duplicates a row. S06 will revisit this
with a probe-before-download optimization. See decision D025.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from vidscope.domain import (
    IngestError,
    MediaType,
    Platform,
    StageName,
    Video,
    detect_platform,
)
from vidscope.ports import (
    Downloader,
    MediaStorage,
    PipelineContext,
    StageResult,
    UnitOfWork,
)

__all__ = ["IngestStage"]


class IngestStage:
    """First stage of the pipeline — download + persist metadata + media."""

    name: str = StageName.INGEST.value

    def __init__(
        self,
        *,
        downloader: Downloader,
        media_storage: MediaStorage,
        cache_dir: Path,
        post_corrections: list[tuple[str, str]] | None = None,
    ) -> None:
        """Construct the stage.

        Parameters
        ----------
        downloader:
            Any :class:`Downloader` implementation. Injected so tests
            can use a fake and production uses :class:`YtdlpDownloader`.
        media_storage:
            Any :class:`MediaStorage` implementation. Receives the
            downloaded file under a stable key.
        cache_dir:
            Directory where the downloader writes temporary files
            before they're copied into :class:`MediaStorage`. Must
            already exist. Passed by the composition root from the
            resolved :class:`Config.cache_dir`.
        """
        self._downloader = downloader
        self._media_storage = media_storage
        self._cache_dir = cache_dir
        self._post_corrections: list[tuple[str, str]] = post_corrections or []

    # ------------------------------------------------------------------
    # Stage protocol
    # ------------------------------------------------------------------

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Return ``False`` — this stage relies on DB-level idempotence.

        See the module docstring for the rationale. S06 will add a
        probe-before-download optimization that returns ``True`` when
        ``videos.media_key`` is already populated for the URL.
        """
        _ = (ctx, uow)  # unused — DB-level idempotence handles dedup
        return False

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Download the video, store the media file, and upsert the
        videos row. Mutates ``ctx`` with video_id / platform /
        platform_id / media_key on success.

        Raises
        ------
        IngestError
            Any failure from the downloader, platform detection, or
            storage. The PipelineRunner catches and persists.
        """
        # 1. Validate the URL and detect the platform eagerly so we
        #    don't even call the downloader on obvious garbage.
        detected_platform = detect_platform(ctx.source_url)

        # 2. Download into an ephemeral subdir of the cache. The
        #    tempdir is cleaned up automatically at the end of
        #    this method regardless of success/failure.
        with tempfile.TemporaryDirectory(
            prefix="vidscope-ingest-", dir=str(self._cache_dir)
        ) as tmp:
            outcome = self._downloader.download(ctx.source_url, tmp)

            # The downloader should already set outcome.platform, but
            # we sanity-check it against our own detection. Mismatch
            # means yt-dlp and our detector disagree on what this URL
            # is — surface it instead of silently trusting yt-dlp.
            if outcome.platform is not detected_platform:
                raise IngestError(
                    f"platform mismatch for {ctx.source_url!r}: "
                    f"url parser says {detected_platform.value}, "
                    f"downloader says {outcome.platform.value}",
                    retryable=False,
                )

            # 3. Copy the downloaded file into MediaStorage under a
            #    stable key. Keep the extension from the downloader
            #    so later stages (transcribe, frames) can dispatch
            #    on it if they want.
            source_path = Path(outcome.media_path)
            if not source_path.exists():
                raise IngestError(
                    f"downloader reported media at {source_path} but "
                    f"the file does not exist",
                    retryable=False,
                )

            # 4. Store the media file(s).
            #    VIDEO/IMAGE → single key; CAROUSEL → one key per slide.
            carousel_stored: list[str] = []
            if outcome.media_type == MediaType.CAROUSEL and outcome.carousel_items:
                for idx, item_path_str in enumerate(outcome.carousel_items):
                    item_path = Path(item_path_str)
                    item_key = (
                        f"videos/{outcome.platform.value}/"
                        f"{outcome.platform_id}/items/{idx:04d}{item_path.suffix}"
                    )
                    stored_item = self._media_storage.store(item_key, item_path)
                    carousel_stored.append(stored_item)
                stored_key = carousel_stored[0]
            else:
                media_key = _build_media_key(
                    platform=outcome.platform,
                    platform_id=outcome.platform_id,
                    source_path=source_path,
                )
                stored_key = self._media_storage.store(media_key, source_path)

            # 5. Build the domain Video entity.
            corrected_title = _correct(outcome.title, self._post_corrections)

            video = Video(
                platform=outcome.platform,
                platform_id=outcome.platform_id,
                url=outcome.url,
                author=outcome.author,
                title=corrected_title,
                duration=outcome.duration,
                upload_date=outcome.upload_date,
                view_count=outcome.view_count,
                media_key=stored_key,
                media_type=outcome.media_type,
            )

            # 6. Upsert the videos row.
            persisted = uow.videos.upsert_by_platform_id(video)

            # 7. Mutate the pipeline context.
            ctx.video_id = persisted.id
            ctx.platform = persisted.platform
            ctx.platform_id = persisted.platform_id
            ctx.media_key = persisted.media_key
            ctx.media_type = persisted.media_type
            ctx.carousel_item_keys = carousel_stored

        message = (
            f"ingested {persisted.platform.value}/{persisted.platform_id}"
            + (f" — {persisted.title}" if persisted.title else "")
        )
        return StageResult(message=message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _correct(text: str | None, corrections: list[tuple[str, str]]) -> str | None:
    if not text or not corrections:
        return text
    for wrong, right in corrections:
        text = re.sub(re.escape(wrong), right, text, flags=re.IGNORECASE)
    return text


def _build_media_key(
    *,
    platform: Platform,
    platform_id: str,
    source_path: Path,
) -> str:
    """Return the stable :class:`MediaStorage` key for a downloaded file.

    Layout: ``videos/{platform}/{platform_id}/media{ext}`` where
    ``{ext}`` is the source file's extension (with dot) or an empty
    string if the source has no extension. Example::

        videos/youtube/dQw4w9WgXcQ/media.mp4
    """
    extension = source_path.suffix
    return f"videos/{platform.value}/{platform_id}/media{extension}"
