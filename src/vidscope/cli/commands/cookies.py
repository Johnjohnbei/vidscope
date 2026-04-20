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

_SUPPORTED_BROWSERS = ("chrome", "chromium", "firefox", "brave", "edge", "opera", "vivaldi", "safari")

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


@cookies_app.command("login")
def login(
    platform: Annotated[
        str,
        typer.Argument(help="Platform to authenticate: instagram, tiktok, youtube."),
    ] = "instagram",
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Seconds to wait for login (default 300)."),
    ] = 300,
) -> None:
    """Open a browser, log in, and capture cookies automatically.

    A Chromium window opens — log into the platform normally.
    Cookies are saved as soon as login is detected. No export needed.

    Requires: uv sync --extra auth
    """
    from vidscope.adapters.auth import capture_platform_cookies  # noqa: PLC0415

    from vidscope.adapters.auth.playwright_login import (  # noqa: PLC0415
        SUPPORTED_PLATFORMS,
    )

    if platform not in SUPPORTED_PLATFORMS:
        raise fail_user(
            f"Unsupported platform {platform!r}. "
            f"Supported: {', '.join(SUPPORTED_PLATFORMS)}"
        )

    container = acquire_container()
    # Save to the active path (env override if set, otherwise default).
    canonical_path = container.config.cookies_file or (
        container.config.data_dir / "cookies.txt"
    )

    console.print(
        f"Opening browser for [bold]{platform}[/bold] login… "
        f"(timeout {timeout}s)"
    )
    console.print("[dim]Log in normally — the window will close automatically.[/dim]")

    try:
        count = capture_platform_cookies(platform, canonical_path, timeout_seconds=timeout)
    except ImportError as exc:
        raise fail_user(str(exc)) from exc
    except RuntimeError as exc:
        raise fail_user(str(exc)) from exc

    console.print(f"[green]OK[/green] {count} cookies saved to {canonical_path}")
    console.print("[dim]Run [bold]vidscope cookies test[/bold] to verify.[/dim]")


@cookies_app.command("from-browser")
def from_browser(
    browser: Annotated[
        str,
        typer.Argument(
            help=(
                "Browser to extract cookies from. "
                f"Supported: {', '.join(_SUPPORTED_BROWSERS)}."
            ),
        ),
    ],
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Browser profile name or path (optional).",
        ),
    ] = None,
) -> None:
    """Extract cookies directly from your browser — no export needed.

    Reads the browser's local cookie store and saves the relevant
    cookies to VidScope's canonical location. You must be logged into
    Instagram (or other platforms) in the specified browser.

    Examples:

        vidscope cookies from-browser chrome

        vidscope cookies from-browser firefox --profile work

    Run ``vidscope cookies test`` afterwards to verify the cookies work.
    """
    import yt_dlp

    browser_lower = browser.lower()
    if browser_lower not in _SUPPORTED_BROWSERS:
        raise fail_user(
            f"Unsupported browser {browser!r}. "
            f"Supported: {', '.join(_SUPPORTED_BROWSERS)}"
        )

    container = acquire_container()
    canonical_path = container.config.data_dir / "cookies.txt"

    browser_spec = f"{browser_lower}:{profile}" if profile else browser_lower
    console.print(f"Extracting cookies from [bold]{browser_spec}[/bold]...")

    try:
        options: dict = {
            "cookiesfrombrowser": (browser_lower, profile, None, None),
            "cookiefile": str(canonical_path),
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(options):
            pass  # cookie load happens in __init__, save happens in __exit__
    except Exception as exc:
        msg = str(exc)
        if any(k in msg.lower() for k in ("not found", "could not find", "no such")):
            raise fail_user(
                f"Browser {browser_lower!r} not found. "
                "Make sure it is installed and you have logged into Instagram."
            ) from exc
        raise fail_user(f"Failed to extract cookies from {browser_lower!r}: {msg}") from exc

    if not canonical_path.exists() or canonical_path.stat().st_size == 0:
        raise fail_user(
            f"No cookies were written for {browser_lower!r}. "
            "Make sure you are logged into Instagram in that browser."
        )

    cookie_lines = [
        ln for ln in canonical_path.read_text(encoding="utf-8").splitlines()
        if ln and not ln.startswith("#")
    ]
    console.print(
        f"[green]OK[/green] {len(cookie_lines)} cookies saved to {canonical_path}"
    )
    console.print(
        "[dim]Run [bold]vidscope cookies test[/bold] to verify Instagram access.[/dim]"
    )


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
