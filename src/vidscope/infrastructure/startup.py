"""Startup system checks.

The pipeline depends on two external binaries/libraries plus an
optional cookies file:

- **ffmpeg** — frame extraction (R003). We check by running ``ffmpeg
  -version`` with a short timeout and parsing the first line.
- **yt-dlp** — ingestion (R001). We check by importing the Python module
  and inspecting its ``version.__version__`` attribute. Since yt-dlp is
  a runtime dependency, this import should always succeed in a clean
  install; a failing import means something is badly wrong.
- **cookies** (S07/R025) — optional Netscape-format cookies file used
  by yt-dlp to authenticate against gated content (Instagram public
  Reels, age-gated YouTube, private TikTok). The check has THREE
  states: ``ok=True`` when cookies are configured AND the file exists,
  ``ok=True`` when no cookies are configured (this is fine — cookies
  are opt-in), and ``ok=False`` only when cookies are configured but
  the file is missing or unreadable.

Checks are exposed through :func:`run_all_checks` which returns a list
of :class:`CheckResult` dataclasses. The CLI's ``doctor`` command prints
them as a rich table. The ``add`` command calls them at startup and
aborts with exit code 2 if either is NOT ok, surfacing
:attr:`CheckResult.remediation` so the user knows how to fix it.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Final

__all__ = [
    "CheckResult",
    "check_analyzer",
    "check_cookies",
    "check_ffmpeg",
    "check_mcp_sdk",
    "check_vision",
    "check_ytdlp",
    "run_all_checks",
]


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Outcome of a single startup check.

    Attributes
    ----------
    name:
        Human-readable name of the check, e.g. ``"ffmpeg"``.
    ok:
        ``True`` when the dependency is present and usable.
    version_or_error:
        On success, the version string reported by the tool. On failure,
        a short description of what went wrong.
    remediation:
        Platform-aware suggestion shown to the user when ``ok`` is
        ``False``. Empty string on success.
    """

    name: str
    ok: bool
    version_or_error: str
    remediation: str


_FFMPEG_TIMEOUT_SECONDS: Final = 5.0

_FFMPEG_REMEDIATION: Final = (
    "Install ffmpeg:\n"
    "  - Windows: `winget install Gyan.FFmpeg`  (or download from "
    "https://www.gyan.dev/ffmpeg/builds/)\n"
    "  - macOS:   `brew install ffmpeg`\n"
    "  - Linux:   `sudo apt install ffmpeg`  or your distro's equivalent\n"
    "Then make sure the `ffmpeg` binary is on your PATH."
)

_YTDLP_REMEDIATION: Final = (
    "yt-dlp is a runtime dependency of vidscope. Reinstall with "
    "`uv sync` from the project directory. If the problem persists, "
    "report the traceback with `uv run vidscope doctor --verbose`."
)

_MCP_REMEDIATION: Final = (
    "mcp is a runtime dependency of vidscope. Reinstall with "
    "`uv sync` from the project directory. If the problem persists, "
    "the `mcp` package may be incompatible with your Python version — "
    "vidscope requires Python 3.12+."
)

_COOKIES_OPTIONAL_REMEDIATION: Final = (
    "Cookies are optional. If you want to ingest Instagram public Reels, "
    "age-gated YouTube content, or private TikTok videos, see "
    "`docs/cookies.md` for how to export your browser cookies and where "
    "to place the file."
)

_COOKIES_MISSING_REMEDIATION: Final = (
    "VIDSCOPE_COOKIES_FILE is set but the file does not exist. Either "
    "create the file (see `docs/cookies.md`) or unset the env var to "
    "disable cookie-based authentication."
)

_ANALYZER_REMEDIATION: Final = (
    "Set VIDSCOPE_ANALYZER to one of: heuristic, stub, groq, nvidia, "
    "openrouter, openai, anthropic. For LLM providers, also set the "
    "matching VIDSCOPE_<PROVIDER>_API_KEY env var. See "
    "`docs/analyzers.md` for the full list and signup URLs."
)

_VISION_OPTIONAL_REMEDIATION: Final = (
    "Vision OCR + face-count are optional (M008). If you want to "
    "extract on-screen text and classify content shape, install the "
    "extra: `uv sync --extra vision`. Without it, the visual_intelligence "
    "pipeline stage emits SKIPPED and the rest of the pipeline is "
    "unaffected."
)


