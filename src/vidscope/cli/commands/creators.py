"""`vidscope creator` sub-commands — show, list, videos."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from vidscope.application.get_creator import GetCreatorUseCase
from vidscope.application.list_creator_videos import ListCreatorVideosUseCase
from vidscope.application.list_creators import ListCreatorsUseCase
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)
from vidscope.domain.values import Platform

__all__ = ["creator_app"]


creator_app = typer.Typer(
    name="creator",
    help="Inspect and list creators in the library.",
    no_args_is_help=True,
)

_PLATFORM_CHOICES = ["youtube", "tiktok", "instagram"]

PlatformArg = Annotated[
    str | None,
    typer.Option(
        "--platform",
        "-p",
        help="Filter by platform: youtube, tiktok, or instagram.",
        case_sensitive=False,
    ),
]


def _parse_platform(value: str | None) -> Platform | None:
    if value is None:
        return None
    v = value.lower()
    try:
        return Platform(v)
    except ValueError:
        raise typer.BadParameter(
            f"'{value}' is not a valid platform. "
            f"Choose from: {', '.join(_PLATFORM_CHOICES)}"
        ) from None


@creator_app.command("show")
def show_creator(
    handle: str = typer.Argument(..., help="Creator handle (e.g. @alice)."),
    platform_str: PlatformArg = None,
) -> None:
    """Show the full profile for a creator identified by handle."""
    platform = _parse_platform(platform_str) or Platform.YOUTUBE

    with handle_domain_errors():
        container = acquire_container()
        use_case = GetCreatorUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(platform, handle)

    if not result.found or result.creator is None:
        raise fail_user(f"no creator '{handle}' found on {platform.value}")

    c = result.creator
    if c.is_verified:
        verified_str = "yes"
    elif c.is_verified is False:
        verified_str = "no"
    else:
        verified_str = "-"
    first_seen = (
        c.first_seen_at.strftime("%Y-%m-%d") if c.first_seen_at else "-"
    )
    last_seen = (
        c.last_seen_at.strftime("%Y-%m-%d") if c.last_seen_at else "-"
    )
    lines = [
        f"[bold]id:[/bold] {int(c.id) if c.id is not None else '-'}",
        f"[bold]platform:[/bold] {c.platform.value}",
        f"[bold]handle:[/bold] {c.handle or '-'}",
        f"[bold]display_name:[/bold] {c.display_name or '-'}",
        (
            f"[bold]followers:[/bold] {c.follower_count:,}"
            if c.follower_count
            else "[bold]followers:[/bold] -"
        ),
        f"[bold]verified:[/bold] {verified_str}",
        f"[bold]profile_url:[/bold] {c.profile_url or '-'}",
        f"[bold]first_seen:[/bold] {first_seen}",
        f"[bold]last_seen:[/bold] {last_seen}",
    ]
    console.print(
        Panel.fit(
            "\n".join(lines),
            title=f"[bold]creator — {c.handle or handle}[/bold]",
            border_style="cyan",
        )
    )


@creator_app.command("list")
def list_creators(
    platform_str: PlatformArg = None,
    min_followers: int | None = typer.Option(
        None,
        "--min-followers",
        "-f",
        help="Only show creators with at least N followers.",
        min=0,
    ),
    limit: int = typer.Option(
        20, "--limit", "-n", help="Number of creators to display.", min=1, max=200
    ),
) -> None:
    """List creators in the library."""
    platform = _parse_platform(platform_str)

    with handle_domain_errors():
        container = acquire_container()
        use_case = ListCreatorsUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(
            platform=platform, min_followers=min_followers, limit=limit
        )

    console.print(f"[bold]total creators:[/bold] {result.total}")

    if not result.creators:
        console.print(
            "[dim]No creators yet. "
            "Run [bold]vidscope add <url>[/bold] to ingest a video.[/dim]"
        )
        return

    table = Table(title=f"Creators ({len(result.creators)})", show_header=True)
    table.add_column("id", justify="right", style="dim")
    table.add_column("platform")
    table.add_column("handle")
    table.add_column("display_name", overflow="fold")
    table.add_column("followers", justify="right")
    table.add_column("verified")
    table.add_column("last_seen")

    for c in result.creators:
        followers = (
            f"{c.follower_count:,}" if c.follower_count is not None else "-"
        )
        if c.is_verified:
            verified = "yes"
        elif c.is_verified is False:
            verified = "no"
        else:
            verified = "-"
        last_seen = (
            c.last_seen_at.strftime("%Y-%m-%d") if c.last_seen_at else "-"
        )
        table.add_row(
            str(int(c.id)) if c.id else "-",
            c.platform.value,
            (c.handle or "-")[:30],
            (c.display_name or "-")[:40],
            followers,
            verified,
            last_seen,
        )

    console.print(table)


@creator_app.command("videos")
def creator_videos(
    handle: str = typer.Argument(..., help="Creator handle (e.g. @alice)."),
    platform_str: PlatformArg = None,
    limit: int = typer.Option(
        20, "--limit", "-n", help="Number of videos to display.", min=1, max=200
    ),
) -> None:
    """List videos ingested from a specific creator."""
    platform = _parse_platform(platform_str) or Platform.YOUTUBE

    with handle_domain_errors():
        container = acquire_container()
        use_case = ListCreatorVideosUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(platform, handle, limit=limit)

    if not result.found or result.creator is None:
        raise fail_user(f"no creator '{handle}' found on {platform.value}")

    creator = result.creator
    console.print(
        f"[bold]creator:[/bold] {creator.handle or handle} "
        f"([dim]{creator.platform.value}[/dim])"
    )
    console.print(f"[bold]total videos:[/bold] {result.total}")

    if not result.videos:
        console.print("[dim]No videos yet for this creator.[/dim]")
        return

    table = Table(
        title=f"Videos by {creator.handle or handle} ({len(result.videos)})",
        show_header=True,
    )
    table.add_column("id", justify="right", style="dim")
    table.add_column("platform")
    table.add_column("title", overflow="fold")
    table.add_column("duration", justify="right")
    table.add_column("ingested")

    for video in result.videos:
        duration = f"{video.duration:.0f}s" if video.duration is not None else "-"
        table.add_row(
            str(int(video.id)) if video.id else "-",
            video.platform.value,
            (video.title or "")[:60],
            duration,
            video.created_at.strftime("%Y-%m-%d") if video.created_at else "-",
        )

    console.print(table)
