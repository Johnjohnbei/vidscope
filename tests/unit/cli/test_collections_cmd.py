"""CliRunner tests for `vidscope collection` (M011/S02/R057)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

from vidscope.cli.app import app


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    yield


def _insert_video(pid: str) -> int:
    from vidscope.infrastructure.container import build_container
    container = build_container()
    try:
        with container.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO videos (platform, platform_id, url, created_at) "
                     "VALUES ('youtube', :p, :u, :c)"),
                {"p": pid, "u": f"https://y.be/{pid}", "c": datetime.now(UTC)},
            )
            return int(conn.execute(
                text("SELECT id FROM videos WHERE platform_id=:p"),
                {"p": pid},
            ).scalar())
    finally:
        container.engine.dispose()


class TestCollectionCmd:
    def test_help(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["collection", "--help"])
        assert r.exit_code == 0
        for sub in ("create", "add", "remove", "list", "show"):
            assert sub in r.output

    def test_create_and_duplicate_fails(self) -> None:
        runner = CliRunner()
        r1 = runner.invoke(app, ["collection", "create", "Concurrents"])
        assert r1.exit_code == 0
        assert "created" in r1.output
        r2 = runner.invoke(app, ["collection", "create", "Concurrents"])
        assert r2.exit_code != 0

    def test_add_to_missing_fails(self) -> None:
        vid = _insert_video("col_miss_1")
        runner = CliRunner()
        r = runner.invoke(app, ["collection", "add", "Ghost", str(vid)])
        assert r.exit_code != 0

    def test_add_and_show(self) -> None:
        vid = _insert_video("col_add_1")
        runner = CliRunner()
        runner.invoke(app, ["collection", "create", "MyCol"])
        runner.invoke(app, ["collection", "add", "MyCol", str(vid)])
        r = runner.invoke(app, ["collection", "show", "MyCol"])
        assert r.exit_code == 0
        assert str(vid) in r.output

    def test_remove(self) -> None:
        vid = _insert_video("col_rem_1")
        runner = CliRunner()
        runner.invoke(app, ["collection", "create", "Rem"])
        runner.invoke(app, ["collection", "add", "Rem", str(vid)])
        r = runner.invoke(app, ["collection", "remove", "Rem", str(vid)])
        assert r.exit_code == 0
        assert "removed" in r.output

    def test_list_with_counts(self) -> None:
        v1 = _insert_video("col_list_1")
        v2 = _insert_video("col_list_2")
        runner = CliRunner()
        runner.invoke(app, ["collection", "create", "Lst"])
        runner.invoke(app, ["collection", "add", "Lst", str(v1)])
        runner.invoke(app, ["collection", "add", "Lst", str(v2)])
        r = runner.invoke(app, ["collection", "list"])
        assert r.exit_code == 0
        assert "Lst" in r.output
        assert "2" in r.output  # video_count=2
