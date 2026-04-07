"""Tests for OpenRouterAnalyzer."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from vidscope.adapters.llm import _base as base_module
from vidscope.adapters.llm.openrouter import OpenRouterAnalyzer
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
        video_id=VideoId(11),
        language=Language.ENGLISH,
        full_text="Quick clip about cooking pasta.",
        segments=(
            TranscriptSegment(start=0.0, end=3.0, text="Quick clip about cooking pasta."),
        ),
    )


def _openai_response(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "or-fake",
        "object": "chat.completion",
        "model": "fake",
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
            OpenRouterAnalyzer(api_key="")

    def test_valid_construction(self) -> None:
        analyzer = OpenRouterAnalyzer(api_key="sk-or-fake")
        assert analyzer.provider_name == "openrouter"


class TestAnalyzeHappyPath:
    def test_returns_analysis(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_openai_response({"keywords": ["pasta"], "score": 55}),
            )

        analyzer = OpenRouterAnalyzer(api_key="sk-or-fake", client=_client(handler))
        result = analyzer.analyze(_transcript())
        assert isinstance(result, Analysis)
        assert result.provider == "openrouter"

    def test_targets_openrouter_endpoint(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenRouterAnalyzer(api_key="sk-or-x", client=_client(handler))
        analyzer.analyze(_transcript())
        assert "openrouter.ai" in captured["url"]
        assert "/api/v1/chat/completions" in captured["url"]

    def test_authorization_header(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenRouterAnalyzer(api_key="sk-or-secret", client=_client(handler))
        analyzer.analyze(_transcript())
        assert captured["headers"]["authorization"] == "Bearer sk-or-secret"

    def test_sends_app_identification_headers(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenRouterAnalyzer(api_key="sk-or-x", client=_client(handler))
        analyzer.analyze(_transcript())
        assert captured["headers"]["x-title"] == "VidScope"
        assert "github.com" in captured["headers"]["http-referer"]

    def test_uses_configured_model(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenRouterAnalyzer(
            api_key="sk-or-x",
            model="anthropic/claude-3.5-sonnet",
            client=_client(handler),
        )
        analyzer.analyze(_transcript())
        assert captured["body"]["model"] == "anthropic/claude-3.5-sonnet"


class TestAnalyzeErrors:
    def test_429_retry(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 2:
                return httpx.Response(429, text="rate limited")
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = OpenRouterAnalyzer(api_key="sk-or-x", client=_client(handler))
        analyzer.analyze(_transcript())
        assert len(calls) == 2

    def test_401_fails_fast(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="invalid")

        analyzer = OpenRouterAnalyzer(api_key="sk-or-x", client=_client(handler))
        with pytest.raises(AnalysisError, match="401"):
            analyzer.analyze(_transcript())

    def test_malformed_content(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "not json"}}
                    ]
                },
            )

        analyzer = OpenRouterAnalyzer(api_key="sk-or-x", client=_client(handler))
        with pytest.raises(AnalysisError, match="parseable"):
            analyzer.analyze(_transcript())
