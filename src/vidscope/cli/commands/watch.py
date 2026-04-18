"""`vidscope watch ...` subcommands — manage the account watchlist.

Four sub-commands sit on top of the M003 watchlist use cases:

- ``vidscope watch add <url>`` — register a public account
- ``vidscope watch list`` — show every watched account
- ``vidscope watch remove <handle> [--platform]`` — drop one
- ``vidscope watch refresh`` — fetch new videos for every account

The Typer sub-application is registered on the root app in
:mod:`vidscope.cli.app` via ``app.add_typer(watch_app, name="watch")``.
"""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.refresh_stats import (
    RefreshStatsForWatchlistUseCase,
    RefreshStatsUseCase,
)
from vidscope.application.watchlist import (
    AddWatchedAccountUseCase,
    ListWatchedAccountsUseCase,
    RefreshWatchlistUseCase,
    RemoveWatchedAccountUseCase,
)
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)
from vidscope.domain import Platform

__all__ = ["watch_app"]


watch_app = typer.Typer(
    name="watch",
    help="Manage the account watchlist (add accounts and refresh on demand).",
    no_args_is_help=True,
    add_completion=False,
)


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


@watch_app.command("add")
def add(
    url: str = typer.Argument(
        ...,
        help=(
            "Public account URL — e.g. https://www.youtube.com/@YouTube, "
            "https://www.tiktok.com/@tiktok, https://www.instagram.com/@instagram."
        ),
    ),
) -> None:
    """Add a public account to the watchlist."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = AddWatchedAccountUseCase(
            unit_of_work_factory=container.unit_of_work
        )
        result = use_case.execute(url)
        if not result.success:
            raise fail_user(result.message)
        assert result.account is not None
        console.print(
            f"[bold green]added[/bold green] "
            f"{result.account.platform.value}/{result.account.handle}"
        )


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@watch_app.command("list")
def list_accounts() -> None:
    """List every watched account."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = ListWatchedAccountsUseCase(
            unit_of_work_factory=container.unit_of_work
        )
        result = use_case.execute()

        console.print(f"[bold]watched accounts:[/bold] {result.total}")
        if result.total == 0:
            console.print(
                "[dim]No accounts yet. "
                "Run [bold]vidscope watch add <url>[/bold] to add one.[/dim]"
            )
            return

        table = Table(
            title=f"Watchlist ({result.total})", show_header=True
        )
        table.add_column("id", justify="right", style="dim")
        table.add_column("platform")
        table.add_column("handle")
        table.add_column("url", overflow="fold")
        table.add_column("last checked")

        for account in result.accounts:
            last = (
                account.last_checked_at.strftime("%Y-%m-%d %H:%M")
                if account.last_checked_at is not None
                else "-"
            )
            table.add_row(
                str(account.id),
                account.platform.value,
                account.handle,
                account.url,
                last,
            )

        console.print(table)


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


@watch_app.command("remove")
def remove(
    handle: str = typer.Argument(
        ...,
        help="Handle to remove (e.g. @YouTube).",
    ),
    platform: str | None = typer.Option(
        None,
        "--platform",
        "-p",
        help="Platform to disambiguate (youtube, tiktok, instagram).",
    ),
) -> None:
    """Remove an account from the watchlist."""
    with handle_domain_errors():
        container = acquire_container()
        platform_enum: Platform | None = None
        if platform is not None:
            try:
                platform_enum = Platform(platform.lower())
            except ValueError as exc:
                raise fail_user(
                    f"unknown platform {platform!r}; "
                    f"expected one of: youtube, tiktok, instagram"
                ) from exc

        use_case = RemoveWatchedAccountUseCase(
            unit_of_work_factory=container.unit_of_work
        )
        result = use_case.execute(handle, platform=platform_enum)
        if not result.success:
            raise fail_user(result.message)
        console.print(f"[bold green]removed[/bold green] {result.message[8:]}")


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


@watch_app.command("refresh")
def refresh(
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Maximum number of recent videos to check per account.",
        min=1,
        max=100,
    ),
) -> None:
    """Fetch new videos for every watched account and refresh their stats."""
    with handle_domain_errors():
        container = acquire_container()

        # Step 1 — M003: ingest new videos for every watched account
        watch_uc = RefreshWatchlistUseCase(
            unit_of_work_factory=container.unit_of_work,
            pipeline_runner=container.pipeline_runner,
            downloader=container.downloader,
            clock=container.clock,
            per_account_limit=limit,
        )
        watch_summary = watch_uc.execute()

        # Step 2 — M009/S03: refresh stats for every video of every watched creator.
        # Wrapped in an isolated try so a global stats failure does NOT hide the
        # watch summary already computed above (T-ISO-03).
        stats_result = None
        stats_error: str | None = None
        try:
            stats_uc = RefreshStatsForWatchlistUseCase(
                refresh_stats=RefreshStatsUseCase(
                    stats_stage=container.stats_stage,
                    unit_of_work_factory=container.unit_of_work,
                    clock=container.clock,
                ),
                unit_of_work_factory=container.unit_of_work,
            )
            stats_result = stats_uc.execute()
        except Exception as exc:
            stats_error = f"stats refresh failed: {exc}"

        _render_combined_summary(watch_summary, stats_result, stats_error)


def _render_combined_summary(
    watch_summary: object,
    stats_result: object,
    stats_error: str | None,
) -> None:
    """Print the combined watch+stats refresh summary.

    Matches D-05 requirement: both counters (new_videos + stats_refreshed)
    visible in one output. ASCII-only — no Unicode glyphs.
    """
    from vidscope.application.refresh_stats import RefreshStatsForWatchlistResult
    from vidscope.application.watchlist import RefreshSummary

    assert isinstance(watch_summary, RefreshSummary)

    console.print(
        f"[bold]watch refresh:[/bold] "
        f"accounts={watch_summary.accounts_checked} "
        f"new_videos={watch_summary.new_videos_ingested}"
    )

    if stats_result is not None:
        assert isinstance(stats_result, RefreshStatsForWatchlistResult)
        console.print(
            f"[bold]stats refresh:[/bold] "
            f"videos={stats_result.videos_checked} "
            f"refreshed={stats_result.stats_refreshed} "
            f"failed={stats_result.failed}"
        )

    if stats_error is not None:
        console.print(f"[red]stats error:[/red] {stats_error}")

    # Per-account detail table (M003 output, preserved)
    if watch_summary.per_account:
        table = Table(title="Per-account results", show_header=True)
        table.add_column("platform")
        table.add_column("handle")
        table.add_column("new", justify="right")
        table.add_column("error", overflow="fold")
        for outcome in watch_summary.per_account:
            table.add_row(
                outcome.platform.value,
                outcome.handle,
                str(outcome.new_videos),
                outcome.error or "",
            )
        console.print(table)

    # Watch-level errors (M003 output, preserved)
    if watch_summary.errors:
        console.print(
            f"[bold yellow]warnings:[/bold yellow] "
            f"{len(watch_summary.errors)} error(s) during watch refresh"
        )
        for err in watch_summary.errors:
            console.print(f"  [yellow]-[/yellow] {err}")

    # Stats-level per-video errors (first 5 only)
    if stats_result is not None:
        assert isinstance(stats_result, RefreshStatsForWatchlistResult)
        if stats_result.errors:
            console.print(f"[dim]stats errors (first 5 of {len(stats_result.errors)}):[/dim]")
            for e in stats_result.errors[:5]:
                console.print(f"  - {e}")
