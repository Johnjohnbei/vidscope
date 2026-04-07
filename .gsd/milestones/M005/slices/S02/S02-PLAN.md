# S02: Cookies probe + typed CookieAuthError + better error remediation

**Goal:** Add the killer feature: vidscope cookies test does a probe download attempt (metadata-only via yt_dlp) against a default Instagram public Reel URL or a user-supplied URL. Detects auth failures, network errors, success. Adds CookieAuthError to the domain error hierarchy and wires the ytdlp adapter to raise it on auth-related yt_dlp exceptions so vidscope add error messages become actionable.
**Demo:** After this: vidscope cookies test reports cookies work/expired/missing without ingesting a video. vidscope add against Instagram with no cookies surfaces actionable error.

## Tasks
- [x] **T01: Shipped vidscope cookies test (probe) + CookieAuthError typed domain error + Downloader.probe port method + ytdlp adapter detection of cookie auth failures. 9 contracts kept, 618 unit tests, all 4 gates clean.** — 
