"""Clock port.

Every place in the codebase that needs the current time goes through this
port instead of calling :func:`datetime.now` directly. Tests inject a
:class:`FixedClock` (provided in test fixtures) so time-dependent behavior
is deterministic.

This is a small thing with large downstream consequences: without it,
pipeline-run timestamp assertions become flaky, retry-backoff tests become
flaky, and "what happened in the last hour" queries become hard to test.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

__all__ = ["Clock"]


@runtime_checkable
class Clock(Protocol):
    """Abstracts "what time is it now" so tests can inject a fixed clock.

    Implementations must return timezone-aware ``datetime`` values (UTC).
    Naive datetimes are a bug.
    """

    def now(self) -> datetime:
        """Return the current time as a timezone-aware ``datetime`` in UTC."""
        ...
