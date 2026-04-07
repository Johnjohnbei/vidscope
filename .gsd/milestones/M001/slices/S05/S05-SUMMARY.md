---
id: S05
parent: M001
milestone: M001
provides:
  - HeuristicAnalyzer + StubAnalyzer implementing the Analyzer port
  - build_analyzer registry function (R010 seam)
  - AnalyzeStage as the 4th pipeline stage
  - Container.analyzer field + 4-stage runner
  - analyses rows in DB linked to videos
  - Pattern for M004 LLM-backed providers (env var + factory + ConfigError)
requires:
  - slice: S03
    provides: Real transcripts in DB that S05 analyzes
affects:
  - S06 (FTS5 + show + search) — will index analyses.summary alongside transcripts.full_text in the FTS5 virtual table; vidscope show will display the analysis fields
key_files:
  - src/vidscope/adapters/heuristic/__init__.py
  - src/vidscope/adapters/heuristic/analyzer.py
  - src/vidscope/adapters/heuristic/stub.py
  - src/vidscope/adapters/heuristic/stopwords.py
  - src/vidscope/infrastructure/analyzer_registry.py
  - src/vidscope/infrastructure/config.py
  - src/vidscope/pipeline/stages/analyze.py
  - src/vidscope/pipeline/stages/__init__.py
  - src/vidscope/infrastructure/container.py
  - tests/unit/adapters/heuristic/test_analyzer.py
  - tests/unit/infrastructure/test_analyzer_registry.py
  - tests/unit/pipeline/stages/test_analyze.py
  - scripts/verify-s05.sh
key_decisions:
  - Pure stdlib heuristic analyzer per D010 — zero network, zero paid API, default for every video
  - Composite scoring: length (40) + diversity (30) + segments (30) = max 100. Each sub-signal capped.
  - Empty transcripts produce valid Analysis with score=0 + summary='no speech detected' — the row exists for FTS5 in S06 even when there's no speech to index
  - Analyzer registry pattern: frozen dict of name → factory callable. Adding M004 LLM providers = adding entries, no caller changes.
  - Validation against registry happens in build_analyzer, not Config — same separation as cookies (Config holds the name string, factory validates)
  - AnalyzeStage rebuilds the Analysis with ctx.video_id explicitly — defensive against analyzers setting wrong video_id
patterns_established:
  - Pluggable provider registry: frozen factory dict + build_x(name) function + ConfigError on unknown name. Will be reused for any future replaceable component (transcribers, downloaders, etc.)
  - Adapter sub-package layout: each provider family in its own subpackage of vidscope.adapters (heuristic/, ytdlp/, whisper/, ffmpeg/, fs/). Future providers slot in cleanly.
observability_surfaces:
  - Pipeline now produces 4 pipeline_runs rows per video (ingest + transcribe + frames + analyze)
  - analyses table has rows with provider, score, keywords, topics, summary — visible in vidscope show after S06
  - Provider name in the analyses table tells operators which analyzer ran — critical when M004 adds LLM-backed providers and we need to know which one produced a given row
drill_down_paths:
  - .gsd/milestones/M001/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S05/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001/slices/S05/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T16:01:57.066Z
blocker_discovered: false
---

# S05: Heuristic analyzer with pluggable provider interface

**Shipped the heuristic analyzer (pure Python, zero cost) plus the pluggable provider registry (R010). Pipeline now runs ingest → transcribe → frames → analyze in 4 stages, validated end-to-end on TikTok + YouTube.**

## What Happened

S05 added the 4th pipeline stage in 4 tasks. The slice closes both R004 (qualitative analysis) and R010 (pluggable provider seam) by registering 2 analyzer implementations behind a single factory function.

**T01**: HeuristicAnalyzer with pure stdlib (re + Counter). Strategy: tokenize → exclude stopwords (FR + EN, ~300 words) → top 8 by frequency = keywords, top 3 = topics. Score is composite of length (40 pts max) + diversity (30) + segments (30). Summary is first ~200 chars truncated at last space. Empty transcripts return valid Analysis with score=0 and summary='no speech detected'. StubAnalyzer is a minimal placeholder to prove the seam.

