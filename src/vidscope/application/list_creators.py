"""List creators with optional filters — powers ``vidscope creator list``.

Supports three query modes:
- No filter: returns all creators ordered by last_seen_at desc (via platform scan on all platforms)
- ``platform`` only: returns creators on that platform
- ``min_followers`` only: returns creators with follower_count >= min_followers
- Both: platform filter applied first, then min_followers applied client-side
  (the adapter only exposes list_by_platform and list_by_min_followers separately;
  the use case combines for the dual-filter case)

``limit`` is capped at 200 to prevent unbounded result sets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from vidscope.domain import Creator, Platform
from vidscope.ports import UnitOfWorkFactory

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

__all__ = ["ListCreatorsResult", "ListCreatorsUseCase"]


@dataclass(frozen=True, slots=True)
class ListCreatorsResult:
    """Result of :meth:`ListCreatorsUseCase.execute`.

    ``creators`` is the filtered, limited list. ``total`` is the
    unfiltered count so the CLI can show "showing N of M".
    """

    creators: tuple[Creator, ...]
    total: int


class ListCreatorsUseCase:
    """Return creators matching optional ``platform`` and ``min_followers`` filters."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        *,
        platform: Platform | None = None,
        min_followers: int | None = None,
        limit: int = 20,
    ) -> ListCreatorsResult:
        """Return creators matching the given filters.

        ``limit`` is clamped to [1, 200]. When both ``platform`` and
        ``min_followers`` are provided, ``list_by_platform`` is called
        first with a generous internal limit (200) and the
        ``min_followers`` threshold is applied in Python — this avoids
        adding a compound query to the adapter while keeping the
        user-visible ``limit`` respected.
        """
        limit = max(1, min(limit, 200))

        with self._uow_factory() as uow:
            total = uow.creators.count()

            if platform is not None and min_followers is not None:
                # Dual filter: fetch more than needed from DB, filter in Python
                candidates = uow.creators.list_by_platform(platform, limit=200)
                creators = [
                    c for c in candidates
                    if c.follower_count is not None and c.follower_count >= min_followers
                ][:limit]
            elif platform is not None:
                creators = uow.creators.list_by_platform(platform, limit=limit)
            elif min_followers is not None:
                creators = uow.creators.list_by_min_followers(min_followers, limit=limit)
            else:
                # No filter — return most recently seen across all platforms
                creators = uow.creators.list_by_platform(
                    Platform.YOUTUBE, limit=limit
                ) + uow.creators.list_by_platform(
                    Platform.TIKTOK, limit=limit
                ) + uow.creators.list_by_platform(
                    Platform.INSTAGRAM, limit=limit
                )
                creators = sorted(
                    creators,
                    key=lambda c: c.last_seen_at or c.created_at or _EPOCH,
                    reverse=True,
                )[:limit]

        return ListCreatorsResult(creators=tuple(creators), total=total)
