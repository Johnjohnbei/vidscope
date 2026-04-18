"""Port for library export adapters (M011/S04/R059).

Stdlib only. Concrete implementations live in
:mod:`vidscope.adapters.export` — JsonExporter, MarkdownExporter,
CsvExporter. The use case :class:`ExportLibraryUseCase` builds a list
of ``ExportRecord`` via the UoW and hands it off to the selected
exporter.

The port declares no YAML, no SQL, no HTTP — it only knows about
an optional output :class:`Path`. Records are typed as ``Any`` to
avoid importing :class:`ExportRecord` from the application layer,
which would break the ``ports-are-pure`` import-linter contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

__all__ = ["Exporter"]


@runtime_checkable
class Exporter(Protocol):
    """Write a list of export records to disk or stdout.

    Implementors receive a ``list[ExportRecord]`` at runtime.
    The type is declared as ``list[Any]`` here to keep the port
    self-contained (no dependency on the application layer).
    """

    def write(
        self,
        records: list[Any],
        out: Path | None = None,
    ) -> None:
        """Serialise ``records``.

        When ``out`` is ``None``, write to stdout. When ``out`` is a
        :class:`Path`, write to the file -- callers ensure the parent
        directory exists and validate the path against traversal.
        """
        ...
