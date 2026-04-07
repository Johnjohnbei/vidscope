"""Tests for OpenAIAnalyzer."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from vidscope.adapters.llm import _base as base_module
from vidscope.adapters.llm.openai import OpenAIAnalyzer
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
        video_id=VideoId(99),
        language=Language.ENGLISH,
        full_text="A short clip about gardening tips.",
        segments=(
            TranscriptSegment(start=0.0, end=4.0, text="A short clip about gardening tips."),
        ),
    )


def _openai_response(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": json.dumps(parsed)},
                "finish_reason": "stop",
            }
        ],
    }


def _client(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base_module.time, "sleep", lambda _: None)


class TestConstruction:
    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(AnalysisError, match="api_key"):
            OpenAIAnalyzer(api_key="")

    def test_valid_construction(self) -> None:
        analyzer = OpenAIAnalyzer(api_key="sk-fake")
        assert analyzer.provider_name == "openai"


class TestAnalyzeHappyPath:
    def test_returns_analysis(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_openai_response({"keywords": ["gardening"], "score": 80}),
            )

        analyzer = OpenAIAnalyzer(api_key="sk-fake", client=_client(handler))
        result = analyzer.analyze(_transcript())
        assert isinstance(result, Analysis)
        assert result.provider == "openai"
        assert result.score == 80.0

    def test_targets_openai_endpoint(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenAIAnalyzer(api_key="sk-x", client=_client(handler))
        analyzer.analyze(_transcript())
        assert "api.openai.com" in captured["url"]
        assert "/v1/chat/completions" in captured["url"]

    def test_authorization_header(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenAIAnalyzer(api_key="sk-secret", client=_client(handler))
        analyzer.analyze(_transcript())
        assert captured["headers"]["authorization"] == "Bearer sk-secret"

    def test_default_model(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenAIAnalyzer(api_key="sk-x", client=_client(handler))
        analyzer.analyze(_transcript())
        assert captured["body"]["model"] == "gpt-4o-mini"

    def test_custom_model(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenAIAnalyzer(api_key="sk-x", model="gpt-4o", client=_client(handler))
        analyzer.analyze(_transcript())
        assert captured["body"]["model"] == "gpt-4o"


class TestAnalyzeErrors:
    def test_429_retry(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 2:
                return httpx.Response(429, text="rate limited")
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenAIAnalyzer(api_key="sk-x", client=_client(handler))
        analyzer.analyze(_transcript())
        assert len(calls) == 2

    def test_401_fails_fast(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="invalid")

        analyzer = OpenAIAnalyzer(api_key="sk-x", client=_client(handler))
        with pytest.raises(AnalysisError, match="401"):
            analyzer.analyze(_transcript())

    def test_500_retry_then_success(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 3:
                return httpx.Response(503, text="overloaded")
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenAIAnalyzer(api_key="sk-x", client=_client(handler))
        analyzer.analyze(_transcript())
        assert len(calls) == 3
