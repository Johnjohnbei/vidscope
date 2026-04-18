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


_DESCRIPTION_PREVIEW_CHARS = 240


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

        # M007: description + music + hashtags + mentions
        if video.description:
            preview = video.description
            if len(preview) > _DESCRIPTION_PREVIEW_CHARS:
                preview = preview[: _DESCRIPTION_PREVIEW_CHARS - 1] + "…"
            console.print(f"[bold]description:[/bold] {preview}")
        else:
            console.print("[dim]description: none[/dim]")

        if video.music_track or video.music_artist:
            track = video.music_track or "-"
            artist = video.music_artist or "-"
            console.print(f"[bold]music:[/bold] {track} — {artist}")
        else:
            console.print("[dim]music: none[/dim]")

        if result.hashtags:
            tags = ", ".join(f"#{h.tag}" for h in result.hashtags)
            console.print(f"[bold]hashtags:[/bold] {tags}")
        else:
            console.print("[dim]hashtags: none[/dim]")

        if result.mentions:
            handles = ", ".join(f"@{m.handle}" for m in result.mentions)
            console.print(f"[bold]mentions:[/bold] {handles}")
        else:
            console.print("[dim]mentions: none[/dim]")

        console.print(f"[bold]links:[/bold] {len(result.links)}")

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

        if result.creator is not None:
            c = result.creator
            followers = f"{c.follower_count:,}" if c.follower_count else "-"
            console.print(
                f"[bold]creator:[/bold] {c.handle or c.display_name or '-'} "
                f"([dim]{c.platform.value}[/dim], {followers} followers)"
            )
        else:
            console.print("[dim]creator: unknown[/dim]")
