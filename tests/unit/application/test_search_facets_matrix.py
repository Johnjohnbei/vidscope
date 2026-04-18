"""Matrix test: sample ≥50 combinations of 3 facets out of 7.

Property: for any combo, execute returns a SearchLibraryResult with
len(hits) <= limit. Guards against regressions in the intersection
logic when the facet count grows.
"""

from __future__ import annotations

import itertools
import random

# Import fakes from the M011 test module to avoid duplicating
from tests.unit.application.test_search_videos_m011 import (
    FakeHit,
    _factory,
    _FakeUoW,
)
from vidscope.application.search_videos import SearchFilters, SearchVideosUseCase
from vidscope.domain import ContentType, TrackingStatus

FACETS = (
    "content_type", "min_actionability", "is_sponsored",
    "status", "starred", "tag", "collection",
)

VALUES = {
    "content_type": ContentType.TUTORIAL,
    "min_actionability": 50.0,
    "is_sponsored": False,
    "status": TrackingStatus.SAVED,
    "starred": True,
    "tag": "idea",
    "collection": "MyCol",
}


def test_matrix_50_combinations_do_not_crash() -> None:
    all_combos = list(itertools.combinations(FACETS, 3))
    assert len(all_combos) >= 35  # C(7, 3) = 35
    # Use all 35 combos (C(7,3)=35) and extend with 15 random 4-facet combos
    # to reach ≥50 as per M011 VALIDATION intent.

    rng = random.Random(42)
    four_combos = list(itertools.combinations(FACETS, 4))
    rng.shuffle(four_combos)
    combos: list[tuple[str, ...]] = list(all_combos) + four_combos[:15]

    assert len(combos) >= 50

    hits = [FakeHit(video_id=i) for i in range(1, 11)]

    for combo in combos:
        uow = _FakeUoW(
            hits,
            analysis_allowed=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            tracking_by_status={TrackingStatus.SAVED: list(range(1, 11))},
            starred=list(range(1, 11)),
            tags={"idea": list(range(1, 11))},
            collections={"MyCol": list(range(1, 11))},
        )
        kwargs = {name: VALUES[name] for name in combo}
        filters = SearchFilters(**kwargs)
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", limit=5, filters=filters)
        assert len(result.hits) <= 5, f"combo={combo} returned {len(result.hits)} hits"