def check_ffmpeg() -> CheckResult:
    """Return a :class:`CheckResult` for the ``ffmpeg`` binary.

    Strategy: ``shutil.which`` first (cheap), then ``ffmpeg -version``
    with a 5-second timeout to confirm it actually runs.
    """
    binary = shutil.which("ffmpeg")
    if binary is None:
        return CheckResult(
            name="ffmpeg",
            ok=False,
            version_or_error="not found on PATH",
            remediation=_FFMPEG_REMEDIATION,
        )

    try:
        completed = subprocess.run(
            [binary, "-version"],
            capture_output=True,
            text=True,
            timeout=_FFMPEG_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="ffmpeg",
            ok=False,
            version_or_error=(
                f"timed out after {_FFMPEG_TIMEOUT_SECONDS:.0f}s "
                f"running `{binary} -version`"
            ),
            remediation=_FFMPEG_REMEDIATION,
        )
    except OSError as exc:
        return CheckResult(
            name="ffmpeg",
            ok=False,
            version_or_error=f"failed to execute: {exc}",
            remediation=_FFMPEG_REMEDIATION,
        )

    if completed.returncode != 0:
        return CheckResult(
            name="ffmpeg",
            ok=False,
            version_or_error=(
                f"`ffmpeg -version` exited with code "
                f"{completed.returncode}: {completed.stderr.strip()}"
            ),
            remediation=_FFMPEG_REMEDIATION,
        )

    first_line = completed.stdout.splitlines()[0] if completed.stdout else "ffmpeg"
    return CheckResult(
        name="ffmpeg",
        ok=True,
        version_or_error=first_line,
        remediation="",
    )


def check_ytdlp() -> CheckResult:
    """Return a :class:`CheckResult` for the ``yt-dlp`` Python module."""
    try:
        import yt_dlp  # noqa: PLC0415 — imported lazily so import failures surface here
    except ImportError as exc:
        return CheckResult(
            name="yt-dlp",
            ok=False,
            version_or_error=f"import failed: {exc}",
            remediation=_YTDLP_REMEDIATION,
        )

    version = getattr(yt_dlp, "version", None)
    version_string = getattr(version, "__version__", None) if version else None
    if version_string is None:
        # Some builds expose __version__ directly on the package.
        version_string = getattr(yt_dlp, "__version__", None)

    if version_string is None:
        return CheckResult(
            name="yt-dlp",
            ok=False,
            version_or_error="imported successfully but version attribute missing",
            remediation=_YTDLP_REMEDIATION,
        )

    return CheckResult(
        name="yt-dlp",
        ok=True,
        version_or_error=str(version_string),
        remediation="",
    )


def check_cookies() -> CheckResult:
    """Return a :class:`CheckResult` for the cookies file.

    Three states (per S07):

    1. **Configured + present**: ``ok=True``, version_or_error shows
       the resolved path.
    2. **Not configured**: ``ok=True``, version_or_error says "not
       configured (optional)" with a pointer to docs/cookies.md.
       Cookies are opt-in, so this is a healthy state.
    3. **Configured + missing**: ``ok=False``, version_or_error names
       the missing path. The user has set ``VIDSCOPE_COOKIES_FILE``
       but the file is gone.
    """
    # Imported here so this module stays free of import-time side
    # effects from infrastructure.config (which would load the
    # cached config on first import — undesirable for a check helper).
    from vidscope.infrastructure.config import get_config  # noqa: PLC0415

    config = get_config()
    if config.cookies_file is None:
        return CheckResult(
            name="cookies",
            ok=True,
            version_or_error="not configured (optional)",
            remediation=_COOKIES_OPTIONAL_REMEDIATION,
        )

    if not config.cookies_file.exists():
        return CheckResult(
            name="cookies",
            ok=False,
            version_or_error=(
                f"configured at {config.cookies_file} but file is missing"
            ),
            remediation=_COOKIES_MISSING_REMEDIATION,
        )

    if not config.cookies_file.is_file():
        return CheckResult(
            name="cookies",
            ok=False,
            version_or_error=(
                f"configured at {config.cookies_file} but path is not "
                f"a file"
            ),
            remediation=_COOKIES_MISSING_REMEDIATION,
        )

    return CheckResult(
        name="cookies",
        ok=True,
        version_or_error=f"configured at {config.cookies_file}",
        remediation="",
    )


def check_mcp_sdk() -> CheckResult:
    """Return a :class:`CheckResult` for the ``mcp`` Python package.

    mcp is a runtime dependency as of M002 (the MCP server interface
    layer). We check by importing the module and reading the version
    via :mod:`importlib.metadata`.
    """
    try:
        import mcp  # noqa: F401, PLC0415
    except ImportError as exc:
        return CheckResult(
            name="mcp",
            ok=False,
            version_or_error=f"import failed: {exc}",
            remediation=_MCP_REMEDIATION,
        )

    try:
        from importlib.metadata import version  # noqa: PLC0415

        version_string = version("mcp")
    except Exception as exc:
        return CheckResult(
            name="mcp",
            ok=False,
            version_or_error=f"imported but version unavailable: {exc}",
            remediation=_MCP_REMEDIATION,
        )

    return CheckResult(
        name="mcp",
        ok=True,
        version_or_error=version_string,
        remediation="",
    )


