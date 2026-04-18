"""MetadataExtractStage — fifth stage of the pipeline (M007/S03).

Extracts URLs from (description, transcript.full_text) via a
:class:`LinkExtractor` port and persists them to the ``links`` side
table via :attr:`UnitOfWork.links`. Positioned between
:class:`AnalyzeStage` and :class:`IndexStage` in the canonical
pipeline graph (see ``StageName`` enum order).

Resume-from-failure
-------------------
``is_satisfied`` returns True when ``uow.links.has_any_for_video(video_id)``
is True — re-runs of ``vidscope add <url>`` on an already-extracted
video skip this stage entirely.

Idempotence caveat
------------------
Unlike :class:`IngestStage` (hashtags/mentions use DELETE-INSERT),
this stage does NOT clear existing links before inserting. The
``is_satisfied`` check ensures we don't double-insert in normal
flow. If a user really wanted to re-run extraction (e.g. after a
regex change), they'd manually DELETE the rows first. M007 is
conservative here; M011 may revisit.
"""

from __future__ import annotations

from vidscope.domain import (
    IndexingError,
    Link,
    StageName,
)
from vidscope.ports import (
    PipelineContext,
    StageResult,
    UnitOfWork,
)
from vidscope.ports.link_extractor import LinkExtractor

__all__ = ["MetadataExtractStage"]


class MetadataExtractStage:
    """Fifth stage — extract URLs from description + transcript."""

    name: str = StageName.METADATA_EXTRACT.value

    def __init__(self, *, link_extractor: LinkExtractor) -> None:
        """Construct the stage.

        Parameters
        ----------
        link_extractor:
            Any :class:`LinkExtractor` implementation. Production uses
            :class:`~vidscope.adapters.text.RegexLinkExtractor`; tests
            inject fakes.
        """
        self._extractor = link_extractor

    # ------------------------------------------------------------------
    # Stage protocol
    # ------------------------------------------------------------------

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Return True when at least one link already exists for
        ``ctx.video_id``. Cheap DB query — no regex re-run."""
        if ctx.video_id is None:
            return False
        return uow.links.has_any_for_video(ctx.video_id)

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Extract URLs from description + transcript, persist them.

        Mutates nothing on ``ctx`` — downstream stages don't read the
        links list.

        Raises
        ------
        IndexingError
            When ``ctx.video_id`` is missing (ingest stage failed silently).
        """
        if ctx.video_id is None:
            raise IndexingError(
                "metadata_extract stage requires ctx.video_id; "
                "ingest must run first"
            )

        # 1. Read description from the videos row (M007 D-01: column).
        video = uow.videos.get(ctx.video_id)
        description = video.description if video is not None else None

        # 2. Read transcript (optional — may be None on transcription
        #    failure or instrumental video).
        transcript = uow.transcripts.get_for_video(ctx.video_id)
        transcript_text = (
            transcript.full_text
            if transcript is not None and transcript.full_text
            else None
        )

        # 3. Extract URLs from each source.
        links: list[Link] = []
        if description:
            for raw in self._extractor.extract(description, source="description"):
                links.append(
                    Link(
                        video_id=ctx.video_id,
                        url=raw["url"],
                        normalized_url=raw["normalized_url"],
                        source=raw["source"],
                        position_ms=raw["position_ms"],
                    )
                )
        if transcript_text:
            for raw in self._extractor.extract(transcript_text, source="transcript"):
                links.append(
                    Link(
                        video_id=ctx.video_id,
                        url=raw["url"],
                        normalized_url=raw["normalized_url"],
                        source=raw["source"],
                        position_ms=raw["position_ms"],
                    )
                )

        # 4. Persist. add_many_for_video dedupes by (normalized_url,
        #    source) within the call; empty list is a no-op.
        persisted = uow.links.add_many_for_video(ctx.video_id, links)

        return StageResult(
            message=f"extracted {len(persisted)} link(s) "
                    f"(description + transcript)"
        )
