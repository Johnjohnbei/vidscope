"""Typer entry point for ``vidscope``.

Builds the root :class:`typer.Typer` app, registers every command, and
provides a top-level error handler that turns :class:`DomainError`
subclasses into user-actionable messages and exit codes:

- ``0`` success
- ``1`` user error (bad URL, missing id, typed domain error from the
  use case)
- ``2`` system error (missing binary, DB unreachable, unexpected crash)
"""

from __future__ import annotations

import typer
from rich.console import Console

from vidscope import __version__
from vidscope.cli.commands import (
    add_command,
    collection_app,
    cookies_app,
    creator_app,
    doctor_command,
    explain_command,
    export_command,
    links_command,
    list_command,
    mcp_app,
    refresh_stats_command,
    review_command,
    search_command,
    show_command,
    status_command,
    suggest_command,
    tag_app,
    trending_command,
    watch_app,
)

__all__ = ["EXIT_OK", "EXIT_SYSTEM_ERROR", "EXIT_USER_ERROR", "app", "console"]


EXIT_OK = 0
EXIT_USER_ERROR = 1
EXIT_SYSTEM_ERROR = 2


console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"vidscope {__version__}")
        raise typer.Exit(EXIT_OK)


app = typer.Typer(
    name="vidscope",
    help=(
        "VidScope — local video intelligence for Instagram, TikTok and "
        "YouTube. Download, transcribe, analyze, and search public "
        "videos from the command line."
    ),
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


@app.callback()
def main(
    _version: bool = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed vidscope version and exit.",
    ),
) -> None:
    """Root callback — accepts global options like ``--version``."""


# Register each command. Every module exposes its function under a
# conventional name `*_command` so the dispatch is obvious.
app.command("add", help="Ingest a video from a public URL.")(add_command)
app.command("show", help="Show the full record for a video id.")(show_command)
app.command("list", help="List recently ingested videos.")(list_command)
app.command("search", help="Full-text search across transcripts and analyses.")(
    search_command
)
app.command(
    "status",
    help="Show the last N pipeline runs and quick aggregate counts.",
)(status_command)
app.command(
    "suggest",
    help="Suggest related videos from the library by keyword overlap.",
)(suggest_command)
app.command(
    "doctor",
    help="Run startup checks (ffmpeg, yt-dlp) and print a report.",
)(doctor_command)
app.add_typer(mcp_app, name="mcp")
app.add_typer(watch_app, name="watch")
app.add_typer(cookies_app, name="cookies")
app.command(
    "refresh-stats",
    help="Refresh engagement stats for a video or all ingested videos (append-only).",
)(refresh_stats_command)
app.command(
    "trending",
    help="Rank ingested videos by views velocity (--since mandatory).",
)(trending_command)
app.command(
    "explain",
    help="Show reasoning and per-dimension scores of a video's latest analysis.",
)(explain_command)
app.command(
    "review",
    help="Set workflow overlay (status, starred, notes) on a video.",
)(review_command)
app.add_typer(tag_app, name="tag")
app.add_typer(collection_app, name="collection")
app.add_typer(creator_app, name="creator")
app.command(
    "links",
    help="List every URL extracted from a video's description + transcript.",
)(links_command)
app.command(
    "export",
    help="Export the library to JSON / Markdown / CSV.",
)(export_command)
