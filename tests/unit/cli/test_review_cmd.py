"""CliRunner tests for `vidscope review` (M011/S01/R056)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from vidscope.cli.app import app
from vidscope.domain import TrackingStatus, VideoId, VideoTracking

runner = CliRunner()


def _make_container(*, existing: VideoTracking | None = None) -> MagicMock:
    """Return a fake container whose UoW exposes a fake video_tracking repo."""

    class _FakeTrackingRepo:
        def __init__(self) -> None:
            self._store: dict[int, VideoTracking] = {}
            if existing is not None:
                self._store[int(existing.video_id)] = existing

        def get_for_video(self, video_id: VideoId) -> VideoTracking | None:
            return self._store.get(int(video_id))

        def upsert(self, tracking: VideoTracking) -> VideoTracking:
            persisted = VideoTracking(
                video_id=tracking.video_id,
                status=tracking.status,
                starred=tracking.starred,
                notes=tracking.notes,
                id=1,
            )
            self._store[int(tracking.video_id)] = persisted
            return persisted

        def list_by_status(self, status: TrackingStatus, *, limit: int = 1000) -> list[VideoTracking]:
            return []

        def list_starred(self, *, limit: int = 1000) -> list[VideoTracking]:
            return []

    class _FakeUoW:
        def __init__(self) -> None:
            self.video_tracking = _FakeTrackingRepo()

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    container = MagicMock()
    container.unit_of_work = lambda: _FakeUoW()
    return container


class TestReviewCmd:
    def test_help_lists_all_statuses(self) -> None:
        result = runner.invoke(app, ["review", "--help"])
        assert result.exit_code == 0
        for s in ("new", "reviewed", "saved", "actioned", "ignored", "archived"):
            assert s in result.output

    def test_review_saved_with_star_and_note(self, monkeypatch) -> None:
        container = _make_container()
        import vidscope.cli.commands.review as r_mod
        monkeypatch.setattr(r_mod, "acquire_container", lambda: container)
        result = runner.invoke(
            app,
            ["review", "42", "--status", "saved", "--star", "--note", "hook"],
        )
        assert result.exit_code == 0, result.output
        assert "saved" in result.output
        assert "starred" in result.output

    def test_review_invalid_status_fails(self, monkeypatch) -> None:
        container = _make_container()
        import vidscope.cli.commands.review as r_mod
        monkeypatch.setattr(r_mod, "acquire_container", lambda: container)
        result = runner.invoke(app, ["review", "42", "--status", "bogus"])
        assert result.exit_code != 0

    def test_review_unstar(self, monkeypatch) -> None:
        container = _make_container()
        import vidscope.cli.commands.review as r_mod
        monkeypatch.setattr(r_mod, "acquire_container", lambda: container)
        # First: star
        r1 = runner.invoke(app, ["review", "42", "--status", "saved", "--star"])
        assert r1.exit_code == 0
        # Then: unstar (fresh container so no existing)
        container2 = _make_container()
        monkeypatch.setattr(r_mod, "acquire_container", lambda: container2)
        r2 = runner.invoke(app, ["review", "42", "--status", "saved", "--unstar"])
        assert r2.exit_code == 0
        assert "unstarred" in r2.output

    def test_review_clear_note(self, monkeypatch) -> None:
        existing = VideoTracking(
            video_id=VideoId(42), status=TrackingStatus.SAVED, notes="initial"
        )
        container = _make_container(existing=existing)
        import vidscope.cli.commands.review as r_mod
        monkeypatch.setattr(r_mod, "acquire_container", lambda: container)
        r = runner.invoke(app, ["review", "42", "--status", "saved", "--clear-note"])
        assert r.exit_code == 0

    def test_review_note_and_clear_note_mutually_exclusive(self, monkeypatch) -> None:
        container = _make_container()
        import vidscope.cli.commands.review as r_mod
        monkeypatch.setattr(r_mod, "acquire_container", lambda: container)
        r = runner.invoke(
            app,
            ["review", "42", "--status", "saved", "--note", "x", "--clear-note"],
        )
        assert r.exit_code != 0
