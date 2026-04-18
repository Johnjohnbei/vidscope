"""`vidscope search <query> [--content-type TYPE] [--min-actionability N]
[--sponsored BOOL] [--status S] [--starred/--unstarred] [--tag NAME]
[--collection NAME]`

M010: content_type, min_actionability, is_sponsored facets.
M011/S03: status, starred, tag, collection facets.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from vidscope.application.search_library import SearchLibraryResult, SearchLibraryUseCase
from vidscope.application.search_videos import SearchFilters, SearchVideosUseCase
from vidscope.cli._support import acquire_container, console, handle_domain_errors, parse_tracking_status
from vidscope.domain import ContentType, TrackingStatus

__all__ = ["search_command"]


def _parse_sponsored(raw: str | None) -> bool | None:
    if raw is None:
        return None
    norm = raw.strip().lower()
    if norm in {"true", "yes", "1"}:
        return True
    if norm in {"false", "no", "0"}:
        return False
    raise typer.BadParameter(f"--sponsored expects true|false, got {raw!r}")


def _parse_content_type(raw: str | None) -> ContentType | None:
    if raw is None:
        return None
    norm = raw.strip().lower()
    try:
        return ContentType(norm)
    except ValueError as exc:
        valid = ", ".join(sorted(c.value for c in ContentType))
        raise typer.BadParameter(
            f"--content-type must be one of: {valid}. Got {raw!r}."
        ) from exc



def search_command(
    query: Annotated[str, typer.Argument(help="FTS5 query to run against the index.")],
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, max=200,
                                       help="Maximum number of hits to display.")] = 20,
    content_type: Annotated[str | None, typer.Option("--content-type",
        help="Restrict to videos whose latest analysis has this content_type "
             "(tutorial, review, vlog, news, story, opinion, comedy, "
             "educational, promo, unknown).")] = None,
    min_actionability: Annotated[int | None, typer.Option("--min-actionability",
        min=0, max=100,
        help="Restrict to videos whose latest analysis has actionability >= N "
             "(0-100, excludes NULL).")] = None,
    sponsored: Annotated[str | None, typer.Option("--sponsored",
        help="true = only sponsored videos, false = only non-sponsored.")] = None,
    status: Annotated[str | None, typer.Option("--status",
        help="Workflow status: new, reviewed, saved, actioned, ignored, archived.")] = None,
    starred: Annotated[bool | None, typer.Option(
        "--starred/--unstarred",
        help="Filter by starred flag (--starred or --unstarred; omit for no filter).",
    )] = None,
    tag: Annotated[str | None, typer.Option("--tag",
        help="Only videos tagged with NAME (case-insensitive).")] = None,
    collection: Annotated[str | None, typer.Option("--collection",
        help="Only videos in collection NAME (case-sensitive).")] = None,
) -> None:
    """Run a full-text query through the SQLite FTS5 index."""
    with handle_domain_errors():
        parsed_ct = _parse_content_type(content_type)
        parsed_sp = _parse_sponsored(sponsored)
        parsed_status = parse_tracking_status(status)

        filters = SearchFilters(
            content_type=parsed_ct,
            min_actionability=float(min_actionability) if min_actionability is not None else None,
            is_sponsored=parsed_sp,
            status=parsed_status,
            starred=starred,
            tag=tag.lower().strip() if tag else None,
            collection=collection.strip() if collection else None,
        )

        container = acquire_container()
        use_case = SearchVideosUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(query, limit=limit, filters=filters)

        console.print(
            f"[bold]query:[/bold] {result.query!r}   "
            f"[bold]hits:[/bold] {len(result.hits)}"
            + (f"   [dim]filters: {_fmt_filters(filters)}[/dim]" if not filters.is_empty() else "")
        )

        if not result.hits:
            console.print("[dim]No matches.[/dim]")
            return

        table = Table(title="Search results", show_header=True)
        table.add_column("video", justify="right", style="dim")
        table.add_column("source")
        table.add_column("rank", justify="right")
        table.add_column("snippet", overflow="fold")

        for hit in result.hits:
            table.add_row(
                str(hit.video_id),
                hit.source,
                f"{hit.rank:.2f}",
                hit.snippet,
            )

        console.print(table)


def _fmt_filters(f: SearchFilters) -> str:
    parts = []
    if f.content_type is not None:
        parts.append(f"content_type={f.content_type.value}")
    if f.min_actionability is not None:
        parts.append(f"min_actionability>={f.min_actionability:.0f}")
    if f.is_sponsored is not None:
        parts.append(f"sponsored={'yes' if f.is_sponsored else 'no'}")
    if f.status is not None:
        parts.append(f"status={f.status.value}")
    if f.starred is not None:
        parts.append(f"starred={'yes' if f.starred else 'no'}")
    if f.tag is not None:
        parts.append(f"tag={f.tag}")
    if f.collection is not None:
        parts.append(f"collection={f.collection}")
    return " ".join(parts) if parts else "none"
