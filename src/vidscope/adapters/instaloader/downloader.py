"""InstaLoaderDownloader — fallback downloader for Instagram image content.

yt-dlp cannot download image-only posts or image carousels from Instagram
(its extractor only handles video formats). This adapter uses ``instaloader``
to fetch metadata and image URLs, then downloads each image with the
authenticated requests session so private content is accessible.

Only ``download`` is implemented; ``list_channel_videos`` and ``probe``
raise immediately — callers must route those to :class:`YtdlpDownloader`
(handled by :class:`~vidscope.adapters.composite.FallbackDownloader`).
"""

from __future__ import annotations

import http.cookiejar
import re
from pathlib import Path
from typing import Any

from vidscope.domain import IngestError, MediaType, Platform, PlatformId
from vidscope.ports import ChannelEntry, IngestOutcome, ProbeResult, ProbeStatus

__all__ = ["InstaLoaderDownloader"]

_SHORTCODE_RE = re.compile(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)")


class InstaLoaderDownloader:
    """Downloader backed by instaloader for Instagram image posts/carousels.

    Parameters
    ----------
    cookies_file:
        Path to a Netscape-format cookies file (produced by
        ``vidscope cookies login instagram``). Required for private
        content; optional for public posts.
    """

    def __init__(self, *, cookies_file: Path | None = None) -> None:
        self._cookies_file = cookies_file

    # ------------------------------------------------------------------
    # Downloader protocol
    # ------------------------------------------------------------------

    def download(self, url: str, destination_dir: str) -> IngestOutcome:
        """Download an Instagram image post or carousel to *destination_dir*.

        Raises
        ------
        IngestError
            If instaloader is not installed, the shortcode cannot be
            extracted, or the post cannot be fetched.
        """
        try:
            import instaloader  # noqa: PLC0415
        except ImportError as exc:
            raise IngestError(
                "instaloader is not installed. Run: uv add instaloader",
                retryable=False,
            ) from exc

        shortcode = _extract_shortcode(url)
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)

        L = instaloader.Instaloader(
            quiet=True,
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern="",
        )

        if self._cookies_file is not None:
            _load_netscape_cookies(L, self._cookies_file)

        try:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
        except Exception as exc:
            raise IngestError(
                f"instaloader failed to fetch post {shortcode!r}: {exc}",
                retryable=True,
            ) from exc

        image_paths = _download_images(post, dest, L.context._session)

        if not image_paths:
            raise IngestError(
                f"no downloadable images found for post {shortcode!r}",
                retryable=False,
            )

        media_type = MediaType.CAROUSEL if len(image_paths) > 1 else MediaType.IMAGE

        return IngestOutcome(
            platform=Platform.INSTAGRAM,
            platform_id=PlatformId(shortcode),
            url=f"https://www.instagram.com/p/{shortcode}/",
            media_path=image_paths[0],
            title=post.caption[:200] if post.caption else None,
            author=post.owner_username,
            upload_date=post.date_utc.strftime("%Y%m%d"),
            media_type=media_type,
            carousel_items=tuple(image_paths) if media_type == MediaType.CAROUSEL else (),
        )

    def list_channel_videos(
        self, url: str, *, limit: int = 10
    ) -> list[ChannelEntry]:
        raise IngestError(
            "list_channel_videos is not supported by InstaLoaderDownloader; "
            "use YtdlpDownloader for channel listing.",
            retryable=False,
        )

    def probe(self, url: str) -> ProbeResult:
        return ProbeResult(
            status=ProbeStatus.UNSUPPORTED,
            url=url,
            detail="probe not supported by InstaLoaderDownloader",
        )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _extract_shortcode(url: str) -> str:
    m = _SHORTCODE_RE.search(url)
    if not m:
        raise IngestError(
            f"cannot extract Instagram shortcode from {url!r}",
            retryable=False,
        )
    return m.group(1)


def _load_netscape_cookies(L: Any, cookies_file: Path) -> None:
    cj = http.cookiejar.MozillaCookieJar(str(cookies_file))
    try:
        cj.load(ignore_discard=True, ignore_expires=True)
        L.context._session.cookies.update(cj)
    except Exception:
        # Best-effort: proceed without cookies if file is malformed.
        pass


def _download_images(post: Any, dest: Path, session: Any) -> list[str]:
    """Download all images from *post* into *dest*, return their paths."""
    paths: list[str] = []
    if post.typename == "GraphSidecar":
        for i, node in enumerate(post.get_sidecar_nodes()):
            if not node.is_video:
                path = dest / f"slide_{i:04d}.jpg"
                _fetch(node.display_url, path, session)
                paths.append(str(path))
    elif not post.is_video:
        path = dest / "image.jpg"
        _fetch(post.url, path, session)
        paths.append(str(path))
    return paths


def _fetch(url: str, dest: Path, session: Any) -> None:
    response = session.get(url, stream=True, timeout=30)
    response.raise_for_status()
    dest.write_bytes(response.content)
