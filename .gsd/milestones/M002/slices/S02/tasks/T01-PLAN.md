---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: SuggestRelatedUseCase with Jaccard keyword overlap

Create src/vidscope/application/suggest_related.py. SuggestRelatedUseCase takes a unit_of_work_factory. execute(video_id, limit=5) returns a SuggestRelatedResult DTO with: source_video (or None if not found), suggestions (tuple of Suggestion dataclasses with video_id, title, platform, score, matched_keywords). Algorithm: (1) open a UoW, (2) fetch source video + its latest analysis, (3) if source analysis is None OR keywords empty, return empty suggestions, (4) fetch all videos in the library up to a reasonable cap (500), (5) for each candidate != source, fetch its latest analysis, compute Jaccard = |intersection| / |union| on keyword sets, skip if score == 0, (6) sort descending by score, take top `limit`. Tests cover every branch.

## Inputs

- ``src/vidscope/ports/repositories.py` — VideoRepository + AnalysisRepository`
- ``src/vidscope/domain/entities.py` — Video, Analysis`

## Expected Output

- ``src/vidscope/application/suggest_related.py``
- ``tests/unit/application/test_suggest_related.py``

## Verification

python -m uv run pytest tests/unit/application/test_suggest_related.py -q
