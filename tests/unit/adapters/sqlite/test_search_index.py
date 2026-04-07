"""Tests for :class:`SearchIndexSQLite`."""

from __future__ import annotations

from sqlalchemy import Engine

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    Analysis,
    Language,
    Platform,
    PlatformId,
    Transcript,
    Video,
    VideoId,
)


def _seed_video(engine: Engine, pid: str = "search1") -> VideoId:
    with SqliteUnitOfWork(engine) as uow:
        v = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId(pid),
                url=f"https://example.com/{pid}",
            )
        )
        assert v.id is not None
        return v.id


class TestSearchIndex:
    def test_index_and_query_a_transcript(self, engine: Engine) -> None:
        video_id = _seed_video(engine)

        with SqliteUnitOfWork(engine) as uow:
            transcript = Transcript(
                video_id=video_id,
                language=Language.FRENCH,
                full_text="Aujourd'hui nous parlons de cuisine italienne et de pâtes fraîches",
            )
            uow.search_index.index_transcript(transcript)

        with SqliteUnitOfWork(engine) as uow:
            results = uow.search_index.search("cuisine", limit=5)
            assert len(results) == 1
            assert results[0].video_id == video_id
            assert results[0].source == "transcript"
            assert "cuisine" in results[0].snippet.lower()

    def test_query_with_no_matches_returns_empty(
        self, engine: Engine
    ) -> None:
        _seed_video(engine)
        with SqliteUnitOfWork(engine) as uow:
            uow.search_index.index_transcript(
                Transcript(
                    video_id=VideoId(1),
                    language=Language.ENGLISH,
                    full_text="hello world",
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            assert uow.search_index.search("completelyunrelatedword") == []

    def test_query_with_empty_string_returns_empty(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            assert uow.search_index.search("   ") == []

    def test_index_analysis_summary(self, engine: Engine) -> None:
        video_id = _seed_video(engine, "analysis1")
        with SqliteUnitOfWork(engine) as uow:
            analysis = Analysis(
                video_id=video_id,
                provider="heuristic",
                language=Language.ENGLISH,
                summary="A short review of a French documentary about architecture.",
                keywords=("architecture", "documentary"),
            )
            uow.search_index.index_analysis(analysis)

        with SqliteUnitOfWork(engine) as uow:
            results = uow.search_index.search("architecture", limit=10)
            assert any(r.video_id == video_id for r in results)
            assert all(
                r.source in ("transcript", "analysis_summary") for r in results
            )

    def test_re_indexing_replaces_previous_content(
        self, engine: Engine
    ) -> None:
        """Indexing a transcript twice for the same video should not
        leave stale text in the index."""
        video_id = _seed_video(engine, "reindex1")

        with SqliteUnitOfWork(engine) as uow:
            uow.search_index.index_transcript(
                Transcript(
                    video_id=video_id,
                    language=Language.ENGLISH,
                    full_text="the quick brown fox",
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            uow.search_index.index_transcript(
                Transcript(
                    video_id=video_id,
                    language=Language.ENGLISH,
                    full_text="the lazy green dog",
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            # Old text must be gone
            assert uow.search_index.search("quick") == []
            # New text must be searchable
            new_results = uow.search_index.search("lazy")
            assert len(new_results) == 1
            assert new_results[0].video_id == video_id

    def test_accent_insensitive_search(self, engine: Engine) -> None:
        """The tokenizer is configured with `remove_diacritics 2` so
        searching for 'pates' should match 'pâtes'."""
        video_id = _seed_video(engine, "accent1")
        with SqliteUnitOfWork(engine) as uow:
            uow.search_index.index_transcript(
                Transcript(
                    video_id=video_id,
                    language=Language.FRENCH,
                    full_text="les pâtes fraîches sont délicieuses",
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            results = uow.search_index.search("pates")
            assert len(results) == 1
            assert results[0].video_id == video_id
