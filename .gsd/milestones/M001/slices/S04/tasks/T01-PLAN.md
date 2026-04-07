---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: FfmpegFrameExtractor adapter shelling out to ffmpeg

Create src/vidscope/adapters/ffmpeg/__init__.py and src/vidscope/adapters/ffmpeg/frame_extractor.py. FfmpegFrameExtractor implements FrameExtractor port. extract_frames(media_path, output_dir, max_frames=30): (1) verify ffmpeg binary is on PATH via shutil.which, raise FrameExtractionError(retryable=False) with install instructions if not. (2) Build an ffmpeg command that extracts frames at a fixed FPS rate (e.g. 0.2 fps = 1 frame per 5 seconds) with output template output_dir/frame_%04d.jpg. (3) Run subprocess with timeout 60s, capture stderr. (4) On non-zero exit, raise FrameExtractionError with the stderr tail. (5) Glob the output_dir for *.jpg, sort by name, cap at max_frames, build a list of Frame entities with timestamp_ms computed from the frame index and the configured fps. Return the list. Tests stub subprocess.run + the glob with monkeypatch — zero real ffmpeg invocation in unit tests.

## Inputs

- ``src/vidscope/ports/pipeline.py` — FrameExtractor Protocol`
- ``src/vidscope/domain/entities.py` — Frame`
- ``src/vidscope/domain/errors.py` — FrameExtractionError`

## Expected Output

- ``src/vidscope/adapters/ffmpeg/frame_extractor.py` — FfmpegFrameExtractor with subprocess + glob`
- ``tests/unit/adapters/ffmpeg/test_frame_extractor.py` — happy path + missing-binary + non-zero exit + timeout tests`

## Verification

python -m uv run pytest tests/unit/adapters/ffmpeg -q
