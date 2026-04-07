"""Unit tests for vidscope.infrastructure.config.

Uses tmp_path + monkeypatch to sandbox the filesystem. No real user data
directory is touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vidscope.infrastructure.config import (
    Config,
    get_config,
    reset_config_cache,
)


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point every test at a temp data dir and reset the config cache."""
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    reset_config_cache()
    yield
    reset_config_cache()


class TestGetConfig:
    def test_returns_a_config_instance(self) -> None:
        cfg = get_config()
        assert isinstance(cfg, Config)

    def test_honors_env_override(self, tmp_path: Path) -> None:
        cfg = get_config()
        assert cfg.data_dir == tmp_path.resolve()

    def test_creates_every_subdirectory(self) -> None:
        cfg = get_config()
        for directory in (
            cfg.data_dir,
            cfg.cache_dir,
            cfg.downloads_dir,
            cfg.frames_dir,
            cfg.models_dir,
        ):
            assert directory.exists(), f"{directory} was not created"
            assert directory.is_dir()

    def test_does_not_create_the_db_file_eagerly(self) -> None:
        cfg = get_config()
        # The DB file itself is the adapter's responsibility to create.
        # Config only guarantees the parent directory exists.
        assert not cfg.db_path.exists()
        assert cfg.db_path.parent.exists()

    def test_db_path_is_inside_data_dir(self, tmp_path: Path) -> None:
        cfg = get_config()
        assert cfg.db_path.parent == tmp_path.resolve()
        assert cfg.db_path.name == "vidscope.db"

    def test_memoization_returns_same_instance(self) -> None:
        a = get_config()
        b = get_config()
        assert a is b

    def test_reset_cache_forces_rebuild(self) -> None:
        a = get_config()
        reset_config_cache()
        b = get_config()
        # Different instances, same resolved path.
        assert a is not b
        assert a.data_dir == b.data_dir

    def test_config_is_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        cfg = get_config()
        with pytest.raises(FrozenInstanceError):
            cfg.data_dir = Path("/tmp/hack")  # type: ignore[misc]


class TestEnvOverrideExpansion:
    def test_tilde_expands_in_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Use ~/<something> to verify tilde expansion. Because we are
        # inside the _sandbox fixture we re-apply the override here.
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("USERPROFILE", str(fake_home))  # Windows
        monkeypatch.setenv("VIDSCOPE_DATA_DIR", "~/vidscope-data")
        reset_config_cache()

        cfg = get_config()
        assert cfg.data_dir == (fake_home / "vidscope-data").resolve()


class TestCookiesFileResolution:
    """S07: cookies_file resolution priority — env var > data_dir default > None."""

    def test_no_cookies_configured_returns_none(self) -> None:
        cfg = get_config()
        assert cfg.cookies_file is None

    def test_env_var_override_resolves_to_absolute_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        external_cookies = tmp_path / "external" / "my-cookies.txt"
        external_cookies.parent.mkdir()
        external_cookies.write_text("# Netscape HTTP Cookie File\n")

        monkeypatch.setenv("VIDSCOPE_COOKIES_FILE", str(external_cookies))
        reset_config_cache()

        cfg = get_config()
        assert cfg.cookies_file == external_cookies.resolve()

    def test_default_cookies_path_picked_up_when_file_exists(
        self, tmp_path: Path
    ) -> None:
        # Pre-create the default cookies file inside the sandbox data dir
        default_cookies = tmp_path / "cookies.txt"
        default_cookies.write_text("# Netscape HTTP Cookie File\n")
        reset_config_cache()

        cfg = get_config()
        assert cfg.cookies_file == default_cookies.resolve()

    def test_default_cookies_path_ignored_when_file_missing(
        self, tmp_path: Path
    ) -> None:
        # Default cookies file does NOT exist in tmp_path — config should
        # leave cookies_file as None
        assert not (tmp_path / "cookies.txt").exists()
        cfg = get_config()
        assert cfg.cookies_file is None

    def test_env_var_takes_precedence_over_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Create both the default and an env-pointed file. The env var
        # should win.
        default_cookies = tmp_path / "cookies.txt"
        default_cookies.write_text("default")
        env_cookies = tmp_path / "env-cookies.txt"
        env_cookies.write_text("env")

        monkeypatch.setenv("VIDSCOPE_COOKIES_FILE", str(env_cookies))
        reset_config_cache()

        cfg = get_config()
        assert cfg.cookies_file == env_cookies.resolve()

    def test_env_var_path_returned_even_when_file_does_not_exist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Validation that the cookies file actually exists is the
        downloader's responsibility (T02). Config returns the path the
        user told us to use; T02 fails fast with a typed error if the
        path is bad."""
        bad_path = tmp_path / "does-not-exist.txt"
        monkeypatch.setenv("VIDSCOPE_COOKIES_FILE", str(bad_path))
        reset_config_cache()

        cfg = get_config()
        assert cfg.cookies_file == bad_path.resolve()
        assert not cfg.cookies_file.exists()


class TestWhisperModelConfig:
    """S03/T01: VIDSCOPE_WHISPER_MODEL env var resolution."""

    def test_default_is_base(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VIDSCOPE_WHISPER_MODEL", raising=False)
        reset_config_cache()
        cfg = get_config()
        assert cfg.whisper_model == "base"

    def test_env_var_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIDSCOPE_WHISPER_MODEL", "small")
        reset_config_cache()
        cfg = get_config()
        assert cfg.whisper_model == "small"

    def test_invalid_model_raises_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.domain.errors import ConfigError

        monkeypatch.setenv("VIDSCOPE_WHISPER_MODEL", "tinyy")
        reset_config_cache()
        with pytest.raises(ConfigError, match="unknown faster-whisper model"):
            get_config()

    def test_distil_model_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIDSCOPE_WHISPER_MODEL", "distil-large-v3")
        reset_config_cache()
        cfg = get_config()
        assert cfg.whisper_model == "distil-large-v3"


class TestAnalyzerNameConfig:
    """S05/T02: VIDSCOPE_ANALYZER env var resolution."""

    def test_default_is_heuristic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VIDSCOPE_ANALYZER", raising=False)
        reset_config_cache()
        cfg = get_config()
        assert cfg.analyzer_name == "heuristic"

    def test_env_var_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIDSCOPE_ANALYZER", "stub")
        reset_config_cache()
        cfg = get_config()
        assert cfg.analyzer_name == "stub"

    def test_empty_env_var_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIDSCOPE_ANALYZER", "  ")
        reset_config_cache()
        cfg = get_config()
        assert cfg.analyzer_name == "heuristic"
