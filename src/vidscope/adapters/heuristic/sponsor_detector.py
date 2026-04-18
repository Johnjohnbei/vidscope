"""Sponsor / paid-partnership detector — lexical, zero deps.

Scans the lowercased transcript for known sponsor markers in French
and English. Matches are substring-based (not token-based) so phrases
like "en partenariat avec" and "paid partnership with" are detected.

Known limitations (documented, not bugs)
----------------------------------------
- No negation parsing: "this is not sponsored" still matches "sponsored"
  → returns True. Acceptable trade-off — short-form videos almost never
  say "not sponsored" without also being obviously NOT a sponsored post,
  and the reasoning step in HeuristicAnalyzerV2 discloses the detected
  marker so users can override the classification.
- False positives possible on meta-content (e.g., reviews of sponsored
  posts). M010 heuristic accepts this noise; LLM V2 (S03) does better.
"""

from __future__ import annotations

from typing import Final

__all__ = ["SPONSOR_MARKERS", "SponsorDetector"]


_MARKERS_EN: Final[frozenset[str]] = frozenset({
    "sponsored",
    "sponsor by",
    "sponsored by",
    "in partnership",
    "paid partnership",
    "paid promotion",
    "partnership with",
    "#ad",
    "#sponsored",
    "#paidpartnership",
    "#partnership",
    "affiliate",
    "affiliate link",
    "link in bio",
    "promo code",
    "discount code",
    "use code",
    "brand deal",
})

_MARKERS_FR: Final[frozenset[str]] = frozenset({
    "partenariat",
    "partenariat rémunéré",
    "sponsorisé",
    "sponsorisée",
    "en collaboration avec",
    "offert par",
    "cadeau de",
    "code promo",
    "lien en bio",
    "lien dans ma bio",
    "collab avec",
    "collaboration payante",
    "publicité",
    "placement de produit",
})

SPONSOR_MARKERS: Final[frozenset[str]] = _MARKERS_EN | _MARKERS_FR


class SponsorDetector:
    """Detect sponsor / paid-partnership markers in transcript text."""

    def __init__(self, *, markers: frozenset[str] | None = None) -> None:
        self._markers = markers if markers is not None else SPONSOR_MARKERS

    def detect(self, text: str) -> bool:
        """Return True if any known sponsor marker appears in ``text``.

        Case-insensitive. Empty input → False.
        """
        if not text:
            return False
        lowered = text.lower()
        for marker in self._markers:
            if marker in lowered:
                return True
        return False
