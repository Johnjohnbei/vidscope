"""Unit tests for YamlTaxonomy — loader + validation + match()."""

from __future__ import annotations

from pathlib import Path

import pytest

from vidscope.adapters.config.yaml_taxonomy import YamlTaxonomy
from vidscope.ports import TaxonomyCatalog


REPO_ROOT = Path(__file__).resolve().parents[4]
REAL_TAXONOMY = REPO_ROOT / "config" / "taxonomy.yaml"


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class TestYamlTaxonomyProtocolConformance:
    def test_instance_is_taxonomy_catalog(self, tmp_path: Path) -> None:
        yaml_path = _write(tmp_path / "t.yaml", "tech:\n  - code\n  - python\n")
        t = YamlTaxonomy(yaml_path)
        assert isinstance(t, TaxonomyCatalog)


class TestYamlTaxonomyLoader:
    def test_loads_minimal_valid_file(self, tmp_path: Path) -> None:
        yaml_path = _write(
            tmp_path / "t.yaml",
            "tech:\n  - code\n  - python\nai:\n  - llm\n  - gpt\n",
        )
        t = YamlTaxonomy(yaml_path)
        assert t.verticals() == ["ai", "tech"]  # sorted alpha
        assert t.keywords_for_vertical("tech") == frozenset({"code", "python"})
        assert t.keywords_for_vertical("ai") == frozenset({"llm", "gpt"})
        assert t.keywords_for_vertical("unknown-slug") == frozenset()

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            YamlTaxonomy(tmp_path / "does-not-exist.yaml")

    def test_non_mapping_root_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "- just a list\n- of items\n")
        with pytest.raises(ValueError, match="top-level mapping"):
            YamlTaxonomy(p)

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "")
        with pytest.raises(ValueError):
            YamlTaxonomy(p)

    def test_non_list_value_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "tech: just-a-string\n")
        with pytest.raises(ValueError, match="list of keywords"):
            YamlTaxonomy(p)

    def test_empty_keyword_list_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "tech: []\n")
        with pytest.raises(ValueError, match="empty keyword list"):
            YamlTaxonomy(p)

    def test_uppercase_slug_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "Tech:\n  - code\n")
        with pytest.raises(ValueError, match="lowercase"):
            YamlTaxonomy(p)

    def test_uppercase_keyword_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "tech:\n  - Python\n")
        with pytest.raises(ValueError, match="lowercase"):
            YamlTaxonomy(p)

    def test_non_string_keyword_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "tech:\n  - 123\n")
        with pytest.raises(ValueError, match="invalid keyword"):
            YamlTaxonomy(p)


class TestYamlTaxonomyMatch:
    def _fixture(self, tmp_path: Path) -> YamlTaxonomy:
        p = _write(
            tmp_path / "t.yaml",
            "tech:\n  - code\n  - python\n  - api\n"
            "ai:\n  - llm\n  - gpt\n  - neural\n"
            "food:\n  - recipe\n  - cooking\n",
        )
        return YamlTaxonomy(p)

    def test_match_returns_empty_on_no_tokens(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        assert t.match([]) == []
        assert t.match(["", ""]) == []

    def test_match_single_vertical(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        assert t.match(["python", "code", "hello"]) == ["tech"]

    def test_match_multiple_verticals_ordered_by_count(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        # tech gets 2 matches (python, code), ai gets 1 (gpt)
        assert t.match(["python", "code", "gpt"]) == ["tech", "ai"]

    def test_match_ties_sorted_alphabetically(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        # tech gets 1 (python), ai gets 1 (gpt) — alphabetical tie-break → ai first
        assert t.match(["python", "gpt"]) == ["ai", "tech"]

    def test_match_is_case_insensitive(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        assert t.match(["PYTHON", "Code"]) == ["tech"]

    def test_match_ignores_unknown_tokens(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        assert t.match(["banana", "xyz"]) == []


class TestRealTaxonomyFile:
    """Sanity checks on the committed config/taxonomy.yaml."""

    def test_real_file_loads(self) -> None:
        assert REAL_TAXONOMY.is_file(), f"expected {REAL_TAXONOMY} to exist"
        t = YamlTaxonomy(REAL_TAXONOMY)
        verticals = t.verticals()
        assert len(verticals) >= 12, (
            f"taxonomy.yaml must have >= 12 verticals, got {len(verticals)}"
        )

    def test_real_file_has_200_plus_keywords(self) -> None:
        t = YamlTaxonomy(REAL_TAXONOMY)
        total = sum(len(t.keywords_for_vertical(v)) for v in t.verticals())
        assert total >= 200, f"taxonomy.yaml must have >= 200 keywords, got {total}"

    def test_real_file_has_no_duplicate_slug(self) -> None:
        t = YamlTaxonomy(REAL_TAXONOMY)
        assert len(t.verticals()) == len(set(t.verticals()))

    def test_match_on_real_file_is_deterministic(self) -> None:
        t = YamlTaxonomy(REAL_TAXONOMY)
        first = t.match(["python", "code", "llm"])
        second = t.match(["python", "code", "llm"])
        assert first == second
