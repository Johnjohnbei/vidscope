"""`vidscope show <id>` — show the full record for a video id."""

from __future__ import annotations

import typer
from rich.panel import Panel

from vidscope.application.show_video import ShowVideoUseCase
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)

__all__ = ["show_command"]


def show_command(
    video_id: int = typer.Argument(..., help="Numeric id of the video to show."),
) -> None:
    """Show the full domain record for one video id."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = ShowVideoUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(video_id)

        if not result.found or result.video is None:
            raise fail_user(f"no video with id {video_id}")

        video = result.video
        lines = [
            f"[bold]id:[/bold] {video.id}",
            f"[bold]platform:[/bold] {video.platform.value}",
            f"[bold]platform_id:[/bold] {video.platform_id}",
            f"[bold]url:[/bold] {video.url}",
            f"[bold]title:[/bold] {video.title or '-'}",
            f"[bold]author:[/bold] {video.author or '-'}",
            f"[bold]duration:[/bold] "
            f"{f'{video.duration:.1f}s' if video.duration else '-'}",
            f"[bold]media_key:[/bold] {video.media_key or '-'}",
        ]
        console.print(
            Panel.fit(
                "\n".join(lines),
                title=f"[bold]video #{video.id}[/bold]",
                border_style="cyan",
            )
        )

        if result.transcript is not None:
            t = result.transcript
            console.print(
                f"[bold]transcript:[/bold] {t.language.value}, "
                f"{len(t.full_text)} chars, {len(t.segments)} segments"
            )
        else:
            console.print("[dim]transcript: none yet[/dim]")

        console.print(f"[bold]frames:[/bold] {len(result.frames)}")

        if result.analysis is not None:
            a = result.analysis
            console.print(
                f"[bold]analysis:[/bold] {a.provider}, "
                f"score={a.score if a.score is not None else '-'}, "
                f"{len(a.keywords)} keywords, {len(a.topics)} topics"
            )
        else:
            console.print("[dim]analysis: none yet[/dim]")
