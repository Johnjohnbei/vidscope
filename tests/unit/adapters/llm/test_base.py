"""Tests for the shared LLM helpers in vidscope.adapters.llm._base.

Every test runs against either pure-Python helpers (no I/O) or
:class:`httpx.MockTransport` so there is zero real network traffic.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from vidscope.adapters.llm._base import (
    DEFAULT_MAX_ATTEMPTS,
    LlmCallContext,
    build_messages,
    call_with_retry,
    make_analysis,
    parse_llm_json,
)
from vidscope.domain import (
    Analysis,
    AnalysisError,
    Language,
    Transcript,
    TranscriptSegment,
    VideoId,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _transcript(
    text: str = "Hello world this is a test",
    *,
    video_id: int = 1,
    language: Language = Language.ENGLISH,
) -> Transcript:
    return Transcript(
        video_id=VideoId(video_id),
        language=language,
        full_text=text,
        segments=(
            TranscriptSegment(start=0.0, end=1.0, text=text),
        ),
    )


def _no_sleep(_seconds: float) -> None:
    pass


# ---------------------------------------------------------------------------
# build_messages
# ---------------------------------------------------------------------------


class TestBuildMessages:
    def test_returns_system_and_user(self) -> None:
        msgs = build_messages(_transcript())
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_user_message_includes_language_hint(self) -> None:
        msgs = build_messages(_transcript(language=Language.FRENCH))
        assert "fr" in msgs[1]["content"]

    def test_user_message_includes_transcript_text(self) -> None:
        msgs = build_messages(_transcript("a unique probe phrase"))
        assert "a unique probe phrase" in msgs[1]["content"]

    def test_empty_transcript_uses_placeholder(self) -> None:
        msgs = build_messages(_transcript(""))
        assert "[no speech detected]" in msgs[1]["content"]

    def test_system_message_asks_for_strict_json(self) -> None:
        msgs = build_messages(_transcript())
        sys_text = msgs[0]["content"]
        assert "JSON" in sys_text
        assert "keywords" in sys_text
        assert "summary" in sys_text


# ---------------------------------------------------------------------------
# parse_llm_json
# ---------------------------------------------------------------------------


class TestParseLlmJson:
    def test_bare_json(self) -> None:
        raw = '{"keywords": ["a", "b"], "score": 50}'
        result = parse_llm_json(raw)
        assert result["keywords"] == ["a", "b"]
        assert result["score"] == 50

    def test_markdown_fenced_json(self) -> None:
        raw = '```json\n{"keywords": ["x"], "score": 10}\n```'
        result = parse_llm_json(raw)
        assert result["keywords"] == ["x"]

    def test_untagged_fence(self) -> None:
        raw = '```\n{"keywords": ["y"]}\n```'
        result = parse_llm_json(raw)
        assert result["keywords"] == ["y"]

    def test_json_with_trailing_prose(self) -> None:
        raw = (
            'Here is the analysis:\n{"keywords": ["z"], "score": 80}\n'
            'Hope that helps!'
        )
        result = parse_llm_json(raw)
        assert result["keywords"] == ["z"]

    def test_empty_response_raises(self) -> None:
        with pytest.raises(AnalysisError, match="empty"):
            parse_llm_json("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(AnalysisError, match="empty"):
            parse_llm_json("   \n\n  ")

    def test_no_json_at_all_raises(self) -> None:
        with pytest.raises(AnalysisError, match="parseable"):
            parse_llm_json("just some prose with no braces anywhere")

    def test_malformed_json_in_fence_raises(self) -> None:
        with pytest.raises(AnalysisError, match="malformed"):
            parse_llm_json('```json\n{not valid json}\n```')

    def test_json_with_nested_objects(self) -> None:
        raw = '{"keywords": ["a"], "meta": {"nested": true}}'
        result = parse_llm_json(raw)
        assert result["meta"]["nested"] is True


# ---------------------------------------------------------------------------
# call_with_retry
# ---------------------------------------------------------------------------


def _make_client(handler: Any) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def _ctx() -> LlmCallContext:
    return LlmCallContext(
        method="POST",
        url="https://api.example.com/v1/chat/completions",
        headers={"Authorization": "Bearer fake"},
        json_body={"model": "test", "messages": []},
        timeout=5.0,
        max_attempts=3,
    )


class TestCallWithRetry:
    def test_happy_path_returns_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        with _make_client(handler) as client:
            response = call_with_retry(client, _ctx(), sleep=_no_sleep)
            assert response.status_code == 200

    def test_429_then_success(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 2:
                return httpx.Response(429, text="rate limited")
            return httpx.Response(200, json={"ok": True})

        with _make_client(handler) as client:
            response = call_with_retry(client, _ctx(), sleep=_no_sleep)
            assert response.status_code == 200
            assert len(calls) == 2

    def test_500_then_success(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 3:
                return httpx.Response(503, text="service unavailable")
            return httpx.Response(200, json={"ok": True})

        with _make_client(handler) as client:
            response = call_with_retry(client, _ctx(), sleep=_no_sleep)
            assert response.status_code == 200
            assert len(calls) == 3

    def test_429_exhausts_retries_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="still rate limited")

        with _make_client(handler) as client, pytest.raises(
            AnalysisError, match="429"
        ):
            call_with_retry(client, _ctx(), sleep=_no_sleep)

    def test_400_fails_fast(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(400, text="bad request")

        with _make_client(handler) as client, pytest.raises(
            AnalysisError, match="400"
        ):
            call_with_retry(client, _ctx(), sleep=_no_sleep)

        assert len(calls) == 1  # No retry on 4xx

    def test_401_fails_fast(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="unauthorized")

        with _make_client(handler) as client, pytest.raises(
            AnalysisError, match="401"
        ):
            call_with_retry(client, _ctx(), sleep=_no_sleep)

    def test_timeout_then_success(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 2:
                raise httpx.ReadTimeout("timed out", request=request)
            return httpx.Response(200, json={"ok": True})

        with _make_client(handler) as client:
            response = call_with_retry(client, _ctx(), sleep=_no_sleep)
            assert response.status_code == 200

    def test_timeout_exhausts_retries(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        with _make_client(handler) as client, pytest.raises(
            AnalysisError, match="timed out"
        ):
            call_with_retry(client, _ctx(), sleep=_no_sleep)

    def test_default_max_attempts(self) -> None:
        assert DEFAULT_MAX_ATTEMPTS == 3


# ---------------------------------------------------------------------------
# make_analysis
# ---------------------------------------------------------------------------


class TestMakeAnalysis:
    def test_happy_path(self) -> None:
        parsed = {
            "language": "en",
            "keywords": ["python", "tutorial", "code"],
            "topics": ["programming"],
            "score": 75,
            "summary": "A short Python tutorial.",
        }
        result = make_analysis(
            parsed, _transcript(), provider="groq"
        )
        assert isinstance(result, Analysis)
        assert result.provider == "groq"
        assert result.video_id == VideoId(1)
        assert result.keywords == ("python", "tutorial", "code")
        assert result.topics == ("programming",)
        assert result.score == 75.0
        assert result.summary == "A short Python tutorial."

    def test_keywords_lowercased_and_capped(self) -> None:
        parsed = {"keywords": [f"KW{i}" for i in range(20)]}
        result = make_analysis(parsed, _transcript(), provider="groq")
        assert len(result.keywords) == 10
        assert all(k == k.lower() for k in result.keywords)

    def test_topics_capped(self) -> None:
        parsed = {"topics": [f"topic-{i}" for i in range(10)]}
        result = make_analysis(parsed, _transcript(), provider="groq")
        assert len(result.topics) == 3

    def test_score_clamped_to_0_100(self) -> None:
        parsed = {"score": 150}
        result = make_analysis(parsed, _transcript(), provider="groq")
        assert result.score == 100.0

        parsed = {"score": -10}
        result = make_analysis(parsed, _transcript(), provider="groq")
        assert result.score == 0.0

    def test_score_invalid_falls_back_to_none(self) -> None:
        parsed = {"score": "not a number"}
        result = make_analysis(parsed, _transcript(), provider="groq")
        assert result.score is None

    def test_summary_truncated_to_200_chars(self) -> None:
        long = "x" * 500
        result = make_analysis(
            {"summary": long}, _transcript(), provider="groq"
        )
        assert result.summary is not None
        assert len(result.summary) == 200

    def test_missing_keys_fall_back_to_safe_defaults(self) -> None:
        result = make_analysis({}, _transcript(), provider="groq")
        assert result.keywords == ()
        assert result.topics == ()
        assert result.score is None
        assert result.summary is None

    def test_keywords_filters_empty_strings(self) -> None:
        parsed = {"keywords": ["valid", "", "  ", None, "another"]}
        result = make_analysis(parsed, _transcript(), provider="groq")
        assert result.keywords == ("valid", "another")

    def test_language_fallback_when_transcript_unknown(self) -> None:
        parsed = {"language": "fr"}
        result = make_analysis(
            parsed,
            _transcript(language=Language.UNKNOWN),
            provider="groq",
        )
        assert result.language == Language.FRENCH

    def test_transcript_language_takes_precedence(self) -> None:
        parsed = {"language": "fr"}  # LLM says French
        result = make_analysis(
            parsed,
            _transcript(language=Language.ENGLISH),  # Whisper says English
            provider="groq",
        )
        assert result.language == Language.ENGLISH

    def test_non_dict_raises(self) -> None:
        with pytest.raises(AnalysisError, match="dict"):
            make_analysis(["not", "a", "dict"], _transcript(), provider="groq")  # type: ignore[arg-type]
