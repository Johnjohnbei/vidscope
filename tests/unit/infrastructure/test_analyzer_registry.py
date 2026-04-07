"""Tests for the analyzer registry."""

from __future__ import annotations

import pytest

from vidscope.adapters.heuristic import HeuristicAnalyzer, StubAnalyzer
from vidscope.adapters.llm.anthropic import AnthropicAnalyzer
from vidscope.adapters.llm.groq import GroqAnalyzer
from vidscope.adapters.llm.nvidia_build import NvidiaBuildAnalyzer
from vidscope.adapters.llm.openai import OpenAIAnalyzer
from vidscope.adapters.llm.openrouter import OpenRouterAnalyzer
from vidscope.domain.errors import ConfigError
from vidscope.infrastructure.analyzer_registry import (
    KNOWN_ANALYZERS,
    build_analyzer,
)


class TestBuildAnalyzer:
    def test_heuristic_returns_heuristic_analyzer(self) -> None:
        analyzer = build_analyzer("heuristic")
        assert isinstance(analyzer, HeuristicAnalyzer)
        assert analyzer.provider_name == "heuristic"

    def test_stub_returns_stub_analyzer(self) -> None:
        analyzer = build_analyzer("stub")
        assert isinstance(analyzer, StubAnalyzer)
        assert analyzer.provider_name == "stub"

    def test_unknown_name_raises_config_error(self) -> None:
        with pytest.raises(ConfigError, match="unknown analyzer provider"):
            build_analyzer("not-a-real-provider")

    def test_unknown_name_lists_registered_providers(self) -> None:
        with pytest.raises(ConfigError) as exc_info:
            build_analyzer("foo")
        assert "heuristic" in str(exc_info.value)
        assert "stub" in str(exc_info.value)

    def test_each_call_returns_a_fresh_instance(self) -> None:
        a = build_analyzer("heuristic")
        b = build_analyzer("heuristic")
        # Same type but different instances
        assert type(a) is type(b)
        assert a is not b


class TestKnownAnalyzers:
    def test_includes_heuristic_and_stub(self) -> None:
        assert "heuristic" in KNOWN_ANALYZERS
        assert "stub" in KNOWN_ANALYZERS

    def test_includes_groq(self) -> None:
        assert "groq" in KNOWN_ANALYZERS

    def test_includes_all_5_llm_providers(self) -> None:
        assert "groq" in KNOWN_ANALYZERS
        assert "nvidia" in KNOWN_ANALYZERS
        assert "openrouter" in KNOWN_ANALYZERS
        assert "openai" in KNOWN_ANALYZERS
        assert "anthropic" in KNOWN_ANALYZERS

    def test_is_immutable(self) -> None:
        # frozenset has no add() method
        assert isinstance(KNOWN_ANALYZERS, frozenset)


class TestBuildGroqAnalyzer:
    def test_missing_api_key_raises_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VIDSCOPE_GROQ_API_KEY", raising=False)
        with pytest.raises(ConfigError, match="VIDSCOPE_GROQ_API_KEY"):
            build_analyzer("groq")

    def test_empty_api_key_raises_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIDSCOPE_GROQ_API_KEY", "   ")
        with pytest.raises(ConfigError, match="VIDSCOPE_GROQ_API_KEY"):
            build_analyzer("groq")

    def test_valid_api_key_returns_groq_analyzer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIDSCOPE_GROQ_API_KEY", "fake-test-key")
        analyzer = build_analyzer("groq")
        assert isinstance(analyzer, GroqAnalyzer)
        assert analyzer.provider_name == "groq"

    def test_default_model_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIDSCOPE_GROQ_API_KEY", "fake-test-key")
        monkeypatch.delenv("VIDSCOPE_GROQ_MODEL", raising=False)
        # Should not raise — default model is hard-coded in the registry
        analyzer = build_analyzer("groq")
        assert isinstance(analyzer, GroqAnalyzer)

    def test_custom_model_via_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIDSCOPE_GROQ_API_KEY", "fake")
        monkeypatch.setenv("VIDSCOPE_GROQ_MODEL", "mixtral-8x7b-32768")
        analyzer = build_analyzer("groq")
        assert isinstance(analyzer, GroqAnalyzer)

    def test_error_message_includes_signup_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VIDSCOPE_GROQ_API_KEY", raising=False)
        with pytest.raises(ConfigError) as exc_info:
            build_analyzer("groq")
        assert "console.groq.com" in str(exc_info.value)


class TestBuildNvidiaAnalyzer:
    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VIDSCOPE_NVIDIA_API_KEY", raising=False)
        with pytest.raises(ConfigError, match="VIDSCOPE_NVIDIA_API_KEY"):
            build_analyzer("nvidia")

    def test_valid_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIDSCOPE_NVIDIA_API_KEY", "nvapi-fake")
        analyzer = build_analyzer("nvidia")
        assert isinstance(analyzer, NvidiaBuildAnalyzer)
        assert analyzer.provider_name == "nvidia"

    def test_error_message_mentions_build_nvidia(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VIDSCOPE_NVIDIA_API_KEY", raising=False)
        with pytest.raises(ConfigError) as exc_info:
            build_analyzer("nvidia")
        assert "build.nvidia.com" in str(exc_info.value)


class TestBuildOpenRouterAnalyzer:
    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VIDSCOPE_OPENROUTER_API_KEY", raising=False)
        with pytest.raises(ConfigError, match="VIDSCOPE_OPENROUTER_API_KEY"):
            build_analyzer("openrouter")

    def test_valid_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIDSCOPE_OPENROUTER_API_KEY", "sk-or-fake")
        analyzer = build_analyzer("openrouter")
        assert isinstance(analyzer, OpenRouterAnalyzer)

    def test_error_message_mentions_openrouter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VIDSCOPE_OPENROUTER_API_KEY", raising=False)
        with pytest.raises(ConfigError) as exc_info:
            build_analyzer("openrouter")
        assert "openrouter.ai" in str(exc_info.value)


class TestBuildOpenAIAnalyzer:
    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VIDSCOPE_OPENAI_API_KEY", raising=False)
        with pytest.raises(ConfigError, match="VIDSCOPE_OPENAI_API_KEY"):
            build_analyzer("openai")

    def test_valid_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIDSCOPE_OPENAI_API_KEY", "sk-fake")
        analyzer = build_analyzer("openai")
        assert isinstance(analyzer, OpenAIAnalyzer)

    def test_error_message_mentions_platform_openai(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VIDSCOPE_OPENAI_API_KEY", raising=False)
        with pytest.raises(ConfigError) as exc_info:
            build_analyzer("openai")
        assert "platform.openai.com" in str(exc_info.value)


class TestBuildAnthropicAnalyzer:
    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VIDSCOPE_ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ConfigError, match="VIDSCOPE_ANTHROPIC_API_KEY"):
            build_analyzer("anthropic")

    def test_valid_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIDSCOPE_ANTHROPIC_API_KEY", "sk-ant-fake")
        analyzer = build_analyzer("anthropic")
        assert isinstance(analyzer, AnthropicAnalyzer)
        assert analyzer.provider_name == "anthropic"

    def test_error_message_mentions_console_anthropic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VIDSCOPE_ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ConfigError) as exc_info:
            build_analyzer("anthropic")
        assert "console.anthropic.com" in str(exc_info.value)
