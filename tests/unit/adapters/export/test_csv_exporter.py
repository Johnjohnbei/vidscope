"""CsvExporter unit tests (M011/S04/R059)."""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from vidscope.adapters.export.csv_exporter import CsvExporter
from vidscope.application.export_library import ExportRecord


def _fixture() -> list[ExportRecord]:
    return [
        ExportRecord(
            video_id=1, platform="youtube", url="https://y.be/a",
            author="a", title="T", upload_date="20260101",
            score=72.0, summary="s1",
            keywords=["code", "python"], topics=["tech"], verticals=["tech", "ai"],
            actionability=80.0, content_type="tutorial",
            status="saved", starred=True, notes="n",
            tags=["idea", "reuse"], collections=["MyCol"],
            exported_at="2026-04-18T10:00:00+00:00",
        ),
        ExportRecord(
            video_id=2, platform="tiktok", url="https://t.co/b",
            author=None, title=None, upload_date=None,
            score=None, summary=None,
            keywords=[], topics=[], verticals=[],
            actionability=None, content_type=None,
            status=None, starred=False, notes=None,
            tags=[], collections=[],
            exported_at="2026-04-18T10:00:00+00:00",
        ),
    ]


class TestCsvExporter:
    def test_write_and_parse(self, tmp_path: Path) -> None:
        out = tmp_path / "out.csv"
        CsvExporter().write(_fixture(), out=out)
        content = out.read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["video_id"] == "1"
        assert rows[0]["tags"] == "idea|reuse"
        assert rows[0]["verticals"] == "tech|ai"
        assert rows[0]["status"] == "saved"
        assert rows[1]["status"] == ""  # None -> empty
        assert rows[1]["starred"] == "False"

    def test_multi_value_joined_by_pipe(self, tmp_path: Path) -> None:
        out = tmp_path / "mv.csv"
        CsvExporter().write(_fixture(), out=out)
        content = out.read_text(encoding="utf-8")
        assert "idea|reuse" in content

    def test_empty_records(self, tmp_path: Path) -> None:
        out = tmp_path / "empty.csv"
        CsvExporter().write([], out=out)
        assert out.read_text(encoding="utf-8") == ""

    def test_empty_records_stdout_no_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        CsvExporter().write([])
        assert capsys.readouterr().out == ""
