---
id: T02
parent: S01
milestone: M005
key_files:
  - src/vidscope/application/cookies.py
  - src/vidscope/application/cookies_validator.py
  - tests/unit/application/test_cookies.py
  - tests/unit/application/test_cookies_validator.py
  - .importlinter
key_decisions:
  - Use cases take simple Path arguments instead of the whole Config — application stays decoupled from infrastructure
  - cookies_validator lives in application layer (pure-Python, only stdlib) — doesn't need to be in infrastructure
  - Tightened application-has-no-adapters contract to forbid infrastructure imports — closes a pre-existing architectural hole
  - All cookies subcommands operate on <data_dir>/cookies.txt only — env override files are owned by the user, never touched by VidScope's CLI
duration: 
verification_result: passed
completed_at: 2026-04-07T18:46:00.930Z
blocker_discovered: false
---

# T02: Shipped 3 cookies use cases (Set/GetStatus/Clear) + tightened the application-has-no-adapters contract to also forbid infrastructure imports. Surfaced an architectural hole and closed it.

**Shipped 3 cookies use cases (Set/GetStatus/Clear) + tightened the application-has-no-adapters contract to also forbid infrastructure imports. Surfaced an architectural hole and closed it.**

## What Happened

**Wrote `src/vidscope/application/cookies.py`** with three frozen-dataclass use cases: `SetCookiesUseCase`, `GetCookiesStatusUseCase`, `ClearCookiesUseCase`. Each takes a `data_dir: Path` constructor argument and operates on `<data_dir>/cookies.txt` (the canonical location). Each returns a typed result dataclass — never raises.

- `SetCookiesUseCase.execute(source)` validates the source via `validate_cookies_file`, copies it to the canonical location via `shutil.copyfile`, then re-validates the destination. Defensive: invalid source never overwrites a working cookies file.
- `GetCookiesStatusUseCase.execute()` returns `CookiesStatus` with default_path, default_exists, size_bytes, modified_at, validation, env_override_path, active_path. The env_override_path is set when the user has pointed `VIDSCOPE_COOKIES_FILE` somewhere other than the canonical location — this surfaces in the status command so the user knows their `vidscope cookies set` won't take effect.
- `ClearCookiesUseCase.execute()` removes the canonical file, never touches an env-override path because that file is owned by the user.

**Surfaced and fixed an architectural hole.** First version of the use cases imported `Config` from `vidscope.infrastructure.config`. The `application-has-no-adapters` import-linter contract had a gap: it forbade `vidscope.adapters.*` and `vidscope.cli` but did NOT forbid `vidscope.infrastructure`. So `from vidscope.infrastructure.config import Config` in the application layer would have passed the linter despite being a real architectural violation (application should never depend on infrastructure — that's the composition root).

**Two-step fix**:
1. Tightened the contract: added `vidscope.infrastructure` to the forbidden list. The contract immediately caught my own violation in `cookies.py`.
2. Refactored the use cases to take `data_dir: Path` and `configured_cookies_file: Path | None` as constructor args instead of the whole `Config`. The composition root in `infrastructure/container.py` will pass these explicitly when wiring the CLI commands in T03.
3. Moved `cookies_validator.py` from `infrastructure/` to `application/` since it's pure-Python (only uses `pathlib` + `dataclass` from stdlib) and is naturally consumed by the application layer. Updated the test path correspondingly.

**`vidscope.application` is now strictly clean**: imports only domain + ports + pipeline + stdlib. Verified by running `lint-imports` — 9 contracts kept, 0 broken.

**13 unit tests** for the use cases in 3 classes:
- `TestSetCookies` (5): valid file copy, invalid source preserves existing, missing source, overwrite existing, creates data_dir if missing
- `TestGetCookiesStatus` (4): no cookies file, valid file present, env override pointing elsewhere, no env override when active==default
- `TestClearCookies` (4): removes existing file, returns failure when no file, only touches default path (not env override), unlink failure → error result

All 13 + the 15 validator tests pass. 28 total cookies-related tests in the application layer.

**Quality gates after T02**:
- ✅ pytest: 28 application/cookies* tests green in 0.15s
- ✅ lint-imports: 9 contracts kept (the new infrastructure-forbidden rule passing now that the use cases are clean)

## Verification

Ran `python -m uv run pytest tests/unit/application/test_cookies.py tests/unit/application/test_cookies_validator.py -q` → 28 passed in 0.15s. Then `python -m uv run lint-imports` → 9 contracts kept, 0 broken.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/application/test_cookies.py tests/unit/application/test_cookies_validator.py -q` | 0 | ✅ 28 passed | 150ms |
| 2 | `python -m uv run lint-imports` | 0 | ✅ 9 contracts kept, 0 broken | 2000ms |

## Deviations

**Architectural improvement** (not a deviation from the plan, but worth flagging): tightened `application-has-no-adapters` contract to forbid `vidscope.infrastructure` imports. This was a pre-existing gap in the contract — every other application file happened to be clean by convention, but the structural enforcement was missing. The cookies use cases triggered the discovery and the fix is now permanent. Also moved `cookies_validator` from infrastructure to application since it's pure-Python.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/application/cookies.py`
- `src/vidscope/application/cookies_validator.py`
- `tests/unit/application/test_cookies.py`
- `tests/unit/application/test_cookies_validator.py`
- `.importlinter`
