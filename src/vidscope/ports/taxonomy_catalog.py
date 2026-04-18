"""Port for controlled vertical taxonomy lookup.

Stdlib only. The port stays portable: no yaml, no SQL, no HTTP. The
concrete loader lives in :mod:`vidscope.adapters.config.yaml_taxonomy`.

Usage in the analyzer layer (S02):

    verticals = taxonomy.match(tokens)

The analyzer calls :meth:`match` with tokenised transcript words and
gets back an ordered list of vertical slugs.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["TaxonomyCatalog"]


@runtime_checkable
class TaxonomyCatalog(Protocol):
    """Read-only controlled vocabulary of verticals.

    Implementations must be effectively immutable after construction —
    a running pipeline must see the same verticals between calls.
    """

    def verticals(self) -> list[str]:
        """Return all vertical slugs, sorted alphabetically.

        The returned list is safe to mutate — implementations return a
        fresh list each call.
        """
        ...

    def keywords_for_vertical(self, vertical: str) -> frozenset[str]:
        """Return every keyword registered under ``vertical``.

        Returns an empty ``frozenset`` when ``vertical`` is not a known
        slug — callers must not rely on exceptions to detect absence.
        """
        ...

    def match(self, tokens: list[str]) -> list[str]:
        """Return vertical slugs whose keywords intersect ``tokens``.

        Ordered by (match_count DESC, slug ASC) for deterministic
        output. Empty ``tokens`` returns ``[]``. Tokens are compared
        lowercase — callers do not need to pre-lower.
        """
        ...
