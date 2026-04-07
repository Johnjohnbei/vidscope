"""yt-dlp adapter package.

Implements the :class:`~vidscope.ports.pipeline.Downloader` port by
wrapping ``yt_dlp.YoutubeDL``. The yt-dlp import is deliberately
contained in this package — no other layer in the codebase references
yt-dlp directly.

When yt-dlp breaks upstream (a platform rotates an API key, changes
its CDN, or renames an extractor field) the blast radius is this
single file plus its tests.
"""

from __future__ import annotations

from vidscope.adapters.ytdlp.downloader import YtdlpDownloader

__all__ = ["YtdlpDownloader"]
