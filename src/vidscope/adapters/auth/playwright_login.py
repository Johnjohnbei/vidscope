"""Playwright-based cookie capture for gated platforms (M012/auth extra).

Opens a real Chromium browser window so the user can log in interactively.
Cookies are captured as soon as the target session cookie appears, then
written in Netscape format so yt-dlp can consume them.

Install: uv sync --extra auth
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

__all__ = ["capture_platform_cookies"]

# Platform-specific config: login URL + cookie that proves login succeeded.
_PLATFORM_CONFIG: dict[str, dict[str, str]] = {
    "instagram": {
        "login_url": "https://www.instagram.com/accounts/login/",
        "session_cookie": "sessionid",
        "domain_filter": "instagram.com",
    },
    "tiktok": {
        "login_url": "https://www.tiktok.com/login",
        "session_cookie": "sessionid",
        "domain_filter": "tiktok.com",
    },
    "youtube": {
        "login_url": "https://accounts.google.com/signin",
        "session_cookie": "SAPISID",
        "domain_filter": ".google.com",
    },
}

SUPPORTED_PLATFORMS = tuple(_PLATFORM_CONFIG.keys())


def capture_platform_cookies(
    platform: str,
    destination: Path,
    *,
    timeout_seconds: int = 300,
) -> int:
    """Open a browser, wait for the user to log in, capture and save cookies.

    Parameters
    ----------
    platform:
        One of ``SUPPORTED_PLATFORMS``.
    destination:
        Where to write the Netscape cookies file.
    timeout_seconds:
        How long to wait for the user to complete login (default 5 min).

    Returns
    -------
    int
        Number of cookies written.

    Raises
    ------
    ImportError
        If ``playwright`` is not installed (``uv sync --extra auth``).
    RuntimeError
        If login times out or the browser is closed before completion.
    """
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "playwright is not installed. Run: uv sync --extra auth"
        ) from exc

    cfg = _PLATFORM_CONFIG[platform]
    login_url: str = cfg["login_url"]
    session_cookie: str = cfg["session_cookie"]
    domain_filter: str = cfg["domain_filter"]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url)

        deadline = time.monotonic() + timeout_seconds
        cookies: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            all_cookies = context.cookies()
            if any(c["name"] == session_cookie for c in all_cookies):
                cookies = all_cookies
                break
            # Small sleep to avoid hammering the browser
            page.wait_for_timeout(1000)

        browser.close()

    if not cookies:
        raise RuntimeError(
            f"Login timed out after {timeout_seconds}s — "
            f"no {session_cookie!r} cookie found for {platform}."
        )

    platform_cookies = [
        c for c in cookies if domain_filter in c.get("domain", "")
    ]
    _write_netscape(platform_cookies, destination)
    return len(platform_cookies)


def _write_netscape(cookies: list[dict[str, Any]], path: Path) -> None:
    lines = ["# Netscape HTTP Cookie File\n"]
    for c in cookies:
        domain: str = c.get("domain", "")
        if not domain.startswith("."):
            domain = f".{domain}"
        include_subdomains = "TRUE"
        secure = "TRUE" if c.get("secure") else "FALSE"
        expiry = int(c.get("expires") or 0)
        if expiry < 0:
            expiry = 0
        name: str = c.get("name", "")
        value: str = c.get("value", "")
        path_val: str = c.get("path", "/")
        lines.append(
            f"{domain}\t{include_subdomains}\t{path_val}\t{secure}\t{expiry}\t{name}\t{value}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")
