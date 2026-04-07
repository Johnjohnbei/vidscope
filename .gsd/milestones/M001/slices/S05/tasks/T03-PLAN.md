---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: AnalyzeStage implementing the Stage protocol

Create src/vidscope/pipeline/stages/analyze.py. AnalyzeStage with name=StageName.ANALYZE.value. __init__ takes Analyzer. is_satisfied returns True if uow.analyses.get_latest_for_video(ctx.video_id) is not None. execute: (1) requires ctx.video_id, (2) reads transcript via uow.transcripts.get_for_video, (3) raises AnalysisError if no transcript exists, (4) calls analyzer.analyze(transcript), (5) overwrites video_id from ctx, (6) persists via uow.analyses.add, (7) mutates ctx.analysis_id. Tests with fake Analyzer + real SqliteUnitOfWork.

## Inputs

- ``src/vidscope/ports/pipeline.py``
- ``src/vidscope/domain/entities.py``

## Expected Output

- ``src/vidscope/pipeline/stages/analyze.py` — AnalyzeStage`
- ``tests/unit/pipeline/stages/test_analyze.py``

## Verification

python -m uv run pytest tests/unit/pipeline/stages -q
