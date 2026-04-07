"""Unit tests for vidscope.domain.errors."""

from __future__ import annotations

import pytest

from vidscope.domain.errors import (
    AnalysisError,
    ConfigError,
    DomainError,
    FrameExtractionError,
    IndexingError,
    IngestError,
    StageCrashError,
    StorageError,
    TranscriptionError,
)
from vidscope.domain.values import StageName


class TestDomainErrorBase:
    def test_is_an_exception(self) -> None:
        assert issubclass(DomainError, Exception)

    def test_carries_message_and_stage(self) -> None:
        err = DomainError("boom", stage=StageName.INGEST)
        assert str(err) == "boom"
        assert err.message == "boom"
        assert err.stage is StageName.INGEST
        assert err.cause is None

    def test_stage_is_optional(self) -> None:
        err = DomainError("boom")
        assert err.stage is None

    def test_retryable_defaults_to_class_default(self) -> None:
        assert DomainError("x").retryable is False

    def test_explicit_retryable_wins_over_default(self) -> None:
        err = DomainError("x", retryable=True)
        assert err.retryable is True

    def test_cause_is_preserved(self) -> None:
        root = ValueError("root cause")
        err = DomainError("wrapped", cause=root)
        assert err.cause is root


class TestIngestError:
    def test_is_retryable_by_default(self) -> None:
        assert IngestError("network down").retryable is True

    def test_stage_is_always_ingest(self) -> None:
        assert IngestError("x").stage is StageName.INGEST

    def test_can_be_raised(self) -> None:
        with pytest.raises(IngestError) as exc_info:
            raise IngestError("download failed")
        assert exc_info.value.stage is StageName.INGEST

    def test_can_override_retryable(self) -> None:
        err = IngestError("permanent", retryable=False)
        assert err.retryable is False


class TestTranscriptionError:
    def test_not_retryable_by_default(self) -> None:
        assert TranscriptionError("audio corrupt").retryable is False

    def test_stage_is_transcribe(self) -> None:
        assert TranscriptionError("x").stage is StageName.TRANSCRIBE


class TestFrameExtractionError:
    def test_not_retryable_by_default(self) -> None:
        assert FrameExtractionError("ffmpeg missing").retryable is False

    def test_stage_is_frames(self) -> None:
        assert FrameExtractionError("x").stage is StageName.FRAMES


class TestAnalysisError:
    def test_not_retryable_by_default(self) -> None:
        assert AnalysisError("heuristic failed").retryable is False

    def test_can_be_marked_retryable_for_llm_providers(self) -> None:
        err = AnalysisError("429", retryable=True)
        assert err.retryable is True
        assert err.stage is StageName.ANALYZE


class TestIndexingError:
    def test_stage_is_index(self) -> None:
        assert IndexingError("fts5 broke").stage is StageName.INDEX


class TestStorageError:
    def test_has_no_associated_stage(self) -> None:
        assert StorageError("disk full").stage is None

    def test_not_retryable_by_default(self) -> None:
        assert StorageError("x").retryable is False


class TestConfigError:
    def test_has_no_stage(self) -> None:
        assert ConfigError("bad path").stage is None

    def test_not_retryable(self) -> None:
        assert ConfigError("x").retryable is False


class TestStageCrashError:
    def test_wraps_an_unexpected_cause(self) -> None:
        original = RuntimeError("unexpected")
        err = StageCrashError("stage leaked untyped exception", cause=original)
        assert err.cause is original
        assert err.retryable is False

    def test_signals_an_adapter_bug(self) -> None:
        # This error existing at all in pipeline_runs is a signal that a
        # stage did not translate its failure into a typed DomainError.
        assert issubclass(StageCrashError, DomainError)


class TestHierarchy:
    @pytest.mark.parametrize(
        "cls",
        [
            IngestError,
            TranscriptionError,
            FrameExtractionError,
            AnalysisError,
            IndexingError,
            StorageError,
            ConfigError,
            StageCrashError,
        ],
    )
    def test_every_subclass_inherits_from_domain_error(
        self, cls: type[DomainError]
    ) -> None:
        assert issubclass(cls, DomainError)

    def test_catching_domain_error_catches_everything(self) -> None:
        for err_cls in [
            IngestError,
            TranscriptionError,
            FrameExtractionError,
            AnalysisError,
            IndexingError,
            StorageError,
            ConfigError,
        ]:
            try:
                raise err_cls("x")
            except DomainError:
                pass
            else:
                pytest.fail(f"{err_cls} not caught by DomainError")
