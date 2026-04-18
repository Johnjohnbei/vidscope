"""Unit tests for AnalysisRepositorySQLite — M010 extended fields."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.analysis_repository import AnalysisRepositorySQLite
from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    SentimentLabel,
    VideoId,
)


def _insert_video(conn, platform_id: str) -> int:
    conn.execute(
        text("INSERT INTO videos (platform, platform_id, url, created_at) "
             "VALUES (:p, :pid, :u, :c)"),
        {"p": "youtube", "pid": platform_id, "u": f"https://y.be/{platform_id}",
         "c": datetime(2026, 1, 1, tzinfo=UTC)},
    )
    return int(conn.execute(
        text("SELECT id FROM videos WHERE platform_id=:pid"),
        {"pid": platform_id},
    ).scalar())


class TestM010Persistence:
    def test_add_persists_all_m010_fields(self, engine: Engine) -> None:
        with engine.begin() as conn:
            vid = _insert_video(conn, "persist1")
            repo = AnalysisRepositorySQLite(conn)
            entity = Analysis(
                video_id=VideoId(vid),
                provider="heuristic",
                language=Language.ENGLISH,
                keywords=("code", "python"),
                topics=("code",),
                score=70.0,
                summary="Tutorial about Python",
                verticals=("tech", "ai"),
                information_density=65.0,
                actionability=80.0,
                novelty=40.0,
                production_quality=55.0,
                sentiment=SentimentLabel.POSITIVE,
                is_sponsored=False,
                content_type=ContentType.TUTORIAL,
                reasoning="Clear structured tutorial covering Python basics.",
            )
            repo.add(entity)

        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            read = repo.get_latest_for_video(VideoId(vid))
        assert read is not None
        assert set(read.verticals) == {"tech", "ai"}
        assert read.information_density == 65.0
        assert read.actionability == 80.0
        assert read.novelty == 40.0
        assert read.production_quality == 55.0
        assert read.sentiment is SentimentLabel.POSITIVE
        assert read.is_sponsored is False
        assert read.content_type is ContentType.TUTORIAL
        assert read.reasoning is not None
        assert "Python" in read.reasoning

    def test_none_values_round_trip(self, engine: Engine) -> None:
        with engine.begin() as conn:
            vid = _insert_video(conn, "none1")
            repo = AnalysisRepositorySQLite(conn)
            entity = Analysis(
                video_id=VideoId(vid),
                provider="heuristic",
                language=Language.ENGLISH,
            )
            repo.add(entity)

        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            read = repo.get_latest_for_video(VideoId(vid))
        assert read is not None
        assert read.verticals == ()
        assert read.sentiment is None
        assert read.content_type is None
        assert read.is_sponsored is None
        assert read.reasoning is None

    def test_corrupt_sentiment_value_becomes_none(self, engine: Engine) -> None:
        """Pitfall 4: unknown string in DB must not crash the reader."""
        with engine.begin() as conn:
            vid = _insert_video(conn, "corrupt1")
            conn.execute(
                text("INSERT INTO analyses (video_id, provider, language, keywords, topics, "
                     "sentiment, content_type, created_at) "
                     "VALUES (:v, 'heuristic', 'en', '[]', '[]', :s, :ct, :c)"),
                {"v": vid, "s": "joyful", "ct": "podcast",
                 "c": datetime(2026, 1, 1, tzinfo=UTC)},
            )
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            read = repo.get_latest_for_video(VideoId(vid))
        assert read is not None
        assert read.sentiment is None
        assert read.content_type is None


class TestListByFilters:
    """M010: facet filtering on the analyses table."""

    def _insert_analysis(
        self, conn, *, vid: int, content_type: str | None = None,
        actionability: float | None = None, is_sponsored: bool | None = None,
        created_at: datetime | None = None,
    ) -> None:
        conn.execute(
            text("""
                INSERT INTO analyses
                (video_id, provider, language, keywords, topics,
                 content_type, actionability, is_sponsored, created_at)
                VALUES (:v, 'heuristic', 'en', '[]', '[]', :ct, :act, :sp, :c)
            """),
            {
                "v": vid, "ct": content_type, "act": actionability,
                "sp": 1 if is_sponsored is True else (0 if is_sponsored is False else None),
                "c": created_at or datetime(2026, 1, 1, tzinfo=UTC),
            },
        )

    def test_filter_by_content_type(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "f1")
            v2 = _insert_video(conn, "f2")
            self._insert_analysis(conn, vid=v1, content_type="tutorial")
            self._insert_analysis(conn, vid=v2, content_type="review")
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = repo.list_by_filters(content_type=ContentType.TUTORIAL)
        assert v1 in [int(x) for x in hits]
        assert v2 not in [int(x) for x in hits]

    def test_filter_min_actionability_excludes_null(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "f3")
            v2 = _insert_video(conn, "f4")
            v3 = _insert_video(conn, "f5")
            self._insert_analysis(conn, vid=v1, actionability=90.0)
            self._insert_analysis(conn, vid=v2, actionability=50.0)
            self._insert_analysis(conn, vid=v3, actionability=None)  # excluded
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = [int(x) for x in repo.list_by_filters(min_actionability=70.0)]
        assert v1 in hits
        assert v2 not in hits
        assert v3 not in hits

    def test_filter_is_sponsored_true(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "f6")
            v2 = _insert_video(conn, "f7")
            v3 = _insert_video(conn, "f8")
            self._insert_analysis(conn, vid=v1, is_sponsored=True)
            self._insert_analysis(conn, vid=v2, is_sponsored=False)
            self._insert_analysis(conn, vid=v3, is_sponsored=None)
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = [int(x) for x in repo.list_by_filters(is_sponsored=True)]
        assert v1 in hits
        assert v2 not in hits
        assert v3 not in hits

    def test_filter_is_sponsored_false_excludes_null(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "g1")
            v2 = _insert_video(conn, "g2")
            v3 = _insert_video(conn, "g3")
            self._insert_analysis(conn, vid=v1, is_sponsored=True)
            self._insert_analysis(conn, vid=v2, is_sponsored=False)
            self._insert_analysis(conn, vid=v3, is_sponsored=None)
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = [int(x) for x in repo.list_by_filters(is_sponsored=False)]
        assert v2 in hits
        assert v1 not in hits
        assert v3 not in hits

    def test_combined_filters_and(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "h1")
            v2 = _insert_video(conn, "h2")
            v3 = _insert_video(conn, "h3")
            self._insert_analysis(conn, vid=v1, content_type="tutorial",
                                  actionability=90.0, is_sponsored=False)
            self._insert_analysis(conn, vid=v2, content_type="tutorial",
                                  actionability=60.0, is_sponsored=False)
            self._insert_analysis(conn, vid=v3, content_type="review",
                                  actionability=95.0, is_sponsored=False)
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = [int(x) for x in repo.list_by_filters(
                content_type=ContentType.TUTORIAL,
                min_actionability=70.0,
                is_sponsored=False,
            )]
        assert v1 in hits
        assert v2 not in hits  # actionability too low
        assert v3 not in hits  # wrong content_type

    def test_no_filters_returns_all_analyzed_videos(self, engine: Engine) -> None:
        with engine.begin() as conn:
            v1 = _insert_video(conn, "i1")
            v2 = _insert_video(conn, "i2")
            _insert_video(conn, "i3_no_analysis")  # excluded -- no analyses row
            self._insert_analysis(conn, vid=v1)
            self._insert_analysis(conn, vid=v2)
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = [int(x) for x in repo.list_by_filters()]
        assert v1 in hits
        assert v2 in hits

    def test_latest_analysis_used(self, engine: Engine) -> None:
        """If a video has multiple analyses, only the latest is checked."""
        with engine.begin() as conn:
            v1 = _insert_video(conn, "j1")
            # Old analysis: content_type=vlog
            self._insert_analysis(conn, vid=v1, content_type="vlog",
                                  created_at=datetime(2025, 1, 1, tzinfo=UTC))
            # Newer analysis: content_type=tutorial (should be the winner)
            self._insert_analysis(conn, vid=v1, content_type="tutorial",
                                  created_at=datetime(2026, 1, 1, tzinfo=UTC))
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            tutorials = [int(x) for x in repo.list_by_filters(content_type=ContentType.TUTORIAL)]
            vlogs = [int(x) for x in repo.list_by_filters(content_type=ContentType.VLOG)]
        assert v1 in tutorials
        assert v1 not in vlogs

    def test_sql_injection_attempt_safe(self, engine: Engine) -> None:
        """ContentType enum -> controlled string; direct string injection impossible."""
        with engine.begin() as conn:
            _insert_video(conn, "k1")
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            # If ContentType("' OR 1=1 --") was accepted, we'd have an issue.
            # But ContentType rejects invalid values -- test that instead.
            import pytest as _pytest
            with _pytest.raises(ValueError):
                ContentType("' OR 1=1 --")
            # And list_by_filters with a valid enum returns safely:
            hits = repo.list_by_filters(content_type=ContentType.UNKNOWN)
            assert isinstance(hits, list)

    def test_limit_respected(self, engine: Engine) -> None:
        with engine.begin() as conn:
            for i in range(10):
                vid = _insert_video(conn, f"lim{i}")
                self._insert_analysis(conn, vid=vid, content_type="tutorial",
                                      created_at=datetime(2026, 1, 1 + i, tzinfo=UTC))
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            hits = repo.list_by_filters(content_type=ContentType.TUTORIAL, limit=3)
        assert len(hits) == 3


class TestContainerTaxonomyWiring:
    def test_container_exposes_taxonomy_catalog(self, tmp_path: Path) -> None:
        """Build a container and verify taxonomy_catalog is a TaxonomyCatalog.

        Skip gracefully if the config/taxonomy.yaml is not found (should
        always exist after Task 2 — this guards against test-env oddities).
        """
        from vidscope.infrastructure.container import build_container
        from vidscope.ports import TaxonomyCatalog

        # build_container resolves the path relative to cwd
        old_cwd = os.getcwd()
        # Walk up from this test file until we find config/taxonomy.yaml
        repo_root = Path(__file__).resolve()
        for _ in range(6):
            if (repo_root / "config" / "taxonomy.yaml").is_file():
                break
            repo_root = repo_root.parent
        try:
            os.chdir(repo_root)
            # Use a tmp DB to avoid touching the real one
            os.environ["VIDSCOPE_DATA_DIR"] = str(tmp_path)
            container = build_container()
            try:
                assert isinstance(container.taxonomy_catalog, TaxonomyCatalog)
                verticals = container.taxonomy_catalog.verticals()
                assert len(verticals) >= 12
            finally:
                container.engine.dispose()
        finally:
            os.chdir(old_cwd)
            os.environ.pop("VIDSCOPE_DATA_DIR", None)
