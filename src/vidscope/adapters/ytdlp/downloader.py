"""YtdlpDownloader — yt-dlp implementation of the Downloader port.

Wraps :class:`yt_dlp.YoutubeDL` behind the Downloader Protocol from
:mod:`vidscope.ports.pipeline`. Every yt-dlp exception is translated
into a typed :class:`~vidscope.domain.errors.IngestError` with the
original exception preserved in ``cause``.

Design notes
------------

- **Single place where yt-dlp is imported.** Every other layer in the
  codebase goes through the :class:`Downloader` Protocol. When yt-dlp
  breaks upstream — and it will, periodically, especially for
  Instagram — the blast radius is confined to this file.

- **Retryable classification.** Transient failures (network errors,
  rate limits, CDN hiccups) are marked ``retryable=True`` so the
  pipeline runner can decide to re-invoke the stage on a later run.
  Permanent failures (unsupported URL, video unavailable, extractor
  broken) are ``retryable=False``.

- **Format selection.** ``format='best[ext=mp4]/best'`` asks yt-dlp
  for the best mp4 when available and falls back to the best-quality
  format of any container. mp4 is the default because faster-whisper
  (S03) and ffmpeg (S04) both handle it natively on every platform.

- **Extractor → Platform mapping.** yt-dlp identifies each platform
  via an extractor name string. We translate those strings to our
  :class:`Platform` enum. Unknown extractors raise an IngestError —
  we never return a platform we can't name.

- **Quiet mode by default.** yt-dlp prints progress to stderr by
  default; we pass ``quiet=True`` + ``no_warnings=True`` so the CLI
  output stays clean. Callers who need progress can wire a progress
  hook later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

import re

from vidscope.domain import CookieAuthError, IngestError, Mention, Platform, PlatformId, VideoId
from vidscope.ports import ChannelEntry, CreatorInfo, IngestOutcome, ProbeResult, ProbeStatus

__all__ = ["YtdlpDownloader"]


# Maps yt-dlp extractor ``ie_key`` values (or their lowercased forms)
# to our :class:`Platform` enum. Keys are lowercased for lookup.
_EXTRACTOR_TO_PLATFORM: Final[dict[str, Platform]] = {
    "youtube": Platform.YOUTUBE,
    "youtubetab": Platform.YOUTUBE,
    "youtubeclip": Platform.YOUTUBE,
    "youtubeshorts": Platform.YOUTUBE,
    "tiktok": Platform.TIKTOK,
    "instagram": Platform.INSTAGRAM,
    "instagramstory": Platform.INSTAGRAM,
}


# Substrings in an error message that indicate a permanent failure
# (not worth retrying). Matched case-insensitively.
_PERMANENT_ERROR_MARKERS: Final[tuple[str, ...]] = (
    "unsupported url",
    "video unavailable",
    "private video",
    "members-only",
    "requested format is not available",
    "is not a valid url",
    "no video formats found",
)

# Substrings that indicate the platform is asking for authentication
# (cookies missing, expired, or insufficient). Matched case-insensitively.
# When detected, we raise CookieAuthError instead of generic IngestError.
_COOKIE_AUTH_MARKERS: Final[tuple[str, ...]] = (
    "login required",
    "cookies needed",
    "use --cookies",
    "rate-limit reached",
    "this content isn't available",
    "this video is private",
    "sign in to confirm",
    "requires login",
    "restricted video",
    "age-restricted",
)


class YtdlpDownloader:
    """Downloader port implementation backed by yt-dlp.

    Parameters
    ----------
    format_spec:
        Optional override for yt-dlp's ``format`` option. Default
        ``'best[ext=mp4]/best'`` picks the best mp4 available and
        falls back to the best-quality format regardless of container.
    cookies_file:
        Optional path to a Netscape-format cookies file. When set,
        yt-dlp uses these cookies for every download — required by
        Instagram public Reels as of 2026-04 (R025) and useful for
        age-gated YouTube content and private TikTok videos. The
        path is validated at init time: if it does not exist, the
        constructor raises :class:`IngestError` (retryable=False)
        immediately so a misconfiguration fails loud at startup
        instead of silently degrading to "no cookies" or crashing
        on the first download.
    """

    def __init__(
        self,
        *,
        format_spec: str = "best[ext=mp4]/best",
        cookies_file: Path | None = None,
    ) -> None:
        self._format_spec = format_spec
        self._cookies_file: Path | None = None

        if cookies_file is not None:
            resolved = Path(cookies_file).expanduser().resolve()
            if not resolved.exists():
                raise IngestError(
                    f"cookies file not found: {resolved}",
                    retryable=False,
                )
            if not resolved.is_file():
                raise IngestError(
                    f"cookies path is not a file: {resolved}",
                    retryable=False,
                )
            self._cookies_file = resolved

    # ------------------------------------------------------------------
    # Downloader protocol
    # ------------------------------------------------------------------

    def download(self, url: str, destination_dir: str) -> IngestOutcome:
        """Download ``url`` into ``destination_dir`` and return an
        :class:`IngestOutcome`.

        Raises
        ------
        IngestError
            Any failure during extraction or download. ``cause``
            carries the original yt-dlp exception.
        """
        if not url or not url.strip():
            raise IngestError("url is empty", retryable=False)

        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)

        options = self._build_options(dest)

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
        except DownloadError as exc:
            raise _translate_download_error(exc, url) from exc
        except ExtractorError as exc:
            raise _translate_extractor_error(exc, url) from exc
        except Exception as exc:
            # Any other exception is unexpected — wrap as a non-retryable
            # IngestError so the runner records it and stops.
            raise IngestError(
                f"unexpected yt-dlp failure for {url!r}: {exc}",
                cause=exc,
                retryable=False,
            ) from exc

        if info is None:
            raise IngestError(
                f"yt-dlp returned no metadata for {url!r}",
                retryable=False,
            )

        return _info_to_outcome(info, url=url, destination_dir=dest)

    def list_channel_videos(
        self, url: str, *, limit: int = 10
    ) -> list[ChannelEntry]:
        """List recent videos for a channel/account URL using yt-dlp's
        ``extract_flat`` mode.

        This is the cheap listing path used by the watchlist refresh
        loop (M003). ``extract_flat=True`` tells yt-dlp to return
        just the video IDs without fetching full metadata or
        downloading, which keeps the call fast (~0.5s for a YouTube
        channel on a fresh connection).

        Raises
        ------
        IngestError
            On any listing failure (unsupported platform, rate limit,
            channel not found, etc.). Cookie-gated channels raise with
            the usual yt-dlp auth error.
        """
        if not url or not url.strip():
            raise IngestError("url is empty", retryable=False)

        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "extract_flat": True,
            "playlist_items": f"1-{limit}",
            "skip_download": True,
            "ignoreerrors": False,
        }
        if self._cookies_file is not None:
            options["cookiefile"] = str(self._cookies_file)

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except DownloadError as exc:
            raise _translate_download_error(exc, url) from exc
        except ExtractorError as exc:
            raise _translate_extractor_error(exc, url) from exc
        except Exception as exc:
            raise IngestError(
                f"unexpected yt-dlp failure listing {url!r}: {exc}",
                cause=exc,
                retryable=False,
            ) from exc

        if info is None:
            raise IngestError(
                f"yt-dlp returned no metadata for channel {url!r}",
                retryable=False,
            )

        entries = info.get("entries") or []
        if not isinstance(entries, list):
            # Some extractors return a generator; drain it
            entries = list(entries)

        results: list[ChannelEntry] = []
        for entry in entries[:limit]:
            if not isinstance(entry, dict):
                continue
            raw_id = entry.get("id")
            if not raw_id:
                continue
            entry_url = (
                entry.get("webpage_url")
                or entry.get("url")
                or f"https://www.youtube.com/watch?v={raw_id}"
            )
            results.append(
                ChannelEntry(
                    platform_id=PlatformId(str(raw_id)),
                    url=str(entry_url),
                )
            )

        return results

    def probe(self, url: str) -> ProbeResult:
        """Fetch metadata only for ``url`` without downloading media.

        Returns a :class:`ProbeResult` describing the outcome — never
        raises. Used by ``vidscope cookies test`` to verify that
        cookies authenticate against gated platforms.
        """
        if not url or not url.strip():
            return ProbeResult(
                status=ProbeStatus.ERROR,
                url=url,
                detail="url is empty",
            )

        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "skip_download": True,
            "ignoreerrors": False,
        }
        if self._cookies_file is not None:
            options["cookiefile"] = str(self._cookies_file)

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except DownloadError as exc:
            return _translate_probe_error(exc, url)
        except ExtractorError as exc:
            return _translate_probe_error(exc, url)
        except Exception as exc:
            return ProbeResult(
                status=ProbeStatus.ERROR,
                url=url,
                detail=f"unexpected yt-dlp failure: {exc}",
            )

        if info is None:
            return ProbeResult(
                status=ProbeStatus.NOT_FOUND,
                url=url,
                detail="yt-dlp returned no metadata",
            )

        title = info.get("title") if isinstance(info, dict) else None
        info_d: dict[str, Any] = info if isinstance(info, dict) else {}
        return ProbeResult(
            status=ProbeStatus.OK,
            url=url,
            detail=f"resolved: {title or info_d.get('id', '?')}",
            title=title if isinstance(title, str) else None,
            uploader=_str_or_none(info_d.get("uploader")),
            uploader_id=_str_or_none(info_d.get("uploader_id")),
            uploader_url=_str_or_none(info_d.get("uploader_url")),
            channel_follower_count=_int_or_none(
                info_d.get("channel_follower_count") or info_d.get("channel_followers")
            ),
            uploader_thumbnail=_resolve_thumbnail(info_d.get("uploader_thumbnail")),
            uploader_verified=_bool_or_none(
                info_d.get("channel_verified") or info_d.get("uploader_verified")
            ),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_options(self, destination_dir: Path) -> dict[str, Any]:
        """Return the yt-dlp options dict for this downloader.

        The options live here so overriding the class (or instantiating
        with a different ``format_spec``) is the only way to change
        behavior — no module-level globals.
        """
        options: dict[str, Any] = {
            "format": self._format_spec,
            "outtmpl": str(destination_dir / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "writeinfojson": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "skip_download": False,
            "ignoreerrors": False,
        }
        if self._cookies_file is not None:
            # yt-dlp expects a string path here, not a Path object.
            options["cookiefile"] = str(self._cookies_file)
        return options


# ---------------------------------------------------------------------------
# Translators — yt-dlp info_dict / exceptions → domain types
# ---------------------------------------------------------------------------


def _info_to_outcome(
    info: dict[str, Any],
    *,
    url: str,
    destination_dir: Path,
) -> IngestOutcome:
    """Translate a yt-dlp ``info_dict`` into an :class:`IngestOutcome`.

    Raises
    ------
    IngestError
        If the info dict is missing the minimum required fields
        (id and a resolvable media path).
    """
    platform = _platform_from_info(info)
    raw_id = info.get("id")
    if not raw_id:
        raise IngestError(
            f"yt-dlp info_dict has no 'id' field for {url!r}",
            retryable=False,
        )

    platform_id = PlatformId(str(raw_id))

    # yt-dlp writes the downloaded file to a path derived from outtmpl.
    # For a playlist we would see 'entries' — for single videos the top
    # level dict carries the file info.
    media_path = _resolve_media_path(info, destination_dir, platform_id)
    if media_path is None:
        raise IngestError(
            f"yt-dlp downloaded {url!r} but no media file was found in "
            f"{destination_dir}",
            retryable=False,
        )

    return IngestOutcome(
        platform=platform,
        platform_id=platform_id,
        url=str(info.get("webpage_url") or url),
        media_path=str(media_path),
        title=_str_or_none(info.get("title")),
        author=_str_or_none(info.get("uploader") or info.get("channel")),
        duration=_float_or_none(info.get("duration")),
        upload_date=_str_or_none(info.get("upload_date")),
        view_count=_int_or_none(info.get("view_count")),
        creator_info=_build_creator_info(info),
        description=_str_or_none(info.get("description")),
        hashtags=_extract_hashtags(info),
        mentions=_extract_mentions(info.get("description"), platform),
        music_track=_str_or_none(info.get("track")),
        music_artist=_extract_music_artist(info),
    )


def _platform_from_info(info: dict[str, Any]) -> Platform:
    """Look up a :class:`Platform` from a yt-dlp info_dict.

    Tries ``extractor_key`` first (canonical), then ``extractor``
    (lowercase fallback). Raises IngestError for anything we don't
    recognize.
    """
    extractor = info.get("extractor_key") or info.get("extractor") or ""
    key = str(extractor).lower()
    # Some extractor keys include colons ('youtube:tab') — normalize by
    # splitting on ':' and trying the first segment too.
    candidates = [key, key.split(":", 1)[0]]
    for candidate in candidates:
        if candidate in _EXTRACTOR_TO_PLATFORM:
            return _EXTRACTOR_TO_PLATFORM[candidate]
    raise IngestError(
        f"unsupported yt-dlp extractor: {extractor!r}. "
        f"Supported extractors: {sorted(_EXTRACTOR_TO_PLATFORM.keys())}",
        retryable=False,
    )


def _resolve_media_path(
    info: dict[str, Any],
    destination_dir: Path,
    platform_id: PlatformId,
) -> Path | None:
    """Find the actual downloaded file on disk.

    Preference order:
    1. ``info['requested_downloads'][0]['filepath']`` (yt-dlp 2024+)
    2. ``info['_filename']`` (older yt-dlp)
    3. Scan ``destination_dir`` for a file whose stem matches the id
    """
    requested = info.get("requested_downloads")
    if isinstance(requested, list) and requested:
        first = requested[0]
        if isinstance(first, dict):
            filepath = first.get("filepath") or first.get("_filename")
            if filepath:
                candidate = Path(str(filepath))
                if candidate.exists():
                    return candidate

    legacy = info.get("_filename")
    if legacy:
        candidate = Path(str(legacy))
        if candidate.exists():
            return candidate

    # Last resort: glob the destination directory for a file whose
    # stem equals the platform id (outtmpl is "%(id)s.%(ext)s").
    matches = list(destination_dir.glob(f"{platform_id}.*"))
    if matches:
        # Prefer files that aren't intermediate (no .part, no .info.json)
        for match in matches:
            if match.suffix in (".part", ".json", ".tmp"):
                continue
            return match
        return matches[0]

    return None


def _translate_download_error(exc: DownloadError, url: str) -> IngestError:
    message = str(exc)
    if _is_cookie_auth_error(message):
        return CookieAuthError(
            f"yt-dlp download failed for {url!r}: cookies missing or expired. "
            f"Run `vidscope cookies test {url}` to verify your cookies.",
            url=url,
            cause=exc,
        )
    retryable = not _is_permanent_error(message)
    return IngestError(
        f"yt-dlp download failed for {url!r}: {message}",
        cause=exc,
        retryable=retryable,
    )


def _translate_extractor_error(exc: ExtractorError, url: str) -> IngestError:
    message = str(exc)
    if _is_cookie_auth_error(message):
        return CookieAuthError(
            f"yt-dlp extractor failed for {url!r}: cookies missing or expired. "
            f"Run `vidscope cookies test {url}` to verify your cookies.",
            url=url,
            cause=exc,
        )
    # Extractor errors are usually permanent (the URL is malformed or
    # the platform changed its HTML). Mark retryable only if the error
    # explicitly mentions a transient condition.
    retryable = "temporarily" in message.lower() or "try again" in message.lower()
    return IngestError(
        f"yt-dlp extractor failed for {url!r}: {message}",
        cause=exc,
        retryable=retryable,
    )


def _is_permanent_error(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _PERMANENT_ERROR_MARKERS)


def _is_cookie_auth_error(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _COOKIE_AUTH_MARKERS)


def _translate_probe_error(
    exc: DownloadError | ExtractorError, url: str
) -> ProbeResult:
    """Translate a yt-dlp exception into a :class:`ProbeResult`.

    Walks the same auth-marker list as the download translators so the
    probe and the download stage agree on what counts as a cookie
    failure.
    """
    message = str(exc)
    lowered = message.lower()

    if _is_cookie_auth_error(message):
        return ProbeResult(
            status=ProbeStatus.AUTH_REQUIRED,
            url=url,
            detail=f"authentication required: {message[:200]}",
        )
    if "unsupported url" in lowered or "is not a valid url" in lowered:
        return ProbeResult(
            status=ProbeStatus.UNSUPPORTED,
            url=url,
            detail=message[:200],
        )
    if "video unavailable" in lowered or "not found" in lowered:
        return ProbeResult(
            status=ProbeStatus.NOT_FOUND,
            url=url,
            detail=message[:200],
        )
    if "name resolution" in lowered or "connection" in lowered or "timed out" in lowered:
        return ProbeResult(
            status=ProbeStatus.NETWORK_ERROR,
            url=url,
            detail=message[:200],
        )
    return ProbeResult(
        status=ProbeStatus.ERROR,
        url=url,
        detail=message[:200],
    )


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _resolve_thumbnail(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw or None
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            return _str_or_none(first.get("url"))
        if isinstance(first, str):
            return first or None
    return None


def _build_creator_info(info: dict[str, Any]) -> CreatorInfo | None:
    uid = _str_or_none(info.get("uploader_id") or info.get("channel_id"))
    if not uid:
        return None
    uploader = _str_or_none(info.get("uploader") or info.get("channel"))
    return CreatorInfo(
        platform_user_id=uid,
        handle=uploader,
        display_name=uploader,
        profile_url=_str_or_none(info.get("uploader_url") or info.get("channel_url")),
        avatar_url=_resolve_thumbnail(info.get("uploader_thumbnail")),
        follower_count=_int_or_none(
            info.get("channel_follower_count") or info.get("channel_followers")
        ),
        is_verified=_bool_or_none(
            info.get("channel_verified") or info.get("uploader_verified")
        ),
    )


_MENTION_RE = re.compile(r"@([\w.]+)")


def _extract_mentions(
    description: str | None, platform: Platform
) -> tuple[Mention, ...]:
    if not description:
        return ()
    seen: set[str] = set()
    result: list[Mention] = []
    for m in _MENTION_RE.finditer(description):
        handle = m.group(1).lower()
        if handle in seen:
            continue
        seen.add(handle)
        result.append(Mention(video_id=VideoId(0), handle=handle, platform=None))
    return tuple(result)


def _extract_hashtags(info: dict[str, Any]) -> tuple[str, ...]:
    tags = info.get("tags")
    if not tags:
        return ()
    return tuple(t for t in tags if t)


def _extract_music_artist(info: dict[str, Any]) -> str | None:
    artists = info.get("artists")
    if artists:
        return _str_or_none(artists[0])
    return _str_or_none(info.get("artist"))
