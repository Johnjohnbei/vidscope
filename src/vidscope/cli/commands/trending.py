"""`vidscope trending --since <window>` — rank ingested videos by velocity.

Per M009 D-04:
- --since MANDATORY (no silent default, D-04)
- --limit default 20, min=1 (T-INPUT-01)
- --platform optional (instagram|tiktok|youtube)
- --min-velocity default 0.0
- rich.Table output, ASCII-only (no Unicode glyphs in stdout)
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

import typer
from rich.table import Table

from vidscope.application.list_trending import ListTrendingUseCase, TrendingEntry
from vidscope.cli._support import (
    acquire_container,
    console,
    handle_domain_errors,
)
from vidscope.domain import Platform

__all__ = ["trending_command"]


def _parse_window(raw: str) -> timedelta:
    """Strict N(h|d) parser — refuses '1week', '7', '30m', '-1d'.

    Per D-04: --since is mandatory and must be an explicit window.
    The parser is intentionally strict to surface misconfiguration
    early rather than silently using a wrong time window.

    Raises
    ------
    typer.BadParameter
        When the format is invalid (T-INPUT-02).
    """
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


def _parse_platform(raw: str | None) -> Platform | None:
    """Parse a platform string into a :class:`Platform` enum value.

    Raises
    ------
    typer.BadParameter
        When the platform string is not a valid platform name (T-INPUT-03).
    """
    if raw is None:
        return None
    try:
        return Platform(raw.strip().lower())
    except ValueError:
        raise typer.BadParameter(
            f"invalid --platform: {raw!r} (expected instagram|tiktok|youtube)"
        )


def trending_command(
    since: Annotated[
        str,
        typer.Option("--since", help="Time window (mandatory), e.g. 7d or 24h."),
    ],
    platform: Annotated[
        str | None,
        typer.Option(
            "--platform",
            help="Filter by platform (instagram|tiktok|youtube).",
        ),
    ] = None,
    min_velocity: Annotated[
        float,
        typer.Option("--min-velocity", help="Minimum views/hour to appear."),
    ] = 0.0,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            min=1,
            help="Max results (must be >= 1).",
        ),
    ] = 20,
) -> None:
    """Rank ingested videos by views_velocity_24h descending.

    --since is MANDATORY (D-04: no silent default).
    """
    with handle_domain_errors():
        window = _parse_window(since)
        plat = _parse_platform(platform)
        container = acquire_container()
        uc = ListTrendingUseCase(
            unit_of_work_factory=container.unit_of_work,
            clock=container.clock,
        )
        results = uc.execute(
            since=window,
            platform=plat,
            min_velocity=min_velocity,
            limit=limit,
        )
        _render_trending(results)


def _render_trending(results: list[TrendingEntry]) -> None:
    """Render the trending results as a rich Table (ASCII-only output).

    ASCII-only: no Unicode checkmarks, arrows, or other glyphs.
    Per .gsd/KNOWLEDGE.md: stdout must be ASCII-safe for log files.
    """
    if not results:
        console.print("[dim]No trending videos in this window.[/dim]")
        return

    table = Table(title=f"Trending ({len(results)})", show_header=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("title", max_width=40)
    table.add_column("platform")
    table.add_column("velocity_24h", justify="right")
    table.add_column("engagement%", justify="right")
    table.add_column("last capture")

    for i, entry in enumerate(results, start=1):
        title = (entry.title or "?")[:40]
        velocity = (
            f"{entry.views_velocity_24h:.1f}"
            if entry.views_velocity_24h
            else "0.0"
        )
        er = (
            f"{entry.engagement_rate * 100:.1f}%"
            if entry.engagement_rate is not None
            else "-"
        )
        last = entry.last_captured_at.strftime("%Y-%m-%d %H:%M")
        table.add_row(str(i), title, entry.platform.value, velocity, er, last)

    console.print(table)
