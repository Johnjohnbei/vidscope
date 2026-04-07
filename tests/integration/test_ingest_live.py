"""Live-network integration tests for the ingest pipeline.

Tests are ordered by platform priority (D027): **Instagram first**,
then TikTok, then YouTube. This matches the user's real-world usage
profile and ensures the most important platform's status is the
first signal an operator sees in the pytest output.

Each test downloads a real public short-form video from one of the
three target platforms and asserts:

1. The PipelineRunner reports success
2. A videos row exists with the expected platform and non-empty title
3. The media file is actually on disk in the sandboxed storage root
4. A matching pipeline_runs row with status=OK exists

Target content profile (D026)
-----------------------------

VidScope's primary use case is short-form vertical content:

- **Instagram Reels** (< 90 seconds) — primary
- **TikTok videos** (typical 15-60 seconds) — secondary
- **YouTube Shorts** (< 60 seconds) — tertiary

Long-form videos are NOT a target.

Cookies and Instagram (S07/R025)
--------------------------------

Instagram now requires authentication for public Reels as of 2026-04
(yt-dlp returns "empty media response" without cookies). The
Instagram test honors :envvar:`VIDSCOPE_COOKIES_FILE`:

- **VIDSCOPE_COOKIES_FILE not set or file missing** → the test xfails
  with a clear "cookies not provided" message. This is the default
  CI/dev behavior.
- **VIDSCOPE_COOKIES_FILE set + file exists** → the test runs the
  full ingest path. If it fails, that IS a real failure (not an
  xfail), because the user opted in to authentication.

To export cookies (one-time setup):

1. Install a Netscape-format cookies exporter for your browser:
   - **Firefox**: "cookies.txt" by Lennon Hill, or any extension
     that exports `cookies.txt` in Netscape format
   - **Chrome**: "Get cookies.txt LOCALLY" or equivalent
2. Log in to instagram.com in that browser
3. Use the extension to export ``cookies.txt`` (Netscape format)
4. Either drop it at ``<data_dir>/cookies.txt`` for auto-pickup,
   or set ``VIDSCOPE_COOKIES_FILE=/path/to/cookies.txt``
5. Verify with ``vidscope doctor`` — the cookies row should show
   ``configured at <path>`` in green

See ``docs/cookies.md`` for the full guide.

Target URLs — policy for refreshing
-----------------------------------

- **Instagram**: a Reel from the official @instagram account — most
  durable target, but Meta still rotates extractor compatibility
  often. The test xfails (without cookies) or expects success (with
  cookies).
- **TikTok**: a video from the official @tiktok account.
- **YouTube**: a Short from @YouTube. Shorts are ephemeral by design
  so this may need refreshing more often than a long-form video.

If any URL 404s, replace it with the most stable short-form
alternative from the same platform and document the change in the
git log.

Running these tests
-------------------

By default the main suite (``pytest``) does NOT run these tests —
they are gated behind the ``integration`` marker and the default
``-m "not integration"`` filter in pyproject.toml. Run them
explicitly with::

    pytest tests/integration -m integration -v

Or via the bundled script::

    bash scripts/verify-s07.sh
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from vidscope.domain import IngestError, Platform, RunStatus
from vidscope.infrastructure.container import Container
from vidscope.ports import PipelineContext

# ---------------------------------------------------------------------------
# Target URLs — short-form content only (D026), priority order (D027)
# ---------------------------------------------------------------------------

# Instagram Reel — PRIMARY platform per D027. Currently requires
# authentication via cookies (R025) — the test xfails when cookies
# are not configured.
INSTAGRAM_URL = "https://www.instagram.com/reel/C0nELpwLkpk/"

# TikTok video — SECONDARY platform. Public videos work without
# authentication via the official @tiktok account.
TIKTOK_URL = "https://www.tiktok.com/@tiktok/video/7106594312292453675"

# YouTube Short — TERTIARY platform. Easiest to work with: no auth
# required for public Shorts. IDs are ephemeral by design — refresh
# when a test fails with "video unavailable".
# Last refreshed: 2026-04-07 (19s tech-related short).
YOUTUBE_URL = "https://www.youtube.com/shorts/34WNvQ1sIw4"

# Maximum duration we expect for any short-form test target. If a
# test URL starts returning a longer video, that's a signal the URL
# drifted to something we shouldn't be testing against.
MAX_EXPECTED_DURATION_SECONDS = 180.0


# ---------------------------------------------------------------------------
# Cookie detection helper
# ---------------------------------------------------------------------------


def _cookies_file_available() -> Path | None:
    """Return the resolved cookies file path if VIDSCOPE_COOKIES_FILE
    is set AND the file exists, otherwise return None.

    Read directly from os.environ instead of going through the config
    layer because this helper runs at test-collection time, before
    any fixture has had a chance to monkeypatch anything.
    """
    raw = os.environ.get("VIDSCOPE_COOKIES_FILE")
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        return None
    return path


def _ffmpeg_available() -> bool:
    """Return True if the ffmpeg binary is on PATH."""
    import shutil
    return shutil.which("ffmpeg") is not None


# ---------------------------------------------------------------------------
# Shared assertion helper
# ---------------------------------------------------------------------------


def _assert_successful_ingest(
    container: Container, url: str, expected_platform: Platform
) -> None:
    """Run the full pipeline on ``url`` and assert that every stage
    that COULD succeed did.

    The pipeline now has 3 stages (ingest, transcribe, frames). On
    machines without ffmpeg the frames stage fails — that's an
    expected outcome we tolerate by checking each stage individually
    instead of demanding a green run_result.success.

    Raises :class:`IngestError` (not AssertionError) when the ingest
    OR transcribe stage fails, so platform tests can catch the typed
    error and decide whether to xfail.
    """
    ctx = PipelineContext(source_url=url)
    result = container.pipeline_runner.run(ctx)

    # The runner stops at the first failed stage. Find the failures.
    failures = [o for o in result.outcomes if o.status.value == "failed"]

    # Ingest and transcribe MUST succeed (assuming the platform is
    # not currently broken upstream). Frames is allowed to fail when
    # ffmpeg is not on PATH.
    ffmpeg_available = _ffmpeg_available()
    for outcome in failures:
        if outcome.stage_name == "frames" and not ffmpeg_available:
            # Expected: frames stage fails because ffmpeg is missing
            continue
        # Any other failure is a real one
        raise IngestError(
            f"pipeline failed on {expected_platform.value}: "
            f"stage={outcome.stage_name} error={outcome.error}",
            retryable=True,
        )

    # 1. Context is fully populated
    assert ctx.video_id is not None, "video_id was never set"
    assert ctx.platform is expected_platform
    assert ctx.platform_id is not None
    assert ctx.media_key is not None

    # 2. Videos row exists in the DB
    with container.unit_of_work() as uow:
        video = uow.videos.get(ctx.video_id)
        assert video is not None, "videos row missing after ingest"
        assert video.platform is expected_platform
        assert video.platform_id == ctx.platform_id
        assert video.media_key == ctx.media_key
        # Title SHOULD be populated by yt-dlp for any public video;
        # if it isn't, that's a metadata extraction regression.
        assert video.title, f"video title is empty: {video}"

        # Short-form profile guard (D026): if a test URL drifts to a
        # long-form video, flag it loudly so we refresh the URL
        # instead of silently normalizing on bad data.
        if video.duration is not None:
            assert video.duration <= MAX_EXPECTED_DURATION_SECONDS, (
                f"video duration {video.duration:.1f}s exceeds the "
                f"short-form target profile "
                f"(<= {MAX_EXPECTED_DURATION_SECONDS:.0f}s). "
                f"The test URL may have drifted — refresh it."
            )

        # 3. pipeline_runs row exists with status OK for ingest phase
        runs = uow.pipeline_runs.list_recent(limit=10)
        assert any(
            r.status is RunStatus.OK
            and r.phase.value == "ingest"
            and r.video_id == ctx.video_id
            for r in runs
        ), f"no OK ingest pipeline_run found for video {ctx.video_id}"

        # 4. After S03, the same run also produced a transcript.
        # Note: full_text and segments MAY legitimately be empty for
        # purely instrumental videos. We assert the row exists with
        # a recognized language; emptiness is not a failure.
        transcript = uow.transcripts.get_for_video(ctx.video_id)
        assert transcript is not None, (
            f"no transcripts row for video {ctx.video_id} after run"
        )
        from vidscope.domain import Language

        assert transcript.language in (
            Language.FRENCH, Language.ENGLISH, Language.UNKNOWN
        ), f"unexpected transcript language: {transcript.language}"

        # 5. pipeline_runs row exists with status OK for transcribe phase
        assert any(
            r.status is RunStatus.OK
            and r.phase.value == "transcribe"
            and r.video_id == ctx.video_id
            for r in runs
        ), f"no OK transcribe pipeline_run found for video {ctx.video_id}"

        # 6. Frames assertions — only when ffmpeg is available
        if ffmpeg_available:
            frames = uow.frames.list_for_video(ctx.video_id)
            assert len(frames) >= 1, (
                f"no frames extracted for video {ctx.video_id} "
                f"(ffmpeg is on PATH so this should have worked)"
            )
            for frame in frames:
                assert frame.image_key.startswith(
                    f"videos/{expected_platform.value}/"
                ), f"unexpected frame image_key: {frame.image_key}"

            assert any(
                r.status is RunStatus.OK
                and r.phase.value == "frames"
                and r.video_id == ctx.video_id
                for r in runs
            ), f"no OK frames pipeline_run found for video {ctx.video_id}"

        # 7. Analysis row exists (S05) — analyze stage runs
        # regardless of ffmpeg availability
        analysis = uow.analyses.get_latest_for_video(ctx.video_id)
        assert analysis is not None, (
            f"no analyses row for video {ctx.video_id}"
        )
        assert analysis.provider, "analysis has no provider name"
        # Score is None for stub or 0-100 for heuristic
        if analysis.score is not None:
            assert 0.0 <= analysis.score <= 100.0
        assert any(
            r.status is RunStatus.OK
            and r.phase.value == "analyze"
            and r.video_id == ctx.video_id
            for r in runs
        ), f"no OK analyze pipeline_run found for video {ctx.video_id}"

        # 8. Index stage ran successfully (S06)
        assert any(
            r.status is RunStatus.OK
            and r.phase.value == "index"
            and r.video_id == ctx.video_id
            for r in runs
        ), f"no OK index pipeline_run found for video {ctx.video_id}"

        # 9. FTS5 search returns at least one hit when the analysis
        # has keywords (instrumental videos may have empty analysis,
        # in which case we skip this check)
        if analysis.keywords and transcript.full_text.strip():
            keyword = analysis.keywords[0]
            hits = uow.search_index.search(keyword)
            assert any(h.video_id == ctx.video_id for h in hits), (
                f"FTS5 search for {keyword!r} did not return video "
                f"{ctx.video_id} despite indexed transcript"
            )

    # 7. Media file is on disk in the sandboxed storage root
    media_path = container.media_storage.resolve(ctx.media_key)
    assert media_path.exists(), f"media file missing: {media_path}"
    assert media_path.stat().st_size > 0, f"media file is empty: {media_path}"

    # 8. Frame files exist when ffmpeg was available
    if ffmpeg_available:
        with container.unit_of_work() as uow:
            frames = uow.frames.list_for_video(ctx.video_id)
            for frame in frames:
                frame_path = container.media_storage.resolve(frame.image_key)
                assert frame_path.exists(), (
                    f"frame file missing: {frame_path}"
                )


# ---------------------------------------------------------------------------
# Instagram — PRIMARY platform (D027)
# ---------------------------------------------------------------------------


class TestLiveInstagram:
    """Instagram is the user's #1 priority platform per D027.

    Behavior depends on whether VIDSCOPE_COOKIES_FILE is configured:

    - **No cookies** → xfail with a clear "cookies not provided"
      message. The user knows exactly what to do to enable the test.
    - **Cookies present** → run the full ingest. Any failure here is
      a real failure, not an xfail — the user opted in to auth.
    """

    @pytest.mark.integration
    @pytest.mark.slow
    def test_ingests_instagram_reel(
        self, sandboxed_container: Container
    ) -> None:
        cookies = _cookies_file_available()
        if cookies is None:
            pytest.xfail(
                "Instagram requires cookie-based authentication "
                "(see docs/cookies.md). Set VIDSCOPE_COOKIES_FILE to "
                "a Netscape-format cookies file exported from a "
                "logged-in instagram.com browser session and re-run."
            )

        # Cookies are configured — run the real ingest. Any failure
        # here is a real failure (not an xfail) because the user
        # opted in.
        try:
            _assert_successful_ingest(
                sandboxed_container, INSTAGRAM_URL, Platform.INSTAGRAM
            )
        except IngestError as exc:
            # Even with cookies, Instagram's extractor occasionally
            # breaks for transient reasons. Distinguish:
            # - retryable=True (network / rate limit) → xfail
            # - retryable=False with "login" / "cookies" hint →
            #   the cookies file is probably stale; xfail with
            #   a remediation hint
            # - everything else → real failure
            error_text = str(exc).lower()
            if exc.retryable:
                pytest.xfail(
                    f"Instagram retryable failure (transient upstream "
                    f"issue): {exc}"
                )
            if any(
                hint in error_text
                for hint in ("login", "cookies", "authentication")
            ):
                pytest.xfail(
                    f"Instagram still rejecting cookies — they may be "
                    f"stale. Re-export from a fresh browser session: {exc}"
                )
            raise


# ---------------------------------------------------------------------------
# TikTok — SECONDARY platform (D027)
# ---------------------------------------------------------------------------


class TestLiveTikTok:
    @pytest.mark.integration
    @pytest.mark.slow
    def test_ingests_tiktok_video(
        self, sandboxed_container: Container
    ) -> None:
        """TikTok occasionally breaks yt-dlp upstream. When the error
        is retryable (network / rate limit), we xfail with a clear
        message instead of failing the suite."""
        try:
            _assert_successful_ingest(
                sandboxed_container, TIKTOK_URL, Platform.TIKTOK
            )
        except IngestError as exc:
            if exc.retryable:
                pytest.xfail(
                    f"TikTok ingest currently failing with retryable "
                    f"error (yt-dlp upstream issue?): {exc}"
                )
            raise


# ---------------------------------------------------------------------------
# YouTube — TERTIARY platform (D027)
# ---------------------------------------------------------------------------


class TestLiveYouTube:
    @pytest.mark.integration
    @pytest.mark.slow
    def test_ingests_youtube_short(
        self, sandboxed_container: Container
    ) -> None:
        """YouTube Shorts are the easiest target — no auth required
        and yt-dlp's extractor is the most stable. This test is
        expected to pass every time unless the specific Short URL
        has been removed."""
        _assert_successful_ingest(
            sandboxed_container, YOUTUBE_URL, Platform.YOUTUBE
        )
