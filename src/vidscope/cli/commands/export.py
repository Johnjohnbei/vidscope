"""`vidscope export --format {json|markdown|csv} [--collection] [--query] [--out]`

M011/S04/R059: export the library (or a filtered subset) to JSON /
Markdown / CSV. Path traversal is validated before writing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from vidscope.adapters.export import CsvExporter, JsonExporter, MarkdownExporter
from vidscope.application.export_library import ExportLibraryUseCase
from vidscope.application.search_videos import SearchFilters
from vidscope.cli._support import (
    acquire_container,
    console,
    handle_domain_errors,
    parse_tracking_status,
)

__all__ = ["export_command"]


_FORMATS = {
    "json": JsonExporter,
    "markdown": MarkdownExporter,
    "csv": CsvExporter,
}


def _validate_out_path(raw: str | None) -> Path | None:
    """Reject path traversal (``..`` segment). Accept absolute or relative."""
    if raw is None:
        return None
    candidate = Path(raw)
    # Reject any path with a literal ".." segment (T-PATH-M011-01).
    if any(part == ".." for part in candidate.parts):
        console.print(
            f"[bold red]error:[/bold red] --out path {raw!r} contains a "
            "'..' segment; path traversal is refused."
        )
        raise typer.Exit(1)
    return candidate



def export_command(
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="json, markdown, or csv."),
    ],
    out: Annotated[
        str | None,
        typer.Option(
            "--out", "-o",
            help="Output file path (absolute or relative). Omit for stdout.",
        ),
    ] = None,
    collection: Annotated[
        str | None,
        typer.Option("--collection", help="Export only videos in this collection."),
    ] = None,
    tag: Annotated[
        str | None,
        typer.Option("--tag", help="Export only videos with this tag."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help="Export only videos with this workflow status."),
    ] = None,
    starred: Annotated[
        bool | None,
        typer.Option(
            "--starred/--unstarred",
            help="Filter by starred flag.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            min=1,
            max=100_000,
            help="Maximum number of records to export.",
        ),
    ] = 10_000,
) -> None:
    """Export the library (or a filtered subset) to JSON / Markdown / CSV."""
    with handle_domain_errors():
        fmt_norm = format.strip().lower()
        exporter_cls = _FORMATS.get(fmt_norm)
        if exporter_cls is None:
            valid = ", ".join(sorted(_FORMATS.keys()))
            console.print(
                f"[bold red]error:[/bold red] --format must be one of: "
                f"{valid}. Got {format!r}."
            )
            raise typer.Exit(1)

        out_path = _validate_out_path(out)

        parsed_status = parse_tracking_status(status)

        filters = SearchFilters(
            status=parsed_status,
            starred=starred,
            tag=tag.lower().strip() if tag else None,
            collection=collection.strip() if collection else None,
        )

        container = acquire_container()
        use_case = ExportLibraryUseCase(
            unit_of_work_factory=container.unit_of_work,
        )
        exporter = exporter_cls()

        n = use_case.execute(
            exporter=exporter,
            out=out_path,
            filters=filters,
            limit=limit,
        )

        target = str(out_path) if out_path is not None else "<stdout>"
        console.print(
            f"[bold green]exported[/bold green] {n} record(s) "
            f"to [bold]{target}[/bold] (format={fmt_norm})"
        )
