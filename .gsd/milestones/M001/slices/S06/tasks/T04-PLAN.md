---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T04: CLI smoke verification: add → status → list → show → search end-to-end

Run a manual end-to-end demo that the CLI can be used as a real tool: vidscope add <url>, vidscope status (5 runs), vidscope list (1 row), vidscope show <id> (full record), vidscope search <keyword> (hits). Capture the output and verify each command produces the expected shape. No new test code — this is a manual smoke that proves the CLI actually works for an end user. Document the commands in a docs/quickstart.md file for users.

## Inputs

- None specified.

## Expected Output

- ``docs/quickstart.md``

## Verification

test -f docs/quickstart.md
