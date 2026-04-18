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


# ---------------------------------------------------------------------------
# M010 — extended JSON fields via MockTransport
# ---------------------------------------------------------------------------


class TestM010ExtendedOpenAIJson:
    """M010: openai must surface new fields via make_analysis."""

    def _transcript(self) -> Transcript:
        return Transcript(
            video_id=VideoId(1),
            language=Language.ENGLISH,
            full_text="hello",
            segments=(),
        )

    def _mock_openai_response(self, payload: dict[str, Any]) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(payload)}}]
        })

    def test_happy_path_all_m010_fields(self) -> None:
        from vidscope.domain import ContentType, SentimentLabel
        payload = {
            "language": "en",
            "keywords": ["garden", "tips"],
            "topics": ["gardening"],
            "verticals": ["education", "fitness"],
            "score": 80,
            "information_density": 72,
            "actionability": 88,
            "novelty": 45,
            "production_quality": 68,
            "sentiment": "positive",
            "is_sponsored": False,
            "content_type": "tutorial",
            "reasoning": "Step-by-step gardening tutorial with actionable tips.",
            "summary": "Gardening tips tutorial",
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_openai_response(payload)
        analyzer = OpenAIAnalyzer(api_key="sk-test", client=_client(handler))
        result = analyzer.analyze(self._transcript())
        assert result.verticals == ("education", "fitness")
        assert result.information_density == 72.0
        assert result.sentiment is SentimentLabel.POSITIVE
        assert result.content_type is ContentType.TUTORIAL
        assert result.reasoning is not None

    def test_partial_m010_fields(self) -> None:
        from vidscope.domain import SentimentLabel
        payload = {
            "language": "en",
            "keywords": ["a"],
            "topics": ["a"],
            "score": 50,
            "summary": "ok",
            "sentiment": "mixed",
            "is_sponsored": False,
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_openai_response(payload)
        analyzer = OpenAIAnalyzer(api_key="sk-test", client=_client(handler))
        result = analyzer.analyze(self._transcript())
        assert result.sentiment is SentimentLabel.MIXED
        assert result.is_sponsored is False
        assert result.content_type is None
        assert result.information_density is None
        assert result.verticals == ()

    def test_invalid_m010_values_safe(self) -> None:
        payload = {
            "language": "en",
            "keywords": [],
            "topics": [],
            "score": 50,
            "summary": "x",
            "sentiment": "ambivalent",
            "content_type": "infomercial",
            "is_sponsored": 99,
            "novelty": "fresh",
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_openai_response(payload)
        analyzer = OpenAIAnalyzer(api_key="sk-test", client=_client(handler))
        result = analyzer.analyze(self._transcript())
        assert result.sentiment is None
        assert result.content_type is None
        assert result.is_sponsored is None
        assert result.novelty is None
