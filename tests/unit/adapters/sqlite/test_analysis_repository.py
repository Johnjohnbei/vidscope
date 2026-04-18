"""Unit tests for AnalysisRepositorySQLite — M010 extended fields."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
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