def check_analyzer() -> CheckResult:
    """Return a :class:`CheckResult` for the configured analyzer.

    States:

    1. **Default heuristic**: ``ok=True``, version_or_error reports
       ``"heuristic (default, zero cost)"``.
    2. **Stub**: ``ok=True``, version_or_error reports ``"stub"``.
    3. **LLM provider configured + key present**: ``ok=True``,
       version_or_error reports the provider name + ``"key present"``.
    4. **LLM provider configured but key missing**: ``ok=False``,
       version_or_error names the missing env var.
    5. **Unknown provider name**: ``ok=False``, lists the known names.
    """
    from vidscope.infrastructure.analyzer_registry import (  # noqa: PLC0415
        KNOWN_ANALYZERS,
        build_analyzer,
    )
    from vidscope.infrastructure.config import get_config  # noqa: PLC0415

    config = get_config()
    name = config.analyzer_name

    if name == "heuristic":
        return CheckResult(
            name="analyzer",
            ok=True,
            version_or_error="heuristic (default, zero cost)",
            remediation="",
        )
    if name == "stub":
        return CheckResult(
            name="analyzer",
            ok=True,
            version_or_error="stub (test placeholder)",
            remediation="",
        )

    if name not in KNOWN_ANALYZERS:
        return CheckResult(
            name="analyzer",
            ok=False,
            version_or_error=(
                f"unknown analyzer {name!r}. Known: {sorted(KNOWN_ANALYZERS)}"
            ),
            remediation=_ANALYZER_REMEDIATION,
        )

    # LLM provider — try to build it. ConfigError means the key is
    # missing or malformed; the message itself is already actionable
    # (every factory wraps it with the env var name + signup URL).
    from vidscope.domain.errors import ConfigError as _ConfigError  # noqa: PLC0415

    try:
        build_analyzer(name)
    except _ConfigError as exc:
        return CheckResult(
            name="analyzer",
            ok=False,
            version_or_error=f"{name}: {exc}",
            remediation=_ANALYZER_REMEDIATION,
        )

    return CheckResult(
        name="analyzer",
        ok=True,
        version_or_error=f"{name} (LLM key present)",
        remediation="",
    )


def check_vision() -> CheckResult:
    """Return a :class:`CheckResult` for the optional vision extra.

    States:

    1. **Both installed**: ``ok=True``, version_or_error reports both
       module versions.
    2. **Neither installed**: ``ok=True`` (optional), version_or_error
       says "not installed (optional)".
    3. **Partial install** (one present, other missing): ``ok=False``,
       names the missing package.

    The vision extra is optional — its absence is a healthy state.
    Only a BROKEN install (one half present, the other missing)
    warrants ``ok=False``.
    """
    from importlib.util import find_spec  # noqa: PLC0415

    has_rapidocr = find_spec("rapidocr_onnxruntime") is not None
    has_cv2 = find_spec("cv2") is not None

    if not has_rapidocr and not has_cv2:
        return CheckResult(
            name="vision",
            ok=True,
            version_or_error="not installed (optional)",
            remediation=_VISION_OPTIONAL_REMEDIATION,
        )
    if has_rapidocr and has_cv2:
        try:
            from importlib.metadata import version  # noqa: PLC0415
            rapidocr_v = version("rapidocr-onnxruntime")
        except Exception:  # noqa: BLE001
            rapidocr_v = "unknown"
        try:
            from importlib.metadata import version  # noqa: PLC0415
            cv2_v = version("opencv-python-headless")
        except Exception:  # noqa: BLE001
            cv2_v = "unknown"
        return CheckResult(
            name="vision",
            ok=True,
            version_or_error=(
                f"rapidocr-onnxruntime={rapidocr_v}, "
                f"opencv-python-headless={cv2_v}"
            ),
            remediation="",
        )
    # Partial install.
    missing = (
        "opencv-python-headless" if has_rapidocr else "rapidocr-onnxruntime"
    )
    return CheckResult(
        name="vision",
        ok=False,
        version_or_error=f"partial install: {missing} missing",
        remediation=_VISION_OPTIONAL_REMEDIATION,
    )


def run_all_checks() -> list[CheckResult]:
    """Run every startup check and return the results.

    The CLI's ``doctor`` command and the ``add`` command's preflight
    both consume this list.
    """
    return [
        check_ffmpeg(),
        check_ytdlp(),
        check_mcp_sdk(),
        check_cookies(),
        check_analyzer(),
        check_vision(),
    ]
