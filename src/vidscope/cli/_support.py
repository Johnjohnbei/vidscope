"""Shared helpers for CLI commands.

Keeps every ``commands/*.py`` file tiny and focused on one thing:
instantiate a use case, call ``execute``, format the result. The
container acquisition, error handling, and rich formatting helpers
all live here.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import typer
from rich.console import Console

from vidscope.domain import DomainError
from vidscope.infrastructure.container import Container, build_container

__all__ = [
    "acquire_container",
    "console",
    "fail_system",
    "fail_user",
    "handle_domain_errors",
]


console = Console()


def acquire_container() -> Container:
    """Build the :class:`Container` once per CLI invocation.

    This is the only function the CLI calls that reaches into
    :mod:`vidscope.infrastructure`. Keeping it here makes the import
    surface of each command file tiny (just this module + the use
    case), which in turn keeps import-linter's ``forbidden`` contracts
    easy to read.
    """
    return build_container()


def fail_user(message: str, *, exit_code: int = 1) -> typer.Exit:
    """Print a red error message and return a :class:`typer.Exit`.

    Callers do ``raise fail_user("bad url")`` so the Typer runtime
    handles the exit cleanly.
    """
    console.print(f"[bold red]error:[/bold red] {message}")
    return typer.Exit(exit_code)


def fail_system(message: str, *, exit_code: int = 2) -> typer.Exit:
    """Same as :func:`fail_user` but uses exit code 2 (system error)."""
    console.print(f"[bold red]system error:[/bold red] {message}")
    console.print(
        "[dim]Run `vidscope doctor` to check your environment.[/dim]"
    )
    return typer.Exit(exit_code)


@contextmanager
def handle_domain_errors() -> Iterator[None]:
    """Wrap the body of a CLI command to turn typed
    :class:`DomainError` subclasses into clean user-facing messages.

    Usage::

        @app.command("add")
        def add_command(url: str) -> None:
            with handle_domain_errors():
                result = IngestVideoUseCase(...).execute(url)
                ...
    """
    try:
        yield
    except DomainError as exc:
        raise fail_user(str(exc)) from exc
