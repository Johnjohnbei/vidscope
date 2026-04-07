"""`vidscope cookies ...` subcommands — manage the cookies file.

Three subcommands sit on top of the M005 cookies use cases:

- ``vidscope cookies set <source-path>`` — copy a cookies.txt into the canonical location
- ``vidscope cookies status`` — show the current cookies state
- ``vidscope cookies clear [--yes]`` — remove the canonical cookies file

The Typer sub-application is registered on the root app in
:mod:`vidscope.cli.app` via ``app.add_typer(cookies_app, name="cookies")``.

The probe subcommand (``vidscope cookies test``) ships in S02.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from vidscope.application.cookies import (
    ClearCookiesUseCase,
    CookiesProbeUseCase,
    GetCookiesStatusUseCase,
    SetCookiesUseCase,
)
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)
from vidscope.ports import ProbeStatus

__all__ = ["cookies_app"]


cookies_app = typer.Typer(
    name="cookies",
    help="Manage the Netscape cookies file used by yt-dlp for gated platforms.",
    no_args_is_help=True,
    add_completion=False,
)


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------


@cookies_app.command("set")
def set_cookies(
    source: Annotated[
        Path,
        typer.Argument(
            help=(
                "Path to a Netscape-format cookies.txt file exported "
                "from your browser."
            ),
            exists=False,
        ),
    ],
) -> None:
    """Copy a cookies file into VidScope's canonical location.

    The source file is validated as Netscape format before being
    copied to ``<data_dir>/cookies.txt``. The original is left
    untouched. If a cookies file already exists at the destination,
    it is overwritten — but only if the new source is valid.
    """
    with handle_domain_errors():
        container = acquire_container()
        use_case = SetCookiesUseCase(data_dir=container.config.data_dir)
        result = use_case.execute(source.expanduser().resolve())

        if not result.success:
            raise fail_user(result.message)

        console.print(f"[green]OK[/green] {result.message}")
        if container.config.cookies_file is not None and (
            container.config.cookies_file != result.destination
        ):
            console.print(
                "[yellow]warning:[/yellow] VIDSCOPE_COOKIES_FILE is set to "
                f"{container.config.cookies_file}, which means yt-dlp will "
                "ignore the file you just installed. Unset VIDSCOPE_COOKIES_FILE "
                "to use the canonical location."
            )


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@cookies_app.command("status")
def status() -> None:
    """Show the current state of the cookies file."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = GetCookiesStatusUseCase(
            data_dir=container.config.data_dir,
            configured_cookies_file=container.config.cookies_file,
        )
        result = use_case.execute()

        table = Table(title="vidscope cookies status", show_header=True, header_style="bold")
        table.add_column("field")
        table.add_column("value", overflow="fold")

        table.add_row("default path", str(result.default_path))
        table.add_row(
            "default exists",
            "[green]yes[/green]" if result.default_exists else "[yellow]no[/yellow]",
        )

        if result.default_exists:
            table.add_row("size", f"{result.size_bytes} bytes")
            if result.modified_at is not None:
                table.add_row(
                    "last modified",
                    result.modified_at.strftime("%Y-%m-%d %H:%M:%S %z"),
                )
            if result.validation.ok:
                table.add_row(
                    "format valid",
                    f"[green]yes[/green] ({result.validation.entries_count} entries)",
                )
            else:
                table.add_row(
                    "format valid",
                    f"[red]no[/red] — {result.validation.reason}",
                )

        if result.env_override_path is not None:
            table.add_row(
                "env override",
                f"[yellow]VIDSCOPE_COOKIES_FILE={result.env_override_path}[/yellow]",
            )
            table.add_row("active path (used by yt-dlp)", str(result.active_path))
        elif result.active_path is not None:
            table.add_row("active path (used by yt-dlp)", str(result.active_path))
        else:
            table.add_row(
                "active path (used by yt-dlp)",
                "[yellow]none — cookies feature disabled[/yellow]",
            )

        console.print(table)


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


@cookies_app.command("test")
def test_cookies(
    url: Annotated[
        str | None,
        typer.Option(
            "--url",
            "-u",
            help=(
                "URL to probe. Defaults to a stable Instagram public Reel. "
                "Use a TikTok or YouTube URL to test those platforms instead."
            ),
        ),
    ] = None,
) -> None:
    """Probe a video URL to verify cookies authenticate against the platform.

    Performs a metadata-only call (no media download, no transcribe,
    no DB write). Reports one of:

    - cookies work / no cookies needed → ``ok``
    - cookies expired or missing → ``auth_required``
    - URL not found / network error / unsupported → corresponding status
    """
    with handle_domain_errors():
        container = acquire_container()
        use_case = CookiesProbeUseCase(
            downloader=container.downloader,
            cookies_configured=container.config.cookies_file is not None,
        )
        result = use_case.execute(url)

        status_color = {
            ProbeStatus.OK: "green",
            ProbeStatus.AUTH_REQUIRED: "yellow",
            ProbeStatus.NOT_FOUND: "yellow",
            ProbeStatus.NETWORK_ERROR: "yellow",
            ProbeStatus.UNSUPPORTED: "red",
            ProbeStatus.ERROR: "red",
        }.get(result.probe.status, "red")

        console.print(
            f"[bold]URL:[/bold]    {result.probe.url}\n"
            f"[bold]status:[/bold] [{status_color}]{result.probe.status.value}[/{status_color}]\n"
            f"[bold]detail:[/bold] {result.probe.detail}\n"
            f"\n[bold]interpretation:[/bold] {result.interpretation}"
        )

        if result.probe.status != ProbeStatus.OK:
            raise typer.Exit(1)


@cookies_app.command("clear")
def clear(
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip the confirmation prompt.",
        ),
    ] = False,
) -> None:
    """Remove the cookies file from VidScope's canonical location.

    Only removes ``<data_dir>/cookies.txt``. A file pointed to by the
    ``VIDSCOPE_COOKIES_FILE`` env var is owned by the user and is
    never touched by this command.
    """
    with handle_domain_errors():
        container = acquire_container()
        target = container.config.data_dir / "cookies.txt"

        if not yes and target.exists():
            confirmed = typer.confirm(
                f"Remove {target}?",
                default=False,
            )
            if not confirmed:
                console.print("[dim]aborted[/dim]")
                raise typer.Exit(0)

        use_case = ClearCookiesUseCase(data_dir=container.config.data_dir)
        result = use_case.execute()

        if not result.success:
            raise fail_user(result.message)

        console.print(f"[green]OK[/green] {result.message}")
