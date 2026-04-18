"""`vidscope explain <id>` -- show reasoning + score vector for a video.

M010 command: surface the qualitative analyzer output in a human-
readable form. Displays all 9 M010 fields (reasoning, 4 score
dimensions, sentiment, is_sponsored, content_type, verticals) plus
the V1 summary / score.

ASCII-only output (Windows cp1252 compat per KNOWLEDGE.md). Uses
``rich.panel.Panel`` with border style for visual anchoring but
only ASCII tags like ``[green]OK[/green]`` in content.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel

from vidscope.application.explain_analysis import ExplainAnalysisUseCase
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)

__all__ = ["explain_command"]


def explain_command(
    video_id: Annotated[int, typer.Argument(help="Numeric id of the video to explain.")],
) -> None:
    """Show the reasoning + per-dimension scores of the latest analysis."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = ExplainAnalysisUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(video_id)

        if not result.found or result.video is None:
            raise fail_user(f"no video with id {video_id}")

        if result.analysis is None:
            raise fail_user(
                f"no analysis yet for video {video_id} - "
                f"run vidscope add again to analyze it"
            )

        _render(result)


def _render(result) -> None:  # type: ignore[no-untyped-def]
    video = result.video
    analysis = result.analysis

    header = (
        f"[bold]video:[/bold] {video.id}  "
        f"[bold]platform:[/bold] {video.platform.value}  "
        f"[bold]provider:[/bold] {analysis.provider}"
    )
    console.print(header)

    # Reasoning panel
    reasoning = analysis.reasoning or "(no reasoning -- legacy analysis)"
    console.print(Panel(reasoning, title="[bold]Reasoning[/bold]", border_style="cyan"))

    # Categorical fields
    console.print(
        f"[bold]content_type:[/bold] {_fmt_enum(analysis.content_type)}   "
        f"[bold]sentiment:[/bold] {_fmt_enum(analysis.sentiment)}   "
        f"[bold]is_sponsored:[/bold] {_fmt_bool(analysis.is_sponsored)}"
    )

    # Verticals
    if analysis.verticals:
        console.print(
            f"[bold]verticals:[/bold] {', '.join(analysis.verticals)}"
        )
    else:
        console.print("[dim]verticals: (none)[/dim]")

    # Per-dimension scores
    console.print("[bold]Scores:[/bold]")
    console.print(f"  overall:             {_fmt_score(analysis.score)}")
    console.print(f"  information_density: {_fmt_score(analysis.information_density)}")
    console.print(f"  actionability:       {_fmt_score(analysis.actionability)}")
    console.print(f"  novelty:             {_fmt_score(analysis.novelty)}")
    console.print(f"  production_quality:  {_fmt_score(analysis.production_quality)}")

    # Legacy summary
    console.print(f"[bold]summary:[/bold] {analysis.summary or '-'}")

    if analysis.keywords:
        console.print(
            f"[bold]keywords:[/bold] {', '.join(analysis.keywords[:8])}"
        )


def _fmt_enum(value: object) -> str:
    if value is None:
        return "-"
    enum_val = getattr(value, "value", None)
    return enum_val if enum_val is not None else str(value)


def _fmt_bool(value: bool | None) -> str:
    if value is None:
        return "-"
    return "yes" if value else "no"


def _fmt_score(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.0f}/100"
