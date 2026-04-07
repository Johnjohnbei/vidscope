"""Cookies management use cases.

Three small use cases that operate on the cookies file under
``<data_dir>/cookies.txt`` (the canonical cookies location). Each one
maps to a single ``vidscope cookies <subcommand>`` invocation.

The CLI sub-application in :mod:`vidscope.cli.commands.cookies`
delegates to these use cases — it never touches the filesystem
directly. This keeps the use cases unit-testable in isolation and
the CLI layer thin.

Why operate on ``<data_dir>/cookies.txt`` and not on the
``VIDSCOPE_COOKIES_FILE`` override? Because the override is meant
for advanced users who manage their own cookies file (e.g. shared
between vidscope and a separate yt-dlp invocation). The CLI's
``set``/``status``/``clear`` commands manage VidScope's *own*
cookies file. The status command surfaces the env var override
explicitly so the user knows when their changes won't take effect.

This module imports only stdlib + ``vidscope.application.cookies_validator``
so the application layer stays free of infrastructure dependencies.
The composition root in :mod:`vidscope.infrastructure.container` builds
each use case with the resolved ``data_dir`` and the optionally-set
``configured_cookies_file`` from :class:`Config`.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from vidscope.application.cookies_validator import (
    CookiesValidation,
    validate_cookies_file,
)
from vidscope.ports import Downloader, ProbeResult, ProbeStatus

__all__ = [
    "ClearCookiesResult",
    "ClearCookiesUseCase",
    "CookiesProbeResult",
    "CookiesProbeUseCase",
    "CookiesStatus",
    "GetCookiesStatusUseCase",
    "SetCookiesResult",
    "SetCookiesUseCase",
]


# Default URL used by `vidscope cookies test` when the user doesn't
# provide --url. Picks a stable Instagram public Reel from a well-known
# verified account so the probe doesn't rot. If this URL ever 404s,
# any user-provided --url override still works.
_DEFAULT_PROBE_URL = "https://www.instagram.com/reel/CzWl8AHr6FT/"


_DEFAULT_COOKIES_FILENAME = "cookies.txt"


def _default_cookies_path(data_dir: Path) -> Path:
    """Return the canonical cookies file path under ``data_dir``."""
    return data_dir / _DEFAULT_COOKIES_FILENAME


# ---------------------------------------------------------------------------
# SetCookies
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetCookiesResult:
    """Outcome of :meth:`SetCookiesUseCase.execute`."""

    success: bool
    destination: Path
    entries_count: int
    message: str


@dataclass(frozen=True, slots=True)
class SetCookiesUseCase:
    """Copy a cookies file into ``<data_dir>/cookies.txt`` after validation.

    Constructor parameters
    ----------------------
    data_dir:
        Resolved data directory. The cookies file is always written to
        ``data_dir / "cookies.txt"`` regardless of any
        ``VIDSCOPE_COOKIES_FILE`` env override (which is owned by the
        user, not VidScope).
    """

    data_dir: Path

    def execute(self, source: Path) -> SetCookiesResult:
        """Validate ``source`` and copy it to the canonical location.

        Returns a :class:`SetCookiesResult` describing the outcome.
        Never raises — every failure produces a structured result.
        """
        destination = _default_cookies_path(self.data_dir)

        # Validate the source first so we don't overwrite a working
        # cookies file with a broken one.
        validation = validate_cookies_file(source)
        if not validation.ok:
            return SetCookiesResult(
                success=False,
                destination=destination,
                entries_count=0,
                message=f"source file invalid: {validation.reason}",
            )

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        except OSError as exc:
            return SetCookiesResult(
                success=False,
                destination=destination,
                entries_count=0,
                message=f"failed to copy: {exc}",
            )

        # Re-validate after copy to confirm the destination is well-formed.
        post_validation = validate_cookies_file(destination)
        if not post_validation.ok:
            return SetCookiesResult(
                success=False,
                destination=destination,
                entries_count=0,
                message=f"destination invalid after copy: {post_validation.reason}",
            )

        return SetCookiesResult(
            success=True,
            destination=destination,
            entries_count=post_validation.entries_count,
            message=(
                f"copied {post_validation.entries_count} cookie rows to "
                f"{destination}"
            ),
        )


# ---------------------------------------------------------------------------
# GetCookiesStatus
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CookiesStatus:
    """Snapshot of the current cookies state.

    Attributes
    ----------
    default_path:
        The canonical ``<data_dir>/cookies.txt`` path. Always set.
    default_exists:
        ``True`` when the canonical file actually exists on disk.
    size_bytes:
        Size of the canonical file. 0 when missing.
    modified_at:
        Modification timestamp of the canonical file. ``None`` when missing.
    validation:
        Result of validating the canonical file.
    env_override_path:
        The path from ``VIDSCOPE_COOKIES_FILE`` if set and != default.
        ``None`` otherwise. When set, yt-dlp uses this instead of the
        default path.
    active_path:
        The path actually used by yt-dlp at runtime, computed by Config.
        Equal to ``env_override_path`` when set, otherwise ``default_path``
        if it exists, otherwise ``None``.
    """

    default_path: Path
    default_exists: bool
    size_bytes: int
    modified_at: datetime | None
    validation: CookiesValidation
    env_override_path: Path | None
    active_path: Path | None


@dataclass(frozen=True, slots=True)
class GetCookiesStatusUseCase:
    """Read the current cookies state and return a :class:`CookiesStatus`.

    Constructor parameters
    ----------------------
    data_dir:
        Resolved data directory.
    configured_cookies_file:
        The cookies path resolved by Config (typically ``Config.cookies_file``).
        Pass ``None`` when no cookies are configured at all.
    """

    data_dir: Path
    configured_cookies_file: Path | None

    def execute(self) -> CookiesStatus:
        """Read the current cookies state and return a snapshot.

        Surfaces both the canonical path under ``data_dir`` and any
        ``VIDSCOPE_COOKIES_FILE`` env override so the CLI can warn the
        user when their installation won't take effect. Never raises —
        a missing or unreadable file produces a structured result.
        """
        default_path = _default_cookies_path(self.data_dir)

        # Detect env override: if active_path is set and != default_path,
        # the user has explicitly pointed VIDSCOPE_COOKIES_FILE elsewhere.
        active_path = self.configured_cookies_file
        env_override_path = (
            active_path
            if active_path is not None and active_path != default_path
            else None
        )

        if not default_path.exists():
            return CookiesStatus(
                default_path=default_path,
                default_exists=False,
                size_bytes=0,
                modified_at=None,
                validation=validate_cookies_file(default_path),
                env_override_path=env_override_path,
                active_path=active_path,
            )

        try:
            stat = default_path.stat()
            size_bytes = stat.st_size
            modified_at = datetime.fromtimestamp(stat.st_mtime).astimezone()
        except OSError:
            size_bytes = 0
            modified_at = None

        return CookiesStatus(
            default_path=default_path,
            default_exists=True,
            size_bytes=size_bytes,
            modified_at=modified_at,
            validation=validate_cookies_file(default_path),
            env_override_path=env_override_path,
            active_path=active_path,
        )


# ---------------------------------------------------------------------------
# ClearCookies
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClearCookiesResult:
    """Outcome of :meth:`ClearCookiesUseCase.execute`."""

    success: bool
    removed_path: Path | None
    message: str


@dataclass(frozen=True, slots=True)
class ClearCookiesUseCase:
    """Remove ``<data_dir>/cookies.txt`` from disk.

    Only operates on the canonical path under ``data_dir``. Never
    touches a path set via ``VIDSCOPE_COOKIES_FILE`` because that
    file is owned by the user, not VidScope.
    """

    data_dir: Path

    def execute(self) -> ClearCookiesResult:
        """Remove the canonical cookies file from disk.

        Only ever touches ``<data_dir>/cookies.txt`` — never an
        env-override file because that file is owned by the user, not
        VidScope. Never raises — every failure (missing file, permission
        denied) produces a structured result with a descriptive message.
        """
        target = _default_cookies_path(self.data_dir)

        if not target.exists():
            return ClearCookiesResult(
                success=False,
                removed_path=None,
                message=f"no cookies file at {target}",
            )

        try:
            target.unlink()
        except OSError as exc:
            return ClearCookiesResult(
                success=False,
                removed_path=None,
                message=f"failed to remove {target}: {exc}",
            )

        return ClearCookiesResult(
            success=True,
            removed_path=target,
            message=f"removed {target}",
        )


# ---------------------------------------------------------------------------
# TestCookies (probe)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CookiesProbeResult:
    """Outcome of :meth:`CookiesProbeUseCase.execute`.

    Attributes
    ----------
    probe:
        The raw :class:`ProbeResult` from the downloader.
    cookies_configured:
        Whether a cookies file is configured at all (env or default).
    interpretation:
        Human-readable verdict suitable for CLI display.
    """

    probe: ProbeResult
    cookies_configured: bool
    interpretation: str


@dataclass(frozen=True, slots=True)
class CookiesProbeUseCase:
    """Probe a video URL via the Downloader without downloading media.

    Used by ``vidscope cookies test`` to verify that the configured
    cookies authenticate against a gated platform. The use case never
    raises — every failure is encoded in the returned
    :class:`CookiesProbeResult`.

    Constructor parameters
    ----------------------
    downloader:
        Concrete :class:`Downloader` from the container. Tests inject
        a fake.
    cookies_configured:
        ``True`` when ``Config.cookies_file`` is non-None. Used to
        produce a more accurate interpretation of failures (e.g. an
        AUTH_REQUIRED with no cookies configured at all is "you need
        to install cookies", not "your cookies are expired").
    """

    downloader: Downloader
    cookies_configured: bool

    def execute(self, url: str | None = None) -> CookiesProbeResult:
        """Probe ``url`` (or the default Instagram Reel) and return the result.

        Calls :meth:`Downloader.probe` which performs a metadata-only
        ``extract_info`` call (no media download, no DB write) and
        wraps the result with a context-aware interpretation derived
        from ``cookies_configured`` × ``ProbeStatus``. Never raises.
        """
        target_url = (url or _DEFAULT_PROBE_URL).strip()
        probe = self.downloader.probe(target_url)
        interpretation = self._interpret(probe)
        return CookiesProbeResult(
            probe=probe,
            cookies_configured=self.cookies_configured,
            interpretation=interpretation,
        )

    def _interpret(self, probe: ProbeResult) -> str:  # noqa: PLR0911
        if probe.status == ProbeStatus.OK:
            if self.cookies_configured:
                return f"cookies work — fetched metadata for {probe.title or probe.url}"
            return (
                f"no cookies needed — fetched metadata for "
                f"{probe.title or probe.url}"
            )
        if probe.status == ProbeStatus.AUTH_REQUIRED:
            if self.cookies_configured:
                return (
                    "cookies are configured but the platform still asks for "
                    "login. Your session has likely expired — re-export "
                    "cookies from your browser and run `vidscope cookies set`."
                )
            return (
                "this URL requires cookies and none are configured. "
                "See `docs/cookies.md` for how to export your browser cookies."
            )
        if probe.status == ProbeStatus.NOT_FOUND:
            return f"URL not found or video deleted: {probe.detail}"
        if probe.status == ProbeStatus.NETWORK_ERROR:
            return f"network error during probe: {probe.detail}"
        if probe.status == ProbeStatus.UNSUPPORTED:
            return f"unsupported URL: {probe.detail}"
        return f"probe failed: {probe.detail}"
