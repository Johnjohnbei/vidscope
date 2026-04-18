"""CliRunner tests for `vidscope tag` (M011/S02/R057)."""

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


def _insert_video(pid: str = "tag_test_1") -> int:
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


class TestTagCmd:
    def test_help(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["tag", "--help"])
        assert r.exit_code == 0
        for sub in ("add", "remove", "list", "video"):
            assert sub in r.output

    def test_add_and_list(self) -> None:
        vid = _insert_video("tag_add_1")
        runner = CliRunner()
        r1 = runner.invoke(app, ["tag", "add", str(vid), "Idea"])
        assert r1.exit_code == 0, r1.output
        assert "added" in r1.output
        r2 = runner.invoke(app, ["tag", "list"])
        assert r2.exit_code == 0
        assert "idea" in r2.output  # lowercased

    def test_remove(self) -> None:
        vid = _insert_video("tag_remove_1")
        runner = CliRunner()
        runner.invoke(app, ["tag", "add", str(vid), "hook"])
        r = runner.invoke(app, ["tag", "remove", str(vid), "hook"])
        assert r.exit_code == 0
        assert "removed" in r.output

    def test_video_subcommand(self) -> None:
        vid = _insert_video("tag_vid_1")
        runner = CliRunner()
        runner.invoke(app, ["tag", "add", str(vid), "idea"])
        runner.invoke(app, ["tag", "add", str(vid), "reuse"])
        r = runner.invoke(app, ["tag", "video", str(vid)])
        assert r.exit_code == 0
        assert "idea" in r.output
        assert "reuse" in r.output