**T02**: analyzer_registry.py with build_analyzer(name) factory mapping 'heuristic' → HeuristicAnalyzer and 'stub' → StubAnalyzer. Config grew Config.analyzer_name + VIDSCOPE_ANALYZER env var (default 'heuristic'). Validation against the registry happens in build_analyzer, raising ConfigError on unknown providers with the registered list in the message.

**T03**: AnalyzeStage reads transcript from DB, raises AnalysisError if missing, calls analyzer.analyze(transcript), persists via uow.analyses.add. Cheap is_satisfied DB check (analyses.get_latest_for_video).

**T04**: Container extension adds analyzer field + AnalyzeStage to the runner. Pipeline order is now ingest → transcribe → frames → analyze. Tests assert stage_names tuple is correct. Integration test helper asserts analyses row exists with provider name and score in [0, 100].

**Live result**: TikTok + YouTube full 4-stage pipeline in 10.52s (model load was already cached from S03). Each video produces 4 pipeline_runs rows + 1 analyses row with the heuristic provider's output. Instagram still xfailed for cookies.

**Pluggable seam validation**: build_analyzer('heuristic') and build_analyzer('stub') both work; build_analyzer('foo') raises ConfigError with the supported list. M004 will extend _FACTORIES with LLM providers (NVIDIA, Groq, OpenAI, etc.) without touching the container.

**Quality gates**: 331 unit + 3 architecture + 3 integration tests. Ruff clean (8 auto-fixes). mypy strict on 64 source files. import-linter 7/7 contracts kept. The heuristic adapter package imports zero third-party deps.

## Verification

Ran `python -m uv run pytest -q` → 331 passed, 3 deselected. Ran `python -m uv run pytest tests/integration -m 'integration and slow' -v` (with ffmpeg) → 2 passed, 1 xfailed in 10.52s. Ran `bash scripts/verify-s05.sh --skip-integration` → 7/7 green. All quality gates clean.

## Requirements Advanced

- R004 — Real heuristic analysis validated on live TikTok + YouTube. Every analysis row has provider='heuristic', detected language, top keywords, topics, score in [0, 100], and a short summary.
- R010 — Pluggable seam proven with 2 registered analyzers (heuristic + stub). build_analyzer is the single factory; M004 will add providers without touching containers.

## Requirements Validated

- R004 — Live integration tests on TikTok + YouTube produce real analyses rows with provider='heuristic', score in [0, 100], non-empty keywords for videos with speech.
- R010 — build_analyzer registry returns HeuristicAnalyzer for 'heuristic' and StubAnalyzer for 'stub'. Two distinct implementations, swapped via VIDSCOPE_ANALYZER env var with no caller changes.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Heuristic analyzer's keyword extraction is frequency-based with no TF-IDF or topic modeling. Topics are just the top 3 keywords. Language detection comes from the transcript (whisper). Score is a composite of length/diversity/segments — useful for sorting but not deeply meaningful. M004 will add LLM-backed providers for richer analysis.

## Follow-ups

M004: register LLM-backed providers (NVIDIA, Groq, OpenRouter, OpenAI, Anthropic) in the analyzer registry. Each will need API key handling — pattern from S07 cookies (env var + Config field + adapter init validation) is the template.

## Files Created/Modified

- `src/vidscope/adapters/heuristic/analyzer.py` — New HeuristicAnalyzer with composite scoring and stopword filtering
- `src/vidscope/adapters/heuristic/stub.py` — New StubAnalyzer placeholder for the registry seam
- `src/vidscope/adapters/heuristic/stopwords.py` — FR + EN stopword frozensets
- `src/vidscope/infrastructure/analyzer_registry.py` — New build_analyzer factory + KNOWN_ANALYZERS frozenset
- `src/vidscope/infrastructure/config.py` — Added analyzer_name field + VIDSCOPE_ANALYZER env var
- `src/vidscope/pipeline/stages/analyze.py` — New AnalyzeStage
- `src/vidscope/infrastructure/container.py` — Wired analyzer + analyze stage as 4th stage in runner
- `tests/unit/adapters/heuristic/test_analyzer.py` — 15 tests covering heuristic + stub
- `tests/unit/infrastructure/test_analyzer_registry.py` — 7 tests covering registry
- `tests/unit/pipeline/stages/test_analyze.py` — 6 tests for AnalyzeStage
- `tests/integration/test_ingest_live.py` — Helper updated with analyses assertions
- `scripts/verify-s05.sh` — New verification script
