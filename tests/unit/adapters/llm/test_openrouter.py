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


# ---------------------------------------------------------------------------
# M010 — extended JSON fields via MockTransport
# ---------------------------------------------------------------------------


class TestM010ExtendedOpenRouterJson:
    """M010: openrouter must surface new fields via make_analysis."""

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
            "keywords": ["cooking", "pasta"],
            "topics": ["italian food"],
            "verticals": ["food", "travel"],
            "score": 65,
            "information_density": 55,
            "actionability": 70,
            "novelty": 35,
            "production_quality": 65,
            "sentiment": "positive",
            "is_sponsored": False,
            "content_type": "vlog",
            "reasoning": "Food vlog with positive tone about cooking.",
            "summary": "Cooking pasta tutorial",
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_openai_response(payload)
        analyzer = OpenRouterAnalyzer(api_key="sk-or-test", client=_client(handler))
        result = analyzer.analyze(self._transcript())
        assert result.verticals == ("food", "travel")
        assert result.information_density == 55.0
        assert result.sentiment is SentimentLabel.POSITIVE
        assert result.content_type is ContentType.VLOG
        assert result.reasoning is not None

    def test_partial_m010_fields(self) -> None:
        from vidscope.domain import ContentType
        payload = {
            "language": "en",
            "keywords": ["a"],
            "topics": ["a"],
            "score": 50,
            "summary": "ok",
            "content_type": "review",
            "is_sponsored": True,
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_openai_response(payload)
        analyzer = OpenRouterAnalyzer(api_key="sk-or-test", client=_client(handler))
        result = analyzer.analyze(self._transcript())
        assert result.content_type is ContentType.REVIEW
        assert result.is_sponsored is True
        assert result.sentiment is None
        assert result.information_density is None
        assert result.verticals == ()

    def test_invalid_m010_values_safe(self) -> None:
        payload = {
            "language": "en",
            "keywords": [],
            "topics": [],
            "score": 50,
            "summary": "x",
            "sentiment": "happy",
            "content_type": "webinar",
            "is_sponsored": "not sure",
            "actionability": "low",
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_openai_response(payload)
        analyzer = OpenRouterAnalyzer(api_key="sk-or-test", client=_client(handler))
        result = analyzer.analyze(self._transcript())
        assert result.sentiment is None
        assert result.content_type is None
        assert result.is_sponsored is None
        assert result.actionability is None
