"""ExplainAnalysisUseCase -- returns video + latest analysis for `vidscope explain`."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Analysis, Video, VideoId
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ExplainAnalysisResult", "ExplainAnalysisUseCase"]


@dataclass(frozen=True, slots=True)
class ExplainAnalysisResult:
    """Result of :meth:`ExplainAnalysisUseCase.execute`.

    ``found`` is ``False`` only when no video matches the given id. When
    the video exists but has no analysis yet, ``found=True`` and
    ``analysis=None`` -- the CLI differentiates those cases in its
    output.
    """

    found: bool
    video: Video | None = None
    analysis: Analysis | None = None


class ExplainAnalysisUseCase:
    """Return the latest analysis for ``video_id`` -- powers `vidscope explain`."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, video_id: int) -> ExplainAnalysisResult:
        with self._uow_factory() as uow:
            video = uow.videos.get(VideoId(video_id))
            if video is None:
                return ExplainAnalysisResult(found=False)
            analysis = uow.analyses.get_latest_for_video(VideoId(video_id))
        return ExplainAnalysisResult(found=True, video=video, analysis=analysis)
