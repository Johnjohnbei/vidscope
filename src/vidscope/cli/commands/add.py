"""`vidscope add <url>` — ingest a video from a public URL."""

from __future__ import annotations

import typer
from rich.panel import Panel

from vidscope.application.ingest_video import IngestResult, IngestVideoUseCase
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_system,
    fail_user,
    handle_domain_errors,
)
from vidscope.domain import RunStatus

__all__ = ["add_command"]

_MISSING = "—"


def add_command(
    url: str = typer.Argument(..., help="Public URL of the video to ingest."),
) -> None:
    """Run the full ingest pipeline for a single URL.

    In S02 this downloads the media via yt-dlp, stores it under
    ``MediaStorage``, and writes a persistent ``videos`` row plus a
    ``pipeline_runs`` row. Later slices add transcribe, frames,
    analyze, and index stages to the same runner without changing
    this command's signature.
    """
    with handle_domain_errors():
        container = acquire_container()
        use_case = IngestVideoUseCase(
            unit_of_work_factory=container.unit_of_work,
            pipeline_runner=container.pipeline_runner,
        )
        result = use_case.execute(url)

        if result.status is RunStatus.FAILED:
            raise fail_user(result.message)

        if result.status is RunStatus.OK:
            _render_result_panel(
                result,
                title="[bold green]ingest OK[/bold green]",
                border_style="green",
            )
            return

        if result.status is RunStatus.SKIPPED:
            # S06 will wire is_satisfied-based skipping; plumbing is
            # here now so when it lights up the display is ready.
            _render_result_panel(
                result,
                title="[bold yellow]already ingested (skipped)[/bold yellow]",
                border_style="yellow",
            )
            return

        # Anything else (PENDING, RUNNING) is an unexpected terminal
        # state — surface it as a system error so it is investigable.
        raise fail_system(
            f"unexpected ingest result status: {result.status.value}"
        )


def _render_result_panel(
    result: IngestResult,
    *,
    title: str,
    border_style: str,
) -> None:
    """Pretty-print an :class:`IngestResult` as a rich :class:`Panel`.

    Shared between the OK and SKIPPED paths. Missing fields (None or
    empty) are displayed as an em-dash rather than Python None so the
    panel stays aligned and readable.
    """
    platform_value = result.platform.value if result.platform else _MISSING
    platform_line = (
        f"{platform_value}/{result.platform_id or _MISSING}"
        if result.platform or result.platform_id
        else _MISSING
    )
    duration_line = (
        f"{result.duration:.1f}s"
        if result.duration is not None
        else _MISSING
    )
    video_id_line = (
        str(result.video_id) if result.video_id is not None else _MISSING
    )
    run_id_line = (
        str(result.run_id) if result.run_id is not None else _MISSING
    )

    lines = [
        f"[bold]video id:[/bold] {video_id_line}",
        f"[bold]platform:[/bold]  {platform_line}",
        f"[bold]title:[/bold]     {result.title or _MISSING}",
        f"[bold]author:[/bold]    {result.author or _MISSING}",
        f"[bold]duration:[/bold]  {duration_line}",
        f"[bold]url:[/bold]       [link={result.url}]{result.url}[/link]",
        f"[bold]run id:[/bold]    {run_id_line}",
    ]
    console.print(
        Panel.fit(
            "\n".join(lines),
            title=title,
            border_style=border_style,
        )
    )
