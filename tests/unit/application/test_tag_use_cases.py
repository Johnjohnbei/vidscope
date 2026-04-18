"""Tag use case tests with InMemory fakes (M011/S02/R057)."""

from __future__ import annotations

from vidscope.application.tag_video import (
    ListTagsUseCase,
    ListVideoTagsUseCase,
    TagVideoUseCase,
    UntagVideoUseCase,
)
from vidscope.domain import Tag, VideoId


class _FakeTagRepo:
    def __init__(self) -> None:
        self._tags: dict[str, Tag] = {}
        self._assignments: set[tuple[int, int]] = set()
        self._next = 1

    def get_or_create(self, name: str) -> Tag:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("empty tag")
        if normalized not in self._tags:
            self._tags[normalized] = Tag(id=self._next, name=normalized)
            self._next += 1
        return self._tags[normalized]

    def get_by_name(self, name: str) -> Tag | None:
        return self._tags.get(name.strip().lower())

    def list_all(self, *, limit: int = 1000) -> list[Tag]:
        return sorted(self._tags.values(), key=lambda t: t.name)

    def list_for_video(self, video_id: VideoId) -> list[Tag]:
        tag_ids = {tid for vid, tid in self._assignments if vid == int(video_id)}
        return sorted(
            [t for t in self._tags.values() if t.id in tag_ids],
            key=lambda t: t.name,
        )

    def assign(self, video_id: VideoId, tag_id: int) -> None:
        self._assignments.add((int(video_id), int(tag_id)))

    def unassign(self, video_id: VideoId, tag_id: int) -> None:
        self._assignments.discard((int(video_id), int(tag_id)))

    def list_video_ids_for_tag(self, name: str, *, limit: int = 1000) -> list[VideoId]:
        t = self.get_by_name(name)
        if t is None:
            return []
        return [VideoId(v) for (v, tid) in self._assignments if tid == t.id]


class _FakeUoW:
    def __init__(self, tags_repo: _FakeTagRepo) -> None:
        self.tags = tags_repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def _factory_from(repo: _FakeTagRepo):
    def _make():
        return _FakeUoW(repo)
    return _make


class TestTagVideoUseCase:
    def test_creates_and_assigns(self) -> None:
        repo = _FakeTagRepo()
        uc = TagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        tag = uc.execute(42, "Idea")
        assert tag.name == "idea"
        assert (42, tag.id) in repo._assignments

    def test_idempotent(self) -> None:
        repo = _FakeTagRepo()
        uc = TagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        uc.execute(42, "idea")
        uc.execute(42, "idea")
        assert len(repo._assignments) == 1


class TestUntagVideoUseCase:
    def test_removes_assignment(self) -> None:
        repo = _FakeTagRepo()
        tag_uc = TagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        tag_uc.execute(42, "idea")
        untag_uc = UntagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        removed = untag_uc.execute(42, "idea")
        assert removed is True
        assert not repo._assignments

    def test_missing_tag_returns_false(self) -> None:
        repo = _FakeTagRepo()
        uc = UntagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        assert uc.execute(42, "ghost") is False


class TestListUseCases:
    def test_list_all(self) -> None:
        repo = _FakeTagRepo()
        repo.get_or_create("zeta")
        repo.get_or_create("alpha")
        uc = ListTagsUseCase(unit_of_work_factory=_factory_from(repo))
        names = [t.name for t in uc.execute()]
        assert names == ["alpha", "zeta"]

    def test_list_for_video(self) -> None:
        repo = _FakeTagRepo()
        tag_uc = TagVideoUseCase(unit_of_work_factory=_factory_from(repo))
        tag_uc.execute(7, "idea")
        tag_uc.execute(7, "hook")
        uc = ListVideoTagsUseCase(unit_of_work_factory=_factory_from(repo))
        names = {t.name for t in uc.execute(7)}
        assert names == {"idea", "hook"}
