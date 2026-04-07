"""`vidscope list` — list recently ingested videos."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.list_videos import ListVideosUseCase
from vidscope.cli._support import acquire_container, console, handle_domain_errors

__all__ = ["list_command"]


def list_command(
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Number of videos to display.",
        min=1,
        max=200,
    ),
) -> None:
    """List the most recently ingested videos."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = ListVideosUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(limit=limit)

        console.print(f"[bold]total videos:[/bold] {result.total}")

        if not result.videos:
            console.print(
                "[dim]No videos yet. "
                "Run [bold]vidscope add <url>[/bold] to ingest one.[/dim]"
            )
            return

        table = Table(title=f"Recent videos ({len(result.videos)})", show_header=True)
        table.add_column("id", justify="right", style="dim")
        table.add_column("platform")
        table.add_column("title", overflow="fold")
        table.add_column("author")
        table.add_column("duration", justify="right")
        table.add_column("ingested")

        for video in result.videos:
            duration = (
                f"{video.duration:.0f}s" if video.duration is not None else "-"
            )
            table.add_row(
                str(video.id) if video.id is not None else "-",
                video.platform.value,
                (video.title or "")[:60],
                (video.author or "-")[:30],
                duration,
                video.created_at.strftime("%Y-%m-%d") if video.created_at else "-",
            )

        console.print(table)
