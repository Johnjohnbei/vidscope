"""Return the full record of one video — powers ``vidscope show <id>``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import (
    Analysis,
    Creator,
    Frame,
    FrameText,
    Hashtag,
    Link,
    Mention,
    Transcript,
    Video,
    VideoId,
    VideoStats,
)
from vidscope.domain.metrics import views_velocity_24h as _compute_velocity
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ShowVideoResult", "ShowVideoUseCase"]


@dataclass(frozen=True, slots=True)
class ShowVideoResult:
    """Everything known about a single video."""

    found: bool
    video: Video | None = None
    transcript: Transcript | None = None
    frames: tuple[Frame, ...] = ()
    analysis: Analysis | None = None
    latest_stats: VideoStats | None = None
    views_velocity_24h: float | None = None
    creator: Creator | None = None
    hashtags: tuple[Hashtag, ...] = ()
    mentions: tuple[Mention, ...] = ()
    links: tuple[Link, ...] = ()
    frame_texts: tuple[FrameText, ...] = ()
    thumbnail_key: str | None = None
    content_shape: str | None = None


class ShowVideoUseCase:
    """Return the full domain record for a video id."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, video_id: int) -> ShowVideoResult:
        """Fetch the full domain record for ``video_id`` in one transaction."""
        with self._uow_factory() as uow:
            video = uow.videos.get(VideoId(video_id))
            if video is None:
                return ShowVideoResult(found=False)
            vid_id: VideoId = video.id  # type: ignore[assignment]
            transcript = uow.transcripts.get_for_video(vid_id)
            frames = tuple(uow.frames.list_for_video(vid_id))
            analysis = uow.analyses.get_latest_for_video(vid_id)

            # video_stats is optional (not all UoW implementations expose it)
            video_stats_repo = getattr(uow, "video_stats", None)
            latest_stats: VideoStats | None = None
            velocity: float | None = None
            if video_stats_repo is not None:
                latest_stats = video_stats_repo.latest_for_video(vid_id)
                history = video_stats_repo.list_for_video(vid_id, limit=1000)
                velocity = _compute_velocity(history) if len(history) >= 2 else None

            creator: Creator | None = None
            if video.creator_id is not None:
                creator = uow.creators.get(video.creator_id)

            hashtags = tuple(uow.hashtags.list_for_video(vid_id))
            mentions = tuple(uow.mentions.list_for_video(vid_id))
            links = tuple(uow.links.list_for_video(vid_id))
            frame_texts = tuple(uow.frame_texts.list_for_video(vid_id))

        return ShowVideoResult(
            found=True,
            video=video,
            transcript=transcript,
            frames=frames,
            analysis=analysis,
            latest_stats=latest_stats,
            views_velocity_24h=velocity,
            creator=creator,
            hashtags=hashtags,
            mentions=mentions,
            links=links,
            frame_texts=frame_texts,
            thumbnail_key=video.thumbnail_key,
            content_shape=video.content_shape,
        )
