---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T09: Quality gates: pytest + ruff + mypy strict + import-linter architecture test

Add quality-gate configuration to pyproject.toml: [tool.pytest.ini_options] (testpaths, markers: unit/integration/architecture), [tool.ruff] (select E,W,F,I,UP,B,SIM,RUF,TCH,PL + line-length 100 + target py312), [tool.ruff.lint.per-file-ignores] (tests allowed to ignore PLR2004 and S101), [tool.mypy] (strict=true on src/vidscope, no_implicit_optional, warn_unused_ignores, warn_return_any, disallow_untyped_defs). Add import-linter as dev dep (`python -m uv add --dev import-linter`). Create .importlinter in repo root with a `layers` contract enforcing the seven layers (domain, ports, adapters, pipeline, application, cli, infrastructure) with inward-only rule + a `forbidden` contract blocking adapters cross-importing each other + a `forbidden` contract blocking domain/ports from importing any third-party runtime dep. Create tests/architecture/test_layering.py that runs lint_imports via its Python API and asserts all contracts pass. Run the full suite (`pytest`, `ruff`, `mypy`, `lint-imports`) and fix any violations surfaced by the code from T03-T08. Definition of done: all four tools clean on the full tree.

## Inputs

- ``src/vidscope/``
- ``.gsd/KNOWLEDGE.md``

## Expected Output

- ``pyproject.toml` — pytest/ruff/mypy config + import-linter dev dep`
- ``.importlinter` — layers + forbidden contracts`
- ``tests/architecture/test_layering.py` — programmatic lint_imports assertion`

## Verification

python -m uv run pytest -q && python -m uv run ruff check src tests && python -m uv run mypy src && python -m uv run lint-imports
