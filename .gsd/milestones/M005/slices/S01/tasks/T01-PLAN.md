---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: validate_cookies_file helper + tests

Create src/vidscope/infrastructure/cookies_validator.py with validate_cookies_file(path) -> CookiesValidation. CookiesValidation is a frozen dataclass with: ok (bool), reason (str), entries_count (int). Format check: starts with '# Netscape HTTP Cookie File' or '# HTTP Cookie File' or any other header line that starts with '#', skips comment + blank lines, parses tab-separated rows, requires 7 columns per row. Permissive about whitespace. Tests: valid file, missing file, empty file, comments-only, malformed rows, mix of comments and valid rows.

## Inputs

- None specified.

## Expected Output

- `validator helper + tests`

## Verification

python -m uv run pytest tests/unit/infrastructure/test_cookies_validator.py -q
