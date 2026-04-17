"""List videos for a creator — powers ``vidscope creator videos <handle>``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Creator, Platform, Video
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ListCreatorVideosResult", "ListCreatorVideosUseCase"]


@dataclass(frozen=True, slots=True)
class ListCreatorVideosResult:
    """Result of :meth:`ListCreatorVideosUseCase.execute`.

    ``found`` is ``False`` when no creator matches ``(platform, handle)``.
    When ``found`` is ``True``, ``creator`` is populated and ``videos``
    holds the creator's videos ordered newest-first.
    """

    found: bool
    creator: Creator | None = None
    videos: tuple[Video, ...] = ()
    total: int = 0


class ListCreatorVideosUseCase:
    """Return videos linked to a creator identified by handle."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        platform: Platform,
        handle: str,
        *,
        limit: int = 20,
    ) -> ListCreatorVideosResult:
        """Fetch videos for the creator matching ``(platform, handle)``.

        Resolution flow:
        1. Resolve creator via :meth:`CreatorRepository.find_by_handle`.
        2. If not found: return ``found=False``.
        3. List videos via :meth:`VideoRepository.list_by_creator(creator.id)`
           ordered newest-first, capped at ``limit``.
        4. Return total count of linked videos (unbounded) alongside the page.

        ``limit`` is clamped to [1, 200].
        """
        limit = max(1, min(limit, 200))

        with self._uow_factory() as uow:
            creator = uow.creators.find_by_handle(platform, handle)
            if creator is None or creator.id is None:
                return ListCreatorVideosResult(found=False)

            videos = uow.videos.list_by_creator(creator.id, limit=limit)
            # Count: list full set to get total — we cap list_by_creator
            # at limit for the page, fetch count separately via large limit
            all_videos = uow.videos.list_by_creator(creator.id, limit=10000)
            total = len(all_videos)

        return ListCreatorVideosResult(
            found=True,
            creator=creator,
            videos=tuple(videos),
            total=total,
        )
