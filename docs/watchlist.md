# VidScope Watchlist

The watchlist lets you track public accounts on YouTube, TikTok, and
Instagram and ingest their newest videos on demand. Where `vidscope
add <url>` handles a single video, `vidscope watch` handles the
ongoing tracking layer on top: declare accounts, refresh on a
schedule, batch-process anything new.

## Concepts

A **watched account** is a `(platform, handle)` pair that points at a
public channel/profile URL. The same handle can exist on multiple
platforms (e.g. `@tiktok` is both a TikTok handle and a YouTube
channel handle), so the database enforces a compound `UNIQUE(platform,
handle)` instead of `UNIQUE(handle)`.

A **watchlist refresh** iterates every watched account, calls
`yt-dlp`'s flat-extract listing endpoint to fetch the most recent N
videos for each, dedupes against videos already in the library, and
runs the new ones through the same 5-stage pipeline as a manual
`vidscope add`. The result is persisted as a `watch_refreshes` row
containing totals and any per-account errors.

Refresh is **idempotent by design**: running it twice in a row
ingests new videos on the first call and zero on the second. The
deduplication happens against the in-memory snapshot of existing
`platform_id` values, so a refresh of a 100-account watchlist with
zero new videos does no work beyond the cheap listing calls.

Per-account errors are **captured and recorded but never block the
iteration**. A broken account (rate-limited, deleted, requires login)
appears in the refresh summary's `errors` list and the database
`watch_refreshes.errors` JSON column, but the rest of the watchlist
keeps running.

## Commands

### `vidscope watch add <url>`

Register a public account for tracking.

```bash
$ vidscope watch add https://www.youtube.com/@YouTube
added youtube/@YouTube

$ vidscope watch add https://www.tiktok.com/@tiktok
added tiktok/@tiktok

$ vidscope watch add https://www.instagram.com/@instagram
added instagram/@instagram
```

The handle is derived from the URL — for `/@<name>` URLs the handle
is `@<name>`; for legacy `/channel/UC...` URLs the handle is the
channel id segment.

### `vidscope watch list`

Show every watched account with its last-refreshed timestamp.

```bash
$ vidscope watch list
watched accounts: 3
                          Watchlist (3)
┌────┬──────────┬──────────────┬───────────────────────────────┬──────────────────┐
│ id │ platform │ handle       │ url                           │ last checked     │
├────┼──────────┼──────────────┼───────────────────────────────┼──────────────────┤
│  1 │ youtube  │ @YouTube     │ https://www.youtube.com/@...  │ 2026-04-07 12:00 │
│  2 │ tiktok   │ @tiktok      │ https://www.tiktok.com/@...   │ 2026-04-07 12:00 │
│  3 │ instagr… │ @instagram   │ https://www.instagram.com/... │ -                │
└────┴──────────┴──────────────┴───────────────────────────────┴──────────────────┘
```

`-` in the `last checked` column means the account has been added
but no refresh has touched it yet.

### `vidscope watch remove <handle> [--platform PLATFORM]`

Remove an account from the watchlist.

```bash
$ vidscope watch remove @YouTube
removed youtube/@YouTube
```

If the same handle exists on multiple platforms (compound UNIQUE
allows this), the command fails with a clear "specify --platform"
message:

```bash
$ vidscope watch remove @shared
error: handle '@shared' matches 2 accounts (youtube, tiktok); specify --platform

$ vidscope watch remove @shared --platform tiktok
removed tiktok/@shared
```

### `vidscope watch refresh [-n LIMIT]`

Fetch new videos for every watched account. The `--limit` flag
controls how many recent videos per account to inspect (default 10).

```bash
$ vidscope watch refresh
watchlist refresh: checked 3 accounts, ingested 5 new videos
                          Per-account results
┌──────────┬──────────────┬─────┬───────────────────────────────────┐
│ platform │ handle       │ new │ error                             │
├──────────┼──────────────┼─────┼───────────────────────────────────┤
│ youtube  │ @YouTube     │   2 │                                   │
│ tiktok   │ @tiktok      │   3 │                                   │
│ instagr… │ @instagram   │   0 │ login required                    │
└──────────┴──────────────┴─────┴───────────────────────────────────┘
warnings: 1 error(s) during refresh
  • instagram/@instagram: login required
```

Each new video flows through the same 5-stage pipeline as
`vidscope add`: ingest → transcribe → frames → analyze → index. The
new videos appear immediately in `vidscope list` and `vidscope search`.

A second `vidscope watch refresh` right after returns 0 new videos —
the dedupe set already knows about everything that just landed.

## Scheduling

VidScope deliberately does not run a daemon. Use your operating
system's scheduler to invoke `vidscope watch refresh` on a cadence:

**Linux/macOS — cron:**

```cron
# Refresh the watchlist every hour
0 * * * * cd /path/to/vidscope && python -m uv run vidscope watch refresh >> ~/.local/state/vidscope/refresh.log 2>&1
```

**macOS — launchd:** create a `~/Library/LaunchAgents/com.user.vidscope.refresh.plist`
that runs `vidscope watch refresh` on `StartInterval=3600`.

**Windows — Task Scheduler:** create a Daily/Hourly task that runs
`vidscope.exe watch refresh` from the project directory.

The watchlist refresh is short-lived (no persistent state, no
background daemon, single SQLite connection) so it composes cleanly
with any external scheduler. The `watch_refreshes` table is the
audit log — query it to see history.

## Cookies

If a watched account requires authentication (Instagram is the most
common case), set the `VIDSCOPE_COOKIES_FILE` environment variable to
a Netscape-format cookies.txt file. See [docs/cookies.md](cookies.md)
for the export instructions. The same cookies file is used by both
`vidscope add` and the watchlist refresh.

## Database

Two tables back the watchlist:

**`watched_accounts`**

| column            | type      | notes                                       |
| ----------------- | --------- | ------------------------------------------- |
| `id`              | INTEGER   | primary key                                 |
| `platform`        | TEXT      | youtube/tiktok/instagram                    |
| `handle`          | TEXT      | e.g. `@YouTube`                             |
| `url`             | TEXT      | original channel URL                        |
| `created_at`      | DATETIME  | when added                                  |
| `last_checked_at` | DATETIME  | when last refresh saw it (NULL until first) |

`UNIQUE(platform, handle)` — different platforms may share the same
handle.

**`watch_refreshes`**

| column                 | type     | notes                                  |
| ---------------------- | -------- | -------------------------------------- |
| `id`                   | INTEGER  | primary key                            |
| `started_at`           | DATETIME | refresh start                          |
| `finished_at`          | DATETIME | refresh end                            |
| `accounts_checked`     | INTEGER  | how many accounts iterated             |
| `new_videos_ingested`  | INTEGER  | net new videos                         |
| `errors`               | JSON     | list of `"platform/handle: message"`  |

Both tables are created on first use by `vidscope`'s startup —
no migration needed.
