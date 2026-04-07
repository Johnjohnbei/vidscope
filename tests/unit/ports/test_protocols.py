"""Structural tests for vidscope.ports.

Pure-Python assertions on Protocol shape. No I/O, no third-party deps
beyond pytest and the stdlib.

These tests exist to catch accidental regressions in the port contracts —
if someone adds a method to VideoRepository without updating the adapter,
the adapter test in T06 will fail; if someone removes a method without
updating a caller, mypy will fail. These structural tests are the third
line of defense and catch "someone removed a Protocol member entirely".
"""

from __future__ import annotations

from typing import Protocol, get_type_hints

from vidscope.ports import (
    AnalysisRepository,
    Analyzer,
    Clock,
    Downloader,
    FrameExtractor,
    FrameRepository,
    IngestOutcome,
    MediaStorage,
    PipelineContext,
    PipelineRunRepository,
    SearchIndex,
    SearchResult,
    Stage,
    StageResult,
    Transcriber,
    TranscriptRepository,
    UnitOfWork,
    VideoRepository,
    WatchAccountRepository,
    WatchRefreshRepository,
)

# Every Protocol that adapters must conform to. Dataclasses
# (PipelineContext, StageResult, IngestOutcome, SearchResult) are not in
# this list — they aren't Protocols.
RUNTIME_CHECKABLE_PROTOCOLS: tuple[type, ...] = (
    Clock,
    MediaStorage,
    VideoRepository,
    TranscriptRepository,
    FrameRepository,
    AnalysisRepository,
    PipelineRunRepository,
    WatchAccountRepository,
    WatchRefreshRepository,
    UnitOfWork,
    Stage,
    Downloader,
    Transcriber,
    FrameExtractor,
    Analyzer,
    SearchIndex,
)


class TestProtocolConformance:
    def test_every_port_is_a_protocol(self) -> None:
        for proto in RUNTIME_CHECKABLE_PROTOCOLS:
            assert issubclass(proto, Protocol), (
                f"{proto.__name__} is not a Protocol"
            )

    def test_every_port_is_runtime_checkable(self) -> None:
        # runtime_checkable injects __instancecheck__ — Protocols without
        # the decorator raise TypeError on isinstance(). We verify by
        # calling isinstance with a dummy object and asserting it does
        # not raise.
        class _Dummy:
            pass

        for proto in RUNTIME_CHECKABLE_PROTOCOLS:
            try:
                isinstance(_Dummy(), proto)  # type: ignore[misc]
            except TypeError as exc:
                msg = f"{proto.__name__} is not @runtime_checkable: {exc}"
                raise AssertionError(msg) from exc


