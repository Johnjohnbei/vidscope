# Cookie-based authentication

VidScope can ingest videos that require a logged-in session by reusing
your browser's cookies. This is **required** for Instagram public Reels
(Meta started requiring authentication for public content in 2026-04)
and **optional** for age-gated YouTube videos.

## 5-minute setup

1. **Export `cookies.txt` from your browser** (instructions per browser below)
2. **Install it** with `vidscope cookies set <path>`
3. **Verify** with `vidscope cookies test`
4. **Ingest** with `vidscope add "https://www.instagram.com/reel/<id>/"`

That's it. No environment variables to manage, no paths to remember.

## Step 1 — Export cookies from your browser

You need a Netscape-format `cookies.txt` file. The recommended browser
extensions:

### Firefox

1. Install **cookies.txt** by Lennon Hill
   <https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/>
2. Log in to instagram.com (or whichever site you need)
3. While on that site, click the cookies.txt extension icon
4. Click **Export** and save the file

### Chrome / Edge / Brave

1. Install **Get cookies.txt LOCALLY**
   <https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc>
2. Log in to instagram.com
3. Click the extension icon
4. Click **Export** and save the file

The exported file should start with this header line:

```
# Netscape HTTP Cookie File
```

If it doesn't, the format is wrong — make sure you picked **Netscape
format**, not JSON.

### Multi-site cookies in one file

Most browser extensions export cookies for **every** site you're logged
into when you click Export. yt-dlp reads them all happily, so you can
use a single `cookies.txt` for Instagram, YouTube, and TikTok at once.
No need to maintain separate files unless you want to.

## Step 2 — Install with `vidscope cookies set`

```bash
vidscope cookies set ~/Downloads/cookies.txt
```

This validates the file as Netscape format and copies it to VidScope's
canonical location (`<vidscope-data-dir>/cookies.txt`). The original
file is left untouched. If a cookies file already exists at the
destination, it's overwritten — but only if the new source is valid.
A broken new file never overwrites a working existing one.

The output looks like:

```
✓ copied 23 cookie rows to /home/you/.local/share/vidscope/cookies.txt
```

## Step 3 — Verify with `vidscope cookies test`

This is the killer command. It does a metadata-only call against a
public Instagram Reel (no media download, no transcribe, no DB write)
and reports whether your cookies authenticate successfully.

```bash
vidscope cookies test
```

Possible outcomes:

| Status | Meaning | What to do |
|---|---|---|
| `ok` (cookies work) | Cookies are valid | Ingest away |
| `ok` (no cookies needed) | The default URL didn't need auth | Try another URL with `--url` |
| `auth_required` (none configured) | No cookies installed yet | Run `vidscope cookies set <path>` |
| `auth_required` (cookies expired) | Cookies installed but session invalid | Re-export from browser, run `vidscope cookies set` |
| `not_found` | URL is dead | Default probe URL has rotted; use `--url <other>` |
| `network_error` | Connectivity issue | Check internet |
| `unsupported` | yt-dlp doesn't recognize the URL | Check the URL format |

You can probe any URL, not just the default:

```bash
vidscope cookies test --url https://www.instagram.com/reel/<id>/
vidscope cookies test --url https://www.youtube.com/shorts/<id>
```

The exit code is `0` on `ok` and `1` on every other status, so you can
script around it.

## Step 4 — Ingest

```bash
vidscope add "https://www.instagram.com/reel/<id>/"
```

If `vidscope cookies test` showed `ok`, this should work. If it fails
with a `cookies missing or expired` error, run `vidscope cookies test`
again — your session may have expired between the test and the ingest
(Instagram sessions are short-lived).

## Other `vidscope cookies` commands

### `vidscope cookies status`

Shows the current state of the cookies file:

```
              vidscope cookies status               
+--------------------------------------------------+
| field          | value                           |
|----------------+---------------------------------|
| default path   | ~/.local/share/vidscope/...    |
| default exists | yes                             |
| size           | 4231 bytes                      |
| last modified  | 2026-04-07 10:23:45 +0200       |
| format valid   | yes (23 entries)                |
| active path    | ~/.local/share/vidscope/...    |
+--------------------------------------------------+
```

When `VIDSCOPE_COOKIES_FILE` is set to a different path, the status
table also shows an "env override" row.

### `vidscope cookies clear`

Removes the canonical cookies file. Prompts by default; use `--yes` /
`-y` to skip the prompt:

```bash
vidscope cookies clear --yes
```

This only ever touches `<vidscope-data-dir>/cookies.txt`. A file
pointed to by `VIDSCOPE_COOKIES_FILE` is owned by you and is never
touched by this command.

## Advanced: `VIDSCOPE_COOKIES_FILE` environment variable

If you maintain your own cookies file (e.g. shared between vidscope and
a separate yt-dlp invocation), set `VIDSCOPE_COOKIES_FILE` to its path:

