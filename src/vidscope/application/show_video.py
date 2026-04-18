"""Return the full record of one video — powers ``vidscope show <id>``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Analysis, Frame, Transcript, Video, VideoId, VideoStats
from vidscope.domain.metrics import views_velocity_24h as _compute_velocity
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ShowVideoResult", "ShowVideoUseCase"]


@dataclass(frozen=True, slots=True)
class ShowVideoResult:
    """Everything known about a single video.

    ``found`` is ``False`` when no video matches the given id; the
    other fields are then empty/None.

    D-05 fields (M009/S04):
    - ``latest_stats``: the most recent VideoStats snapshot, or None if
      no stats have been captured yet.
    - ``views_velocity_24h``: computed via metrics.views_velocity_24h on
      the full history if >= 2 snapshots exist, otherwise None.
    """

    found: bool
    video: Video | None = None
    transcript: Transcript | None = None
    frames: tuple[Frame, ...] = ()
    analysis: Analysis | None = None

    # D-05: Latest captured stats snapshot + computed velocity over full history.
    latest_stats: VideoStats | None = None
    views_velocity_24h: float | None = None


class ShowVideoUseCase:
    """Return the full domain record for a video id."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, video_id: int) -> ShowVideoResult:
        """Fetch the full domain record for ``video_id`` in one transaction.

        Joins video metadata + transcript + frames + latest analysis
        into a single :class:`ShowVideoResult`. Returns ``found=False``
        when no video matches the id — never raises on missing rows.

        D-05 (M009/S04): also loads the latest stats snapshot and
        computes views_velocity_24h from the full history when >= 2
        snapshots are available.
        """
        with self._uow_factory() as uow:
            video = uow.videos.get(VideoId(video_id))
            if video is None:
                return ShowVideoResult(found=False)
            transcript = uow.transcripts.get_for_video(video.id)  # type: ignore[arg-type]
            frames = tuple(uow.frames.list_for_video(video.id))  # type: ignore[arg-type]
            analysis = uow.analyses.get_latest_for_video(video.id)  # type: ignore[arg-type]

            # D-05: latest stats snapshot + full-history velocity
            vid_id = video.id  # type: ignore[assignment]
            latest_stats = uow.video_stats.latest_for_video(vid_id)
            history = uow.video_stats.list_for_video(vid_id, limit=1000)
            velocity = _compute_velocity(history) if len(history) >= 2 else None

        return ShowVideoResult(
            found=True,
            video=video,
            transcript=transcript,
            frames=frames,
            analysis=analysis,
            latest_stats=latest_stats,
            views_velocity_24h=velocity,
        )
