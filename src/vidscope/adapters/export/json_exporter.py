"""JSON library exporter (M011/S04/R059).

Serialises ``list[ExportRecord]`` to a JSON array of objects.
Stdlib only (json). Self-contained per the
``export-adapter-is-self-contained`` import-linter contract.

Note: ``records`` is typed as ``list[Any]`` to avoid importing
``ExportRecord`` from the application layer (which would break the
self-containment contract). At runtime the objects must be dataclass
instances so that ``dataclasses.asdict`` works correctly.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

__all__ = ["JsonExporter"]


class JsonExporter:
    """Write export records as a pretty JSON array."""

    def write(
        self,
        records: list[Any],
        out: Path | None = None,
    ) -> None:
        data = [dataclasses.asdict(r) for r in records]
        content = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
        if out is None:
            sys.stdout.write(content)
            sys.stdout.write("\n")
        else:
            out.write_text(content, encoding="utf-8")
