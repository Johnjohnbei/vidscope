"""`vidscope status` — show the last N pipeline runs."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.get_status import GetStatusUseCase
from vidscope.cli._support import acquire_container, console, handle_domain_errors
from vidscope.domain import RunStatus

__all__ = ["status_command"]


_STATUS_STYLE: dict[RunStatus, str] = {
    RunStatus.OK: "green",
    RunStatus.FAILED: "red",
    RunStatus.SKIPPED: "yellow",
    RunStatus.PENDING: "cyan",
    RunStatus.RUNNING: "blue",
}


def status_command(
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Number of recent runs to display.",
        min=1,
        max=100,
    ),
) -> None:
    """Show the last N pipeline runs and quick aggregate counts."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = GetStatusUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(limit=limit)

        console.print(
            f"[bold]videos:[/bold] {result.total_videos}   "
            f"[bold]pipeline runs:[/bold] {result.total_runs}"
        )

        if not result.runs:
            console.print(
                "[dim]No pipeline runs yet. "
                "Run [bold]vidscope add <url>[/bold] to create one.[/dim]"
            )
            return

        table = Table(
            title=f"Last {len(result.runs)} pipeline runs",
            show_header=True,
            header_style="bold",
        )
        table.add_column("id", justify="right", style="dim")
        table.add_column("phase")
        table.add_column("status")
        table.add_column("video", justify="right")
        table.add_column("started")
        table.add_column("duration", justify="right")
        table.add_column("error", overflow="fold")

        for run in result.runs:
            style = _STATUS_STYLE.get(run.status, "")
            duration = run.duration()
            table.add_row(
                str(run.id) if run.id is not None else "-",
                run.phase.value,
                f"[{style}]{run.status.value}[/{style}]" if style else run.status.value,
                str(run.video_id) if run.video_id is not None else "-",
                run.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                f"{duration.total_seconds():.1f}s" if duration else "-",
                (run.error or "")[:80],
            )

        console.print(table)
