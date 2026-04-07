"""Runtime configuration for VidScope.

Resolves every filesystem path used by the pipeline:

- ``data_dir``: root directory for persistent data (DB + downloaded media +
  extracted frames + whisper model cache)
- ``cache_dir``: ephemeral workspace for in-flight downloads and temp files
- ``db_path``: SQLite database file
- ``downloads_dir``: where yt-dlp stores media files
- ``frames_dir``: where ffmpeg writes extracted frames
- ``models_dir``: where faster-whisper caches downloaded model weights
- ``cookies_file``: optional path to a Netscape-format cookies file
  used by yt-dlp to authenticate against gated content (Instagram
  public Reels currently require this — see R025 / S07)

Defaults follow platform conventions via ``platformdirs``:

- Windows: ``%LOCALAPPDATA%/vidscope``
- macOS:   ``~/Library/Application Support/vidscope``
- Linux:   ``~/.local/share/vidscope``

All paths can be overridden by setting ``VIDSCOPE_DATA_DIR`` to an absolute
path — every subdirectory is then rooted under that override. This is the
escape hatch tests use to sandbox the filesystem.

The cookies file is resolved with three-step priority:

1. ``VIDSCOPE_COOKIES_FILE`` env var, if set, points at the cookies file
2. Otherwise, ``<data_dir>/cookies.txt`` if that file exists
3. Otherwise, ``cookies_file`` is ``None`` (cookies feature is opt-in)

``reset_config_cache()`` is exposed as a test hook. Production code never
mutates the cache directly.

This module is in the infrastructure layer — it is the single place in
the codebase allowed to read ``os.environ`` and build filesystem paths.
Everything else receives a :class:`Config` through the container.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

__all__ = ["Config", "get_config", "reset_config_cache"]

_APP_NAME = "vidscope"
_ENV_DATA_DIR = "VIDSCOPE_DATA_DIR"
_ENV_COOKIES_FILE = "VIDSCOPE_COOKIES_FILE"
_ENV_WHISPER_MODEL = "VIDSCOPE_WHISPER_MODEL"
_ENV_ANALYZER = "VIDSCOPE_ANALYZER"
_DEFAULT_COOKIES_FILENAME = "cookies.txt"
_DEFAULT_WHISPER_MODEL = "base"
_DEFAULT_ANALYZER = "heuristic"

# Known faster-whisper model names. Anything outside this set is
# rejected with a typed ConfigError to catch typos before the model
# loader silently downloads "tinyy" or fails on a misspelled name.
_KNOWN_WHISPER_MODELS: frozenset[str] = frozenset({
    "tiny", "tiny.en",
    "base", "base.en",
    "small", "small.en",
    "medium", "medium.en",
    "large-v1", "large-v2", "large-v3",
    "distil-small.en", "distil-medium.en",
    "distil-large-v2", "distil-large-v3",
})


@dataclass(frozen=True, slots=True)
class Config:
    """Resolved runtime paths. Immutable once built.

    Every directory referenced here is guaranteed to exist on disk by
    the time a :class:`Config` instance is returned from
    :func:`get_config`. The DB file itself is NOT created here — the
    SQLite adapter creates it on ``init_db``.

    ``cookies_file`` is ``None`` when no cookies are configured. When
    set, it points at a Netscape-format cookies file that yt-dlp uses
    to authenticate. The path is NOT validated for existence at
    Config construction time — that check happens in the downstream
    :class:`YtdlpDownloader` so failures are reported via the typed
    domain error path.
    """

    data_dir: Path
    cache_dir: Path
    db_path: Path
    downloads_dir: Path
    frames_dir: Path
    models_dir: Path
    cookies_file: Path | None = None
    whisper_model: str = _DEFAULT_WHISPER_MODEL
    analyzer_name: str = _DEFAULT_ANALYZER


_cached_config: Config | None = None


def _resolve_data_dir() -> Path:
    """Return the root data directory, honoring the env override."""
    override = os.environ.get(_ENV_DATA_DIR)
    if override:
        return Path(override).expanduser().resolve()
    return Path(user_data_dir(appname=_APP_NAME, appauthor=False)).resolve()


def _resolve_whisper_model() -> str:
    """Return the configured faster-whisper model name.

    Resolution: ``VIDSCOPE_WHISPER_MODEL`` env var if set, otherwise
    the default ``"base"``. Validates against the known set of model
    names so a typo fails loud at config build time, not at the first
    transcribe call.
    """
    from vidscope.domain.errors import ConfigError  # noqa: PLC0415

    raw = os.environ.get(_ENV_WHISPER_MODEL, _DEFAULT_WHISPER_MODEL).strip()
    if not raw:
        return _DEFAULT_WHISPER_MODEL
    if raw not in _KNOWN_WHISPER_MODELS:
        raise ConfigError(
            f"unknown faster-whisper model: {raw!r}. "
            f"Supported models: {sorted(_KNOWN_WHISPER_MODELS)}"
        )
    return raw


def _resolve_analyzer_name() -> str:
    """Return the configured analyzer provider name.

    Resolution: ``VIDSCOPE_ANALYZER`` env var if set, otherwise the
    default ``"heuristic"``. The actual validation against the
    registry happens in
    :func:`vidscope.infrastructure.analyzer_registry.build_analyzer`,
    which raises ConfigError if the name is unknown.
    """
    raw = os.environ.get(_ENV_ANALYZER, _DEFAULT_ANALYZER).strip()
    return raw or _DEFAULT_ANALYZER


def _resolve_cookies_file(data_dir: Path) -> Path | None:
    """Return the configured cookies file path, or ``None``.

    Resolution priority (per S07):

    1. ``VIDSCOPE_COOKIES_FILE`` env var, expanded and resolved
    2. ``<data_dir>/cookies.txt`` if that file actually exists
    3. ``None`` (cookies are an opt-in feature)

    The path is NOT validated for existence here when it comes from
    the env var — we want a misconfigured env var to surface as a
    typed :class:`IngestError` from :class:`YtdlpDownloader`, not as
    a silent fall-through to the default.
    """
    override = os.environ.get(_ENV_COOKIES_FILE)
    if override:
        return Path(override).expanduser().resolve()

    default = data_dir / _DEFAULT_COOKIES_FILENAME
    if default.exists():
        return default.resolve()

    return None


def _build_config() -> Config:
    """Construct a :class:`Config` and materialize every directory on disk."""
    data_dir = _resolve_data_dir()
    cache_dir = data_dir / "cache"
    downloads_dir = data_dir / "downloads"
    frames_dir = data_dir / "frames"
    models_dir = data_dir / "models"
    db_path = data_dir / "vidscope.db"

    for directory in (data_dir, cache_dir, downloads_dir, frames_dir, models_dir):
        directory.mkdir(parents=True, exist_ok=True)

    cookies_file = _resolve_cookies_file(data_dir)
    whisper_model = _resolve_whisper_model()
    analyzer_name = _resolve_analyzer_name()

    return Config(
        data_dir=data_dir,
        cache_dir=cache_dir,
        db_path=db_path,
        downloads_dir=downloads_dir,
        frames_dir=frames_dir,
        models_dir=models_dir,
        cookies_file=cookies_file,
        whisper_model=whisper_model,
        analyzer_name=analyzer_name,
    )


def get_config() -> Config:
    """Return the process-wide :class:`Config`, building it on first call.

    The result is cached for the lifetime of the process. Use
    :func:`reset_config_cache` in tests that mutate
    ``VIDSCOPE_DATA_DIR``.
    """
    global _cached_config
    if _cached_config is None:
        _cached_config = _build_config()
    return _cached_config


def reset_config_cache() -> None:
    """Drop the memoized config so the next :func:`get_config` call
    rebuilds it. Intended for tests only."""
    global _cached_config
    _cached_config = None
