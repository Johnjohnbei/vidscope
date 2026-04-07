"""Return the full record of one video — powers ``vidscope show <id>``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Analysis, Frame, Transcript, Video, VideoId
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ShowVideoResult", "ShowVideoUseCase"]


@dataclass(frozen=True, slots=True)
class ShowVideoResult:
    """Everything known about a single video.

    ``found`` is ``False`` when no video matches the given id; the
    other fields are then empty/None.
    """

    found: bool
    video: Video | None = None
    transcript: Transcript | None = None
    frames: tuple[Frame, ...] = ()
    analysis: Analysis | None = None


class ShowVideoUseCase:
    """Return the full domain record for a video id."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, video_id: int) -> ShowVideoResult:
        with self._uow_factory() as uow:
            video = uow.videos.get(VideoId(video_id))
            if video is None:
                return ShowVideoResult(found=False)
            transcript = uow.transcripts.get_for_video(video.id)  # type: ignore[arg-type]
            frames = tuple(uow.frames.list_for_video(video.id))  # type: ignore[arg-type]
            analysis = uow.analyses.get_latest_for_video(video.id)  # type: ignore[arg-type]

        return ShowVideoResult(
            found=True,
            video=video,
            transcript=transcript,
            frames=frames,
            analysis=analysis,
        )
