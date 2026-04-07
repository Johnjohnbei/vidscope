# S02: Cookies probe + typed CookieAuthError + better error remediation — UAT

**Milestone:** M005
**Written:** 2026-04-07T19:01:17.837Z

## UAT — M005/S02: Cookies probe + CookieAuthError + remediation

### Manual smoke test (no real network, no real cookies)

```bash
# 1. cookies --help shows the new test subcommand
vidscope cookies --help
# Expected: set, status, test, clear listed

# 2. cookies test --help shows the --url option
vidscope cookies test --help
# Expected: --url / -u option documented with default to Instagram

# 3. Run a real probe (requires real network)
vidscope cookies test --url https://www.youtube.com/shorts/<some-public-short>
# Expected (no cookies): status=ok, "no cookies needed", exit 0

# 4. Try without cookies against Instagram
vidscope cookies test
# Expected: status=auth_required, "none are configured", exit 1
#   (because Instagram requires cookies and none are set)
```

### Verify the typed error path (no real network)

```bash
python -m uv run python -c "
from vidscope.adapters.ytdlp.downloader import _translate_download_error
from yt_dlp.utils import DownloadError
from vidscope.domain import CookieAuthError

err = _translate_download_error(
    DownloadError('ERROR: login required to view this content'),
    'https://www.instagram.com/reel/abc/',
)
assert isinstance(err, CookieAuthError)
assert 'vidscope cookies test' in str(err)
print('OK')
"
# Expected: OK
```

### Quality gates

- [x] ruff clean
- [x] mypy strict on 84 source files
- [x] pytest 618 passed (was 598 + 20 new probe/error tests)
- [x] lint-imports 9 contracts kept
- [x] No real network calls in unit tests (all via monkeypatched yt_dlp.YoutubeDL)

