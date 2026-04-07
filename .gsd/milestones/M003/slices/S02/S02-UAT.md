# S02: WatchRefreshUseCase + vidscope watch CLI sub-application — UAT

**Milestone:** M003
**Written:** 2026-04-07T17:59:10.245Z

## S02 UAT

### Manual checks
1. `python -m uv run vidscope watch --help` shows add/list/remove/refresh
2. `python -m uv run vidscope watch add https://www.youtube.com/@YouTube` adds and confirms
3. `python -m uv run vidscope watch list` shows the row
4. `python -m uv run vidscope watch remove @YouTube` removes it
5. (S03 verify script does the live refresh end-to-end)

### Quality gates
- [x] 432 unit + 3 architecture tests
- [x] ruff, mypy strict (74 files), lint-imports (8 contracts) all clean
- [x] vidscope watch sub-application wired on root app
- [x] Refresh idempotent through stubbed pipeline

