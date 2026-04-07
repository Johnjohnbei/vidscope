"""SuggestRelatedUseCase — keyword-overlap-based related-video suggestion.

Given a source video id, returns the top N videos from the library
ranked by keyword overlap with the source video's analysis. Uses
Jaccard similarity on the keyword sets — pure Python, zero deps,
no embeddings.

This is the v1 suggestion engine per R023. It's deliberately simple:

- **Score** = |source_keywords ∩ candidate_keywords| / |source_keywords ∪ candidate_keywords|
- **Exclusions**: the source video itself; candidates with score 0
- **Cap**: the library is scanned up to a reasonable limit (500) to
  avoid pathological cost in large libraries. Future optimization
  (M003+) can add an index on keywords if needed.

Limitations
-----------

- Keyword sets come from the heuristic analyzer (frequency-based).
  Quality is correlated with analysis quality. Weak analyses ⇒
  weak suggestions.
- No creator overlap, no title similarity, no transcript similarity.
  R026 (semantic search via embeddings) is deferred.
- Empty source keywords ⇒ empty suggestions. The use case is honest:
  can't suggest without signal.

Design notes
------------

- The use case uses a single UnitOfWork that stays open for the
  duration of execute(). All reads happen in one transaction.
- No writes. Pure read operation. is_satisfied-style caching would
  be premature — the library is small and scans are fast.
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Platform, VideoId
from vidscope.ports import UnitOfWorkFactory

__all__ = ["SuggestRelatedResult", "SuggestRelatedUseCase", "Suggestion"]


_MAX_CANDIDATES_SCANNED = 500


@dataclass(frozen=True, slots=True)
class Suggestion:
    """One related-video entry returned by SuggestRelatedUseCase."""

    video_id: VideoId
    title: str | None
    platform: Platform
    score: float  # Jaccard in [0, 1]
    matched_keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SuggestRelatedResult:
    """Result of a suggest_related call.

    ``source_video_id`` is the requested video id. ``source_found`` is
    False if the video does not exist. ``reason`` carries a human-
    readable explanation when ``suggestions`` is empty.
    """

    source_video_id: VideoId
    source_found: bool
    source_title: str | None
    source_keywords: tuple[str, ...]
    suggestions: tuple[Suggestion, ...]
    reason: str


class SuggestRelatedUseCase:
    """Return the top N videos related to a source video by keyword overlap."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, video_id: int, *, limit: int = 5) -> SuggestRelatedResult:
        """Return up to ``limit`` related videos, ranked by Jaccard overlap.

        Parameters
        ----------
        video_id:
            The source video id.
        limit:
            Maximum number of suggestions to return. Clamped to
            [1, 100].

        Returns
        -------
        SuggestRelatedResult
            Always a valid result. Empty ``suggestions`` tuple when
            no candidates match; ``reason`` explains why.
        """
        clamped_limit = max(1, min(limit, 100))
        source_id = VideoId(video_id)

        with self._uow_factory() as uow:
            source_video = uow.videos.get(source_id)
            if source_video is None:
                return SuggestRelatedResult(
                    source_video_id=source_id,
                    source_found=False,
                    source_title=None,
                    source_keywords=(),
                    suggestions=(),
                    reason=f"no video with id {video_id}",
                )

            source_analysis = uow.analyses.get_latest_for_video(source_id)
            if source_analysis is None or not source_analysis.keywords:
                return SuggestRelatedResult(
                    source_video_id=source_id,
                    source_found=True,
                    source_title=source_video.title,
                    source_keywords=(),
                    suggestions=(),
                    reason=(
                        "source video has no analysis keywords yet — "
                        "run `vidscope add` on the URL to produce one"
                    ),
                )

            source_kw_set = frozenset(source_analysis.keywords)
            candidates = uow.videos.list_recent(limit=_MAX_CANDIDATES_SCANNED)

            scored: list[Suggestion] = []
            for candidate in candidates:
                if candidate.id is None or candidate.id == source_id:
                    continue
                cand_analysis = uow.analyses.get_latest_for_video(candidate.id)
                if cand_analysis is None or not cand_analysis.keywords:
                    continue
                cand_kw_set = frozenset(cand_analysis.keywords)
                score, matched = _jaccard(source_kw_set, cand_kw_set)
                if score <= 0.0:
                    continue
                scored.append(
                    Suggestion(
                        video_id=candidate.id,
                        title=candidate.title,
                        platform=candidate.platform,
                        score=score,
                        matched_keywords=matched,
                    )
                )

            scored.sort(key=lambda s: (-s.score, int(s.video_id)))
            top = tuple(scored[:clamped_limit])

        if not top:
            reason = (
                "no candidates share keywords with the source video"
                if candidates
                else "library is empty"
            )
        else:
            reason = f"found {len(top)} related videos"

        return SuggestRelatedResult(
            source_video_id=source_id,
            source_found=True,
            source_title=source_video.title,
            source_keywords=tuple(source_analysis.keywords),
            suggestions=top,
            reason=reason,
        )


def _jaccard(
    a: frozenset[str], b: frozenset[str]
) -> tuple[float, tuple[str, ...]]:
    """Return (Jaccard score, sorted matched keywords) for two sets.

    Jaccard = |a ∩ b| / |a ∪ b|. Both sets empty ⇒ score 0 (not 1,
    because we want "no signal" to be a non-match).
    """
    if not a or not b:
        return 0.0, ()
    intersection = a & b
    if not intersection:
        return 0.0, ()
    union = a | b
    score = len(intersection) / len(union)
    matched = tuple(sorted(intersection))
    return score, matched
