"""Return the full record of one video — powers ``vidscope show <id>``."""

from __future__ import annotations

from dataclasses import dataclass, field

from vidscope.domain import (
    Analysis,
    Creator,
    Frame,
    Hashtag,
    Link,
    Mention,
    Transcript,
    Video,
    VideoId,
)
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ShowVideoResult", "ShowVideoUseCase"]


@dataclass(frozen=True, slots=True)
class ShowVideoResult:
    """Everything known about a single video.

    ``found`` is ``False`` when no video matches the given id; the
    other fields are then empty/None.

    M007 adds ``hashtags``, ``mentions``, ``links`` as tuples; they
    default to empty on miss so existing callers keep working without
    modification.
    """

    found: bool
    video: Video | None = None
    transcript: Transcript | None = None
    frames: tuple[Frame, ...] = ()
    analysis: Analysis | None = None
    creator: Creator | None = None
    hashtags: tuple[Hashtag, ...] = ()
    mentions: tuple[Mention, ...] = ()
    links: tuple[Link, ...] = ()


class ShowVideoUseCase:
    """Return the full domain record for a video id."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, video_id: int) -> ShowVideoResult:
        """Fetch the full domain record for ``video_id`` in one transaction.

        Joins video metadata + transcript + frames + latest analysis
        + creator + hashtags + mentions + links into a single
        :class:`ShowVideoResult`. Returns ``found=False`` when no
        video matches the id — never raises on missing rows.
        """
        with self._uow_factory() as uow:
            video = uow.videos.get(VideoId(video_id))
            if video is None:
                return ShowVideoResult(found=False)
            transcript = uow.transcripts.get_for_video(video.id)  # type: ignore[arg-type]
            frames = tuple(uow.frames.list_for_video(video.id))  # type: ignore[arg-type]
            analysis = uow.analyses.get_latest_for_video(video.id)  # type: ignore[arg-type]
            creator: Creator | None = None
            if video.creator_id is not None:
                creator = uow.creators.get(video.creator_id)
            hashtags = tuple(uow.hashtags.list_for_video(video.id))  # type: ignore[arg-type]
            mentions = tuple(uow.mentions.list_for_video(video.id))  # type: ignore[arg-type]
            links = tuple(uow.links.list_for_video(video.id))  # type: ignore[arg-type]

        return ShowVideoResult(
            found=True,
            video=video,
            transcript=transcript,
            frames=frames,
            analysis=analysis,
            creator=creator,
            hashtags=hashtags,
            mentions=mentions,
            links=links,
        )
