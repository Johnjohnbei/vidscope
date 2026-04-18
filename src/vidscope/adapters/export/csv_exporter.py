"""CSV library exporter (M011/S04/R059).

Flat CSV via stdlib ``csv.DictWriter``. Multi-value fields (keywords,
topics, verticals, tags, collections) are joined by ``|``. Self-contained.

Note: ``records`` is typed as ``list[Any]`` to avoid importing
``ExportRecord`` from the application layer (self-containment contract).
"""

from __future__ import annotations

import csv
import dataclasses
import io
import sys
from pathlib import Path
from typing import Any

__all__ = ["CsvExporter"]


_MULTI_VALUE_FIELDS = ("keywords", "topics", "verticals", "tags", "collections")


class CsvExporter:
    """Write export records as a flat CSV with ``|`` multi-value separator."""

    def write(
        self,
        records: list[Any],
        out: Path | None = None,
    ) -> None:
        if not records:
            # Even empty export writes nothing (caller may expect it)
            if out is None:
                return
            out.write_text("", encoding="utf-8")
            return

        sample = dataclasses.asdict(records[0])
        fieldnames = list(sample.keys())

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for rec in records:
            row: dict[str, Any] = dataclasses.asdict(rec)
            for mv in _MULTI_VALUE_FIELDS:
                if isinstance(row.get(mv), list):
                    row[mv] = "|".join(str(x) for x in row[mv])
            writer.writerow(row)
        content = buf.getvalue()

        if out is None:
            sys.stdout.write(content)
        else:
            out.write_text(content, encoding="utf-8")
