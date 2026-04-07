---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T01: HeuristicAnalyzer adapter (pure Python, zero deps)

Create src/vidscope/adapters/heuristic/analyzer.py. HeuristicAnalyzer implements the Analyzer port. provider_name = 'heuristic'. analyze(transcript) returns an Analysis with: language copied from transcript.language, keywords extracted via simple frequency analysis on words >= 4 chars excluding stopwords (basic FR + EN stopwords list), topics derived from the top 3 most frequent keywords as topic candidates, score = composite of (text length, word diversity, segment count) normalized to 0-100, summary = first 200 chars of full_text or 'no speech detected' for empty transcripts. Pure Python, stdlib only (re, collections.Counter). Tests cover: empty transcript (no speech), short transcript, long English transcript, French transcript, score bounds.

## Inputs

- ``src/vidscope/ports/pipeline.py` — Analyzer Protocol`
- ``src/vidscope/domain/entities.py` — Analysis, Transcript`

## Expected Output

- ``src/vidscope/adapters/heuristic/analyzer.py` — HeuristicAnalyzer + helper functions`
- ``src/vidscope/adapters/heuristic/stopwords.py` — FR + EN stopwords`
- ``tests/unit/adapters/heuristic/test_analyzer.py``

## Verification

python -m uv run pytest tests/unit/adapters/heuristic -q
