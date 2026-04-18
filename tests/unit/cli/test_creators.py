"""Snapshot tests for `vidscope creator` sub-commands (M006/S03-P02).

Uses Typer's CliRunner with a real SQLite engine wired to a tmp DB,
mocking `build_container` so no filesystem side-effects occur outside
the test's tmp_path. Pattern mirrors tests/unit/cli/test_cookies.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.cli.app import app
from vidscope.domain import Creator, Platform
from vidscope.domain.values import PlatformUserId
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.ports import UnitOfWork, UnitOfWorkFactory

runner = CliRunner()


@pytest.fixture()
def uow_factory(tmp_path: Path) -> UnitOfWorkFactory:
    engine = build_engine(tmp_path / "test.db")
    init_db(engine)

    def _factory() -> UnitOfWork:
        return SqliteUnitOfWork(engine)

    return _factory


@pytest.fixture()
def mock_container(uow_factory: UnitOfWorkFactory) -> MagicMock:
    container = MagicMock()
    container.unit_of_work = uow_factory
    return container


def _insert_creator(
    uow_factory: UnitOfWorkFactory,
    handle: str = "@alice",
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str = "UC_alice",
    follower_count: int | None = 42000,
) -> Creator:
    creator = Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id),
        handle=handle,
        display_name=handle.lstrip("@").title(),
        follower_count=follower_count,
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with uow_factory() as uow:
        return uow.creators.upsert(creator)


_PATCH = "vidscope.cli._support.build_container"


class TestCreatorShowCommand:
    def test_show_found(
        self, mock_container: MagicMock, uow_factory: UnitOfWorkFactory
    ) -> None:
        _insert_creator(uow_factory, "@alice", Platform.YOUTUBE)
        with patch(_PATCH, return_value=mock_container):
            result = runner.invoke(app, ["creator", "show", "@alice"])
        assert result.exit_code == 0
        assert "@alice" in result.output

    def test_show_not_found(self, mock_container: MagicMock) -> None:
        with patch(_PATCH, return_value=mock_container):
            result = runner.invoke(app, ["creator", "show", "@ghost"])
        assert result.exit_code == 1
        assert "no creator" in result.output.lower()

    def test_show_with_platform_flag(
        self, mock_container: MagicMock, uow_factory: UnitOfWorkFactory
    ) -> None:
        _insert_creator(uow_factory, "@tiktokuser", Platform.TIKTOK, "TT_user")
        with patch(_PATCH, return_value=mock_container):
            result = runner.invoke(
                app, ["creator", "show", "@tiktokuser", "--platform", "tiktok"]
            )
        assert result.exit_code == 0
        assert "@tiktokuser" in result.output

    def test_show_displays_followers(
        self, mock_container: MagicMock, uow_factory: UnitOfWorkFactory
    ) -> None:
        _insert_creator(
            uow_factory, "@rich", Platform.YOUTUBE, "UC_rich", follower_count=100000
        )
        with patch(_PATCH, return_value=mock_container):
            result = runner.invoke(app, ["creator", "show", "@rich"])
        assert result.exit_code == 0
        assert "100" in result.output  # follower count present


class TestCreatorListCommand:
    def test_list_empty(self, mock_container: MagicMock) -> None:
        with patch(_PATCH, return_value=mock_container):
            result = runner.invoke(app, ["creator", "list"])
        assert result.exit_code == 0
        assert "total creators: 0" in result.output

    def test_list_shows_creators(
        self, mock_container: MagicMock, uow_factory: UnitOfWorkFactory
    ) -> None:
        _insert_creator(uow_factory, "@alice", platform_user_id="alice")
        _insert_creator(uow_factory, "@bob", platform_user_id="bob")
        with patch(_PATCH, return_value=mock_container):
            result = runner.invoke(app, ["creator", "list"])
        assert result.exit_code == 0
        assert "total creators: 2" in result.output

    def test_list_platform_filter(
        self, mock_container: MagicMock, uow_factory: UnitOfWorkFactory
    ) -> None:
        _insert_creator(uow_factory, "@yt", Platform.YOUTUBE, "yt")
        _insert_creator(uow_factory, "@tt", Platform.TIKTOK, "tt")
        with patch(_PATCH, return_value=mock_container):
            result = runner.invoke(app, ["creator", "list", "--platform", "youtube"])
        assert result.exit_code == 0
        assert "@yt" in result.output
        assert "@tt" not in result.output


class TestCreatorVideosCommand:
    def test_videos_not_found_creator(self, mock_container: MagicMock) -> None:
        with patch(_PATCH, return_value=mock_container):
            result = runner.invoke(app, ["creator", "videos", "@ghost"])
        assert result.exit_code == 1
        assert "no creator" in result.output.lower()

    def test_videos_empty_for_existing_creator(
        self, mock_container: MagicMock, uow_factory: UnitOfWorkFactory
    ) -> None:
        _insert_creator(uow_factory, "@empty", platform_user_id="empty_uid")
        with patch(_PATCH, return_value=mock_container):
            result = runner.invoke(app, ["creator", "videos", "@empty"])
        assert result.exit_code == 0
        assert "total videos: 0" in result.output
