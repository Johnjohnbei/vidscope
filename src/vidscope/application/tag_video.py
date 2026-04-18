"""Tag use cases (M011/S02/R057).

4 use cases operating on the tags + tag_assignments tables. Every use
case uses `unit_of_work_factory` for atomicity and imports only from
vidscope.domain and vidscope.ports (application-has-no-adapters).
"""

from __future__ import annotations

from vidscope.domain import Tag, VideoId
from vidscope.domain.errors import DomainError
from vidscope.ports import UnitOfWorkFactory

__all__ = [
    "ListTagsUseCase",
    "ListVideoTagsUseCase",
    "TagVideoUseCase",
    "UntagVideoUseCase",
]


class TagVideoUseCase:
    """Tag a single video. Idempotent on re-tag."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, video_id: int, name: str) -> Tag:
        vid = VideoId(int(video_id))
        with self._uow() as uow:
            tag = uow.tags.get_or_create(name)
            if tag.id is None:  # pragma: no cover — defensive
                raise DomainError(f"tag {name!r} has no id after get_or_create")
            uow.tags.assign(vid, tag.id)
            return tag


class UntagVideoUseCase:
    """Remove a tag from a video. No-op if the tag or assignment is absent."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, video_id: int, name: str) -> bool:
        """Return True if an assignment was actually removed."""
        vid = VideoId(int(video_id))
        with self._uow() as uow:
            tag = uow.tags.get_by_name(name)
            if tag is None or tag.id is None:
                return False
            uow.tags.unassign(vid, tag.id)
            return True


class ListTagsUseCase:
    """Return every tag globally."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, *, limit: int = 1000) -> list[Tag]:
        with self._uow() as uow:
            return uow.tags.list_all(limit=limit)


class ListVideoTagsUseCase:
    """Return tags assigned to a single video."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, video_id: int) -> list[Tag]:
        vid = VideoId(int(video_id))
        with self._uow() as uow:
            return uow.tags.list_for_video(vid)
