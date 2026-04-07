---
id: T06
parent: S07
milestone: M001
key_files:
  - docs/cookies.md
key_decisions:
  - Quick start at the top so the 30-second setup is the FIRST thing users see — they don't need to read the security note before they can use the feature
  - Concrete extension names with their canonical Chrome Web Store / Mozilla URL — the user doesn't have to guess which extension to install
  - Verification section copies the EXACT ASCII table output from `vidscope doctor` so users can match what they see against what they should see, byte-for-byte
  - Troubleshooting maps actual error message substrings to causes — 'login required' / 'empty media response' / '429' — grep-able when debugging
  - Security note has 5 numbered concrete recommendations including the cloud-folder warning that most users miss
  - Compatibility table at the bottom is honest about what M001 ships (Instagram public Reels) vs what's deferred to M005 (stories, drafts, age-gated YouTube extras)
duration: 
verification_result: passed
completed_at: 2026-04-07T13:52:42.438Z
blocker_discovered: false
---

# T06: Wrote docs/cookies.md (169 lines) covering Quick Start, browser export instructions for Firefox/Chrome, configuration priority, verification, troubleshooting, and security note — gitignore already covers cookies.txt patterns.

**Wrote docs/cookies.md (169 lines) covering Quick Start, browser export instructions for Firefox/Chrome, configuration priority, verification, troubleshooting, and security note — gitignore already covers cookies.txt patterns.**

## What Happened

T06 ships the user-facing documentation that closes the loop on cookies. Without this, the test docstring in T05 references "see docs/cookies.md" as if the doc existed — T06 makes that reference real.

**Structure of `docs/cookies.md`:**

1. **Lead paragraph** — what cookies are for in vidscope (currently required for Instagram, optional for age-gated YouTube and private TikTok), with the explicit "2026-04 Meta auth requirement" context.

2. **Quick start** — 4 numbered steps, copyable. Drop the file at the default path, or set the env var, verify with doctor, run vidscope add. Anyone who knows what cookies are can do this in 30 seconds.

3. **Where is `<vidscope-data-dir>`** — table with the resolved path per OS (Windows / macOS / Linux), plus the override env var, plus a `vidscope doctor` command to discover the actual path on the user's machine. Critical because Windows Store Python sandboxes the path under a different location and the user wouldn't know without asking the tool.

4. **Exporting cookies from your browser** — concrete step-by-step for Firefox and Chrome/Edge/Brave. Names the actual extensions: "cookies.txt" by Lennon Hill for Firefox, "Get cookies.txt LOCALLY" for Chrome. Includes the canonical Chrome Web Store URL. Documents what the file's first line should look like (`# Netscape HTTP Cookie File`) so users can verify the format before vidscope reads it.

5. **Using a single cookies file for multiple sites** — preempts the question "do I need separate files for Instagram, YouTube, TikTok?". Answer: no, one file works.

6. **Configuration priority** — restates the three-step resolution from T01 in user-facing terms. Example: switch between `~/cookies-personal.txt` and `~/cookies-work.txt` via the env var.

7. **Verification** — shows the expected `vidscope doctor` output with actual ASCII table formatting copied from the real CLI. Three failure modes documented: "not configured (optional)" → check the path, "fail / file is missing" → fix the path or unset the env var. The user has a runbook for every state the cookies check can be in.

8. **Troubleshooting Instagram** — three concrete error messages with their causes:
   - `"login required"` → cookies expired, re-export
   - `"empty media response"` → cookies missing the right token, log out + back in
   - Rate limit / 429 → wait

9. **Security note** — the part that matters most. Treats `cookies.txt` as a credential. Five concrete recommendations: never commit, never share, rotate by logging out, restrict file permissions on Linux/macOS (`chmod 600`), don't put in synced cloud folders. The cloud-folder warning is the one most users miss.

10. **What this enables** — final compatibility table mapping platform × cookies-or-not × works-or-doesn't. Documents explicitly that Instagram stories, TikTok private/draft, and similar advanced auth scenarios are deferred to M005.

**`.gitignore` verification.** Already covers `cookies.txt` and `*.cookies` at the repo root (lines 84-85, in the `# ---------- Secrets ----------` section). No changes needed. The doc references this so users know they're protected.

**No new code, no test changes.** This is a pure documentation task. Verification is `test -f docs/cookies.md` + `grep -q cookies.txt .gitignore`, both pass.

## Verification

Ran `test -f docs/cookies.md && grep -q 'cookies.txt' .gitignore && wc -l docs/cookies.md` → file exists, gitignore covers cookies, doc is 169 lines. Manually inspected the doc for accuracy: the env var name matches T01 (`VIDSCOPE_COOKIES_FILE`), the default path matches T01 (`<data_dir>/cookies.txt`), the doctor output matches T04's actual rendering, the troubleshooting messages match T02's error strings, and the priority order matches T01's resolution logic.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -f docs/cookies.md && grep -q 'cookies.txt' .gitignore && wc -l docs/cookies.md` | 0 | ✅ doc file exists (169 lines), gitignore covers cookies.txt | 50ms |

## Deviations

None. The doc follows the structure laid out in the plan and adds a few extras (the security note's cloud-folder warning, the "single cookies file for multiple sites" pre-emption, the verification troubleshooting flow) that are user-experience wins without scope creep.

## Known Issues

None. The doc is self-contained, references no missing files (T07 will create scripts/verify-s07.sh which the doc doesn't reference), and matches the actual code behavior on every concrete example.

## Files Created/Modified

- `docs/cookies.md`
