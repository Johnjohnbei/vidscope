"""`vidscope links <id>` — list extracted URLs for a video."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.list_links import ListLinksUseCase
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)

__all__ = ["links_command"]


def links_command(
    video_id: int = typer.Argument(..., help="Numeric id of the video."),
    source: str | None = typer.Option(
        None,
        "--source",
        help="Filter by source: description, transcript, or ocr.",
    ),
) -> None:
    """List every URL extracted from a video's description + transcript."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = ListLinksUseCase(
            unit_of_work_factory=container.unit_of_work
        )
        result = use_case.execute(video_id, source=source)

        if not result.found:
            raise fail_user(f"no video with id {video_id}")

        console.print(
            f"[bold]video:[/bold] {result.video_id}   "
            f"[bold]links:[/bold] {len(result.links)}"
            + (f"   [bold]source:[/bold] {source}" if source else "")
        )

        if not result.links:
            console.print("[dim]No URLs extracted for this video.[/dim]")
            return

        table = Table(title=f"Links for video #{result.video_id}", show_header=True)
        table.add_column("id", justify="right", style="dim")
        table.add_column("source")
        table.add_column("url", overflow="fold")
        table.add_column("position", justify="right")

        for link in result.links:
            pos = f"{link.position_ms}ms" if link.position_ms is not None else "-"
            table.add_row(
                str(link.id) if link.id is not None else "-",
                link.source,
                link.url,
                pos,
            )

        console.print(table)
