"""`vidscope refresh-stats ...` — probe engagement counters on ingested videos.

Adds one row to ``video_stats`` per invocation (append-only, D031). The
command supports:

- Single-video mode: ``vidscope refresh-stats <video_id>``
- Batch mode: ``vidscope refresh-stats --all [--since Nd|Nh] [--limit N]``

Follows the M002/M003/M005 Typer command pattern (registered on the root
app as a direct command, matching add_command, list_command, etc.).

T-INPUT-01: ``--limit`` enforces ``min=1`` at Typer parse time. The use
case double-validates via ``ValueError`` for defense-in-depth.

T-INPUT-02: ``--since`` uses a strict ``N(h|d)`` parser that rejects
bare numbers (``7``), verbose strings (``1week``), and negative values.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

import typer

from vidscope.application.refresh_stats import RefreshStatsBatchResult, RefreshStatsResult, RefreshStatsUseCase
from vidscope.cli._support import acquire_container, console, fail_user, handle_domain_errors
from vidscope.domain import VideoId

__all__ = ["refresh_stats_command"]


def _parse_since(raw: str | None) -> timedelta | None:
    """Parse a short window string like ``7d`` or ``24h``.

    Format: ``N(h|d)`` where N is a positive integer. Returns ``None``
    if ``raw`` is empty or ``None``.

    Raises
    ------
    typer.BadParameter
        When the format is invalid (T-INPUT-02).
    """
    if raw is None or not raw.strip():
        return None
    s = raw.strip().lower()
    if len(s) < 2 or not s[:-1].isdigit():
        raise typer.BadParameter(
            f"invalid --since window: {raw!r} (expected N(h|d), e.g. 7d or 24h)"
        )
    n = int(s[:-1])
    unit = s[-1]
    if n <= 0:
        raise typer.BadParameter(f"--since must be positive, got {raw!r}")
    if unit == "h":
        return timedelta(hours=n)
    if unit == "d":
        return timedelta(days=n)
    raise typer.BadParameter(
        f"invalid --since unit: {unit!r} (expected 'h' or 'd')"
    )


def refresh_stats_command(
    video_id: Annotated[
        int | None,
        typer.Argument(help="Video id to refresh stats for (omit with --all)."),
    ] = None,
    all_: Annotated[
        bool,
        typer.Option("--all", help="Refresh stats for every ingested video."),
    ] = False,
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help="Only refresh videos ingested within this window (e.g. 7d, 24h).",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            min=1,
            help="Max videos to refresh in batch mode (must be >= 1).",
        ),
    ] = 1000,
) -> None:
    """Refresh engagement stats for one video or all ingested videos.

    Single-video mode: ``vidscope refresh-stats <video_id>``

    Batch mode: ``vidscope refresh-stats --all [--since 7d] [--limit 500]``

    Each invocation appends a new stats row (append-only). Duplicate
    probes within the same second are silently ignored at the DB level
    (UNIQUE constraint, D-01).
    """
    with handle_domain_errors():
        container = acquire_container()
        use_case = RefreshStatsUseCase(
            stats_stage=container.stats_stage,
            unit_of_work_factory=container.unit_of_work,
            clock=container.clock,
        )

        if all_:
            window = _parse_since(since)
            batch = use_case.execute_all(since=window, limit=limit)
            _render_batch(batch)
            return

        if video_id is None:
            raise fail_user(
                "Provide a video id or use --all to refresh all videos. See --help."
            )

        result = use_case.execute_one(VideoId(video_id))
        if not result.success:
            raise fail_user(result.message)
        _render_single(result)


def _render_single(result: RefreshStatsResult) -> None:
    """Print a human-readable summary for a single refresh-stats result."""
    console.print(f"[green]OK[/green] refreshed stats for video_id={result.video_id}")
    stats = result.stats
    if stats is not None:
        console.print(
            f"  captured_at: {stats.captured_at.isoformat()}\n"
            f"  views: {stats.view_count}  "
            f"likes: {stats.like_count}  "
            f"reposts: {stats.repost_count}  "
            f"comments: {stats.comment_count}  "
            f"saves: {stats.save_count}"
        )


def _render_batch(batch: RefreshStatsBatchResult) -> None:
    """Print a summary table for a batch refresh-stats result."""
    console.print(
        f"[bold]refresh-stats:[/bold] "
        f"total={batch.total} refreshed={batch.refreshed} failed={batch.failed}"
    )
    if batch.total == 0:
        console.print("[dim]No videos matched.[/dim]")
        return

    from rich.table import Table  # noqa: PLC0415 — local import keeps startup fast

    table = Table(
        title=f"Refresh-stats ({batch.refreshed}/{batch.total})",
        show_header=True,
    )
    table.add_column("video_id", justify="right")
    table.add_column("status")
    table.add_column("message")
    for r in batch.per_video[:100]:
        status = "[green]OK[/green]" if r.success else "[red]FAIL[/red]"
        table.add_row(str(r.video_id), status, (r.message or "")[:80])
    console.print(table)
