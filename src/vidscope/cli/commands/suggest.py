"""`vidscope suggest <id>` — propose related videos by keyword overlap."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.application.suggest_related import SuggestRelatedUseCase
from vidscope.cli._support import acquire_container, console, handle_domain_errors

__all__ = ["suggest_command"]


def suggest_command(
    video_id: int = typer.Argument(
        ..., help="Source video id. Run `vidscope list` to find ids."
    ),
    limit: int = typer.Option(
        5,
        "--limit",
        "-n",
        help="Number of related videos to return.",
        min=1,
        max=100,
    ),
) -> None:
    """Suggest related videos from the library using keyword overlap.

    Ranks candidates by Jaccard similarity on the heuristic analyzer's
    keyword sets. Requires the source video to have an analysis row
    with non-empty keywords.
    """
    with handle_domain_errors():
        container = acquire_container()
        use_case = SuggestRelatedUseCase(
            unit_of_work_factory=container.unit_of_work
        )
        result = use_case.execute(video_id, limit=limit)

        if not result.source_found:
            console.print(
                f"[bold red]error:[/bold red] {result.reason}"
            )
            raise typer.Exit(1)

        header = (
            f"[bold]source:[/bold] #{result.source_video_id} "
            f"{result.source_title or '[dim]<no title>[/dim]'}"
        )
        console.print(header)
        if result.source_keywords:
            console.print(
                f"[bold]source keywords:[/bold] "
                f"{', '.join(result.source_keywords[:10])}"
            )

        if not result.suggestions:
            console.print(f"[dim]{result.reason}[/dim]")
            return

        table = Table(
            title=f"Related videos ({len(result.suggestions)})",
            show_header=True,
            header_style="bold",
        )
        table.add_column("id", justify="right", style="dim")
        table.add_column("platform")
        table.add_column("title", overflow="fold")
        table.add_column("score", justify="right")
        table.add_column("matched keywords", overflow="fold")

        for suggestion in result.suggestions:
            score_display = f"{suggestion.score * 100:.0f}%"
            matched_display = ", ".join(suggestion.matched_keywords[:5])
            if len(suggestion.matched_keywords) > 5:
                matched_display += "…"
            table.add_row(
                str(int(suggestion.video_id)),
                suggestion.platform.value,
                (suggestion.title or "")[:60],
                score_display,
                matched_display,
            )

        console.print(table)
