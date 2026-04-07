"""Permissive Netscape-format cookies file validator.

The Netscape "cookies.txt" format is the de-facto standard for browser
cookie exports consumed by yt-dlp / curl / wget. The spec is informal
and exports vary across browser extensions, so this validator stays
permissive:

- Header line: any comment starting with ``#`` (most exports use
  ``# Netscape HTTP Cookie File`` or ``# HTTP Cookie File``, but
  some extensions skip the header altogether — we accept both)
- Comments: any line starting with ``#``, skipped
- Blank lines: skipped
- Data lines: tab-separated, exactly 7 columns
  ``domain | include_subdomains | path | secure | expiration | name | value``
  Permissive about whitespace inside fields. Empty value column is OK.
- At least one data line is required for the file to be considered valid

The validator never tries to make sense of cookie *contents* (no
expiration check, no domain check, no name validation). Its only job
is "is this a syntactically valid cookies.txt that yt-dlp can read?"

This module is in the infrastructure layer because it does file I/O.
The domain layer stays pure.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["CookiesValidation", "validate_cookies_file"]


_NETSCAPE_COLUMN_COUNT = 7


@dataclass(frozen=True, slots=True)
class CookiesValidation:
    """Result of validating a cookies file.

    Attributes
    ----------
    ok:
        ``True`` only when the file exists, is readable, and contains
        at least one syntactically valid Netscape cookie row.
    reason:
        Human-readable description. Empty string when ``ok=True``,
        otherwise a short message suitable for CLI display.
    entries_count:
        Number of valid cookie rows found. Always 0 when ``ok=False``.
    """

    ok: bool
    reason: str
    entries_count: int


def validate_cookies_file(path: Path) -> CookiesValidation:  # noqa: PLR0911
    """Validate that ``path`` is a syntactically valid Netscape cookies file.

    Parameters
    ----------
    path:
        Filesystem path to the cookies file. May or may not exist.

    Returns
    -------
    CookiesValidation
        ``ok=True`` and ``entries_count > 0`` when valid. ``ok=False``
        with a descriptive ``reason`` otherwise. Never raises.
    """
    if not path.exists():
        return CookiesValidation(
            ok=False,
            reason=f"file does not exist: {path}",
            entries_count=0,
        )

    if not path.is_file():
        return CookiesValidation(
            ok=False,
            reason=f"path is not a regular file: {path}",
            entries_count=0,
        )

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return CookiesValidation(
            ok=False,
            reason=f"failed to read file: {exc}",
            entries_count=0,
        )

    if not raw.strip():
        return CookiesValidation(
            ok=False,
            reason="file is empty",
            entries_count=0,
        )

    valid_rows = 0
    malformed_rows = 0
    for raw_line in raw.splitlines():
        line = raw_line.rstrip("\r\n")
        # Skip blank lines and comments
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # Tab-separated row, exactly 7 columns
        columns = line.split("\t")
        if len(columns) != _NETSCAPE_COLUMN_COUNT:
            malformed_rows += 1
            continue
        # Domain must be non-empty (the only column we sanity-check)
        if not columns[0].strip():
            malformed_rows += 1
            continue
        valid_rows += 1

    if valid_rows == 0:
        if malformed_rows > 0:
            return CookiesValidation(
                ok=False,
                reason=(
                    f"no valid cookie rows found "
                    f"({malformed_rows} malformed). Expected tab-separated "
                    f"rows with {_NETSCAPE_COLUMN_COUNT} columns."
                ),
                entries_count=0,
            )
        return CookiesValidation(
            ok=False,
            reason="no cookie rows found (file contains only comments or blanks)",
            entries_count=0,
        )

    return CookiesValidation(
        ok=True,
        reason="",
        entries_count=valid_rows,
    )
