"""`vidscope review <video_id> --status X [--star/--unstar] [--note TEXT] [--clear-note]`

M011/S01/R056: set a user workflow overlay on a single video.
"""

from __future__ import annotations

from typing import Annotated

import typer

from vidscope.application.set_video_tracking import SetVideoTrackingUseCase
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)
from vidscope.domain import TrackingStatus

__all__ = ["review_command"]


def _parse_status(raw: str) -> TrackingStatus:
    norm = raw.strip().lower()
    try:
        return TrackingStatus(norm)
    except ValueError as exc:
        valid = ", ".join(s.value for s in TrackingStatus)
        raise typer.BadParameter(
            f"--status must be one of: {valid}. Got {raw!r}."
        ) from exc


def review_command(
    video_id: Annotated[int, typer.Argument(help="Video id (from `vidscope list`).")],
    status: Annotated[
        str,
        typer.Option(
            "--status",
            help=(
                "Workflow status: new, reviewed, saved, actioned, ignored, archived."
            ),
        ),
    ],
    star: Annotated[
        bool,
        typer.Option("--star/--unstar", help="Set or unset the starred flag."),
    ] = False,
    note: Annotated[
        str | None,
        typer.Option("--note", help="Set a free-text note (overwrites existing)."),
    ] = None,
    clear_note: Annotated[
        bool,
        typer.Option("--clear-note", help="Clear the existing note (sets to '')."),
    ] = False,
) -> None:
    """Set workflow overlay (status, starred, notes) on a video."""
    with handle_domain_errors():
        if note is not None and clear_note:
            raise fail_user("--note and --clear-note are mutually exclusive.")

        parsed_status = _parse_status(status)
        resolved_notes: str | None
        if clear_note:
            resolved_notes = ""
        else:
            resolved_notes = note  # None -> preserve, str -> replace

        container = acquire_container()
        use_case = SetVideoTrackingUseCase(
            unit_of_work_factory=container.unit_of_work
        )
        result = use_case.execute(
            video_id,
            status=parsed_status,
            starred=star,
            notes=resolved_notes,
        )

        verb = "created" if result.created else "updated"
        star_label = "starred" if result.tracking.starred else "unstarred"
        console.print(
            f"[bold green]{verb}[/bold green] tracking for video "
            f"{int(result.tracking.video_id)}: "
            f"status={result.tracking.status.value}, {star_label}"
            + (
                f", notes={result.tracking.notes!r}"
                if result.tracking.notes is not None
                else ""
            )
        )
