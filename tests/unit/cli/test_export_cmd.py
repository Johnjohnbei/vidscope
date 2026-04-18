"""CliRunner tests for `vidscope export` (M011/S04/R059)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

from vidscope.cli.app import app


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))


def _insert_video(tmp_path: Path, pid: str) -> int:
    """Insert a minimal video row and return its id."""
    from vidscope.adapters.sqlite.schema import init_db
    from vidscope.infrastructure.sqlite_engine import build_engine

    db_path = tmp_path / "vidscope.db"
    engine = build_engine(db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO videos (platform, platform_id, url, created_at) "
                "VALUES ('youtube', :p, :u, :c)"
            ),
            {"p": pid, "u": f"https://y.be/{pid}", "c": datetime.now(UTC)},
        )
        row = conn.execute(
            text("SELECT id FROM videos WHERE platform_id=:p"),
            {"p": pid},
        ).fetchone()
    engine.dispose()
    return int(row[0])


class TestExportCmd:
    def test_help(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["export", "--help"])
        assert r.exit_code == 0
        for opt in ("--format", "--out", "--collection", "--tag", "--status"):
            assert opt in r.output

    def test_invalid_format_fails(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["export", "--format", "xml"])
        assert r.exit_code != 0
        assert "xml" in r.output or "--format" in r.output

    def test_json_export_to_file(self, tmp_path: Path) -> None:
        _insert_video(tmp_path, "exp_json_1")
        out = tmp_path / "out.json"
        runner = CliRunner()
        r = runner.invoke(
            app, ["export", "--format", "json", "--out", str(out)],
        )
        assert r.exit_code == 0, r.output
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "exported" in r.output

    def test_markdown_to_stdout(self, tmp_path: Path) -> None:
        _insert_video(tmp_path, "exp_md_1")
        runner = CliRunner()
        r = runner.invoke(app, ["export", "--format", "markdown"])
        assert r.exit_code == 0, r.output
        # stdout contient le markdown ou le recapitulatif
        assert "---" in r.output or "exported" in r.output

    def test_csv_export(self, tmp_path: Path) -> None:
        _insert_video(tmp_path, "exp_csv_1")
        out = tmp_path / "out.csv"
        runner = CliRunner()
        r = runner.invoke(
            app, ["export", "--format", "csv", "--out", str(out)],
        )
        assert r.exit_code == 0, r.output
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "video_id" in content

    def test_path_traversal_rejected(self) -> None:
        runner = CliRunner()
        r = runner.invoke(
            app,
            [
                "export", "--format", "json",
                "--out", "../../../etc/passwd",
            ],
        )
        assert r.exit_code != 0
        assert ".." in r.output or "traversal" in r.output

    def test_collection_filter(self, tmp_path: Path) -> None:
        vid = _insert_video(tmp_path, "exp_col_1")
        runner = CliRunner()
        # Create collection and add the video
        runner.invoke(app, ["collection", "create", "ExpCol"])
        runner.invoke(app, ["collection", "add", "ExpCol", str(vid)])
        out = tmp_path / "coll.json"
        r = runner.invoke(
            app,
            [
                "export", "--format", "json",
                "--out", str(out), "--collection", "ExpCol",
            ],
        )
        assert r.exit_code == 0, r.output
        data = json.loads(out.read_text(encoding="utf-8"))
        assert any(rec["video_id"] == vid for rec in data)
