"""Unit tests for :class:`RegexLinkExtractor`.

The non-negotiable corpus-driven test (:meth:`TestLinkCorpus.test_corpus`)
iterates every entry in ``tests/fixtures/link_corpus.json`` and fails
if the extractor misses a positive or produces a false positive. New
edge cases go in the corpus, not here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vidscope.adapters.text import RegexLinkExtractor, normalize_url

CORPUS_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "link_corpus.json"


@pytest.fixture(scope="module")
def extractor() -> RegexLinkExtractor:
    return RegexLinkExtractor()


@pytest.fixture(scope="module")
def corpus() -> dict[str, list[dict[str, Any]]]:
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert len(data["positive"]) >= 50, (
        f"corpus must have >=50 positives (has {len(data['positive'])})"
    )
    assert len(data["negative"]) >= 30, (
        f"corpus must have >=30 negatives (has {len(data['negative'])})"
    )
    assert len(data["edge"]) >= 20, (
        f"corpus must have >=20 edge cases (has {len(data['edge'])})"
    )
    return data


class TestRegexLinkExtractorBasics:
    def test_scheme_url(self, extractor: RegexLinkExtractor) -> None:
        hits = extractor.extract("visit https://example.com today", source="description")
        assert len(hits) == 1
        assert hits[0]["source"] == "description"

    def test_query_and_fragment_normalized(self, extractor: RegexLinkExtractor) -> None:
        hits = extractor.extract(
            "https://shop.com/p?id=1&utm_source=ig#frag", source="description"
        )
        assert len(hits) == 1
        assert hits[0]["normalized_url"] == "https://shop.com/p?id=1"

    def test_bare_tld_known(self, extractor: RegexLinkExtractor) -> None:
        hits = extractor.extract("go to bit.ly/abc", source="description")
        assert len(hits) == 1
        assert hits[0]["normalized_url"] == "https://bit.ly/abc"

    def test_false_positive_hello_world(self, extractor: RegexLinkExtractor) -> None:
        assert extractor.extract("hello.world is not a URL", source="description") == []

    def test_false_positive_version_string(self, extractor: RegexLinkExtractor) -> None:
        assert extractor.extract("version 1.0.0 and file.txt", source="description") == []

    def test_multiple_urls(self, extractor: RegexLinkExtractor) -> None:
        hits = extractor.extract(
            "url1 https://a.com and url2 https://b.com", source="description"
        )
        assert len(hits) == 2

    def test_dedup_by_normalized_url(self, extractor: RegexLinkExtractor) -> None:
        hits = extractor.extract(
            "https://a.com and https://a.com/", source="description"
        )
        assert len(hits) == 1

    def test_strip_trailing_parenthesis(self, extractor: RegexLinkExtractor) -> None:
        hits = extractor.extract("(visit https://example.com)", source="description")
        assert len(hits) == 1
        assert ")" not in hits[0]["url"]

    def test_empty_text(self, extractor: RegexLinkExtractor) -> None:
        assert extractor.extract("", source="description") == []

    def test_no_url_text(self, extractor: RegexLinkExtractor) -> None:
        assert extractor.extract("no urls here", source="description") == []

    def test_source_propagated(self, extractor: RegexLinkExtractor) -> None:
        hits = extractor.extract("https://a.com", source="transcript")
        assert len(hits) == 1
        assert hits[0]["source"] == "transcript"

    def test_hello_world_is_not_url(self, extractor: RegexLinkExtractor) -> None:
        assert extractor.extract("hello.world", source="description") == []

    def test_version_string_is_not_url(self, extractor: RegexLinkExtractor) -> None:
        assert extractor.extract("version 1.0.0", source="description") == []

    def test_file_extension_is_not_url(self, extractor: RegexLinkExtractor) -> None:
        assert extractor.extract("file.txt", source="description") == []

    def test_email_is_not_url(self, extractor: RegexLinkExtractor) -> None:
        """Email addresses must not be captured as bare-domain URLs."""
        assert extractor.extract("firstname.lastname@email.com", source="description") == []

    def test_position_ms_is_none(self, extractor: RegexLinkExtractor) -> None:
        hits = extractor.extract("https://example.com", source="description")
        assert hits[0]["position_ms"] is None

    def test_never_raises_on_garbage(self, extractor: RegexLinkExtractor) -> None:
        for garbage in ["", "   ", "??!!", "\x00\x01", "a" * 10000]:
            extractor.extract(garbage, source="description")  # must not raise


class TestLinkCorpus:
    """Gate qualite non-negotiable (M007 ROADMAP).

    Itere le corpus complet ; fail si l'extracteur manque un positif
    ou produit un faux positif. Un echec = broken build.
    """

    def _compare(
        self,
        extractor: RegexLinkExtractor,
        entry: dict[str, Any],
        category: str,
    ) -> None:
        text = entry["text"]
        expected = {normalize_url(u) for u in entry["expected_urls"]}
        actual = {
            h["normalized_url"]
            for h in extractor.extract(text, source="description")
        }
        assert actual == expected, (
            f"{category} fixture mismatch for text={text!r}\n"
            f"  expected={sorted(expected)}\n"
            f"  actual  ={sorted(actual)}"
        )

    def test_positive_corpus(
        self,
        extractor: RegexLinkExtractor,
        corpus: dict[str, list[dict[str, Any]]],
    ) -> None:
        for entry in corpus["positive"]:
            self._compare(extractor, entry, "positive")

    def test_negative_corpus(
        self,
        extractor: RegexLinkExtractor,
        corpus: dict[str, list[dict[str, Any]]],
    ) -> None:
        for entry in corpus["negative"]:
            self._compare(extractor, entry, "negative")

    def test_edge_corpus(
        self,
        extractor: RegexLinkExtractor,
        corpus: dict[str, list[dict[str, Any]]],
    ) -> None:
        for entry in corpus["edge"]:
            self._compare(extractor, entry, "edge")
