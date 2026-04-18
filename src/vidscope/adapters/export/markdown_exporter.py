"""Markdown library exporter (M011/S04/R059).

Each record becomes a Markdown block:

    ---
    <YAML frontmatter>
    ---
    # Title
    Summary body...
    ---

Uses ``yaml.dump`` from pyyaml (already a project dep) for the
frontmatter -- D7 M011 RESEARCH: python-frontmatter is NOT a runtime
requirement. Self-contained per import-linter contract.

Note: ``records`` is typed as ``list[Any]`` to avoid importing
``ExportRecord`` from the application layer (self-containment contract).
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any

import yaml

__all__ = ["MarkdownExporter"]


class MarkdownExporter:
    """Write export records as one concatenated Markdown stream."""

    def write(
        self,
        records: list[Any],
        out: Path | None = None,
    ) -> None:
        lines: list[str] = []
        for rec in records:
            frontmatter = dataclasses.asdict(rec)
            lines.append("---")
            lines.append(
                yaml.dump(
                    frontmatter,
                    allow_unicode=True,
                    sort_keys=True,
                    default_flow_style=False,
                ).rstrip()
            )
            lines.append("---")
            lines.append(f"# {rec.title or rec.url}")
            if rec.summary:
                lines.append("")
                lines.append(rec.summary)
            lines.append("")
            lines.append("---")
            lines.append("")
        content = "\n".join(lines)
        if out is None:
            sys.stdout.write(content)
            sys.stdout.write("\n")
        else:
            out.write_text(content, encoding="utf-8")
