"""Collection use cases (M011/S02/R057).

4 use cases operating on the collections + collection_items tables.
Every use case uses `unit_of_work_factory` for atomicity and imports
only from vidscope.domain and vidscope.ports (application-has-no-adapters).
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Collection, VideoId
from vidscope.domain.errors import DomainError
from vidscope.ports import UnitOfWorkFactory

__all__ = [
    "AddToCollectionUseCase",
    "CollectionSummary",
    "CreateCollectionUseCase",
    "ListCollectionsUseCase",
    "RemoveFromCollectionUseCase",
]


@dataclass(frozen=True, slots=True)
class CollectionSummary:
    """Row used by `vidscope collection list`."""

    collection: Collection
    video_count: int


class CreateCollectionUseCase:
    """Create a new named collection. Raises on duplicate name."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, name: str) -> Collection:
        with self._uow() as uow:
            return uow.collections.create(name)


class AddToCollectionUseCase:
    """Add a video to a collection (by collection name)."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, collection_name: str, video_id: int) -> Collection:
        vid = VideoId(int(video_id))
        with self._uow() as uow:
            coll = uow.collections.get_by_name(collection_name)
            if coll is None or coll.id is None:
                raise DomainError(
                    f"collection {collection_name!r} does not exist"
                )
            uow.collections.add_video(coll.id, vid)
            return coll


class RemoveFromCollectionUseCase:
    """Remove a video from a collection."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, collection_name: str, video_id: int) -> Collection:
        vid = VideoId(int(video_id))
        with self._uow() as uow:
            coll = uow.collections.get_by_name(collection_name)
            if coll is None or coll.id is None:
                raise DomainError(
                    f"collection {collection_name!r} does not exist"
                )
            uow.collections.remove_video(coll.id, vid)
            return coll


class ListCollectionsUseCase:
    """Return every collection with its video count."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow = unit_of_work_factory

    def execute(self, *, limit: int = 1000) -> list[CollectionSummary]:
        with self._uow() as uow:
            cols = uow.collections.list_all(limit=limit)
            results: list[CollectionSummary] = []
            for c in cols:
                if c.id is None:
                    continue
                vids = uow.collections.list_videos(c.id, limit=10_000)
                results.append(CollectionSummary(collection=c, video_count=len(vids)))
            return results
