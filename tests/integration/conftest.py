"""Integration-test fixtures.

Every integration test gets:

- a sandboxed ``VIDSCOPE_DATA_DIR`` under ``tmp_path`` so real
  downloads never touch the user's library
- a freshly built :class:`Container` with the production
  :class:`YtdlpDownloader`, :class:`LocalMediaStorage`, and
  :class:`PipelineRunner` already wired

Integration tests are marked ``@pytest.mark.integration`` and skipped
by default — the main unit suite (``pytest tests/unit``) does NOT run
them. They run on demand via ``pytest tests/integration -m integration``
or through ``scripts/verify-s02.sh``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vidscope.infrastructure.config import reset_config_cache
from vidscope.infrastructure.container import Container, build_container


@pytest.fixture()
def sandboxed_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Container:
    """Return a fully wired :class:`Container` rooted at a fresh
    ``tmp_path``.

    Uses ``monkeypatch.setenv`` so the override is automatically
    cleared after the test — even on failure. Resets the cached
    config before and after to guarantee isolation between tests.
    """
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    reset_config_cache()
    try:
        yield build_container()
    finally:
        reset_config_cache()
