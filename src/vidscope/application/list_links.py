"""List extracted links for a video — powers ``vidscope links <id>``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Link, VideoId
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ListLinksResult", "ListLinksUseCase"]


@dataclass(frozen=True, slots=True)
class ListLinksResult:
    """Outcome of :meth:`ListLinksUseCase.execute`.

    ``found`` is ``False`` when no video matches the given id — the
    CLI surfaces a "no video" message in that case. When ``found`` is
    ``True`` but ``links`` is empty, the video exists but the
    extractor found no URL.
    """

    video_id: int
    found: bool
    links: tuple[Link, ...] = ()


class ListLinksUseCase:
    """Return every :class:`Link` for a video, optionally filtered by source."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        video_id: int,
        *,
        source: str | None = None,
    ) -> ListLinksResult:
        """Fetch links for ``video_id``, optionally filtered by source
        (``"description"``, ``"transcript"``, ``"ocr"``)."""
        with self._uow_factory() as uow:
            video = uow.videos.get(VideoId(video_id))
            if video is None:
                return ListLinksResult(video_id=video_id, found=False)
            links = tuple(
                uow.links.list_for_video(VideoId(video_id), source=source)
            )
        return ListLinksResult(
            video_id=video_id,
            found=True,
            links=links,
        )
