"""`vidscope search <query>` — full-text search across transcripts and analyses."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.search_library import SearchLibraryUseCase
from vidscope.cli._support import acquire_container, console, handle_domain_errors

__all__ = ["search_command"]


def search_command(
    query: str = typer.Argument(..., help="FTS5 query to run against the index."),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Maximum number of hits to display.",
        min=1,
        max=200,
    ),
) -> None:
    """Run a full-text query through the SQLite FTS5 index."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = SearchLibraryUseCase(
            unit_of_work_factory=container.unit_of_work
        )
        result = use_case.execute(query, limit=limit)

        console.print(
            f"[bold]query:[/bold] {result.query!r}   "
            f"[bold]hits:[/bold] {len(result.hits)}"
        )

        if not result.hits:
            console.print(
                "[dim]No matches. The index is empty until "
                "S06 wires the real pipeline.[/dim]"
            )
            return

        table = Table(title="Search results", show_header=True)
        table.add_column("video", justify="right", style="dim")
        table.add_column("source")
        table.add_column("rank", justify="right")
        table.add_column("snippet", overflow="fold")

        for hit in result.hits:
            table.add_row(
                str(hit.video_id),
                hit.source,
                f"{hit.rank:.2f}",
                hit.snippet,
            )

        console.print(table)
