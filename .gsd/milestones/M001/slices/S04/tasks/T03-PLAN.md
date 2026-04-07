---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: Container wiring + CLI test stub for ffmpeg

Update src/vidscope/infrastructure/container.py to instantiate FfmpegFrameExtractor and FramesStage, and append the stage to the runner stages list AFTER TranscribeStage. Add frame_extractor: FrameExtractor field to Container. Update the CLI test fixture stub_pipeline to also stub FfmpegFrameExtractor (or rather, stub subprocess.run since FfmpegFrameExtractor calls it). Update test_after_add to expect 3 pipeline_runs (ingest+transcribe+frames). Update test_container assertions: stage_names == ('ingest','transcribe','frames'), container.frame_extractor is not None.

## Inputs

- ``src/vidscope/adapters/ffmpeg/frame_extractor.py``
- ``src/vidscope/pipeline/stages/frames.py``

## Expected Output

- ``src/vidscope/infrastructure/container.py` — frame_extractor field + 3-stage runner`
- ``tests/unit/infrastructure/test_container.py` — updated assertions`
- ``tests/unit/cli/test_app.py` — stub_pipeline extended for ffmpeg subprocess + 3-run assertion`

## Verification

python -m uv run pytest tests/unit -q
