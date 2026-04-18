"""`vidscope collection ...` subcommands (M011/S02/R057)."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.collection_library import (
    AddToCollectionUseCase,
    CreateCollectionUseCase,
    ListCollectionsUseCase,
    RemoveFromCollectionUseCase,
)
from vidscope.cli._support import acquire_container, console, handle_domain_errors

__all__ = ["collection_app"]


collection_app = typer.Typer(
    name="collection",
    help="Manage video collections (create, add, remove, list, show).",
    no_args_is_help=True,
    add_completion=False,
)


@collection_app.command("create")
def collection_create(
    name: str = typer.Argument(..., help="Collection name (case-preserved)."),
) -> None:
    """Create a new collection."""
    with handle_domain_errors():
        container = acquire_container()
        uc = CreateCollectionUseCase(unit_of_work_factory=container.unit_of_work)
        c = uc.execute(name)
        console.print(
            f"[bold green]created[/bold green] collection [bold]{c.name}[/bold] (id={c.id})"
        )


@collection_app.command("add")
def collection_add(
    collection_name: str = typer.Argument(..., help="Collection name."),
    video_id: int = typer.Argument(..., help="Video id."),
) -> None:
    """Add a video to a collection."""
    with handle_domain_errors():
        container = acquire_container()
        uc = AddToCollectionUseCase(unit_of_work_factory=container.unit_of_work)
        c = uc.execute(collection_name, video_id)
        console.print(
            f"[bold green]added[/bold green] video {video_id} to "
            f"[bold]{c.name}[/bold]"
        )


@collection_app.command("remove")
def collection_remove(
    collection_name: str = typer.Argument(..., help="Collection name."),
    video_id: int = typer.Argument(..., help="Video id."),
) -> None:
    """Remove a video from a collection."""
    with handle_domain_errors():
        container = acquire_container()
        uc = RemoveFromCollectionUseCase(unit_of_work_factory=container.unit_of_work)
        c = uc.execute(collection_name, video_id)
        console.print(
            f"[bold green]removed[/bold green] video {video_id} from "
            f"[bold]{c.name}[/bold]"
        )


@collection_app.command("list")
def collection_list() -> None:
    """List every collection with its video count."""
    with handle_domain_errors():
        container = acquire_container()
        uc = ListCollectionsUseCase(unit_of_work_factory=container.unit_of_work)
        summaries = uc.execute()
        console.print(f"[bold]collections:[/bold] {len(summaries)}")
        if not summaries:
            console.print(
                "[dim]No collections yet. "
                "Run [bold]vidscope collection create <name>[/bold].[/dim]"
            )
            return
        table = Table(title="Collections", show_header=True)
        table.add_column("id", justify="right", style="dim")
        table.add_column("name")
        table.add_column("videos", justify="right")
        table.add_column("created")
        for s in summaries:
            created = (
                s.collection.created_at.strftime("%Y-%m-%d %H:%M")
                if s.collection.created_at else "-"
            )
            table.add_row(
                str(s.collection.id), s.collection.name,
                str(s.video_count), created,
            )
        console.print(table)


@collection_app.command("show")
def collection_show(
    name: str = typer.Argument(..., help="Collection name."),
) -> None:
    """Show the videos in a collection."""
    with handle_domain_errors():
        container = acquire_container()
        with container.unit_of_work() as uow:
            coll = uow.collections.get_by_name(name)
            if coll is None or coll.id is None:
                console.print(f"[red]collection {name!r} does not exist[/red]")
                raise typer.Exit(code=1)
            video_ids = uow.collections.list_videos(coll.id)
        console.print(
            f"[bold]{coll.name}[/bold]: "
            + (
                ", ".join(str(int(v)) for v in video_ids)
                if video_ids else "(empty)"
            )
        )
