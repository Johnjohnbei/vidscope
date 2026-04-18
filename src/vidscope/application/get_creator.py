"""Return the full record of one creator — powers ``vidscope creator show``.

The use case resolves a creator by ``(platform, handle)``. It does NOT
raise on miss — callers check ``result.found`` and display an error.
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Creator, Platform
from vidscope.ports import UnitOfWorkFactory

__all__ = ["GetCreatorResult", "GetCreatorUseCase"]


@dataclass(frozen=True, slots=True)
class GetCreatorResult:
    """Result of :meth:`GetCreatorUseCase.execute`.

    ``found`` is ``False`` when no creator matches ``(platform, handle)``.
    ``creator`` is ``None`` iff ``found`` is ``False``.
    """

    found: bool
    creator: Creator | None = None


class GetCreatorUseCase:
    """Return the full domain record for a creator identified by handle."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, platform: Platform, handle: str) -> GetCreatorResult:
        """Fetch the creator matching ``(platform, handle)``.

        ``handle`` is the human-facing @-name. Since handles are
        platform-enforced unique at any point in time, this lookup is
        unambiguous. Returns ``found=False`` — never raises — when no
        creator matches.
        """
        with self._uow_factory() as uow:
            creator = uow.creators.find_by_handle(platform, handle)

        if creator is None:
            return GetCreatorResult(found=False)
        return GetCreatorResult(found=True, creator=creator)
