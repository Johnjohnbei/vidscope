---
id: T03
parent: S01
milestone: M001
key_files:
  - src/vidscope/domain/__init__.py
  - src/vidscope/domain/values.py
  - src/vidscope/domain/errors.py
  - src/vidscope/domain/entities.py
  - tests/unit/domain/test_values.py
  - tests/unit/domain/test_entities.py
  - tests/unit/domain/test_errors.py
key_decisions:
  - String-backed enums (inherit from `str, Enum`) so values round-trip through JSON/SQLite without encoders
  - Media references stored as opaque string keys, not `pathlib.Path`, so the domain is storage-agnostic and MediaStorage adapter can be swapped without entity changes
  - Typed ids via `NewType` (VideoId = int, PlatformId = str) for compile-time safety without runtime overhead
  - Renamed `IndexError` subclass to `IndexingError` to avoid shadowing the built-in `IndexError`
  - `StageCrashError` kept as an explicit wrapper class so a crashed-stage row in `pipeline_runs` is immediately diagnosable as an adapter bug (untyped exception leaked out)
  - `default_retryable` is a class attribute per error subclass encoding the usual behavior, overridable per instance via `retryable=` kwarg
duration: 
verification_result: passed
completed_at: 2026-04-07T10:59:12.217Z
blocker_discovered: false
---

# T03: Built the pure-Python domain layer: entities, value objects, typed error hierarchy, 60 unit tests running in 80ms with zero third-party imports.

**Built the pure-Python domain layer: entities, value objects, typed error hierarchy, 60 unit tests running in 80ms with zero third-party imports.**

## What Happened

The domain layer is the innermost ring of the hexagonal architecture. Everything else imports from it; it imports from nothing project-internal and nothing third-party (stdlib + `typing` only). That invariant is what makes the layer testable in milliseconds, substitutable at will, and never the reason a refactor cascades.

**values.py** — Three string-backed enums (`Platform`, `Language`, `StageName`, `RunStatus`) plus two `NewType` aliases (`VideoId = int`, `PlatformId = str`). String enums were chosen over plain enums so they round-trip through JSON and SQLite without encoders. `StageName` declaration order is the canonical execution order of the pipeline — the runner iterates `list(StageName)` if it ever needs a default ordering. `RunStatus` separates terminal (`OK`/`FAILED`/`SKIPPED`) from non-terminal (`PENDING`/`RUNNING`) states so the runner can make invariant decisions without ambiguity.

**errors.py** — A single root `DomainError(Exception)` with eight subclasses, one per failure domain (`IngestError`, `TranscriptionError`, `FrameExtractionError`, `AnalysisError`, `IndexingError`, `StorageError`, `ConfigError`) plus a special `StageCrashError` that wraps any untyped exception that leaks out of an adapter. Each subclass sets a `default_retryable` class variable encoding the usual failure-mode behavior (`IngestError` defaults retryable because network hiccups self-heal; `TranscriptionError` defaults non-retryable because audio corruption does not). Callers can override via the `retryable=` kwarg. Errors carry `stage`, `cause`, `retryable`, and `message` as instance attributes so the pipeline runner and the CLI can introspect without parsing strings.

The `StageCrashError` existence is deliberate: if that row ever appears in `pipeline_runs`, it's a signal that an adapter didn't translate its failure into a typed domain error. That's a bug, not a runtime condition.

**entities.py** — Six `@dataclass(frozen=True, slots=True)` classes: `Video`, `TranscriptSegment`, `Transcript`, `Frame`, `Analysis`, `PipelineRun`. Three design choices worth noting:

1. **Media references are strings, not Paths.** `Video.media_key`, `Frame.image_key` are `str` so the domain is filesystem-agnostic. The `MediaStorage` port (T04) resolves keys to concrete locations. This lets us swap LocalMediaStorage for S3/MinIO later without touching a single entity or use case.
2. **Timestamps are always timezone-aware `datetime`.** No naive datetimes anywhere. Every adapter that returns a row must attach `timezone.utc`.
3. **Typed ids on foreign keys.** `Transcript.video_id: VideoId` (not `int`). mypy catches accidental cross-wiring.

Each entity exposes a small amount of pure behavior: `Video.is_ingested()`, `Transcript.is_empty()`, `PipelineRun.duration()`, `PipelineRun.is_terminal()`. No method touches I/O. No method calls a port. Anything that would need I/O belongs in a use case or an adapter.

**Tests** — 60 parametrized tests across `test_values.py`, `test_entities.py`, `test_errors.py`. Total runtime: 80ms. They cover: enum membership and string values, frozen-ness (attempting to mutate raises `FrozenInstanceError`), retryable defaults and overrides, exception hierarchy (catching `DomainError` catches every subclass), duration math on inverted times, terminal-status detection, and the typed-id `NewType` runtime behavior. The test layout mirrors the source layout: `tests/unit/domain/` matches `src/vidscope/domain/` — a pattern T04 onwards will follow.

**Architecture check** — Manual grep confirms `src/vidscope/domain/` imports only: `__future__`, `dataclasses`, `datetime`, `enum`, `typing`, and its own sibling modules. Zero third-party deps, zero imports from outer layers. The rule will be enforced mechanically by import-linter in T09 but I verified it by hand now so the baseline is clean.

## Verification

Ran `python -m uv run pytest tests/unit/domain -q` → 60 tests passed in 80ms. Ran `python -m uv run python -c "import vidscope.domain as d; assert d.Platform.INSTAGRAM; assert d.StageName.INGEST; assert issubclass(d.IngestError, d.DomainError); assert issubclass(d.StageCrashError, d.DomainError); [hasattr(d, n) for n in d.__all__]; print('domain ok', len(d.__all__), 'exports')"` → `domain ok 21 exports`. Ran `grep -rhE "^(from|import)" src/vidscope/domain/` → only stdlib (`__future__`, `dataclasses`, `datetime`, `enum`, `typing`) and intra-domain imports appear. No third-party or outer-layer imports.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/domain -q` | 0 | ✅ pass | 80ms |
| 2 | `python -m uv run python -c "import vidscope.domain as d; assert d.Platform.INSTAGRAM; assert d.StageName.INGEST; assert issubclass(d.IngestError, d.DomainError); print('domain ok', len(d.__all__), 'exports')"` | 0 | ✅ pass | 500ms |
| 3 | `grep -rhE '^(from|import)' src/vidscope/domain/ | sort -u` | 0 | ✅ pass — only stdlib + intra-domain imports | 30ms |

## Deviations

None from the replanned T03. The original plan mentioned "IndexError" as a subclass name; I used "IndexingError" instead to avoid shadowing the built-in `IndexError` which would have been a subtle footgun in any module that does `except IndexError:`. Updated KNOWLEDGE.md-style intent is preserved via the alias.

## Known Issues

None. Every planned module and test file exists, every test passes, the architectural invariant (no outer-layer imports, no third-party imports) is satisfied.

## Files Created/Modified

- `src/vidscope/domain/__init__.py`
- `src/vidscope/domain/values.py`
- `src/vidscope/domain/errors.py`
- `src/vidscope/domain/entities.py`
- `tests/unit/domain/test_values.py`
- `tests/unit/domain/test_entities.py`
- `tests/unit/domain/test_errors.py`
