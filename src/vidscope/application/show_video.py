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
)
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ShowVideoResult", "ShowVideoUseCase"]


@dataclass(frozen=True, slots=True)
class ShowVideoResult:
    """Everything known about a single video.

    ``found`` is ``False`` when no video matches the given id; the
    other fields are then empty/None.

    M007 adds ``hashtags``, ``mentions``, ``links``. M008 adds
    ``frame_texts`` (on-screen OCR), ``thumbnail_key`` (canonical
    thumbnail path), ``content_shape`` (face-count heuristic).
    All defaults are safe-empty so existing callers keep working.
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
    frame_texts: tuple[FrameText, ...] = ()
    thumbnail_key: str | None = None
    content_shape: str | None = None


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
            # video.id is VideoId | None by definition (None before first
            # persist), but at this point the row was fetched from the DB so
            # id is always populated.  Assert to narrow the type without
            # suppressing mypy with type: ignore.
            assert video.id is not None, "fetched video has no id — DB invariant broken"
            vid_id: VideoId = video.id
            transcript = uow.transcripts.get_for_video(vid_id)
            frames = tuple(uow.frames.list_for_video(vid_id))
            analysis = uow.analyses.get_latest_for_video(vid_id)
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
            creator=creator,
            hashtags=hashtags,
            mentions=mentions,
            links=links,
            frame_texts=frame_texts,
            thumbnail_key=video.thumbnail_key,
            content_shape=video.content_shape,
        )
