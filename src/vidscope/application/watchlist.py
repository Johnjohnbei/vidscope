"""Watchlist use cases.

Four use cases on top of the WatchAccountRepository + pipeline_runner:

- :class:`AddWatchedAccountUseCase` — register a public account by URL
- :class:`ListWatchedAccountsUseCase` — return all watched accounts
- :class:`RemoveWatchedAccountUseCase` — delete by handle (+ platform)
- :class:`RefreshWatchlistUseCase` — iterate accounts, list new videos,
  ingest the new ones via the existing pipeline runner

Refresh is the heart of M003. It reuses the M001 PipelineRunner
without modification — every newly discovered video flows through
the same 5-stage pipeline as a manual ``vidscope add``.

Per-account errors during refresh are captured and stored in the
watch_refreshes row but do not stop the iteration: a broken account
shouldn't block the rest of the watchlist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from vidscope.domain import (
    DomainError,
    IngestError,
    Platform,
    PlatformId,
    WatchedAccount,
    WatchRefresh,
    detect_platform,
)
from vidscope.pipeline import PipelineRunner
from vidscope.ports import (
    Clock,
    Downloader,
    PipelineContext,
    UnitOfWorkFactory,
)

__all__ = [
    "AddWatchedAccountUseCase",
    "AddedAccountResult",
    "ListWatchedAccountsUseCase",
    "ListedAccountsResult",
    "RefreshSummary",
    "RefreshWatchlistUseCase",
    "RemoveWatchedAccountUseCase",
    "RemovedAccountResult",
]


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AddedAccountResult:
    success: bool
    account: WatchedAccount | None
    message: str


@dataclass(frozen=True, slots=True)
class ListedAccountsResult:
    accounts: tuple[WatchedAccount, ...]
    total: int


@dataclass(frozen=True, slots=True)
class RemovedAccountResult:
    success: bool
    handle: str
    platform: Platform | None
    message: str


@dataclass(frozen=True, slots=True)
class RefreshAccountOutcome:
    handle: str
    platform: Platform
    new_videos: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshSummary:
    started_at: datetime
    finished_at: datetime
    accounts_checked: int
    new_videos_ingested: int
    errors: tuple[str, ...]
    per_account: tuple[RefreshAccountOutcome, ...]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _handle_from_url(url: str, platform: Platform) -> str:
    """Derive a canonical handle from a channel/account URL.

    Returns the @handle for YouTube/TikTok/Instagram. Falls back to
    the path's last segment if no @ is present.
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        # No path: derive from host
        return parsed.hostname or url

    # Take the first path segment for /@handle, /user/X, /channel/X
    first = path.split("/")[0]
    if first.startswith("@"):
        return first  # YouTube + TikTok + Instagram all use @handle now
    if first in ("user", "c", "channel") and "/" in path:
        return path.split("/")[1]
    return first


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------


class AddWatchedAccountUseCase:
    """Register a public account for periodic refresh."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, url: str) -> AddedAccountResult:
        """Validate ``url``, derive a (platform, handle) pair, and persist.

        Detects the platform via :func:`detect_platform`, derives the
        handle from the URL path, and inserts a :class:`WatchedAccount`
        row. Returns a structured failure (not an exception) for empty
        URLs, unknown platforms, unparseable handles, and duplicate
        ``(platform, handle)`` pairs.
        """
        cleaned = url.strip() if url else ""
        if not cleaned:
            return AddedAccountResult(
                success=False, account=None, message="url is empty"
            )

        try:
            platform = detect_platform(cleaned)
        except DomainError as exc:
            return AddedAccountResult(
                success=False, account=None, message=str(exc)
            )

        handle = _handle_from_url(cleaned, platform)
        if not handle:
            return AddedAccountResult(
                success=False,
                account=None,
                message=f"could not derive handle from {cleaned!r}",
            )

        with self._uow_factory() as uow:
            existing = uow.watch_accounts.get_by_handle(platform, handle)
            if existing is not None:
                return AddedAccountResult(
                    success=False,
                    account=existing,
                    message=f"{platform.value}/{handle} already in watchlist",
                )
            try:
                stored = uow.watch_accounts.add(
                    WatchedAccount(
                        platform=platform, handle=handle, url=cleaned
                    )
                )
            except DomainError as exc:
                return AddedAccountResult(
                    success=False, account=None, message=str(exc)
                )

        return AddedAccountResult(
            success=True,
            account=stored,
            message=f"added {platform.value}/{handle}",
        )


class ListWatchedAccountsUseCase:
    """Return every watched account in insertion order."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self) -> ListedAccountsResult:
        """Return all watched accounts and the total count."""
        with self._uow_factory() as uow:
            accounts = tuple(uow.watch_accounts.list_all())
        return ListedAccountsResult(accounts=accounts, total=len(accounts))


