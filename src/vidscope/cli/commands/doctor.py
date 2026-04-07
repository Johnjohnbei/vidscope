"""`vidscope doctor` — run startup checks and print a report."""

from __future__ import annotations

import typer
from rich.table import Table

from vidscope.cli._support import console
from vidscope.infrastructure.startup import run_all_checks

__all__ = ["doctor_command"]


def doctor_command() -> None:
    """Run every startup check and print a rich table.

    Exit codes
    ----------
    - ``0`` — every check passed
    - ``2`` — at least one check failed; remediation advice printed per
      failed check so the operator knows what to install or fix.
    """
    results = run_all_checks()

    table = Table(title="vidscope doctor", show_header=True, header_style="bold")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail", overflow="fold")

    any_failed = False
    for res in results:
        if res.ok:
            status_cell = "[green]ok[/green]"
        else:
            status_cell = "[red]fail[/red]"
            any_failed = True
        table.add_row(res.name, status_cell, res.version_or_error)

    console.print(table)

    if any_failed:
        console.print("")
        for res in results:
            if not res.ok:
                console.print(f"[bold red]# {res.name}[/bold red]")
                console.print(res.remediation)
                console.print("")
        raise typer.Exit(2)
