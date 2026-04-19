"""`vidscope show <id>` — show the full record for a video id."""

from __future__ import annotations

import typer
from rich.panel import Panel

from vidscope.application.show_video import ShowVideoResult, ShowVideoUseCase
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)

__all__ = ["show_command"]

_DESC_MAX = 240
_FRAME_TEXT_PREVIEW = 5


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
        desc = video.description or "-"
        if len(desc) > _DESC_MAX:
            desc = desc[:_DESC_MAX] + "..."

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
            f"[bold]description:[/bold] {desc}",
        ]
        console.print(
            Panel.fit(
                "\n".join(lines),
                title=f"[bold]video #{video.id}[/bold]",
                border_style="cyan",
            )
        )

        # Music
        if video.music_track:
            music = video.music_track
            if video.music_artist:
                music = f"{music} — {video.music_artist}"
            console.print(f"[bold]music:[/bold] {music}")
        else:
            console.print("[dim]music: none[/dim]")

        # Hashtags
        if result.hashtags:
            tags_str = "  ".join(f"#{h.tag}" for h in result.hashtags)
            console.print(f"[bold]hashtags:[/bold] {tags_str}")
        else:
            console.print("[dim]hashtags: none[/dim]")

        # Mentions
        if result.mentions:
            ment_str = "  ".join(f"@{m.handle}" for m in result.mentions)
            console.print(f"[bold]mentions:[/bold] {ment_str}")
        else:
            console.print("[dim]mentions: none[/dim]")

        # Transcript / frames / analysis
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

        # M008: on-screen text (frame_texts)
        _render_frame_texts(result)

        # M008: thumbnail + content_shape
        thumb = result.thumbnail_key or "none"
        console.print(f"[bold]thumbnail:[/bold] {thumb}")
        shape = result.content_shape or "unknown"
        console.print(f"[bold]content_shape:[/bold] {shape}")

        _render_stats(result, video_id)


def _render_frame_texts(result: ShowVideoResult) -> None:
    """Render on-screen text section (M008)."""
    if not result.frame_texts:
        console.print("[dim]on-screen text: none[/dim]")
        return
    n = len(result.frame_texts)
    console.print(f"[bold]on-screen text:[/bold] {n} block(s)")
    preview = result.frame_texts[:_FRAME_TEXT_PREVIEW]
    for ft in preview:
        console.print(f"  - {ft.text}")
    remaining = n - len(preview)
    if remaining > 0:
        console.print(f"  ...and {remaining} more")


def _render_stats(result: ShowVideoResult, video_id: int) -> None:
    """D-05: display latest stats snapshot + computed velocity."""
    if result.latest_stats is None:
        console.print(
            "[dim]Stats:[/dim] "
            f"Aucune stat capturee - lancez: vidscope refresh-stats {video_id}"
        )
        return

    s = result.latest_stats
    parts = [
        f"captured_at={s.captured_at.strftime('%Y-%m-%d %H:%M')}",
        f"views={s.view_count if s.view_count is not None else '-'}",
        f"likes={s.like_count if s.like_count is not None else '-'}",
        f"reposts={s.repost_count if s.repost_count is not None else '-'}",
        f"comments={s.comment_count if s.comment_count is not None else '-'}",
        f"saves={s.save_count if s.save_count is not None else '-'}",
    ]
    console.print("[bold]Stats[/bold]: " + "  ".join(parts))

    if result.views_velocity_24h is not None:
        console.print(
            f"  velocity_24h: {result.views_velocity_24h:.1f} views/hour"
        )
    else:
        console.print(
            f"  velocity_24h: n/a (need >= 2 snapshots - "
            f"run vidscope refresh-stats {video_id} again)"
        )
