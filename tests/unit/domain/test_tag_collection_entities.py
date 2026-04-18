"""Tag + Collection entities (M011/S02/R057)."""
from __future__ import annotations

import dataclasses

import pytest

from vidscope.domain import Collection, Tag


class TestTagEntity:
    def test_minimal(self) -> None:
        t = Tag(name="idea")
        assert t.name == "idea"
        assert t.id is None

    def test_frozen(self) -> None:
        t = Tag(name="idea")
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.name = "other"  # type: ignore[misc]


class TestCollectionEntity:
    def test_minimal(self) -> None:
        c = Collection(name="Concurrents")
        assert c.name == "Concurrents"
        assert c.id is None

    def test_frozen(self) -> None:
        c = Collection(name="X")
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.name = "Y"  # type: ignore[misc]


class TestPortReExports:
    def test_tag_repo_importable(self) -> None:
        from vidscope.ports import TagRepository
        assert getattr(TagRepository, "_is_runtime_protocol", False) is True

    def test_collection_repo_importable(self) -> None:
        from vidscope.ports import CollectionRepository
        assert getattr(CollectionRepository, "_is_runtime_protocol", False) is True

    def test_uow_has_tags_and_collections(self) -> None:
        from vidscope.ports import UnitOfWork
        anns = UnitOfWork.__annotations__
        assert "tags" in anns
        assert "collections" in anns
