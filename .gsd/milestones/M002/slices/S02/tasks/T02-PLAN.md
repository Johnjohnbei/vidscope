---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: `vidscope suggest <id>` CLI command

Create src/vidscope/cli/commands/suggest.py with a suggest_command(video_id, limit=5) that builds a container, instantiates SuggestRelatedUseCase, renders results as a rich Table: columns video_id, platform, title, score (0-100 display), matched_keywords. Handles the empty-suggestions case with a clear message. Register on the root Typer app. Add to CliRunner tests.

## Inputs

- ``src/vidscope/application/suggest_related.py``

## Expected Output

- ``src/vidscope/cli/commands/suggest.py``
- `Updated cli/app.py`
- `Updated CliRunner tests`

## Verification

python -m uv run pytest tests/unit/cli -q && python -m uv run vidscope suggest --help
