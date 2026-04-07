# S03: Docs rewrite + verify-m005.sh + R025 validation + milestone closure — UAT

**Milestone:** M005
**Written:** 2026-04-07T19:09:01.376Z

## UAT — M005/S03: Closure (docs + verify + R025 validated)

### Verify the closure signal

```bash
bash scripts/verify-m005.sh --skip-integration
# Expected: 10 steps, 0 failed, "M005 VERIFICATION PASSED"
```

### Verify docs

```bash
test -f docs/cookies.md && wc -l docs/cookies.md
# Expected: > 200 lines, file exists

# Verify it mentions all 4 subcommands
for cmd in set status test clear; do
    grep -q "vidscope cookies $cmd" docs/cookies.md && echo "$cmd: documented"
done
# Expected: 4 lines, all documented
```

### Verify R025 is validated

```bash
grep -A 2 "^### R025" .gsd/REQUIREMENTS.md | head -5
# Expected: status: validated
```

### Verify the cookies cycle works

```bash
# Create a sandbox + fake cookies file
export VIDSCOPE_DATA_DIR=/tmp/m005-uat
unset VIDSCOPE_COOKIES_FILE
mkdir -p $VIDSCOPE_DATA_DIR

cat > /tmp/m005-fake-cookies.txt <<EOF
# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	1893456000	sessionid	demo
EOF

vidscope cookies set /tmp/m005-fake-cookies.txt
vidscope cookies status
vidscope cookies clear --yes
vidscope cookies status
# Expected: set says "copied 1", status reports "1 entries", clear says "removed", final status reports "feature disabled"
```

### Quality gates

- [x] ruff clean
- [x] mypy strict on 84 source files
- [x] pytest 618 passed
- [x] lint-imports 9 contracts kept (with tightened application-has-no-adapters)
- [x] verify-m005.sh 10/10 steps green
- [x] No real network calls anywhere