class TestPortSignatures:
    """Assert every port carries the methods the adapters/tests rely on.

    If a method gets renamed or removed, these tests fail BEFORE any
    adapter test does — giving a precise error message."""

    def test_clock_has_now(self) -> None:
        assert hasattr(Clock, "now")

    def test_media_storage_has_required_methods(self) -> None:
        for name in ("store", "resolve", "exists", "delete", "open"):
            assert hasattr(MediaStorage, name), f"MediaStorage missing {name}"

    def test_video_repository_has_required_methods(self) -> None:
        for name in (
            "add",
            "upsert_by_platform_id",
            "get",
            "get_by_platform_id",
            "list_recent",
            "count",
        ):
            assert hasattr(VideoRepository, name), (
                f"VideoRepository missing {name}"
            )

    def test_pipeline_run_repository_has_required_methods(self) -> None:
        for name in (
            "add",
            "update_status",
            "latest_for_video",
            "latest_by_phase",
            "list_recent",
            "count",
        ):
            assert hasattr(PipelineRunRepository, name), (
                f"PipelineRunRepository missing {name}"
            )

    def test_transcript_repository_methods(self) -> None:
        for name in ("add", "get_for_video"):
            assert hasattr(TranscriptRepository, name)

    def test_frame_repository_methods(self) -> None:
        for name in ("add_many", "list_for_video"):
            assert hasattr(FrameRepository, name)

    def test_analysis_repository_methods(self) -> None:
        for name in ("add", "get_latest_for_video"):
            assert hasattr(AnalysisRepository, name)

    def test_unit_of_work_exposes_every_repository(self) -> None:
        # UnitOfWork declares every repository as a class-level
        # annotation so adapters know what to implement. We read
        # __annotations__ directly instead of get_type_hints because
        # `search_index` is a forward ref (TYPE_CHECKING import) to
        # break a circular import with ports.pipeline.
        annotations = set(UnitOfWork.__annotations__.keys())
        expected = {
            "videos",
            "transcripts",
            "frames",
            "analyses",
            "pipeline_runs",
            "search_index",
            "watch_accounts",
            "watch_refreshes",
        }
        assert expected.issubset(annotations), (
            f"UnitOfWork missing repository fields: "
            f"{expected - annotations}"
        )

    def test_stage_has_name_execute_and_is_satisfied(self) -> None:
        # `name` is declared as a class-level annotation on the Protocol
        # (`name: str`) without a default, so it only appears in
        # get_type_hints — not in hasattr(). Both methods are real
        # attributes.
        hints = get_type_hints(Stage)
        assert "name" in hints, f"Stage missing 'name' annotation, got {hints}"
        for method in ("execute", "is_satisfied"):
            assert hasattr(Stage, method), f"Stage missing {method}"

    def test_per_stage_service_methods(self) -> None:
        assert hasattr(Downloader, "download")
        assert hasattr(Downloader, "list_channel_videos")
        assert hasattr(Downloader, "probe")
        assert hasattr(Transcriber, "transcribe")
        assert hasattr(FrameExtractor, "extract_frames")
        assert hasattr(Analyzer, "analyze")
        assert hasattr(Analyzer, "provider_name")
        assert hasattr(SearchIndex, "index_transcript")
        assert hasattr(SearchIndex, "index_analysis")
        assert hasattr(SearchIndex, "search")

    def test_watch_account_repository_methods(self) -> None:
        for name in (
            "add", "get", "get_by_handle", "list_all", "remove",
            "update_last_checked",
        ):
            assert hasattr(WatchAccountRepository, name), (
                f"WatchAccountRepository missing {name}"
            )

    def test_watch_refresh_repository_methods(self) -> None:
        for name in ("add", "list_recent"):
            assert hasattr(WatchRefreshRepository, name), (
                f"WatchRefreshRepository missing {name}"
            )


class TestDataclassShapes:
    """The dataclasses exported from ports carry concrete data between
    stages — their fields are part of the contract, not implementation
    detail."""

    def test_pipeline_context_is_mutable(self) -> None:
        ctx = PipelineContext(source_url="https://example.com/x")
        ctx.media_key = "videos/1/media.mp4"
        assert ctx.media_key == "videos/1/media.mp4"
        assert ctx.frame_ids == []

    def test_stage_result_defaults_to_not_skipped(self) -> None:
        res = StageResult()
        assert res.skipped is False
        assert res.message == ""

    def test_ingest_outcome_fields(self) -> None:
        from vidscope.domain import Platform, PlatformId

        out = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc"),
            url="https://www.youtube.com/watch?v=abc",
            media_path="/tmp/abc.mp4",
        )
        assert out.title is None
        assert out.duration is None

    def test_search_result_has_rank(self) -> None:
        from vidscope.domain import VideoId

        r = SearchResult(
            video_id=VideoId(1),
            source="transcript",
            snippet="...match...",
            rank=1.25,
        )
        assert r.rank == 1.25


class TestLayerIsolation:
    """Smoke test that ports only reach into vidscope.domain. A full
    check lives in tests/architecture/test_layering.py (T09); this is an
    inexpensive early warning."""

    def test_ports_package_imports_only_domain_from_project(self) -> None:
        import pkgutil

        import vidscope.ports as ports_pkg

        allowed_prefixes = (
            "vidscope.domain",
            "vidscope.ports",  # intra-package is fine
        )

        for mod_info in pkgutil.walk_packages(
            ports_pkg.__path__, prefix="vidscope.ports."
        ):
            mod = __import__(mod_info.name, fromlist=["_"])
            # Inspect the module's __dict__ for any attribute referring
            # to a submodule of vidscope that isn't in the allowed list.
            for obj_name, obj in vars(mod).items():
                if obj_name.startswith("_"):
                    continue
                module = getattr(obj, "__module__", "") or ""
                if module.startswith("vidscope.") and not module.startswith(
                    allowed_prefixes
                ):
                    raise AssertionError(
                        f"{mod.__name__}.{obj_name} comes from {module}, "
                        f"which is not an allowed upstream of ports/"
                    )
