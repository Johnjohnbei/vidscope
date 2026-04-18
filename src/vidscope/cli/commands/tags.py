"""`vidscope tag ...` subcommands (M011/S02/R057)."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.tag_video import (
    ListTagsUseCase,
    ListVideoTagsUseCase,
    TagVideoUseCase,
    UntagVideoUseCase,
)
from vidscope.cli._support import acquire_container, console, handle_domain_errors

__all__ = ["tag_app"]


tag_app = typer.Typer(
    name="tag",
    help="Manage video tags (add, remove, list).",
    no_args_is_help=True,
    add_completion=False,
)


@tag_app.command("add")
def tag_add(
    video_id: int = typer.Argument(..., help="Video id (from `vidscope list`)."),
    name: str = typer.Argument(..., help="Tag name (will be lowercased)."),
) -> None:
    """Tag a video."""
    with handle_domain_errors():
        container = acquire_container()
        uc = TagVideoUseCase(unit_of_work_factory=container.unit_of_work)
        tag = uc.execute(video_id, name)
        console.print(
            f"[bold green]added[/bold green] tag [bold]{tag.name}[/bold] "
            f"to video {video_id}"
        )


@tag_app.command("remove")
def tag_remove(
    video_id: int = typer.Argument(..., help="Video id."),
    name: str = typer.Argument(..., help="Tag name."),
) -> None:
    """Remove a tag from a video."""
    with handle_domain_errors():
        container = acquire_container()
        uc = UntagVideoUseCase(unit_of_work_factory=container.unit_of_work)
        removed = uc.execute(video_id, name)
        if removed:
            console.print(
                f"[bold green]removed[/bold green] tag {name!r} from video {video_id}"
            )
        else:
            console.print(
                f"[dim]tag {name!r} not assigned to video {video_id} — nothing to do[/dim]"
            )


@tag_app.command("list")
def tag_list() -> None:
    """List every tag globally."""
    with handle_domain_errors():
        container = acquire_container()
        uc = ListTagsUseCase(unit_of_work_factory=container.unit_of_work)
        tags = uc.execute()
        console.print(f"[bold]tags:[/bold] {len(tags)}")
        if not tags:
            console.print(
                "[dim]No tags yet. Run [bold]vidscope tag add <id> <name>[/bold].[/dim]"
            )
            return
        table = Table(title="Tags", show_header=True)
        table.add_column("id", justify="right", style="dim")
        table.add_column("name")
        table.add_column("created")
        for t in tags:
            created = t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "-"
            table.add_row(str(t.id), t.name, created)
        console.print(table)


@tag_app.command("video")
def tag_video_cmd(
    video_id: int = typer.Argument(..., help="Video id."),
) -> None:
    """List the tags assigned to a single video."""
    with handle_domain_errors():
        container = acquire_container()
        uc = ListVideoTagsUseCase(unit_of_work_factory=container.unit_of_work)
        tags = uc.execute(video_id)
        console.print(
            f"[bold]tags for video {video_id}:[/bold] "
            + (", ".join(t.name for t in tags) if tags else "(none)")
        )
