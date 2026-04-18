"""ExportLibraryUseCase unit tests (M011/S04/R059)."""
from __future__ import annotations

from pathlib import Path

import pytest

from vidscope.application.export_library import (
    ExportLibraryUseCase,
    ExportRecord,
)
from vidscope.application.search_videos import SearchFilters
from vidscope.domain import TrackingStatus


class _CaptureExporter:
    def __init__(self) -> None:
        self.records: list[ExportRecord] = []
        self.out: Path | None = None
        self.call_count = 0

    def write(self, records, out=None):
        self.records = list(records)
        self.out = out
        self.call_count += 1


@pytest.fixture
def _seeded_db(engine):
    """Seed the DB with 3 videos + analyses + tracking + tags + collections."""
    from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
    from vidscope.domain import (
        Analysis,
        Language,
        Platform,
        PlatformId,
        Video,
        VideoId,
        VideoTracking,
    )

    ids: list[int] = []
    with SqliteUnitOfWork(engine) as uow:
        for i in range(1, 4):
            v = uow.videos.upsert_by_platform_id(Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId(f"exp{i}"),
                url=f"https://y.be/exp{i}",
                author=f"creator{i}",
                title=f"Title {i}",
                upload_date="20260101",
            ))
            ids.append(int(v.id))
            uow.analyses.add(Analysis(
                video_id=VideoId(int(v.id)),
                provider="heuristic",
                language=Language.ENGLISH,
                keywords=(f"k{i}", "python"),
                summary=f"summary {i}",
                score=50.0 + i,
            ))
            if i % 2 == 1:
                uow.video_tracking.upsert(VideoTracking(
                    video_id=VideoId(int(v.id)),
                    status=TrackingStatus.SAVED,
                    starred=True,
                    notes=f"note {i}",
                ))

    with SqliteUnitOfWork(engine) as uow:
        t = uow.tags.get_or_create("idea")
        assert t.id is not None
        uow.tags.assign(VideoId(ids[0]), t.id)
        c = uow.collections.create("MyCol")
        assert c.id is not None
        uow.collections.add_video(c.id, VideoId(ids[1]))

    return ids, engine


def _factory_from(engine):
    from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork

    def _make():
        return SqliteUnitOfWork(engine)
    return _make


class TestExportLibraryUseCase:
    def test_export_all_no_filters(self, _seeded_db) -> None:
        ids, engine = _seeded_db
        exp = _CaptureExporter()
        uc = ExportLibraryUseCase(unit_of_work_factory=_factory_from(engine))
        n = uc.execute(exporter=exp)
        assert n == 3
        assert len(exp.records) == 3
        by_id = {r.video_id: r for r in exp.records}
        assert by_id[ids[0]].tags == ["idea"]
        assert by_id[ids[1]].collections == ["MyCol"]
        assert by_id[ids[0]].status == "saved"
        assert by_id[ids[0]].starred is True

    def test_export_with_collection_filter(self, _seeded_db) -> None:
        ids, engine = _seeded_db
        exp = _CaptureExporter()
        uc = ExportLibraryUseCase(unit_of_work_factory=_factory_from(engine))
        n = uc.execute(
            exporter=exp, filters=SearchFilters(collection="MyCol"),
        )
        assert n == 1
        assert exp.records[0].video_id == ids[1]

    def test_export_with_starred_filter(self, _seeded_db) -> None:
        ids, engine = _seeded_db
        exp = _CaptureExporter()
        uc = ExportLibraryUseCase(unit_of_work_factory=_factory_from(engine))
        n = uc.execute(exporter=exp, filters=SearchFilters(starred=True))
        # Videos 1 and 3 are starred (odd i)
        assert n == 2
        assert {r.video_id for r in exp.records} == {ids[0], ids[2]}

    def test_export_empty_db(self, engine) -> None:
        exp = _CaptureExporter()
        uc = ExportLibraryUseCase(unit_of_work_factory=_factory_from(engine))
        n = uc.execute(exporter=exp)
        assert n == 0
        assert exp.records == []
        assert exp.call_count == 1  # write called with empty list

    def test_export_record_has_all_fields(self, _seeded_db) -> None:
        ids, engine = _seeded_db
        exp = _CaptureExporter()
        uc = ExportLibraryUseCase(unit_of_work_factory=_factory_from(engine))
        uc.execute(exporter=exp)
        r = next(r for r in exp.records if r.video_id == ids[0])
        assert r.platform == "youtube"
        assert r.url == "https://y.be/exp1"
        assert r.title == "Title 1"
        assert "k1" in r.keywords
        assert r.score == 51.0
        assert r.status == "saved"
        assert r.tags == ["idea"]
        assert r.exported_at  # ISO string
