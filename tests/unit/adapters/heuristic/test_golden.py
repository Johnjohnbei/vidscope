"""Golden-set gate: HeuristicAnalyzerV2 must achieve >= 70% match rate.

Match criterion: a fixture is a match ONLY IF the predicted
(content_type, is_sponsored, sentiment) triplet equals the expected
triplet exactly (all three fields).

If the gate fails, the test prints the per-fixture mismatches so
the failing lexicons / heuristics can be tuned.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from vidscope.adapters.heuristic.heuristic_v2 import HeuristicAnalyzerV2
from vidscope.domain import (
    ContentType,
    Language,
    SentimentLabel,
    Transcript,
    VideoId,
)


GOLDEN_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "analysis_golden.jsonl"
GATE_THRESHOLD = 0.70
EXPECTED_FIXTURE_COUNT = 40


class _StubTaxonomy:
    def __init__(self) -> None:
        self._data = {
            "tech": frozenset({"python", "code", "pip", "terminal", "install",
                               "vs", "notion", "npm", "premiere"}),
            "fitness": frozenset({"workout", "squat", "reps", "running", "yoga"}),
            "food": frozenset({"pizza", "cook", "recipe", "meal"}),
            "travel": frozenset({"paris", "louvre", "marseille", "villages"}),
            "gaming": frozenset({"ps5", "xbox", "playstation"}),
        }

    def verticals(self) -> list[str]:
        return sorted(self._data.keys())

    def keywords_for_vertical(self, vertical: str) -> frozenset[str]:
        return self._data.get(vertical, frozenset())

    def match(self, tokens: list[str]) -> list[str]:
        lowered = {t.lower() for t in tokens}
        scored = [
            (len(lowered & kws), slug)
            for slug, kws in self._data.items()
            if lowered & kws
        ]
        scored.sort(key=lambda p: (-p[0], p[1]))
        return [s for _, s in scored]


def _load_fixtures() -> list[dict]:
    assert GOLDEN_PATH.is_file(), f"golden fixture file missing: {GOLDEN_PATH}"
    lines = [
        ln for ln in GOLDEN_PATH.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    fixtures = [json.loads(ln) for ln in lines]
    return fixtures


class TestFixtureStructure:
    def test_file_exists(self) -> None:
        assert GOLDEN_PATH.is_file(), f"expected {GOLDEN_PATH}"

    def test_count_is_exactly_40(self) -> None:
        fixtures = _load_fixtures()
        assert len(fixtures) == EXPECTED_FIXTURE_COUNT, (
            f"expected {EXPECTED_FIXTURE_COUNT} fixtures, got {len(fixtures)}"
        )

    def test_every_fixture_has_required_keys(self) -> None:
        required = {
            "id", "language", "transcript",
            "expected_content_type", "expected_is_sponsored",
            "expected_sentiment",
        }
        for fx in _load_fixtures():
            assert required.issubset(fx.keys()), f"fixture {fx.get('id')} missing keys"

    def test_no_duplicate_ids(self) -> None:
        ids = [f["id"] for f in _load_fixtures()]
        assert len(ids) == len(set(ids)), "duplicate fixture ids"

    def test_expected_fields_are_valid_enum_values(self) -> None:
        content_values = {c.value for c in ContentType}
        sentiment_values = {s.value for s in SentimentLabel}
        for fx in _load_fixtures():
            assert fx["expected_content_type"] in content_values, (
                f"bad content_type in {fx['id']}: {fx['expected_content_type']}"
            )
            assert fx["expected_sentiment"] in sentiment_values, (
                f"bad sentiment in {fx['id']}: {fx['expected_sentiment']}"
            )
            assert isinstance(fx["expected_is_sponsored"], bool)

    def test_language_coverage(self) -> None:
        langs = Counter(f["language"] for f in _load_fixtures())
        assert langs["en"] >= 15
        assert langs["fr"] >= 15

    def test_sentiment_coverage(self) -> None:
        sents = Counter(f["expected_sentiment"] for f in _load_fixtures())
        assert sents["positive"] >= 10
        assert sents["negative"] >= 10
        assert sents["neutral"] >= 10
        assert sents["mixed"] >= 5

    def test_sponsored_coverage(self) -> None:
        spon = Counter(f["expected_is_sponsored"] for f in _load_fixtures())
        assert spon[True] >= 8
        assert spon[False] >= 20

    def test_content_type_coverage(self) -> None:
        ct = Counter(f["expected_content_type"] for f in _load_fixtures())
        # At least 4 tutorials, reviews and vlogs each
        for key in ("tutorial", "review", "vlog"):
            assert ct[key] >= 4, f"only {ct[key]} {key} fixtures"


class TestGoldenGate:
    def test_heuristic_v2_meets_70_pct_match_rate(self) -> None:
        analyzer = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        fixtures = _load_fixtures()

        matches = 0
        mismatches: list[str] = []
        for fx in fixtures:
            lang_code = fx["language"]
            try:
                lang = Language(lang_code)
            except ValueError:
                lang = Language.UNKNOWN

            transcript = Transcript(
                video_id=VideoId(1),
                language=lang,
                full_text=fx["transcript"],
                segments=(),
            )
            result = analyzer.analyze(transcript)
            expected_ct = fx["expected_content_type"]
            expected_spon = fx["expected_is_sponsored"]
            expected_sent = fx["expected_sentiment"]

            actual_ct = result.content_type.value if result.content_type else None
            actual_spon = result.is_sponsored
            actual_sent = result.sentiment.value if result.sentiment else None

            triplet_ok = (
                actual_ct == expected_ct
                and actual_spon == expected_spon
                and actual_sent == expected_sent
            )
            if triplet_ok:
                matches += 1
            else:
                mismatches.append(
                    f"  {fx['id']}: expected ({expected_ct},{expected_spon},{expected_sent}) "
                    f"got ({actual_ct},{actual_spon},{actual_sent})"
                )

        rate = matches / len(fixtures)
        assert rate >= GATE_THRESHOLD, (
            f"golden gate failed: {matches}/{len(fixtures)} = {rate:.0%} "
            f"< required {GATE_THRESHOLD:.0%}\n"
            f"mismatches:\n" + "\n".join(mismatches)
        )
