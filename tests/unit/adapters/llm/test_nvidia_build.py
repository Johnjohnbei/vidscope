"""Tests for NvidiaBuildAnalyzer.

All tests use httpx.MockTransport so there is zero real network.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from vidscope.adapters.llm import _base as base_module
from vidscope.adapters.llm.nvidia_build import NvidiaBuildAnalyzer
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
        video_id=VideoId(7),
        language=Language.ENGLISH,
        full_text="A short clip about machine learning.",
        segments=(
            TranscriptSegment(start=0.0, end=2.0, text="A short clip about machine learning."),
        ),
    )


def _openai_response(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "cmpl-fake",
        "object": "chat.completion",
        "model": "fake-model",
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
            NvidiaBuildAnalyzer(api_key="")

    def test_whitespace_only_api_key_raises(self) -> None:
        with pytest.raises(AnalysisError, match="api_key"):
            NvidiaBuildAnalyzer(api_key="   ")

    def test_valid_construction(self) -> None:
        analyzer = NvidiaBuildAnalyzer(api_key="nvapi-fake")
        assert analyzer.provider_name == "nvidia"


class TestAnalyzeHappyPath:
    def test_returns_analysis_with_provider_name(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_openai_response({"keywords": ["ml"], "score": 65}),
            )

        analyzer = NvidiaBuildAnalyzer(api_key="nvapi-fake", client=_client(handler))
        result = analyzer.analyze(_transcript())
        assert isinstance(result, Analysis)
        assert result.provider == "nvidia"
        assert result.score == 65.0

    def test_targets_nvidia_endpoint(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = NvidiaBuildAnalyzer(api_key="nvapi-x", client=_client(handler))
        analyzer.analyze(_transcript())
        assert "integrate.api.nvidia.com" in captured["url"]
        assert "/chat/completions" in captured["url"]

    def test_authorization_header(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = NvidiaBuildAnalyzer(api_key="nvapi-secret", client=_client(handler))
        analyzer.analyze(_transcript())
        assert captured["headers"]["authorization"] == "Bearer nvapi-secret"

    def test_uses_configured_model(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = NvidiaBuildAnalyzer(
            api_key="nvapi-x",
            model="meta/llama-3.3-70b-instruct",
            client=_client(handler),
        )
        analyzer.analyze(_transcript())
        assert captured["body"]["model"] == "meta/llama-3.3-70b-instruct"


class TestAnalyzeErrors:
    def test_429_then_success(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 2:
                return httpx.Response(429, text="rate limited")
            return httpx.Response(200, json=_openai_response({"score": 50}))

        analyzer = NvidiaBuildAnalyzer(api_key="nvapi-x", client=_client(handler))
        result = analyzer.analyze(_transcript())
        assert result.score == 50.0
        assert len(calls) == 2

    def test_401_fails_fast(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="invalid api key")

        analyzer = NvidiaBuildAnalyzer(api_key="nvapi-x", client=_client(handler))
        with pytest.raises(AnalysisError, match="401"):
            analyzer.analyze(_transcript())

    def test_response_missing_choices(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "x"})

        analyzer = NvidiaBuildAnalyzer(api_key="nvapi-x", client=_client(handler))
        with pytest.raises(AnalysisError, match="choices"):
            analyzer.analyze(_transcript())
