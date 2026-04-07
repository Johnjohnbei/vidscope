---
id: T01
parent: S01
milestone: M005
key_files:
  - src/vidscope/infrastructure/cookies_validator.py
  - tests/unit/infrastructure/test_cookies_validator.py
key_decisions:
  - Permissive validator: header line is optional, empty values OK, CRLF handled — real exports vary
  - Validator never raises — always returns CookiesValidation with ok+reason+entries_count
  - Domain column non-empty check is the only content validation — keeps the validator format-only
  - Module lives in infrastructure layer because it does file I/O — domain stays pure
duration: 
verification_result: passed
completed_at: 2026-04-07T18:42:02.973Z
blocker_discovered: false
---

# T01: Shipped permissive Netscape cookies validator with 15 unit tests covering valid files, no-header exports, mixed comments, CRLF, and every error path.

**Shipped permissive Netscape cookies validator with 15 unit tests covering valid files, no-header exports, mixed comments, CRLF, and every error path.**

## What Happened

Created `src/vidscope/infrastructure/cookies_validator.py` with `validate_cookies_file(path) -> CookiesValidation` and a frozen `CookiesValidation` dataclass (`ok`, `reason`, `entries_count`).

**Permissive parsing rules** documented in the module docstring:
- Header line: any `#` comment (most exports use `# Netscape HTTP Cookie File`, some skip the header)
- Comments: any `#` line, skipped
- Blank lines: skipped
- Data lines: tab-separated, exactly 7 columns (`domain | include_subdomains | path | secure | expiration | name | value`)
- Domain column must be non-empty
- Empty value column is OK (some cookies legitimately have empty values)
- CRLF handled via `rstrip("\r\n")`

The validator never tries to interpret cookie *contents* — no expiration check, no domain validation, no name parsing. Its only job is "is this a syntactically valid cookies.txt that yt-dlp can read?"

**Error path messages are actionable**:
- Missing file → `"file does not exist: <path>"`
- Path is directory → `"path is not a regular file: <path>"`
- Empty file → `"file is empty"`
- Read error → `"failed to read file: <exc>"`
- Only comments → `"no cookie rows found (file contains only comments or blanks)"`
- Malformed rows → `"no valid cookie rows found (N malformed). Expected tab-separated rows with 7 columns."`

**15 unit tests** in 3 classes:
- `TestValidCookies` (6): minimal valid file, multiple rows, no-header export, mixed comments + rows, empty value field, CRLF line endings
- `TestInvalidCookies` (8): missing file, directory path, empty file, whitespace-only, comments-only, malformed rows, wrong column count, empty domain
- `TestCookiesValidation` (1): frozen dataclass cannot be mutated

All 15 pass in 0.39s. Pure-Python, no third-party deps, infrastructure-layer module.

## Verification

Ran `python -m uv run pytest tests/unit/infrastructure/test_cookies_validator.py -q` → 15 passed in 0.39s.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/infrastructure/test_cookies_validator.py -q` | 0 | ✅ 15/15 validator tests green | 390ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/infrastructure/cookies_validator.py`
- `tests/unit/infrastructure/test_cookies_validator.py`
