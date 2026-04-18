"""`vidscope search <query>` — FTS5 + M007 facets."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.search_library import SearchLibraryUseCase
from vidscope.cli._support import acquire_container, console, handle_domain_errors

__all__ = ["search_command"]


def search_command(
    query: str = typer.Argument(
        "",
        help="FTS5 query to run against the index. Empty when using facets only.",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Maximum number of hits to display.",
        min=1,
        max=200,
    ),
    hashtag: str | None = typer.Option(
        None,
        "--hashtag",
        help="Filter videos carrying this hashtag (exact match after "
             "canonicalisation, #Coding == coding).",
    ),
    mention: str | None = typer.Option(
        None,
        "--mention",
        help="Filter videos mentioning this @handle (case-insensitive).",
    ),
    has_link: bool = typer.Option(
        False,
        "--has-link",
        help="Only videos with at least one extracted URL.",
    ),
    music_track: str | None = typer.Option(
        None,
        "--music-track",
        help="Filter videos whose music_track field matches exactly.",
    ),
    on_screen_text: str | None = typer.Option(
        None,
        "--on-screen-text",
        help="Filter videos whose OCR-extracted on-screen text matches "
             "this FTS5 query (e.g. 'promo' or 'link bio').",
    ),
) -> None:
    """Run a full-text query + optional facets through the library."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = SearchLibraryUseCase(
            unit_of_work_factory=container.unit_of_work
        )
        result = use_case.execute(
            query,
            limit=limit,
            hashtag=hashtag,
            mention=mention,
            has_link=has_link,
            music_track=music_track,
            on_screen_text=on_screen_text,
        )

        facets: list[str] = []
        if hashtag:
            facets.append(f"#{hashtag.lstrip('#')}")
        if mention:
            facets.append(f"@{mention.lstrip('@')}")
        if has_link:
            facets.append("has-link")
        if music_track:
            facets.append(f"music={music_track}")
        if on_screen_text:
            facets.append(f"on-screen={on_screen_text}")
        facet_str = (" \\[" + ", ".join(facets) + "]") if facets else ""

        console.print(
            f"[bold]query:[/bold] {result.query!r}{facet_str}   "
            f"[bold]hits:[/bold] {len(result.hits)}"
        )

        if not result.hits:
            console.print(
                "[dim]No matches. Try broader query or fewer facets.[/dim]"
            )
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
