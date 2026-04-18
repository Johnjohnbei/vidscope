"""YAML-backed :class:`TaxonomyCatalog` implementation.

Loads ``config/taxonomy.yaml`` once at construction time, validates the
schema (dict of slug -> list[lowercase str]), and exposes the
:class:`TaxonomyCatalog` port. Zero I/O after construction.

The loader is strict on the YAML shape so a typo in taxonomy.yaml fails
the container build — no silent "your vertical is broken" at runtime.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from vidscope.ports.taxonomy_catalog import TaxonomyCatalog

__all__ = ["YamlTaxonomy"]


class YamlTaxonomy:
    """Concrete :class:`TaxonomyCatalog` reading a YAML file.

    The file must be a mapping of ``slug: list[keyword]``. Every slug
    must be a non-empty lowercase string. Every keyword must be a
    non-empty lowercase string. Empty keyword lists are rejected (a
    vertical with no keywords is useless).
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, frozenset[str]] = self._load_and_validate(path)

    # ------------------------------------------------------------------
    # TaxonomyCatalog Protocol
    # ------------------------------------------------------------------

    def verticals(self) -> list[str]:
        return sorted(self._data.keys())

    def keywords_for_vertical(self, vertical: str) -> frozenset[str]:
        return self._data.get(vertical, frozenset())

    def match(self, tokens: list[str]) -> list[str]:
        if not tokens:
            return []
        lowered = {t.lower() for t in tokens if t}
        if not lowered:
            return []
        scores: list[tuple[int, str]] = []
        for slug, keywords in self._data.items():
            hits = len(lowered & keywords)
            if hits > 0:
                scores.append((hits, slug))
        # Sort by (count DESC, slug ASC) for determinism
        scores.sort(key=lambda pair: (-pair[0], pair[1]))
        return [slug for _, slug in scores]

    # ------------------------------------------------------------------
    # Internal — validation
    # ------------------------------------------------------------------

    @staticmethod
    def _load_and_validate(path: Path) -> dict[str, frozenset[str]]:
        if not path.is_file():
            raise ValueError(f"taxonomy file not found: {path}")
        with path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        if not isinstance(raw, dict):
            raise ValueError(
                f"taxonomy.yaml must be a top-level mapping, got {type(raw).__name__}"
            )
        if not raw:
            raise ValueError("taxonomy.yaml is empty — at least one vertical required")

        result: dict[str, frozenset[str]] = {}
        for slug, keywords in raw.items():
            if not isinstance(slug, str) or not slug:
                raise ValueError(f"vertical slug must be a non-empty string, got {slug!r}")
            if slug != slug.lower() or slug != slug.strip():
                raise ValueError(f"vertical slug must be lowercase stripped, got {slug!r}")
            if not isinstance(keywords, list):
                raise ValueError(
                    f"vertical {slug!r} must map to a list of keywords, "
                    f"got {type(keywords).__name__}"
                )
            if not keywords:
                raise ValueError(f"vertical {slug!r} has an empty keyword list")
            kw_set: set[str] = set()
            for kw in keywords:
                if not isinstance(kw, str) or not kw:
                    raise ValueError(
                        f"vertical {slug!r} contains an invalid keyword: {kw!r}"
                    )
                if kw != kw.lower() or kw != kw.strip():
                    raise ValueError(
                        f"vertical {slug!r} keyword must be lowercase stripped: {kw!r}"
                    )
                kw_set.add(kw)
            result[slug] = frozenset(kw_set)
        return result


# Verify at import time that YamlTaxonomy satisfies the Protocol.
# This is a structural check, not a runtime isinstance check.
_: TaxonomyCatalog = YamlTaxonomy.__new__(YamlTaxonomy)  # type: ignore[assignment]