```bash
export VIDSCOPE_COOKIES_FILE=/path/to/your/cookies.txt
```

The env var **overrides** `<vidscope-data-dir>/cookies.txt`. When
overridden:

- `vidscope cookies status` shows the env override path explicitly
- `vidscope cookies set` warns that yt-dlp will ignore the canonical
  installation in favor of the env var
- `vidscope cookies clear` only touches the canonical path, never the
  env-override file

This is the escape hatch for advanced users. **Most people should use
`vidscope cookies set` instead.**

### Where is `<vidscope-data-dir>`?

| OS | Default location |
|---|---|
| **Windows** | `%LOCALAPPDATA%\vidscope\cookies.txt` |
| **macOS** | `~/Library/Application Support/vidscope/cookies.txt` |
| **Linux** | `~/.local/share/vidscope/cookies.txt` |

You can override this by setting `VIDSCOPE_DATA_DIR` to any absolute
path. To find the resolved path on your machine, run
`vidscope cookies status`.

## Troubleshooting

### "cookies missing or expired" during `vidscope add`

The download stage detected an authentication failure and raised a
`CookieAuthError`. Two possible causes:

1. **You haven't installed cookies yet.** Run `vidscope cookies set <path>`.
2. **Your cookies expired.** Re-export from a fresh logged-in browser
   session and run `vidscope cookies set <path>` again.

The error message includes the URL — pass it to `vidscope cookies test
--url <url>` for a faster confirmation than re-running the full ingest.

### `vidscope cookies test` says `auth_required` but I just exported fresh cookies

Make sure you're logged in **in the same browser** you exported from.
Some extensions silently export old cookies if the active tab isn't on
the target site. The fix:

1. Open instagram.com in a fresh tab
2. Confirm you see your feed (not the login screen)
3. Click the cookies.txt extension icon **while on that tab**
4. Export and re-run `vidscope cookies set`

### `vidscope cookies test` says `not_found` for the default URL

The default probe URL is a hard-coded Instagram Reel that may rot over
time. Use `--url` with any current public Reel:

```bash
vidscope cookies test --url https://www.instagram.com/reel/<your-url>/
```

### "rate limit" / 429 errors

yt-dlp doesn't throttle on its own. Wait a few minutes between
requests, or use a different network. If you're scraping a watchlist
on a schedule, space out the cron entries.

### Cookies work in `vidscope cookies test` but `vidscope add` still fails

The session likely expired between the two commands. Instagram
sessions can be very short. Re-run `vidscope cookies test` immediately
before `vidscope add`, or set up a script that does both back-to-back.

## Security

**Treat your `cookies.txt` file as a credential.** Anyone with access
to it can act as you on the sites whose cookies it contains.

- **Never commit it to git.** VidScope's `.gitignore` covers `cookies.txt`
  and `*.cookies` at the repo root.
- **Don't share it.** Passing the file is functionally equivalent to
  giving someone a logged-in browser tab.
- **Rotate it** by logging out of the site (which invalidates the
  session), then re-exporting fresh cookies.
- **Restrict file permissions** on Linux/macOS:
  ```bash
  chmod 600 /path/to/cookies.txt
  ```
- **Don't store it in a synced cloud folder** (Dropbox, OneDrive,
  iCloud Drive) unless you're comfortable with the cloud provider
  having access to your session tokens.

VidScope's cookies file is created with default OS permissions when
copied via `vidscope cookies set`. The CLI never logs the file
contents.

## Platform support matrix

| Platform | Without cookies | With cookies |
|---|---|---|
| **Instagram** Reels (public) | ❌ Requires auth as of 2026-04 | ✅ Works |
| **TikTok** videos (public) | ✅ Works | ✅ Works |
| **YouTube** Shorts (public) | ✅ Works | ✅ Works |
| **YouTube** age-gated | ❌ | ✅ Works |

## Architecture notes

For curious users / contributors:

- The Netscape format validator (`vidscope.application.cookies_validator`)
  is permissive: header line is optional, comments and blank lines are
  skipped, data rows must have exactly 7 tab-separated columns with
  non-empty domain. It never tries to interpret cookie *contents*.
- Cookies file resolution lives in `vidscope.infrastructure.config` with
  three-step priority: env var → canonical path → none. Documented in
  the Config docstring.
- The `Downloader.probe()` port method (M005/S02) is what backs
  `vidscope cookies test`. It performs a metadata-only `extract_info`
  call with `download=False` and never raises — every failure is
  encoded in the returned `ProbeResult.status`.
- `CookieAuthError` is a typed subclass of `IngestError` raised by the
  ytdlp adapter when yt-dlp's error message matches one of 10 known
  authentication-failure substrings. The CLI catches it and shows the
  remediation pointing at `vidscope cookies test`.
- Adding a new authentication-failure marker is a one-line change in
  `_COOKIE_AUTH_MARKERS` in `src/vidscope/adapters/ytdlp/downloader.py`.
