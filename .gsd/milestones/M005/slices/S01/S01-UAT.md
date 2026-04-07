# S01: Cookies file validation + status + clear (read-only + simple writes) — UAT

**Milestone:** M005
**Written:** 2026-04-07T18:51:51.972Z

## UAT — M005/S01: Cookies validation + status + clear

### Manual smoke test (no real network needed)

```bash
# 1. Help command shows cookies sub-app
vidscope --help | grep cookies
# Expected: "cookies" listed alongside add/show/list/.../mcp/watch

# 2. cookies --help shows 3 subcommands
vidscope cookies --help
# Expected: set, status, clear listed

# 3. Status with no cookies
vidscope cookies status
# Expected: rich table with "default path", "default exists: no", "cookies feature disabled"

# 4. Create a fake cookies.txt
cat > /tmp/test-cookies.txt <<EOF
# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	1893456000	sessionid	abc123
EOF

# 5. Set it
vidscope cookies set /tmp/test-cookies.txt
# Expected: ✓ copied 1 cookie rows to <data_dir>/cookies.txt

# 6. Status shows it
vidscope cookies status
# Expected: default exists: yes, format valid: yes (1 entries)

# 7. Clear it
vidscope cookies clear --yes
# Expected: ✓ removed <data_dir>/cookies.txt

# 8. Status confirms it's gone
vidscope cookies status
# Expected: default exists: no
```

### Quality gates

- [x] ruff clean
- [x] mypy strict on 84 source files
- [x] pytest 598 passed (was 558 + 40 cookies tests)
- [x] lint-imports 9 contracts kept (including the tightened application-has-no-adapters)
- [x] All tests use sandboxed VIDSCOPE_DATA_DIR via tmp_path

