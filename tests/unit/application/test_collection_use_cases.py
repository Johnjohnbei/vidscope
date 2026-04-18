"""Collection use case tests with InMemory fakes (M011/S02/R057)."""

from __future__ import annotations

import pytest

from vidscope.application.collection_library import (
    AddToCollectionUseCase,
    CreateCollectionUseCase,
    ListCollectionsUseCase,
    RemoveFromCollectionUseCase,
)
from vidscope.domain import Collection, VideoId
from vidscope.domain.errors import DomainError, StorageError


class _FakeCollectionRepo:
    def __init__(self) -> None:
        self._colls: dict[str, Collection] = {}
        self._members: set[tuple[int, int]] = set()
        self._next = 1

    def create(self, name: str) -> Collection:
        stripped = name.strip()
        if not stripped:
            raise StorageError("empty name")
        if stripped in self._colls:
            raise StorageError(f"duplicate: {stripped!r}")
        c = Collection(id=self._next, name=stripped)
        self._colls[stripped] = c
        self._next += 1
        return c

    def get_by_name(self, name: str) -> Collection | None:
        return self._colls.get(name.strip())

    def list_all(self, *, limit: int = 1000) -> list[Collection]:
        return sorted(self._colls.values(), key=lambda c: c.name)

    def add_video(self, collection_id: int, video_id: VideoId) -> None:
        self._members.add((int(collection_id), int(video_id)))

    def remove_video(self, collection_id: int, video_id: VideoId) -> None:
        self._members.discard((int(collection_id), int(video_id)))

    def list_videos(self, collection_id: int, *, limit: int = 1000) -> list[VideoId]:
        return [VideoId(v) for (c, v) in self._members if c == int(collection_id)]

    def list_collections_for_video(self, video_id: VideoId) -> list[Collection]:
        cids = {c for (c, v) in self._members if v == int(video_id)}
        return sorted(
            [c for c in self._colls.values() if c.id in cids],
            key=lambda c: c.name,
        )

    def list_video_ids_for_collection(self, name: str, *, limit: int = 1000) -> list[VideoId]:
        c = self.get_by_name(name)
        if c is None:
            return []
        return self.list_videos(c.id) if c.id else []


class _FakeUoW:
    def __init__(self, repo: _FakeCollectionRepo) -> None:
        self.collections = repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def _factory_from(repo: _FakeCollectionRepo):
    def _make():
        return _FakeUoW(repo)
    return _make


class TestCreateCollection:
    def test_creates(self) -> None:
        repo = _FakeCollectionRepo()
        uc = CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo))
        c = uc.execute("X")
        assert c.name == "X"

    def test_duplicate_raises(self) -> None:
        repo = _FakeCollectionRepo()
        uc = CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo))
        uc.execute("X")
        with pytest.raises(StorageError):
            uc.execute("X")


class TestAddRemove:
    def test_add(self) -> None:
        repo = _FakeCollectionRepo()
        CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X")
        AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X", 42)
        assert repo._members == {(1, 42)}

    def test_add_missing_collection_raises(self) -> None:
        repo = _FakeCollectionRepo()
        uc = AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo))
        with pytest.raises(DomainError):
            uc.execute("ghost", 42)

    def test_remove(self) -> None:
        repo = _FakeCollectionRepo()
        CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X")
        AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X", 42)
        RemoveFromCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X", 42)
        assert repo._members == set()


class TestListCollections:
    def test_returns_summary_with_count(self) -> None:
        repo = _FakeCollectionRepo()
        CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X")
        CreateCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("Y")
        AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X", 42)
        AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("X", 43)
        AddToCollectionUseCase(unit_of_work_factory=_factory_from(repo)).execute("Y", 42)
        uc = ListCollectionsUseCase(unit_of_work_factory=_factory_from(repo))
        summaries = uc.execute()
        by_name = {s.collection.name: s.video_count for s in summaries}
        assert by_name == {"X": 2, "Y": 1}
