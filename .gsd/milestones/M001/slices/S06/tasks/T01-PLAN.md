---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: IndexStage implementing the Stage protocol

Create src/vidscope/pipeline/stages/index.py. IndexStage with name=StageName.INDEX.value. __init__ takes nothing (uses uow.search_index from the unit of work). is_satisfied is a no-op returning False (the search index is rebuilt on every run because it's idempotent via DELETE+INSERT). execute: (1) requires ctx.video_id, (2) reads the latest transcript via uow.transcripts.get_for_video, (3) reads the latest analysis via uow.analyses.get_latest_for_video, (4) calls uow.search_index.index_transcript(transcript) if transcript exists, (5) calls uow.search_index.index_analysis(analysis) if analysis has a non-empty summary. Returns StageResult with the indexed document count. Tests with real adapters.

## Inputs

- ``src/vidscope/ports/pipeline.py``
- ``src/vidscope/ports/unit_of_work.py` (search_index attribute)`

## Expected Output

- ``src/vidscope/pipeline/stages/index.py``
- ``tests/unit/pipeline/stages/test_index.py``

## Verification

python -m uv run pytest tests/unit/pipeline/stages -q
