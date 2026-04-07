---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T06: Documentation: docs/cookies.md

Create docs/cookies.md with concrete instructions to export cookies from Firefox and Chrome, where to place the cookies.txt file (default: <data_dir>/cookies.txt), how to verify the configuration with `vidscope doctor`, and a note on which platforms benefit (Instagram is the primary use case per D027, also useful for age-gated YouTube and private TikTok). Include the Firefox add-on name (cookies.txt LOCAL or similar) and the Chrome equivalent. Document the security note: cookies grant the same access as a logged-in browser session, so the file should be treated as a credential and never committed to git. Ensure cookies.txt patterns are in .gitignore (verify and add if needed).

## Inputs

- `.gitignore`

## Expected Output

- ``docs/cookies.md` — user-facing cookies setup guide`
- ``.gitignore` — cookies.txt and *.cookies patterns confirmed present`

## Verification

test -f docs/cookies.md && grep -q 'cookies.txt' .gitignore
