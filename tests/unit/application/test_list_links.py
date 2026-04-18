"""Tests for ListLinksUseCase — M007/S04-P01.

Pattern: FakeUoW with controllable fakes for VideoRepository and
LinkRepository. The use case returns ListLinksResult(video_id, found, links).
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import pytest

from vidscope.domain import Link, Platform, Video, VideoId
from vidscope.domain.values import PlatformId


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeVideoRepo:
    def __init__(self, videos: dict[int, Video] | None = None) -> None:
        self._videos: dict[int, Video] = videos or {}

    def get(self, video_id: VideoId) -> Video | None:
        return self._videos.get(int(video_id))

    # stubs
    def add(self, video: Video) -> Video: return video  # noqa: E704
    def upsert_by_platform_id(self, video: Video) -> Video: return video  # noqa: E704
    def get_by_platform_id(self, platform: Any, platform_id: Any) -> Video | None: return None  # noqa: E704
    def list_recent(self, limit: int = 20) -> list[Video]: return []  # noqa: E704
    def count(self) -> int: return 0  # noqa: E704


class FakeLinkRepo:
    def __init__(self, links_by_video: dict[int, list[Link]] | None = None) -> None:
        self._links: dict[int, list[Link]] = links_by_video or {}

    def list_for_video(
        self, video_id: VideoId, *, source: str | None = None
    ) -> list[Link]:
        all_links = self._links.get(int(video_id), [])
        if source is not None:
            return [lk for lk in all_links if lk.source == source]
        return list(all_links)

    # stubs
    def add_many_for_video(self, video_id: VideoId, links: list[Link]) -> list[Link]: return []  # noqa: E704
    def has_any_for_video(self, video_id: VideoId) -> bool: return False  # noqa: E704
    def find_video_ids_with_any_link(self, *, limit: int = 50) -> list[VideoId]: return []  # noqa: E704


class FakeUoW:
    def __init__(
        self,
        *,
        videos: FakeVideoRepo | None = None,
        links: FakeLinkRepo | None = None,
    ) -> None:
        self.videos = videos or FakeVideoRepo()
        self.links = links or FakeLinkRepo()

    def __enter__(self) -> FakeUoW:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass


def _make_uow_factory(
    videos: dict[int, Video] | None = None,
    links_by_video: dict[int, list[Link]] | None = None,
) -> Any:
    uow = FakeUoW(
        videos=FakeVideoRepo(videos),
        links=FakeLinkRepo(links_by_video),
    )

    def _factory() -> FakeUoW:
        return uow

    return _factory


def _make_video(vid: int) -> Video:
    return Video(
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"yt{vid}"),
        url=f"https://youtube.com/watch?v=yt{vid}",
        id=VideoId(vid),
        title=f"Video {vid}",
    )


def _make_link(
    vid: int,
    url: str = "https://example.com",
    source: str = "description",
    position_ms: int | None = None,
    link_id: int | None = None,
) -> Link:
    return Link(
        video_id=VideoId(vid),
        url=url,
        normalized_url=url.lower(),
        source=source,
        position_ms=position_ms,
        id=link_id,
    )


# ---------------------------------------------------------------------------
# Lazy import of use case (so tests fail gracefully if file doesn't exist yet)
# ---------------------------------------------------------------------------


def _get_use_case_classes() -> tuple[Any, Any]:
    from vidscope.application.list_links import ListLinksResult, ListLinksUseCase
    return ListLinksResult, ListLinksUseCase


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListLinksUseCaseBasic:
    def test_returns_all_links_for_video(self) -> None:
        """execute(42) sans filtre retourne tous les Link du video."""
        ListLinksResult, ListLinksUseCase = _get_use_case_classes()
        links = [
            _make_link(42, "https://a.com", link_id=1),
            _make_link(42, "https://b.com", source="transcript", link_id=2),
        ]
        factory = _make_uow_factory(
            videos={42: _make_video(42)},
            links_by_video={42: links},
        )
        uc = ListLinksUseCase(unit_of_work_factory=factory)

        result = uc.execute(42)

        assert result.found is True
        assert result.video_id == 42
        assert len(result.links) == 2

    def test_filters_by_source_description(self) -> None:
        """execute(42, source='description') filtre par source."""
        ListLinksResult, ListLinksUseCase = _get_use_case_classes()
        links = [
            _make_link(42, "https://a.com", source="description", link_id=1),
            _make_link(42, "https://b.com", source="transcript", link_id=2),
        ]
        factory = _make_uow_factory(
            videos={42: _make_video(42)},
            links_by_video={42: links},
        )
        uc = ListLinksUseCase(unit_of_work_factory=factory)

        result = uc.execute(42, source="description")

        assert result.found is True
        assert len(result.links) == 1
        assert result.links[0].source == "description"

    def test_filters_by_source_transcript(self) -> None:
        """execute(42, source='transcript') filtre par source."""
        ListLinksResult, ListLinksUseCase = _get_use_case_classes()
        links = [
            _make_link(42, "https://a.com", source="description", link_id=1),
            _make_link(42, "https://b.com", source="transcript", link_id=2),
        ]
        factory = _make_uow_factory(
            videos={42: _make_video(42)},
            links_by_video={42: links},
        )
        uc = ListLinksUseCase(unit_of_work_factory=factory)

        result = uc.execute(42, source="transcript")

        assert result.found is True
        assert len(result.links) == 1
        assert result.links[0].source == "transcript"

    def test_video_not_found_returns_found_false(self) -> None:
        """execute(999) sur video inexistant → found=False, pas d'exception."""
        ListLinksResult, ListLinksUseCase = _get_use_case_classes()
        factory = _make_uow_factory()  # empty repos
        uc = ListLinksUseCase(unit_of_work_factory=factory)

        result = uc.execute(999)

        assert result.found is False
        assert result.video_id == 999
        assert result.links == ()

    def test_video_exists_no_links_returns_found_true_empty_links(self) -> None:
        """execute(42) sur video existant sans link → found=True, links=()."""
        ListLinksResult, ListLinksUseCase = _get_use_case_classes()
        factory = _make_uow_factory(
            videos={42: _make_video(42)},
            links_by_video={},  # no links for any video
        )
        uc = ListLinksUseCase(unit_of_work_factory=factory)

        result = uc.execute(42)

        assert result.found is True
        assert result.links == ()

    def test_found_is_true_when_video_exists_even_without_links(self) -> None:
        """found dépend de l'existence de la vidéo, pas du nombre de liens."""
        ListLinksResult, ListLinksUseCase = _get_use_case_classes()
        factory = _make_uow_factory(
            videos={7: _make_video(7)},
        )
        uc = ListLinksUseCase(unit_of_work_factory=factory)

        result = uc.execute(7)

        assert result.found is True
        assert result.video_id == 7
        # links is empty but found must be True
        assert result.links == ()

    def test_result_is_frozen_dataclass(self) -> None:
        """ListLinksResult est un frozen dataclass — immutabilité."""
        import dataclasses
        ListLinksResult, ListLinksUseCase = _get_use_case_classes()

        res = ListLinksResult(video_id=1, found=False)
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            res.found = True  # type: ignore[misc]
