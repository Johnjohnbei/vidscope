"""VidScope application layer.

Use cases — one class per user-facing intention. Use cases orchestrate
the pipeline and the repositories to produce a single logical outcome.
They are the only layer between the CLI (and future MCP server) and
the pipeline/ports.

Design rules
------------

- A use case holds its collaborators via constructor injection. It
  never calls :func:`build_container` itself — the CLI does, and passes
  the needed fields in.
- A use case's ``execute`` method returns a typed DTO (a frozen
  dataclass declared in the same module). The CLI formats the DTO for
  display; never pass raw SQL rows or ORM objects back.
- Errors bubble up as typed :class:`DomainError` subclasses. The CLI
  catches :class:`DomainError` at the boundary and turns it into an
  actionable message + exit code.
"""

from __future__ import annotations

from vidscope.application.get_status import GetStatusResult, GetStatusUseCase
from vidscope.application.ingest_video import IngestResult, IngestVideoUseCase
from vidscope.application.refresh_stats import (
    RefreshStatsBatchResult,
    RefreshStatsForWatchlistResult,
    RefreshStatsForWatchlistUseCase,
    RefreshStatsResult,
    RefreshStatsUseCase,
)
from vidscope.application.list_videos import ListVideosResult, ListVideosUseCase
from vidscope.application.search_library import (
    SearchLibraryResult,
    SearchLibraryUseCase,
)
from vidscope.application.show_video import ShowVideoResult, ShowVideoUseCase
from vidscope.application.suggest_related import (
    Suggestion,
    SuggestRelatedResult,
    SuggestRelatedUseCase,
)
from vidscope.application.watchlist import (
    AddedAccountResult,
    AddWatchedAccountUseCase,
    ListedAccountsResult,
    ListWatchedAccountsUseCase,
    RefreshAccountOutcome,
    RefreshSummary,
    RefreshWatchlistUseCase,
    RemovedAccountResult,
    RemoveWatchedAccountUseCase,
)

__all__ = [
    "AddWatchedAccountUseCase",
    "AddedAccountResult",
    "GetStatusResult",
    "GetStatusUseCase",
    "IngestResult",
    "IngestVideoUseCase",
    "RefreshStatsBatchResult",
    "RefreshStatsForWatchlistResult",
    "RefreshStatsForWatchlistUseCase",
    "RefreshStatsResult",
    "RefreshStatsUseCase",
    "ListVideosResult",
    "ListVideosUseCase",
    "ListWatchedAccountsUseCase",
    "ListedAccountsResult",
    "RefreshAccountOutcome",
    "RefreshSummary",
    "RefreshWatchlistUseCase",
    "RemoveWatchedAccountUseCase",
    "RemovedAccountResult",
    "SearchLibraryResult",
    "SearchLibraryUseCase",
    "ShowVideoResult",
    "ShowVideoUseCase",
    "SuggestRelatedResult",
    "SuggestRelatedUseCase",
    "Suggestion",
]
