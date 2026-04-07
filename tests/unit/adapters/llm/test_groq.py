"""Tests for GroqAnalyzer.

All tests use httpx.MockTransport so there is zero real network.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from vidscope.adapters.llm import _base as base_module
from vidscope.adapters.llm.groq import GroqAnalyzer
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
        video_id=VideoId(42),
        language=Language.ENGLISH,
        full_text="A short transcript about Python programming and tutorials.",
        segments=(
            TranscriptSegment(
                start=0.0,
                end=5.0,
                text="A short transcript about Python programming and tutorials.",
            ),
        ),
    )


def _groq_response(parsed_content: dict[str, Any]) -> dict[str, Any]:
    """Build a fake Groq chat-completion response wrapping ``parsed_content``."""
    return {
        "id": "chatcmpl-fake-123",
        "object": "chat.completion",
        "model": "llama-3.1-8b-instant",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(parsed_content),
                },
                "finish_reason": "stop",
            }
        ],
    }


def _client(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every retry sleep instant so the test suite stays fast."""
    monkeypatch.setattr(base_module.time, "sleep", lambda _: None)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(AnalysisError, match="api_key"):
            GroqAnalyzer(api_key="")

    def test_whitespace_only_api_key_raises(self) -> None:
        with pytest.raises(AnalysisError, match="api_key"):
            GroqAnalyzer(api_key="   ")

    def test_valid_construction(self) -> None:
        analyzer = GroqAnalyzer(api_key="fake-key")
        assert analyzer.provider_name == "groq"

    def test_custom_model(self) -> None:
        analyzer = GroqAnalyzer(api_key="fake", model="mixtral-8x7b-32768")
        assert analyzer.provider_name == "groq"

    def test_strips_whitespace_from_api_key(self) -> None:
        # No exception means the strip happened
        analyzer = GroqAnalyzer(api_key="  fake-key  ")
        assert analyzer.provider_name == "groq"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestAnalyzeHappyPath:
    def test_returns_analysis_with_provider_name(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_groq_response(
                    {
                        "language": "en",
                        "keywords": ["python", "programming"],
                        "topics": ["tutorial"],
                        "score": 70,
                        "summary": "About Python programming.",
                    }
                ),
            )

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="fake-key", client=client)
        result = analyzer.analyze(_transcript())

        assert isinstance(result, Analysis)
        assert result.provider == "groq"
        assert result.video_id == VideoId(42)
        assert "python" in result.keywords
        assert result.score == 70.0

    def test_authorization_header_present(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(
                200,
                json=_groq_response({"keywords": [], "score": 50}),
            )

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="my-secret-key", client=client)
        analyzer.analyze(_transcript())

        assert captured["headers"]["authorization"] == "Bearer my-secret-key"

    def test_request_targets_groq_endpoint(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(
                200, json=_groq_response({"keywords": [], "score": 50})
            )

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="fake", client=client)
        analyzer.analyze(_transcript())

        assert "api.groq.com" in captured["url"]
        assert "/chat/completions" in captured["url"]

    def test_uses_configured_model(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200, json=_groq_response({"keywords": [], "score": 50})
            )

        client = _client(handler)
        analyzer = GroqAnalyzer(
            api_key="fake", model="custom-model-9000", client=client
        )
        analyzer.analyze(_transcript())

        assert captured["body"]["model"] == "custom-model-9000"

    def test_request_uses_json_response_format(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200, json=_groq_response({"keywords": [], "score": 50})
            )

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="fake", client=client)
        analyzer.analyze(_transcript())

        assert captured["body"]["response_format"]["type"] == "json_object"


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
            return httpx.Response(
                200,
                json=_groq_response({"keywords": ["a"], "score": 50}),
            )

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="fake", client=client)
        result = analyzer.analyze(_transcript())

        assert result.score == 50.0
        assert len(calls) == 2

    def test_401_fails_fast(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="invalid api key")

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="fake", client=client)
        with pytest.raises(AnalysisError, match="401"):
            analyzer.analyze(_transcript())

    def test_response_missing_choices_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "x", "model": "y"})

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="fake", client=client)
        with pytest.raises(AnalysisError, match="choices"):
            analyzer.analyze(_transcript())

    def test_response_with_non_json_body_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=b"not json at all",
                headers={"content-type": "text/plain"},
            )

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="fake", client=client)
        with pytest.raises(AnalysisError, match="non-JSON"):
            analyzer.analyze(_transcript())

    def test_message_missing_content_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant"}},
                    ]
                },
            )

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="fake", client=client)
        with pytest.raises(AnalysisError, match="content"):
            analyzer.analyze(_transcript())

    def test_message_content_with_malformed_json_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "not parseable as json",
                            }
                        }
                    ]
                },
            )

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="fake", client=client)
        with pytest.raises(AnalysisError, match="parseable"):
            analyzer.analyze(_transcript())

    def test_timeout_then_success(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 2:
                raise httpx.ReadTimeout("timed out", request=request)
            return httpx.Response(
                200,
                json=_groq_response({"keywords": ["x"], "score": 60}),
            )

        client = _client(handler)
        analyzer = GroqAnalyzer(api_key="fake", client=client)
        result = analyzer.analyze(_transcript())

        assert result.score == 60.0
        assert len(calls) == 2