class RemoveWatchedAccountUseCase:
    """Remove a watched account by handle, optionally narrowed by platform."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self, handle: str, platform: Platform | None = None
    ) -> RemovedAccountResult:
        """Remove the account matching ``handle`` (and optional ``platform``).

        When ``platform`` is omitted and the handle exists on multiple
        platforms (e.g. ``@tiktok`` on both YouTube and TikTok), returns
        a structured failure asking the caller to disambiguate. Never
        raises on missing accounts — returns ``success=False`` instead.
        """
        normalized = handle.strip()
        if not normalized:
            return RemovedAccountResult(
                success=False,
                handle=handle,
                platform=platform,
                message="handle is empty",
            )

        with self._uow_factory() as uow:
            if platform is not None:
                account = uow.watch_accounts.get_by_handle(
                    platform, normalized
                )
                if account is None:
                    return RemovedAccountResult(
                        success=False,
                        handle=normalized,
                        platform=platform,
                        message=(
                            f"no watched account with handle "
                            f"{normalized!r} on {platform.value}"
                        ),
                    )
                assert account.id is not None
                uow.watch_accounts.remove(account.id)
                return RemovedAccountResult(
                    success=True,
                    handle=normalized,
                    platform=platform,
                    message=f"removed {platform.value}/{normalized}",
                )

            # No platform: search across all platforms
            matches = [
                a
                for a in uow.watch_accounts.list_all()
                if a.handle == normalized
            ]
            if not matches:
                return RemovedAccountResult(
                    success=False,
                    handle=normalized,
                    platform=None,
                    message=f"no watched account with handle {normalized!r}",
                )
            if len(matches) > 1:
                platforms = ", ".join(m.platform.value for m in matches)
                return RemovedAccountResult(
                    success=False,
                    handle=normalized,
                    platform=None,
                    message=(
                        f"handle {normalized!r} matches {len(matches)} "
                        f"accounts ({platforms}); specify --platform"
                    ),
                )
            match = matches[0]
            assert match.id is not None
            uow.watch_accounts.remove(match.id)
            return RemovedAccountResult(
                success=True,
                handle=normalized,
                platform=match.platform,
                message=f"removed {match.platform.value}/{normalized}",
            )


class RefreshWatchlistUseCase:
    """Iterate every watched account, list new videos, ingest them.

    Per-account errors are captured and the iteration continues.
    A WatchRefresh row is persisted at the end with totals + errors.
    """

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        pipeline_runner: PipelineRunner,
        downloader: Downloader,
        clock: Clock,
        per_account_limit: int = 10,
    ) -> None:
        self._uow_factory = unit_of_work_factory
        self._runner = pipeline_runner
        self._downloader = downloader
        self._clock = clock
        self._per_account_limit = per_account_limit

    def execute(self) -> RefreshSummary:
        """Iterate every watched account and ingest any new videos.

        Snapshots the watchlist + existing video IDs in one transaction
        at the start so the iteration runs against an in-memory dedupe
        set (O(1) per candidate). Per-account errors are caught and
        recorded in the returned :class:`RefreshSummary` — a broken
        account never blocks the rest of the watchlist. Idempotent: a
        second run after a first ingests zero new videos.
        """
        started_at = self._clock.now()

        # Snapshot the watchlist + collect existing platform_ids per
        # platform in a single transaction so the iteration below
        # doesn't hold the DB.
        with self._uow_factory() as uow:
            accounts = uow.watch_accounts.list_all()
            existing_videos = uow.videos.list_recent(limit=10000)

        existing_ids: set[tuple[Platform, str]] = {
            (v.platform, str(v.platform_id)) for v in existing_videos
        }

        per_account: list[RefreshAccountOutcome] = []
        errors: list[str] = []
        total_new = 0

        for account in accounts:
            try:
                entries = self._downloader.list_channel_videos(
                    account.url, limit=self._per_account_limit
                )
            except IngestError as exc:
                error_msg = f"{account.platform.value}/{account.handle}: {exc}"
                errors.append(error_msg)
                per_account.append(
                    RefreshAccountOutcome(
                        handle=account.handle,
                        platform=account.platform,
                        new_videos=0,
                        error=str(exc),
                    )
                )
                continue
            except Exception as exc:
                error_msg = (
                    f"{account.platform.value}/{account.handle}: "
                    f"unexpected: {exc}"
                )
                errors.append(error_msg)
                per_account.append(
                    RefreshAccountOutcome(
                        handle=account.handle,
                        platform=account.platform,
                        new_videos=0,
                        error=str(exc),
                    )
                )
                continue

            account_new = 0
            for entry in entries:
                key = (account.platform, str(entry.platform_id))
                if key in existing_ids:
                    continue
                # Run the new URL through the pipeline. The runner
                # handles its own transactions; we don't open one here.
                ctx = PipelineContext(source_url=entry.url)
                run_result = self._runner.run(ctx)
                if run_result.success:
                    account_new += 1
                    total_new += 1
                    existing_ids.add(key)
                else:
                    failure_msg = next(
                        (o.error for o in run_result.outcomes if o.error),
                        f"pipeline failed at {run_result.failed_at}",
                    )
                    errors.append(
                        f"{account.platform.value}/{account.handle} "
                        f"video {entry.platform_id}: {failure_msg}"
                    )

            per_account.append(
                RefreshAccountOutcome(
                    handle=account.handle,
                    platform=account.platform,
                    new_videos=account_new,
                )
            )

            # Update last_checked_at in its own short transaction
            with self._uow_factory() as uow:
                if account.id is not None:
                    uow.watch_accounts.update_last_checked(
                        account.id, last_checked_at=self._clock.now()
                    )

        finished_at = self._clock.now()

        # Persist the WatchRefresh row
        refresh = WatchRefresh(
            started_at=started_at,
            finished_at=finished_at,
            accounts_checked=len(accounts),
            new_videos_ingested=total_new,
            errors=tuple(errors),
        )
        with self._uow_factory() as uow:
            uow.watch_refreshes.add(refresh)

        # Coerce types so dataclass init below typechecks (clock returns
        # tz-aware datetime so we know they're not None)
        assert isinstance(started_at, datetime)
        assert isinstance(finished_at, datetime)

        return RefreshSummary(
            started_at=started_at,
            finished_at=finished_at,
            accounts_checked=len(accounts),
            new_videos_ingested=total_new,
            errors=tuple(errors),
            per_account=tuple(per_account),
        )


# Silence "imported but unused" warnings for symbols referenced only in
# type annotations on the dataclasses above.
_ = (datetime, PlatformId, UTC)
