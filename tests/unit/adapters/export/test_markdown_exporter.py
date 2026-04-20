"""MarkdownExporter unit tests (M011/S04/R059)."""
from __future__ import annotations

from pathlib import Path

import yaml

from vidscope.adapters.export.markdown_exporter import MarkdownExporter
from vidscope.application.export_library import ExportRecord


def _fixture() -> list[ExportRecord]:
    return [
        ExportRecord(
            video_id=1, platform="youtube", url="https://y.be/a",
            author="a", title="Title A", upload_date="20260101",
            score=72.0, summary="Summary body text.",
            keywords=["code"], topics=["tech"], verticals=["tech"],
            actionability=80.0, content_type="tutorial",
            status="saved", starred=True, notes="nope",
            tags=["idea"], collections=["MyCol"],
            media_type="video",
            exported_at="2026-04-18T10:00:00+00:00",
        ),
    ]


class TestMarkdownExporter:
    def test_writes_frontmatter_and_body(self, tmp_path: Path) -> None:
        out = tmp_path / "out.md"
        MarkdownExporter().write(_fixture(), out=out)
        content = out.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "# Title A" in content
        assert "Summary body text." in content

    def test_frontmatter_parseable_by_yaml_safe_load(self, tmp_path: Path) -> None:
        out = tmp_path / "ya.md"
        MarkdownExporter().write(_fixture(), out=out)
        content = out.read_text(encoding="utf-8")
        # Extract the first frontmatter block between --- lines
        parts = content.split("---", 2)
        # parts[0] is empty (before first ---), parts[1] is the YAML
        yaml_block = parts[1].strip()
        data = yaml.safe_load(yaml_block)
        assert data["video_id"] == 1
        assert data["status"] == "saved"
        assert data["tags"] == ["idea"]
        assert data["collections"] == ["MyCol"]

    def test_empty_records_writes_empty(self, tmp_path: Path) -> None:
        out = tmp_path / "empty.md"
        MarkdownExporter().write([], out=out)
        content = out.read_text(encoding="utf-8").strip()
        assert content == ""

    def test_writes_to_stdout(self, capsys) -> None:
        MarkdownExporter().write(_fixture(), out=None)
        captured = capsys.readouterr()
        assert "# Title A" in captured.out
