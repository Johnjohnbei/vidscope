"""Tests for scripts/backfill_creators.py (M006/S01)."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.ports import (
    ChannelEntry,
    IngestOutcome,
    ProbeResult,
    ProbeStatus,
)

# Import the script module to test its main() entry point directly.
# scripts/ is not a package by default; add it to sys.path via a
# conftest-style pattern.
_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "backfill_creators.py"
)
_spec = importlib.util.spec_from_file_location(
    "backfill_creators_module", _SCRIPT_PATH
)
assert _spec is not None and _spec.loader is not None
backfill_module = importlib.util.module_from_spec(_spec)
sys.modules["backfill_creators_module"] = backfill_module
_spec.loader.exec_module(backfill_module)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _FakeDownloader:
    """Stub Downloader for backfill tests. Returns pre-seeded
    ProbeResult keyed by URL.
    """

    probe_map: dict[str, ProbeResult] = field(default_factory=dict)

    def probe(self, url: str) -> ProbeResult:
        if url in self.probe_map:
            return self.probe_map[url]
        return ProbeResult(
            status=ProbeStatus.ERROR, url=url, detail="no stub seeded"
        )

    def download(self, url: str, destination_dir: str) -> IngestOutcome:
        raise NotImplementedError("unused by backfill")

    def list_channel_videos(
        self, url: str, *, limit: int = 10
    ) -> list[ChannelEntry]:
        raise NotImplementedError("unused by backfill")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_engine(tmp_path: Path) -> Engine:
    """Pre-M006-style DB with 3 videos, creator_id all NULL."""
    db_path = tmp_path / "seed.db"
    eng = build_engine(db_path)
    init_db(eng)

    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO videos (platform, platform_id, url, author, created_at) "
                "VALUES "
                "('youtube', 'yt_ok_1', 'https://y/ok_1', 'Alice', CURRENT_TIMESTAMP), "
                "('tiktok',  'tt_ok_2', 'https://t/ok_2', 'Bob', CURRENT_TIMESTAMP), "
                "('youtube', 'yt_404_3','https://y/404_3','Charlie', CURRENT_TIMESTAMP)"
            )
        )
    return eng


def _fake_container(engine: Engine, downloader: _FakeDownloader) -> Any:
    """Build a minimal Container backed by the seeded engine + stub
    downloader. Only fields backfill_creators.py touches are wired.
    """

    @dataclass(frozen=True)
    class _BackfillContainer:
        downloader: Any
        unit_of_work: Any

    def _uow_factory() -> SqliteUnitOfWork:
        return SqliteUnitOfWork(engine)

    return _BackfillContainer(
        downloader=downloader, unit_of_work=_uow_factory
    )


# ---------------------------------------------------------------------------
# Tests — R042
# ---------------------------------------------------------------------------


class TestBackfillDryRun:
    def test_dry_run_writes_nothing(
        self, seeded_engine: Engine
    ) -> None:
        """Default mode (no --apply) must not mutate the DB."""
        downloader = _FakeDownloader(
            probe_map={
                "https://y/ok_1": ProbeResult(
                    status=ProbeStatus.OK,
                    url="https://y/ok_1",
                    detail="ok",
                    title="Ok1",
                    uploader="AliceChannel",
                    uploader_id="UC_alice",
                ),
                "https://t/ok_2": ProbeResult(
                    status=ProbeStatus.OK,
                    url="https://t/ok_2",
                    detail="ok",
                    title="Ok2",
                    uploader="BobTok",
                    uploader_id="123456",
                ),
                "https://y/404_3": ProbeResult(
                    status=ProbeStatus.NOT_FOUND,
                    url="https://y/404_3",
                    detail="gone",
                ),
            }
        )
        container = _fake_container(seeded_engine, downloader)

        exit_code = backfill_module.main([], container=container)
        assert exit_code == 0

        with SqliteUnitOfWork(seeded_engine) as uow:
            assert uow.creators.count() == 0
            # Every video still has creator_id IS NULL
            conn = uow._connection  # type: ignore[attr-defined]
            rows = conn.execute(
                text("SELECT creator_id FROM videos")
            ).all()
            assert all(r[0] is None for r in rows)


class TestBackfillApply:
    def test_apply_fills_creator_id_for_every_video(
        self, seeded_engine: Engine
    ) -> None:
        downloader = _FakeDownloader(
            probe_map={
                "https://y/ok_1": ProbeResult(
                    status=ProbeStatus.OK,
                    url="https://y/ok_1",
                    detail="ok",
                    title="Ok1",
                    uploader="AliceChannel",
                    uploader_id="UC_alice",
                ),
                "https://t/ok_2": ProbeResult(
                    status=ProbeStatus.OK,
                    url="https://t/ok_2",
                    detail="ok",
                    title="Ok2",
                    uploader="BobTok",
                    uploader_id="123456",
                ),
                "https://y/404_3": ProbeResult(
                    status=ProbeStatus.NOT_FOUND,
                    url="https://y/404_3",
                    detail="gone",
                ),
            }
        )
        container = _fake_container(seeded_engine, downloader)

        exit_code = backfill_module.main(["--apply"], container=container)
        assert exit_code == 0

        with SqliteUnitOfWork(seeded_engine) as uow:
            assert uow.creators.count() == 3  # 2 OK + 1 orphan
            conn = uow._connection  # type: ignore[attr-defined]
            rows = conn.execute(
                text(
                    "SELECT platform_id, creator_id, author FROM videos "
                    "ORDER BY platform_id"
                )
            ).all()
            for row in rows:
                assert row[1] is not None, f"video {row[0]} still unlinked"

    def test_apply_orphan_on_not_found(
        self, seeded_engine: Engine
    ) -> None:
        downloader = _FakeDownloader(
            probe_map={
                "https://y/ok_1": ProbeResult(
                    status=ProbeStatus.OK,
                    url="https://y/ok_1",
                    detail="ok",
                    title="Ok1",
                    uploader="Alice",
                    uploader_id="UC_alice",
                ),
                "https://t/ok_2": ProbeResult(
                    status=ProbeStatus.OK,
                    url="https://t/ok_2",
                    detail="ok",
                    uploader="Bob",
                    uploader_id="123",
                ),
                "https://y/404_3": ProbeResult(
                    status=ProbeStatus.NOT_FOUND,
                    url="https://y/404_3",
                    detail="gone",
                ),
            }
        )
        container = _fake_container(seeded_engine, downloader)
        backfill_module.main(["--apply"], container=container)

        with SqliteUnitOfWork(seeded_engine) as uow:
            conn = uow._connection  # type: ignore[attr-defined]
            orphans = conn.execute(
                text("SELECT COUNT(*) FROM creators WHERE is_orphan = 1")
            ).scalar()
            assert orphans == 1
            orphan_row = conn.execute(
                text(
                    "SELECT platform_user_id FROM creators WHERE is_orphan = 1"
                )
            ).first()
            assert orphan_row is not None
            assert orphan_row[0].startswith("orphan:")

    def test_apply_twice_is_idempotent(self, seeded_engine: Engine) -> None:
        downloader = _FakeDownloader(
            probe_map={
                "https://y/ok_1": ProbeResult(
                    status=ProbeStatus.OK,
                    url="https://y/ok_1",
                    detail="ok",
                    uploader="Alice",
                    uploader_id="UC_alice",
                ),
                "https://t/ok_2": ProbeResult(
                    status=ProbeStatus.OK,
                    url="https://t/ok_2",
                    detail="ok",
                    uploader="Bob",
                    uploader_id="123",
                ),
                "https://y/404_3": ProbeResult(
                    status=ProbeStatus.NOT_FOUND,
                    url="https://y/404_3",
                    detail="gone",
                ),
            }
        )
        container = _fake_container(seeded_engine, downloader)
        backfill_module.main(["--apply"], container=container)

        # Snapshot state
        with SqliteUnitOfWork(seeded_engine) as uow:
            first_count = uow.creators.count()

        # Second run should be a no-op (videos have creator_id set)
        backfill_module.main(["--apply"], container=container)

        with SqliteUnitOfWork(seeded_engine) as uow:
            assert uow.creators.count() == first_count


class TestBackfillEdgeCases:
    def test_empty_db_exits_cleanly(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        eng = build_engine(db_path)
        init_db(eng)

        downloader = _FakeDownloader()
        container = _fake_container(eng, downloader)

        exit_code = backfill_module.main(["--apply"], container=container)
        assert exit_code == 0

        with SqliteUnitOfWork(eng) as uow:
            assert uow.creators.count() == 0

    def test_help_prints_and_exits_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as excinfo:
            backfill_module.main(["--help"])
        assert excinfo.value.code == 0
        out = capsys.readouterr().out
        assert "--apply" in out
        assert "--limit" in out
