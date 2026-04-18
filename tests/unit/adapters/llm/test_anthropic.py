"""Tests for AnthropicAnalyzer (native /v1/messages format)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from vidscope.adapters.llm import _base as base_module
from vidscope.adapters.llm.anthropic import AnthropicAnalyzer
from vidscope.domain import (
    Analysis,
    AnalysisError,
    Language,
    Transcript,
    TranscriptSegment,
    VideoId,
)


def _transcript() -> Transcript:
    return Transcript(
        video_id=VideoId(101),
        language=Language.ENGLISH,
        full_text="A short clip about woodworking.",
        segments=(
            TranscriptSegment(start=0.0, end=3.0, text="A short clip about woodworking."),
        ),
    )


def _anthropic_response(parsed: dict[str, Any]) -> dict[str, Any]:
    """Build a fake Anthropic /v1/messages response."""
    return {
        "id": "msg_fake",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-4-5",
        "content": [
            {"type": "text", "text": json.dumps(parsed)},
        ],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 50, "output_tokens": 80},
    }


def _client(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base_module.time, "sleep", lambda _: None)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(AnalysisError, match="api_key"):
            AnthropicAnalyzer(api_key="")

    def test_whitespace_only_api_key_raises(self) -> None:
        with pytest.raises(AnalysisError, match="api_key"):
            AnthropicAnalyzer(api_key="   ")

    def test_valid_construction(self) -> None:
        analyzer = AnthropicAnalyzer(api_key="sk-ant-fake")
        assert analyzer.provider_name == "anthropic"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestAnalyzeHappyPath:
    def test_returns_analysis_with_provider_name(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_anthropic_response(
                    {
                        "language": "en",
                        "keywords": ["woodworking", "tools"],
                        "topics": ["crafts"],
                        "score": 75,
                        "summary": "About woodworking tools.",
                    }
                ),
            )

        analyzer = AnthropicAnalyzer(api_key="sk-ant-fake", client=_client(handler))
        result = analyzer.analyze(_transcript())

        assert isinstance(result, Analysis)
        assert result.provider == "anthropic"
        assert "woodworking" in result.keywords
        assert result.score == 75.0

    def test_targets_messages_endpoint(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(200, json=_anthropic_response({"score": 50}))

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        analyzer.analyze(_transcript())

        assert "api.anthropic.com" in captured["url"]
        assert captured["url"].endswith("/v1/messages")
        assert "/chat/completions" not in captured["url"]

    def test_uses_x_api_key_header_not_bearer(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, json=_anthropic_response({"score": 50}))

        analyzer = AnthropicAnalyzer(api_key="sk-ant-secret", client=_client(handler))
        analyzer.analyze(_transcript())

        assert captured["headers"]["x-api-key"] == "sk-ant-secret"
        # Bearer header NOT used
        assert "authorization" not in captured["headers"]

    def test_sends_anthropic_version_header(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, json=_anthropic_response({"score": 50}))

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        analyzer.analyze(_transcript())

        assert "anthropic-version" in captured["headers"]
        assert captured["headers"]["anthropic-version"] == "2023-06-01"

    def test_request_body_has_top_level_system_field(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_anthropic_response({"score": 50}))

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        analyzer.analyze(_transcript())

        # Anthropic requires top-level system, not a system role message
        assert "system" in captured["body"]
        assert isinstance(captured["body"]["system"], str)
        assert len(captured["body"]["system"]) > 0
        # Confirm no system message in messages array
        for msg in captured["body"]["messages"]:
            assert msg["role"] != "system"

    def test_max_tokens_is_set(self) -> None:
        # Anthropic REQUIRES max_tokens — this would 400 otherwise
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_anthropic_response({"score": 50}))

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        analyzer.analyze(_transcript())

        assert "max_tokens" in captured["body"]
        assert isinstance(captured["body"]["max_tokens"], int)

    def test_no_response_format_field(self) -> None:
        # Anthropic doesn't support response_format — sending it would 400
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_anthropic_response({"score": 50}))

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        analyzer.analyze(_transcript())

        assert "response_format" not in captured["body"]

    def test_uses_configured_model(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_anthropic_response({"score": 50}))

        analyzer = AnthropicAnalyzer(
            api_key="sk-ant-x",
            model="claude-sonnet-4-6",
            client=_client(handler),
        )
        analyzer.analyze(_transcript())

        assert captured["body"]["model"] == "claude-sonnet-4-6"

    def test_handles_multi_block_content(self) -> None:
        # Anthropic responses can have multiple text blocks; we should
        # join them. Only text blocks count — tool_use, image are skipped.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "text", "text": '{"keywords": ["a"], '},
                        {"type": "text", "text": '"score": 60}'},
                    ]
                },
            )

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        result = analyzer.analyze(_transcript())
        assert result.score == 60.0


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestAnalyzeErrors:
    def test_429_then_success(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 2:
                return httpx.Response(429, text="rate limited")
            return httpx.Response(200, json=_anthropic_response({"score": 50}))

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        analyzer.analyze(_transcript())
        assert len(calls) == 2

    def test_401_fails_fast(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="invalid api key")

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        with pytest.raises(AnalysisError, match="401"):
            analyzer.analyze(_transcript())

    def test_529_overload_retry(self) -> None:
        # 529 is Anthropic's "overloaded" status — should be retried as 5xx
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 2:
                return httpx.Response(529, text="overloaded")
            return httpx.Response(200, json=_anthropic_response({"score": 50}))

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        analyzer.analyze(_transcript())
        assert len(calls) == 2

    def test_response_missing_content_array_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "msg_x"})

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        with pytest.raises(AnalysisError, match="content"):
            analyzer.analyze(_transcript())

    def test_response_with_only_non_text_blocks_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "tool_use", "id": "x", "name": "y", "input": {}},
                    ]
                },
            )

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        with pytest.raises(AnalysisError, match="text blocks"):
            analyzer.analyze(_transcript())

    def test_text_block_with_malformed_json_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "text", "text": "this is not parseable JSON"},
                    ]
                },
            )

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        with pytest.raises(AnalysisError, match="parseable"):
            analyzer.analyze(_transcript())

    def test_non_json_body_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=b"not json",
                headers={"content-type": "text/plain"},
            )

        analyzer = AnthropicAnalyzer(api_key="sk-ant-x", client=_client(handler))
        with pytest.raises(AnalysisError, match="non-JSON"):
            analyzer.analyze(_transcript())


# ---------------------------------------------------------------------------
# M010 — extended JSON fields via MockTransport (Anthropic native format)
# ---------------------------------------------------------------------------


class TestM010ExtendedAnthropicJson:
    """M010: anthropic must surface new fields via make_analysis."""

    def _transcript(self) -> Transcript:
        return Transcript(
            video_id=VideoId(1),
            language=Language.ENGLISH,
            full_text="hello",
            segments=(),
        )

    def _mock_anthropic_response(self, payload: dict[str, Any]) -> httpx.Response:
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": json.dumps(payload)}]
        })

    def test_happy_path_all_m010_fields(self) -> None:
        from vidscope.domain import ContentType, SentimentLabel
        payload = {
            "language": "en",
            "keywords": ["code"],
            "topics": ["code"],
            "verticals": ["tech"],
            "score": 80,
            "information_density": 65,
            "actionability": 85,
            "novelty": 50,
            "production_quality": 70,
            "sentiment": "positive",
            "is_sponsored": False,
            "content_type": "tutorial",
            "reasoning": "Structured technical tutorial.",
            "summary": "A tutorial",
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_anthropic_response(payload)
        analyzer = AnthropicAnalyzer(api_key="sk-ant-test", client=_client(handler))
        result = analyzer.analyze(self._transcript())
        assert result.verticals == ("tech",)
        assert result.information_density == 65.0
        assert result.sentiment is SentimentLabel.POSITIVE
        assert result.content_type is ContentType.TUTORIAL
        assert result.reasoning is not None

    def test_partial_m010_fields(self) -> None:
        from vidscope.domain import SentimentLabel
        payload = {
            "language": "en",
            "keywords": ["a"],
            "topics": [],
            "score": 50,
            "summary": "x",
            "sentiment": "negative",
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_anthropic_response(payload)
        analyzer = AnthropicAnalyzer(api_key="sk-ant-test", client=_client(handler))
        result = analyzer.analyze(self._transcript())
        assert result.sentiment is SentimentLabel.NEGATIVE
        assert result.content_type is None
        assert result.reasoning is None
        assert result.verticals == ()

    def test_invalid_m010_values_safe(self) -> None:
        payload = {
            "language": "en",
            "keywords": [],
            "topics": [],
            "score": 50,
            "summary": "x",
            "sentiment": "thrilled",
            "content_type": "podcast",
            "is_sponsored": "maybe",
            "production_quality": "great",
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_anthropic_response(payload)
        analyzer = AnthropicAnalyzer(api_key="sk-ant-test", client=_client(handler))
        result = analyzer.analyze(self._transcript())
        assert result.sentiment is None
        assert result.content_type is None
        assert result.is_sponsored is None
        assert result.production_quality is None
