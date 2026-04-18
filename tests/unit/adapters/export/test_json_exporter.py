"""JsonExporter unit tests (M011/S04/R059)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vidscope.adapters.export.json_exporter import JsonExporter
from vidscope.application.export_library import ExportRecord
from vidscope.ports import Exporter


def _fixture_records() -> list[ExportRecord]:
    return [
        ExportRecord(
            video_id=1, platform="youtube", url="https://y.be/a",
            author="creator", title="Title A", upload_date="20260101",
            score=72.0, summary="summary A",
            keywords=["code", "python"], topics=["tech"], verticals=["tech"],
            actionability=80.0, content_type="tutorial",
            status="saved", starred=True, notes="great hook",
            tags=["idea"], collections=["Concurrents"],
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


class TestProtocolConformance:
    def test_is_exporter(self) -> None:
        assert isinstance(JsonExporter(), Exporter)


class TestJsonExporter:
    def test_write_to_path(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        JsonExporter().write(_fixture_records(), out=out)
        content = out.read_text(encoding="utf-8")
        data = json.loads(content)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["video_id"] == 1
        assert data[0]["tags"] == ["idea"]
        assert data[0]["status"] == "saved"
        assert data[1]["status"] is None
        assert data[1]["starred"] is False

    def test_roundtrip_preserves_fields(self, tmp_path: Path) -> None:
        records = _fixture_records()
        out = tmp_path / "rt.json"
        JsonExporter().write(records, out=out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data[0]["platform"] == "youtube"
        assert data[0]["score"] == 72.0
        assert data[0]["keywords"] == ["code", "python"]
        assert data[0]["verticals"] == ["tech"]
        assert data[0]["collections"] == ["Concurrents"]

    def test_write_to_stdout(self, capsys) -> None:
        JsonExporter().write(_fixture_records(), out=None)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 2

    def test_empty_records_writes_empty_array(self, tmp_path: Path) -> None:
        out = tmp_path / "empty.json"
        JsonExporter().write([], out=out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == []
