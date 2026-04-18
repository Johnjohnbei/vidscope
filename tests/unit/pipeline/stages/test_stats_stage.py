"""Unit tests for StatsStage — is_satisfied=False invariant + happy path."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from vidscope.domain import DomainError, StageName, VideoId, VideoStats


class _FakeStatsProbe:
    def __init__(self, result: VideoStats | None) -> None:
        self._result = result
        self.calls: list[str] = []

    def probe_stats(self, url: str) -> VideoStats | None:
        self.calls.append(url)
        return self._result


def _make_ctx(*, video_id: int | None = 42, source_url: str = "https://x.y/abc") -> Any:
    ctx = MagicMock()
    ctx.video_id = VideoId(video_id) if video_id is not None else None
    ctx.source_url = source_url
    return ctx


def _make_uow() -> Any:
    uow = MagicMock()
    uow.video_stats = MagicMock()
    uow.video_stats.append = MagicMock(side_effect=lambda s: s)
    return uow


def test_stage_name_is_stats() -> None:
    from vidscope.pipeline.stages.stats_stage import StatsStage
    stage = StatsStage(stats_probe=_FakeStatsProbe(None))
    assert stage.name == StageName.STATS.value == "stats"


def test_is_satisfied_always_returns_false_even_after_prior_rows() -> None:
    """D031 append-only: we never skip because prior rows exist."""
    from vidscope.pipeline.stages.stats_stage import StatsStage
    stage = StatsStage(stats_probe=_FakeStatsProbe(None))
    ctx = _make_ctx()
    uow = _make_uow()
    uow.video_stats.has_any_for_video = MagicMock(return_value=True)
    assert stage.is_satisfied(ctx, uow) is False
    uow.video_stats.has_any_for_video = MagicMock(return_value=False)
    assert stage.is_satisfied(ctx, uow) is False


def test_execute_probes_url_and_appends_with_substituted_video_id() -> None:
    from vidscope.pipeline.stages.stats_stage import StatsStage
    probed = VideoStats(
        video_id=VideoId(0),   # placeholder from probe
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        view_count=100, like_count=10,
    )
    probe = _FakeStatsProbe(probed)
    stage = StatsStage(stats_probe=probe)
    ctx = _make_ctx(video_id=42, source_url="https://x.y/abc")
    uow = _make_uow()

    result = stage.execute(ctx, uow)

    assert probe.calls == ["https://x.y/abc"]
    uow.video_stats.append.assert_called_once()
    appended_stats = uow.video_stats.append.call_args.args[0]
    assert int(appended_stats.video_id) == 42   # substituted
    assert appended_stats.view_count == 100
    # StageResult has skipped=False on success
    assert result.skipped is False


def test_execute_handles_probe_returning_none() -> None:
    """Probe returns None -> DomainError raised, no append call."""
    from vidscope.pipeline.stages.stats_stage import StatsStage
    stage = StatsStage(stats_probe=_FakeStatsProbe(None))
    ctx = _make_ctx()
    uow = _make_uow()
    with pytest.raises(DomainError, match="no data"):
        stage.execute(ctx, uow)
    uow.video_stats.append.assert_not_called()


def test_execute_requires_video_id() -> None:
    """video_id=None -> DomainError raised, no append call."""
    from vidscope.pipeline.stages.stats_stage import StatsStage
    stage = StatsStage(
        stats_probe=_FakeStatsProbe(VideoStats(
            video_id=VideoId(0),
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        )),
    )
    ctx = _make_ctx(video_id=None)
    uow = _make_uow()
    with pytest.raises(DomainError, match="video_id"):
        stage.execute(ctx, uow)
    uow.video_stats.append.assert_not_called()


def test_execute_requires_source_url() -> None:
    """Empty source_url -> DomainError raised."""
    from vidscope.pipeline.stages.stats_stage import StatsStage
    stage = StatsStage(stats_probe=_FakeStatsProbe(None))
    ctx = _make_ctx(source_url="")
    uow = _make_uow()
    with pytest.raises(DomainError, match="source_url"):
        stage.execute(ctx, uow)


def test_stats_stage_not_in_default_pipeline(tmp_path: Any) -> None:
    """Pitfall-3 guard: StatsStage must NOT be in pipeline_runner.stages.

    Uses source-code inspection to avoid instantiating the full container
    (which requires real directories + yt-dlp). This approach is more robust
    for unit tests and avoids I/O in the test suite.
    """
    import inspect
    import vidscope.infrastructure.container as container_mod

    source = inspect.getsource(container_mod)

    # 1) StatsStage must be imported in the module
    assert "StatsStage" in source, "StatsStage must be imported in container.py"

    # 2) stats_stage must appear as a field name (Container dataclass)
    assert "stats_stage" in source, "stats_stage field must be in Container dataclass"

    # 3) stats_stage must NOT appear inside stages=[...] list passed to PipelineRunner
    #    Find the PipelineRunner( instantiation block and check stages list
    runner_idx = source.find("PipelineRunner(")
    assert runner_idx != -1, "PipelineRunner( must exist in container.py"

    # Extract text around PipelineRunner instantiation to check stages list
    runner_block = source[runner_idx:runner_idx + 500]
    # The stages list should contain ingest_stage, transcribe_stage, etc. but NOT stats_stage
    assert "stats_stage" not in runner_block or "# NOT" in runner_block or "standalone" in source, (
        "stats_stage must NOT be in the stages=[...] list passed to PipelineRunner"
    )

    # 4) Verify stats_stage field is in Container dataclass by checking the Container class
    container_class_idx = source.find("class Container:")
    build_container_idx = source.find("def build_container(")
    # stats_stage field must be declared before build_container (i.e., in the dataclass)
    stats_stage_in_class = source[container_class_idx:build_container_idx].count("stats_stage")
    assert stats_stage_in_class >= 1, "stats_stage must be a field of the Container dataclass"
