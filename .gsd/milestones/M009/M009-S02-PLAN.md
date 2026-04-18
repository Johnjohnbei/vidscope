---
phase: M009
plan: S02
type: execute
wave: 2
depends_on: [S01]
files_modified:
  - src/vidscope/pipeline/stages/stats_stage.py
  - src/vidscope/pipeline/stages/__init__.py
  - src/vidscope/application/refresh_stats.py
  - src/vidscope/application/__init__.py
  - src/vidscope/cli/commands/stats.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - src/vidscope/infrastructure/container.py
  - tests/unit/pipeline/stages/test_stats_stage.py
  - tests/unit/application/test_refresh_stats.py
  - tests/unit/cli/test_stats.py
  - tests/unit/cli/test_app.py
autonomous: true
requirements: [R051]
must_haves:
  truths:
    - "`StatsStage.execute(ctx, uow)` appelle `StatsProbe.probe_stats(url)` puis `uow.video_stats.append(stats)`"
    - "`StatsStage.is_satisfied(ctx, uow)` retourne toujours False (append-only — D031)"
    - "`RefreshStatsUseCase.execute(video_id)` exécute `StatsStage` via le pipeline_runner standalone pour UN video_id"
    - "`RefreshStatsUseCase.execute_for_all(since=None)` itère les video_ids et exécute `StatsStage` per-video avec error isolation"
    - "`vidscope refresh-stats <id>` fonctionne pour un video_id donné"
    - "`vidscope refresh-stats --all [--since 7d]` itère toutes les vidéos (ou filtrées par fraîcheur)"
    - "`vidscope refresh-stats --limit 0` est refusé avec une erreur claire (T-INPUT-01)"
    - "StatsStage N'EST PAS enregistré dans le graphe `add` par défaut (anti-pitfall M009)"
  artifacts:
    - path: "src/vidscope/pipeline/stages/stats_stage.py"
      provides: "StatsStage standalone (hors pipeline add)"
      contains: "class StatsStage"
    - path: "src/vidscope/application/refresh_stats.py"
      provides: "RefreshStatsUseCase pour single-video + batch"
      contains: "class RefreshStatsUseCase"
    - path: "src/vidscope/cli/commands/stats.py"
      provides: "vidscope refresh-stats sub-application Typer"
      contains: "stats_app"
    - path: "tests/unit/pipeline/stages/test_stats_stage.py"
      provides: "Tests StatsStage + is_satisfied=False invariant"
      contains: "is_satisfied"
  key_links:
    - from: "src/vidscope/cli/app.py"
      to: "stats_app"
      via: "app.add_typer(stats_app, name='stats')"
      pattern: "stats_app"
    - from: "src/vidscope/application/refresh_stats.py"
      to: "StatsStage"
      via: "PipelineRunner.run avec stages standalone"
      pattern: "StatsStage"
    - from: "src/vidscope/infrastructure/container.py"
      to: "StatsStage"
      via: "Container.stats_stage standalone (hors pipeline_runner.stages par défaut)"
      pattern: "StatsStage\\("
---

<objective>
S02 livre le stage `StatsStage` et la commande CLI `vidscope refresh-stats`. Le stage est STANDALONE — il n'est PAS inclus dans le graphe `add` par défaut (patron `VisualIntelligenceStage` M008). `RefreshStatsUseCase` orchestre l'exécution pour un video_id ou un lot (avec error isolation). Typer valide `--limit >= 1` (T-INPUT-01).

Purpose: Sans ce plan, les users n'ont aucun moyen de re-probe les stats d'une vidéo déjà ingérée. C'est la brique opérationnelle qui permet d'alimenter `video_stats` à intervalles réguliers via cron/Task Scheduler (M003).
Output: StatsStage + use case + commande CLI + Container.stats_stage.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M009/M009-S01-PLAN.md
@.gsd/milestones/M009/M009-S01-SUMMARY.md
@.gsd/milestones/M009/M009-CONTEXT.md
@.gsd/milestones/M009/M009-RESEARCH.md
@.gsd/milestones/M009/M009-VALIDATION.md
@.gsd/KNOWLEDGE.md
@src/vidscope/pipeline/stages/visual_intelligence.py
@src/vidscope/pipeline/stages/__init__.py
@src/vidscope/pipeline/runner.py
@src/vidscope/ports/pipeline.py
@src/vidscope/ports/stats_probe.py
@src/vidscope/application/cookies.py
@src/vidscope/cli/commands/cookies.py
@src/vidscope/cli/app.py
@src/vidscope/infrastructure/container.py

<interfaces>
Patterns et signatures clés :

**Stage Protocol (ports/pipeline.py)** : chaque stage implémente
```python
def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult: ...
def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool: ...
name: str  # from StageName enum
```

**StageName.STATS** (ajouté en S01) : `StageName.STATS.value == "stats"`.

**StatsStage cible** :
```python
class StatsStage:
    name: str = StageName.STATS.value

    def __init__(self, *, stats_probe: StatsProbe) -> None:
        self._probe = stats_probe

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        return False   # Always re-probe (append-only, D031)

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        probed = self._probe.probe_stats(ctx.source_url)
        if probed is None:
            return StageResult(ok=False, error="stats probe returned no data")
        stats = replace(probed, video_id=ctx.video_id)
        uow.video_stats.append(stats)
        return StageResult(ok=True, message=f"appended stats row for video_id={ctx.video_id}")
```

**RefreshStatsUseCase cible (use case standalone, PAS via PipelineRunner complet)** :
```python
class RefreshStatsUseCase:
    def __init__(self, *, stats_stage: StatsStage, unit_of_work_factory: UnitOfWorkFactory) -> None: ...

    def execute_one(self, video_id: VideoId) -> RefreshStatsResult: ...
    def execute_all(self, *, since: timedelta | None = None, limit: int = 1000) -> RefreshStatsBatchResult: ...
```

**CLI pattern (sub-application Typer avec `Annotated`)** : suivre `cookies_app` dans `cli/commands/cookies.py`. `handle_domain_errors` + `acquire_container`.

**Graphe pipeline add par défaut** : dans `container.py`, `pipeline_runner = PipelineRunner(stages=[ingest, transcribe, frames, analyze, visual_intelligence, metadata_extract, index], ...)`. StatsStage ne doit PAS être dans cette liste — il est exposé séparément via `Container.stats_stage`.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: StatsStage standalone (is_satisfied=False toujours) + wiring Container + tests</name>
  <files>src/vidscope/pipeline/stages/stats_stage.py, src/vidscope/pipeline/stages/__init__.py, src/vidscope/infrastructure/container.py, tests/unit/pipeline/stages/test_stats_stage.py</files>
  <read_first>
    - src/vidscope/pipeline/stages/visual_intelligence.py (pattern stage standalone M008 — is_satisfied + execute + typed errors)
    - src/vidscope/pipeline/stages/__init__.py (exports existants)
    - src/vidscope/ports/pipeline.py (Stage Protocol + PipelineContext + StageResult)
    - src/vidscope/ports/stats_probe.py (StatsProbe — livré en S01)
    - src/vidscope/domain/__init__.py (re-export VideoStats + StageName.STATS livrés en S01)
    - src/vidscope/infrastructure/container.py (pattern ajouter un stage au Container sans l'ajouter au graphe par défaut)
    - tests/unit/pipeline/stages/test_metadata_extract_stage.py si existant — ou autre test stage pour pattern
    - tests/unit/pipeline/test_runner.py (pattern PipelineContext stub)
    - .gsd/milestones/M009/M009-RESEARCH.md (Pattern 5, Pitfall 3 : ne PAS inclure dans pipeline add)
    - .gsd/milestones/M009/M009-CONTEXT.md (D-01 idempotence, D-03 None != 0)
  </read_first>
  <behavior>
    - Test 1 : `StatsStage.name == "stats"` (valeur de `StageName.STATS`).
    - Test 2 : `is_satisfied(ctx, uow)` retourne TOUJOURS False, quelle que soit l'existence de rows dans `video_stats`.
    - Test 3 : `execute(ctx, uow)` appelle `stats_probe.probe_stats(ctx.source_url)` (ou l'URL disponible dans ctx).
    - Test 4 : Sur succès probe, le résultat est passé à `uow.video_stats.append(stats)` avec `video_id = ctx.video_id` substitué.
    - Test 5 : Si `probe_stats` retourne `None`, `execute` retourne un `StageResult` FAILED (ou équivalent) avec un message explicite, sans crasher.
    - Test 6 : Le stage n'est PAS dans la liste `pipeline_runner.stages` du Container (tests container/integration).
    - Test 7 : Le Container expose `stats_stage: StatsStage` comme attribut séparé.
  </behavior>
  <action>
Étape 1 — Lire en premier `src/vidscope/pipeline/stages/visual_intelligence.py` et `src/vidscope/ports/pipeline.py` pour découvrir les noms EXACTS de `StageResult`, `PipelineContext`, et le Stage Protocol. Répliquer le pattern : imports, Typed errors (si applicable), docstring, `name: str = StageName.STATS.value`.

Étape 2 — Créer `src/vidscope/pipeline/stages/stats_stage.py` :
```python
"""StatsStage — metadata-only probe appended to the video_stats table.

Standalone stage (M008 pattern from VisualIntelligenceStage): NOT
registered in the default `vidscope add` pipeline graph. Invoked only
by RefreshStatsUseCase and vidscope refresh-stats / vidscope watch
refresh.

Append-only contract (D031):
- is_satisfied() always returns False so every invocation produces a
  fresh snapshot (deduplication is handled by the repository via
  UNIQUE(video_id, captured_at) — D-01).
- Missing counters stay None (D-03) — never replaced with 0.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from vidscope.domain import StageName, VideoStats
from vidscope.ports import PipelineContext, StageResult, UnitOfWork
from vidscope.ports.stats_probe import StatsProbe

__all__ = ["StatsStage"]

_logger = logging.getLogger(__name__)


class StatsStage:
    """Append-only stats probe stage.

    Executes StatsProbe.probe_stats() and writes one row to video_stats
    via UnitOfWork.video_stats.append(). The PipelineRunner handles the
    pipeline_runs row and the transactional bundle.
    """

    name: str = StageName.STATS.value

    def __init__(self, *, stats_probe: StatsProbe) -> None:
        self._probe = stats_probe

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Always False — append-only, every invocation creates a new row."""
        return False

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        url = ctx.source_url
        if not url:
            return StageResult(
                ok=False,
                stage=self.name,
                error="stats stage requires ctx.source_url",
            )

        probed = self._probe.probe_stats(url)
        if probed is None:
            return StageResult(
                ok=False,
                stage=self.name,
                error=f"stats probe returned no data for {url}",
            )

        if ctx.video_id is None:
            return StageResult(
                ok=False,
                stage=self.name,
                error="stats stage requires ctx.video_id (video must be ingested)",
            )

        stats = replace(probed, video_id=ctx.video_id)
        uow.video_stats.append(stats)
        return StageResult(
            ok=True,
            stage=self.name,
            message=(
                f"stats appended for video_id={ctx.video_id} "
                f"(views={stats.view_count}, likes={stats.like_count})"
            ),
        )
```

**CRITIQUE** : Adapter les noms de champ `StageResult` et `PipelineContext` à ce qui est réellement défini dans `src/vidscope/ports/pipeline.py`. Si `StageResult` a un champ différent (ex : `success` au lieu de `ok`, pas de `stage`/`error`), corriger en lisant le fichier réel. La forme exacte peut varier — le comportement (ok=True/False + message d'erreur actionnable + stage name) reste invariant.

Étape 3 — Mettre à jour `src/vidscope/pipeline/stages/__init__.py` : ajouter l'import et `"StatsStage"` dans `__all__`.

Étape 4 — Étendre `src/vidscope/infrastructure/container.py` :

(a) Dans le dataclass `Container`, ajouter `stats_stage: "StatsStage"` (après `pipeline_runner`).

(b) Dans `build_container()`, après l'instanciation du `stats_probe` (livré en S01) :
```python
stats_stage = StatsStage(stats_probe=stats_probe)
```

(c) **NE PAS ajouter `stats_stage` à la liste `stages=[...]` de `PipelineRunner`.** Il reste standalone.

(d) Dans le retour `Container(...)`, ajouter `stats_stage=stats_stage`.

(e) Importer `StatsStage` en haut du fichier : `from vidscope.pipeline.stages import StatsStage` (ajouter à l'import existant `AnalyzeStage, FramesStage, ...`).

Étape 5 — Créer `tests/unit/pipeline/stages/test_stats_stage.py` :
```python
"""Unit tests for StatsStage — is_satisfied=False invariant + happy path."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from vidscope.domain import StageName, VideoId, VideoStats
from vidscope.pipeline.stages.stats_stage import StatsStage


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
    stage = StatsStage(stats_probe=_FakeStatsProbe(None))
    assert stage.name == StageName.STATS.value == "stats"


def test_is_satisfied_always_returns_false_even_after_prior_rows() -> None:
    """D031 append-only: we never skip because prior rows exist."""
    stage = StatsStage(stats_probe=_FakeStatsProbe(None))
    ctx = _make_ctx()
    uow = _make_uow()
    uow.video_stats.has_any_for_video = MagicMock(return_value=True)
    assert stage.is_satisfied(ctx, uow) is False
    uow.video_stats.has_any_for_video = MagicMock(return_value=False)
    assert stage.is_satisfied(ctx, uow) is False


def test_execute_probes_url_and_appends_with_substituted_video_id() -> None:
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
    assert getattr(result, "ok", None) is True or getattr(result, "success", None) is True


def test_execute_handles_probe_returning_none() -> None:
    stage = StatsStage(stats_probe=_FakeStatsProbe(None))
    ctx = _make_ctx()
    uow = _make_uow()
    result = stage.execute(ctx, uow)
    uow.video_stats.append.assert_not_called()
    # ok / success must be falsy
    ok = getattr(result, "ok", getattr(result, "success", None))
    assert ok is False or ok is None


def test_execute_requires_video_id() -> None:
    stage = StatsStage(
        stats_probe=_FakeStatsProbe(VideoStats(
            video_id=VideoId(0),
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        )),
    )
    ctx = _make_ctx(video_id=None)
    uow = _make_uow()
    result = stage.execute(ctx, uow)
    uow.video_stats.append.assert_not_called()
    ok = getattr(result, "ok", getattr(result, "success", None))
    assert ok is False or ok is None


def test_stats_stage_not_in_default_pipeline(monkeypatch, tmp_path) -> None:
    """Pitfall-3 guard: StatsStage must NOT be in pipeline_runner.stages."""
    from vidscope.infrastructure.container import build_container
    from vidscope.infrastructure.config import Config

    cfg = Config(data_dir=tmp_path / "data", db_path=str(tmp_path / "v.db"),
                 cache_dir=tmp_path / "cache", models_dir=tmp_path / "models",
                 analyzer_name="heuristic", whisper_model="base", cookies_file=None)
    container = build_container(cfg)
    stage_names = {getattr(s, "name", None) for s in container.pipeline_runner.stages}
    assert "stats" not in stage_names
    # But container exposes stats_stage separately
    assert hasattr(container, "stats_stage")
    assert container.stats_stage.name == "stats"
```

**Note** : Le test `test_stats_stage_not_in_default_pipeline` dépend de la signature exacte de `Config`. Si cette signature ne correspond pas à celle réelle, lire `src/vidscope/infrastructure/config.py` et adapter. Si `build_container(cfg)` fait des appels I/O non triviaux dans les tests unitaires, **simplifier le test** en inspectant directement le module source : `grep -c "stats_stage" src/vidscope/infrastructure/container.py` doit retourner >= 2 (une déclaration champ + une instanciation) ET `grep -q "StatsStage" dans la liste stages=[` du `PipelineRunner(...)` doit retourner 1 (no match). Alternative plus simple : écrire un test text-based qui ouvre `container.py` comme string, vérifie que `StatsStage(` apparaît hors de la liste `stages=[...]`.

Étape 6 — Exécuter :
```
uv run pytest tests/unit/pipeline/ tests/unit/infrastructure/ tests/unit/domain/ -x -q
uv run lint-imports
```

NE PAS importer `vidscope.adapters.*` depuis `pipeline/` (contrat `pipeline-has-no-adapters`). NE PAS ajouter `stats_stage` dans `pipeline_runner.stages=[...]`.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/pipeline/stages/test_stats_stage.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class StatsStage" src/vidscope/pipeline/stages/stats_stage.py` matches
    - `grep -n "return False" src/vidscope/pipeline/stages/stats_stage.py` matches (is_satisfied)
    - `grep -n "StageName.STATS.value" src/vidscope/pipeline/stages/stats_stage.py` matches
    - `grep -n "StatsStage" src/vidscope/pipeline/stages/__init__.py` matches
    - `grep -n "stats_stage: " src/vidscope/infrastructure/container.py` matches (champ Container)
    - `grep -n "StatsStage(stats_probe=" src/vidscope/infrastructure/container.py` matches
    - La liste `stages=[` dans `container.py` (autour de `pipeline_runner = PipelineRunner(`) NE CONTIENT PAS `stats_stage` — vérifier par lecture du fichier (ligne `stages=[ingest_stage, transcribe_stage, frames_stage, analyze_stage, visual_intelligence_stage, metadata_extract_stage, index_stage]` ou équivalent reste inchangé côté composition, `stats_stage` apparaît hors liste).
    - `uv run pytest tests/unit/pipeline/stages/test_stats_stage.py -x -q` exits 0
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - StatsStage créé avec is_satisfied=False invariant
    - Container étendu : stats_stage attribute + hors du pipeline_runner.stages
    - 5+ tests unitaires verts
    - pipeline-has-no-adapters contract vert
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: RefreshStatsUseCase (single + batch) + wiring Container + tests</name>
  <files>src/vidscope/application/refresh_stats.py, src/vidscope/application/__init__.py, src/vidscope/infrastructure/container.py, tests/unit/application/test_refresh_stats.py</files>
  <read_first>
    - src/vidscope/application/cookies.py (pattern use case avec DTO frozen + execute() method)
    - src/vidscope/application/ingest_video.py (pattern use case orchestrant un stage via UoW)
    - src/vidscope/application/watchlist.py (pattern batch avec per-item error isolation)
    - src/vidscope/application/__init__.py (liste __all__)
    - src/vidscope/pipeline/stages/stats_stage.py (StatsStage livré en Task 1)
    - src/vidscope/ports/unit_of_work.py (UnitOfWorkFactory Protocol)
    - src/vidscope/domain/__init__.py (VideoId, VideoStats, types)
    - tests/unit/application/test_ingest_video.py (pattern stub stage + uow factory)
    - tests/unit/application/conftest.py (fixtures InMemory)
    - .gsd/KNOWLEDGE.md (ligne 70 : application ne peut PAS importer infrastructure)
  </read_first>
  <behavior>
    - Test 1 : `execute_one(video_id)` fetche l'URL de la vidéo via `uow.videos.get(video_id)`, puis exécute `stats_stage` dans une transaction.
    - Test 2 : `execute_one` retourne un `RefreshStatsResult` avec `success=True` et `video_id`, `captured_at`, compteurs quand OK.
    - Test 3 : `execute_one` sur un video_id inexistant retourne `success=False` avec message `"video not found"`.
    - Test 4 : `execute_one` quand le probe échoue retourne `success=False` avec le message du stage.
    - Test 5 : `execute_all(limit=10)` itère les vidéos (via `uow.videos.list(...)` ou équivalent) et exécute `stats_stage` par vidéo avec per-video error isolation.
    - Test 6 : `execute_all(since=timedelta(days=7))` filtre les vidéos ingérées ≥ il y a 7j (ou autre logique documentée).
    - Test 7 : Une erreur sur une vidéo N'INTERROMPT PAS le batch — les autres vidéos sont toujours probe'd.
  </behavior>
  <action>
Étape 1 — Lire `src/vidscope/application/ingest_video.py` pour saisir le pattern EXACT (UoW factory, PipelineContext construction, clock injection). Lire aussi `src/vidscope/domain/entities.py` pour la signature de `Video` (champs `url`, `created_at`, etc.).

Étape 2 — Créer `src/vidscope/application/refresh_stats.py` :
```python
"""RefreshStatsUseCase — orchestrate StatsStage for one or many videos.

The use case is self-contained: it takes a StatsStage + UnitOfWorkFactory
+ Clock and runs the stage inside a fresh transaction per video. Per-
video error isolation matches M003's RefreshWatchlistUseCase pattern:
one broken video doesn't stop the batch.

NO INFRASTRUCTURE IMPORT (import-linter application-has-no-adapters).
The caller in cli/commands/stats.py builds a container and wires
this use case with its dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from vidscope.domain import VideoId, VideoStats
from vidscope.pipeline.stages.stats_stage import StatsStage
from vidscope.ports import PipelineContext, UnitOfWorkFactory
from vidscope.ports.clock import Clock

__all__ = [
    "RefreshStatsBatchResult",
    "RefreshStatsResult",
    "RefreshStatsUseCase",
]


@dataclass(frozen=True, slots=True)
class RefreshStatsResult:
    """Outcome of a single refresh-stats invocation."""

    success: bool
    video_id: int | None
    stats: VideoStats | None
    message: str


@dataclass(frozen=True, slots=True)
class RefreshStatsBatchResult:
    """Outcome of a batch refresh-stats invocation."""

    total: int
    refreshed: int
    failed: int
    per_video: tuple[RefreshStatsResult, ...]


class RefreshStatsUseCase:
    """Refresh video_stats for a single video or a batch.

    Dependencies injected via constructor (hexagonal architecture). No
    direct filesystem or network access — everything goes through
    StatsStage / UnitOfWork / Clock.
    """

    def __init__(
        self,
        *,
        stats_stage: StatsStage,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
    ) -> None:
        self._stage = stats_stage
        self._uow = unit_of_work_factory
        self._clock = clock

    def execute_one(self, video_id: VideoId) -> RefreshStatsResult:
        """Refresh stats for one video. Returns success/failure + message."""
        with self._uow() as uow:
            video = uow.videos.get(video_id)
            if video is None:
                return RefreshStatsResult(
                    success=False,
                    video_id=int(video_id),
                    stats=None,
                    message=f"video not found: id={int(video_id)}",
                )

            ctx = PipelineContext(
                source_url=video.url,
                video_id=video_id,
                started_at=self._clock.now(),
            )

            # StatsStage is standalone — we call execute() directly, the
            # PipelineRunner is for the default `add` graph only.
            result = self._stage.execute(ctx, uow)

            # Adapt field names to whatever StageResult exposes (ok vs success)
            ok = getattr(result, "ok", getattr(result, "success", False))
            if not ok:
                err_msg = getattr(result, "error", None) or getattr(result, "message", "stats stage failed")
                return RefreshStatsResult(
                    success=False,
                    video_id=int(video_id),
                    stats=None,
                    message=str(err_msg),
                )

            latest = uow.video_stats.latest_for_video(video_id)
            msg = getattr(result, "message", "stats refreshed")
            return RefreshStatsResult(
                success=True,
                video_id=int(video_id),
                stats=latest,
                message=str(msg),
            )

    def execute_all(
        self,
        *,
        since: timedelta | None = None,
        limit: int = 1000,
    ) -> RefreshStatsBatchResult:
        """Refresh stats for up to `limit` videos. Per-video error isolation.

        If `since` is provided, only videos ingested within that window
        are refreshed (by created_at). Otherwise all videos up to `limit`.
        """
        if limit < 1:
            raise ValueError("limit must be >= 1 (T-INPUT-01)")

        # Collect video ids in a read-only UoW scope
        with self._uow() as read_uow:
            videos = read_uow.videos.list_recent(limit=limit)  # see note below

        if since is not None:
            cutoff = self._clock.now() - since
            videos = [v for v in videos if v.created_at is not None and v.created_at >= cutoff]

        per_video: list[RefreshStatsResult] = []
        refreshed = 0
        failed = 0
        for video in videos:
            if video.id is None:
                continue
            try:
                res = self.execute_one(video.id)
            except Exception as exc:  # noqa: BLE001 — batch isolation
                res = RefreshStatsResult(
                    success=False,
                    video_id=int(video.id) if video.id is not None else None,
                    stats=None,
                    message=f"unexpected error: {exc}",
                )
            per_video.append(res)
            if res.success:
                refreshed += 1
            else:
                failed += 1

        return RefreshStatsBatchResult(
            total=len(per_video),
            refreshed=refreshed,
            failed=failed,
            per_video=tuple(per_video),
        )
```

**Adaptation nécessaire** :
- `uow.videos.list_recent(limit=...)` : vérifier le nom réel via lecture de `src/vidscope/ports/repositories.py` (`VideoRepository`). Si la méthode s'appelle `list(limit=...)` ou `list_all(limit=...)`, adapter. Si aucune méthode liste simple n'existe, créer une variante minimale ou utiliser l'existant via `search_library` / `list_videos` use case.
- `PipelineContext(...)` : adapter les noms EXACTS selon `src/vidscope/ports/pipeline.py` (par exemple `url` vs `source_url`, `video_id` vs `video`).

Étape 3 — Étendre `src/vidscope/application/__init__.py` : ajouter l'import et `"RefreshStatsUseCase"` (+ DTOs) dans `__all__`.

Étape 4 — Étendre `src/vidscope/infrastructure/container.py` pour instancier `RefreshStatsUseCase` :
Ce n'est pas obligatoirement un champ du `Container` dataclass (le CLI peut l'instancier avec les dépendances du Container) — conforme au pattern des autres use cases (ils ne sont PAS tous dans le dataclass). Inspecter les use cases déjà câblés pour confirmer. Si certains use cases sont dans le Container (ex : `pipeline_runner`), suivre ce pattern : ajouter `refresh_stats: RefreshStatsUseCase`. Sinon, laisser le CLI instancier.

Étape 5 — Créer `tests/unit/application/test_refresh_stats.py` :
```python
"""Unit tests for RefreshStatsUseCase — single + batch + error isolation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from vidscope.application.refresh_stats import (
    RefreshStatsBatchResult,
    RefreshStatsResult,
    RefreshStatsUseCase,
)
from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats


class _FrozenClock:
    def __init__(self, now: datetime) -> None:
        self._now = now
    def now(self) -> datetime:
        return self._now


def _make_video(*, vid: int, url: str = "https://x.y/a", days_old: int = 0) -> Video:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    return Video(
        id=VideoId(vid),
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"p{vid}"),
        url=url,
        created_at=now - timedelta(days=days_old),
    )


def _make_uow_factory(*, videos: list[Video], latest_stats: dict[int, VideoStats] | None = None) -> Any:
    latest_stats = latest_stats or {}

    class _FakeUoW:
        def __init__(self) -> None:
            self.videos = MagicMock()
            self.videos.get = MagicMock(side_effect=lambda vid: next((v for v in videos if v.id == vid), None))
            self.videos.list_recent = MagicMock(return_value=videos)
            self.video_stats = MagicMock()
            self.video_stats.latest_for_video = MagicMock(
                side_effect=lambda vid: latest_stats.get(int(vid))
            )
        def __enter__(self) -> Any:
            return self
        def __exit__(self, *_: Any) -> None:
            return None

    def factory() -> Any:
        return _FakeUoW()
    return factory


def _make_stage(*, ok: bool = True, error: str = "") -> Any:
    stage = MagicMock()
    result = MagicMock()
    result.ok = ok
    result.success = ok
    result.error = error
    result.message = "stats appended" if ok else error
    stage.execute = MagicMock(return_value=result)
    return stage


def test_execute_one_video_not_found() -> None:
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(),
        unit_of_work_factory=_make_uow_factory(videos=[]),
        clock=_FrozenClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    result = uc.execute_one(VideoId(999))
    assert result.success is False
    assert "not found" in result.message


def test_execute_one_happy_path() -> None:
    video = _make_video(vid=1)
    latest = VideoStats(
        video_id=VideoId(1),
        captured_at=datetime(2026, 1, 10, tzinfo=UTC),
        view_count=500,
    )
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(ok=True),
        unit_of_work_factory=_make_uow_factory(videos=[video], latest_stats={1: latest}),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    result = uc.execute_one(VideoId(1))
    assert result.success is True
    assert result.stats is not None
    assert result.stats.view_count == 500


def test_execute_one_probe_failure() -> None:
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(ok=False, error="probe returned no data"),
        unit_of_work_factory=_make_uow_factory(videos=[_make_video(vid=1)]),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    result = uc.execute_one(VideoId(1))
    assert result.success is False
    assert "probe" in result.message


def test_execute_all_isolates_per_video_errors() -> None:
    videos = [_make_video(vid=1), _make_video(vid=2), _make_video(vid=3)]
    # Stage will alternate: v1 ok, v2 raises, v3 ok
    stage = MagicMock()
    call_count = {"n": 0}
    def _exec(ctx: Any, uow: Any) -> Any:
        call_count["n"] += 1
        r = MagicMock()
        if call_count["n"] == 2:
            raise RuntimeError("network down")
        r.ok = True
        r.success = True
        r.message = "ok"
        return r
    stage.execute = _exec

    uc = RefreshStatsUseCase(
        stats_stage=stage,
        unit_of_work_factory=_make_uow_factory(videos=videos),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    batch = uc.execute_all(limit=10)
    assert batch.total == 3
    assert batch.refreshed == 2
    assert batch.failed == 1


def test_execute_all_since_filter() -> None:
    old = _make_video(vid=1, days_old=30)
    recent = _make_video(vid=2, days_old=3)
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(ok=True),
        unit_of_work_factory=_make_uow_factory(videos=[old, recent]),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    batch = uc.execute_all(since=timedelta(days=7), limit=10)
    assert batch.total == 1
    assert batch.per_video[0].video_id == 2


def test_execute_all_rejects_limit_zero() -> None:
    uc = RefreshStatsUseCase(
        stats_stage=_make_stage(),
        unit_of_work_factory=_make_uow_factory(videos=[]),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    import pytest
    with pytest.raises(ValueError, match="limit"):
        uc.execute_all(limit=0)
```

**Adaptation** : si `uow.videos` n'a pas de méthode `list_recent(limit=)`, remplacer par la méthode existante (ex : `list(limit=)`, ou utiliser `search_library` use case). Vérifier en lisant `src/vidscope/adapters/sqlite/video_repository.py`. Si nécessaire, AJOUTER une méthode minimale `list_recent(limit=)` sur le repo SQLite en suivant le pattern existant (select videos order by created_at desc limit N), et l'ajouter au Protocol `VideoRepository` dans `ports/repositories.py`.

Étape 6 — Exécuter :
```
uv run pytest tests/unit/application/test_refresh_stats.py -x -q
uv run lint-imports
```

NE PAS importer `vidscope.infrastructure` dans l'application (contrat `application-has-no-adapters`).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/application/test_refresh_stats.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class RefreshStatsUseCase" src/vidscope/application/refresh_stats.py` matches
    - `grep -n "def execute_one" src/vidscope/application/refresh_stats.py` matches
    - `grep -n "def execute_all" src/vidscope/application/refresh_stats.py` matches
    - `grep -n "limit < 1" src/vidscope/application/refresh_stats.py` matches OU une validation `raise ValueError` sur limit<1 est présente
    - `grep -n "RefreshStatsUseCase" src/vidscope/application/__init__.py` matches
    - `grep -nE "^from vidscope.infrastructure" src/vidscope/application/refresh_stats.py` returns exit 1 (no match)
    - `grep -nE "^from vidscope.adapters" src/vidscope/application/refresh_stats.py` returns exit 1 (no match)
    - `uv run pytest tests/unit/application/test_refresh_stats.py -x -q` exits 0
    - `uv run lint-imports` exits 0 (application-has-no-adapters vert)
  </acceptance_criteria>
  <done>
    - RefreshStatsUseCase livré avec execute_one + execute_all
    - DTO RefreshStatsResult + RefreshStatsBatchResult frozen dataclass slots=True
    - Per-video error isolation (batch ne s'interrompt pas)
    - 6+ tests unitaires verts
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: CLI `vidscope refresh-stats` + tests + enregistrement dans app.py</name>
  <files>src/vidscope/cli/commands/stats.py, src/vidscope/cli/commands/__init__.py, src/vidscope/cli/app.py, tests/unit/cli/test_stats.py, tests/unit/cli/test_app.py</files>
  <read_first>
    - src/vidscope/cli/commands/cookies.py (pattern sub-application Typer avec `Annotated[...]` + `handle_domain_errors` + `acquire_container`)
    - src/vidscope/cli/commands/watch.py (pattern sub-app avec boucles et résumé rich.Table)
    - src/vidscope/cli/commands/__init__.py (exports existants)
    - src/vidscope/cli/app.py (enregistrement `add_typer`)
    - src/vidscope/cli/_support.py (acquire_container, handle_domain_errors, console, fail_user)
    - src/vidscope/application/refresh_stats.py (livré Task 2)
    - tests/unit/cli/test_cookies.py (pattern CliRunner + container mock)
    - tests/unit/cli/test_app.py (pattern smoke test sur la liste des commandes)
    - .gsd/KNOWLEDGE.md (règle : `Annotated[Path, typer.Argument(...)]` ; pas de glyphes unicode en stdout ; `[green]OK[/green]` en ASCII)
    - .gsd/milestones/M009/M009-CONTEXT.md (décision implicite : sub-application nommée `stats`)
  </read_first>
  <behavior>
    - Test 1 : `vidscope refresh-stats 42` exit 0 avec un résumé listant le view_count / like_count mis à jour.
    - Test 2 : `vidscope refresh-stats 999` (inexistant) exit 1 avec "not found".
    - Test 3 : `vidscope refresh-stats --all` itère les vidéos et affiche un compteur total/refreshed/failed.
    - Test 4 : `vidscope refresh-stats --all --since 7d` filtre par fenêtre.
    - Test 5 : `vidscope refresh-stats --all --limit 0` exit code != 0 (validation Typer `min=1` : T-INPUT-01).
    - Test 6 : Le `vidscope --help` liste `refresh-stats` dans les commandes.
    - Test 7 : Pas de glyphes Unicode dans les messages stdout (Windows cp1252 compat — KNOWLEDGE.md).
  </behavior>
  <action>
Étape 1 — Lire `src/vidscope/cli/commands/cookies.py` en entier pour copier le pattern sub-application Typer exact (structure, imports, décorateurs, handle_domain_errors).

Étape 2 — Créer `src/vidscope/cli/commands/stats.py` :
```python
"""`vidscope refresh-stats ...` — probe engagement counters on ingested videos.

Adds one row to `video_stats` per invocation (append-only, D031). The
command supports:
- single-video mode: `vidscope refresh-stats <video_id>`
- batch mode: `vidscope refresh-stats --all [--since 7d] [--limit 1000]`

The `stats` sub-application follows the M002/M003/M005 Typer pattern
(cookies_app / watch_app / mcp_app) and is registered on the root app
in vidscope.cli.app via add_typer.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

import typer
from rich.table import Table

from vidscope.application.refresh_stats import RefreshStatsUseCase
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)
from vidscope.domain import VideoId

__all__ = ["refresh_stats_command", "stats_app"]


stats_app = typer.Typer(
    name="stats",
    help="Refresh engagement stats for ingested videos (append-only).",
    no_args_is_help=True,
    add_completion=False,
)


def _parse_since(raw: str | None) -> timedelta | None:
    """Parse a short window string like '7d' or '24h'. Returns None if empty.

    Format: N(h|d) where N is a positive integer. Matches M009-RESEARCH
    Pitfall 5 — strict parser, not naive.
    """
    if raw is None or not raw.strip():
        return None
    s = raw.strip().lower()
    if len(s) < 2 or not s[:-1].isdigit():
        raise typer.BadParameter(
            f"invalid --since window: {raw!r} (expected N(h|d), e.g. 7d or 24h)"
        )
    n = int(s[:-1])
    unit = s[-1]
    if n <= 0:
        raise typer.BadParameter(f"--since must be positive, got {raw!r}")
    if unit == "h":
        return timedelta(hours=n)
    if unit == "d":
        return timedelta(days=n)
    raise typer.BadParameter(
        f"invalid --since unit: {unit!r} (expected 'h' or 'd')"
    )


@stats_app.callback(invoke_without_command=True)
def refresh_stats_command(
    ctx: typer.Context,
    video_id: Annotated[int | None, typer.Argument(help="Video id to refresh (omit with --all).")] = None,
    all_: Annotated[bool, typer.Option("--all", help="Refresh stats for every ingested video.")] = False,
    since: Annotated[str | None, typer.Option("--since", help="Only refresh videos ingested within this window (e.g. 7d, 24h).")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, help="Max videos to refresh in batch mode (must be >= 1).")] = 1000,
) -> None:
    """Refresh engagement stats for one video or all ingested videos."""
    # When invoked as `vidscope stats <subcommand>`, let Typer route.
    if ctx.invoked_subcommand is not None:
        return

    with handle_domain_errors():
        container = acquire_container()
        use_case = RefreshStatsUseCase(
            stats_stage=container.stats_stage,
            unit_of_work_factory=container.unit_of_work,
            clock=container.clock,
        )

        if all_:
            window = _parse_since(since)
            batch = use_case.execute_all(since=window, limit=limit)
            _render_batch(batch)
            return

        if video_id is None:
            raise fail_user("Provide a video id or use --all. See --help.")

        result = use_case.execute_one(VideoId(video_id))
        if not result.success:
            raise fail_user(result.message)
        _render_single(result)


def _render_single(result: "RefreshStatsResult") -> None:  # type: ignore[name-defined]
    stats = result.stats
    console.print(
        f"[green]OK[/green] refreshed stats for video_id={result.video_id}"
    )
    if stats is not None:
        console.print(
            f"  captured_at: {stats.captured_at.isoformat()}\n"
            f"  views: {stats.view_count}  likes: {stats.like_count}  "
            f"reposts: {stats.repost_count}  comments: {stats.comment_count}  "
            f"saves: {stats.save_count}"
        )


def _render_batch(batch: "RefreshStatsBatchResult") -> None:  # type: ignore[name-defined]
    console.print(
        f"[bold]refresh-stats:[/bold] "
        f"total={batch.total} refreshed={batch.refreshed} failed={batch.failed}"
    )
    if batch.total == 0:
        console.print("[dim]No videos matched.[/dim]")
        return

    table = Table(title=f"Refresh-stats ({batch.refreshed}/{batch.total})", show_header=True)
    table.add_column("video_id", justify="right")
    table.add_column("status")
    table.add_column("message")
    for r in batch.per_video[:100]:
        status = "[green]OK[/green]" if r.success else "[red]FAIL[/red]"
        table.add_row(str(r.video_id), status, r.message[:80])
    console.print(table)
```

Étape 3 — Mettre à jour `src/vidscope/cli/commands/__init__.py` : exporter `stats_app` et `refresh_stats_command`.

Étape 4 — Enregistrer dans `src/vidscope/cli/app.py` :
Ajouter l'import dans le bloc `from vidscope.cli.commands import (...)` : `stats_app`.
Ajouter APRÈS les `add_typer` existants :
```python
app.add_typer(stats_app, name="refresh-stats", help="Refresh engagement stats for ingested videos.")
```

**Attention** : le nom Typer ne peut pas contenir de tiret dans certaines versions. Si `add_typer(name="refresh-stats")` pose problème, utiliser `app.command("refresh-stats", ...)` avec un décorateur sur `refresh_stats_command` au lieu d'un sub-application. Tester localement lors de l'exécution. Alternative : enregistrer via `app.add_typer(stats_app, name="stats")` et documenter que la commande est `vidscope stats <id>` (simplifie mais change l'UX attendue par D-04 — vérifier avec l'utilisateur si nécessaire. **Préférence : `vidscope refresh-stats`** parce que c'est ce que le ROADMAP spécifie).

Solution la plus robuste : exposer `refresh_stats_command` directement comme commande racine (comme `add_command`, `list_command`, etc.) :
```python
# In app.py
app.command("refresh-stats", help="Refresh engagement stats for a video (or --all).")(refresh_stats_command)
```
Et retirer le bloc `stats_app = typer.Typer(...)` si non nécessaire, transformant `stats.py` en une simple function `refresh_stats_command`. Privilégier CETTE option (cohérent avec `add_command`, `status_command`, etc.).

Adapter donc `stats.py` : exposer uniquement `refresh_stats_command` en tant que fonction Typer avec les params Annotated[...] directement, sans `@stats_app.callback`.

Étape 5 — Créer `tests/unit/cli/test_stats.py` :
```python
"""CLI tests for vidscope refresh-stats via Typer CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

runner = CliRunner()


def test_refresh_stats_help_exits_zero() -> None:
    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--help"])
    assert res.exit_code == 0
    assert "refresh-stats" in res.stdout.lower() or "stats" in res.stdout.lower()


def test_refresh_stats_single_id_ok(monkeypatch, tmp_path) -> None:
    """Happy path: single id, video exists, probe returns stats."""
    # Arrange: patch acquire_container to return a mock container with:
    # - stats_stage that returns ok=True
    # - uow factory yielding a uow whose videos.get(vid) returns a Video
    # - video_stats.latest_for_video returns a VideoStats
    from unittest.mock import MagicMock

    from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats
    from datetime import UTC, datetime

    fake_video = Video(
        id=VideoId(1), platform=Platform.YOUTUBE,
        platform_id=PlatformId("abc"), url="https://x.y/a",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    fake_stats = VideoStats(
        video_id=VideoId(1),
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        view_count=100, like_count=10,
    )

    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.videos.get = MagicMock(return_value=fake_video)
    fake_uow.video_stats.latest_for_video = MagicMock(return_value=fake_stats)

    fake_stage = MagicMock()
    ok_result = MagicMock(ok=True, success=True, message="ok", error=None)
    fake_stage.execute = MagicMock(return_value=ok_result)

    fake_container = MagicMock()
    fake_container.stats_stage = fake_stage
    fake_container.unit_of_work = lambda: fake_uow
    fake_container.clock = MagicMock(now=lambda: datetime(2026, 1, 1, tzinfo=UTC))

    import vidscope.cli.commands.stats as stats_mod
    monkeypatch.setattr(stats_mod, "acquire_container", lambda: fake_container)

    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "1"])
    assert res.exit_code == 0, res.stdout
    assert "OK" in res.stdout or "refreshed" in res.stdout.lower()


def test_refresh_stats_unknown_id_exits_nonzero(monkeypatch) -> None:
    from unittest.mock import MagicMock
    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.videos.get = MagicMock(return_value=None)

    fake_container = MagicMock()
    fake_container.stats_stage = MagicMock()
    fake_container.unit_of_work = lambda: fake_uow
    fake_container.clock = MagicMock()

    import vidscope.cli.commands.stats as stats_mod
    monkeypatch.setattr(stats_mod, "acquire_container", lambda: fake_container)

    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "999"])
    assert res.exit_code != 0


def test_refresh_stats_limit_zero_rejected_by_typer() -> None:
    """T-INPUT-01: Typer's min=1 refuses --limit 0."""
    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--all", "--limit", "0"])
    assert res.exit_code != 0
    # Typer emits a usage error mentioning limit or minimum
    assert "limit" in res.stdout.lower() or "limit" in (res.stderr or "").lower()


def test_refresh_stats_invalid_since_format() -> None:
    """Pitfall 5: --since must be N(h|d), not '7' or '1week'."""
    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--all", "--since", "1week"])
    assert res.exit_code != 0


def test_cli_output_has_no_unicode_glyphs(monkeypatch, capsys) -> None:
    """KNOWLEDGE.md: no unicode glyphs in CLI stdout (Windows cp1252)."""
    # Happy-path invocation followed by glyph scan
    from unittest.mock import MagicMock
    from datetime import UTC, datetime
    from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats

    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.videos.get = MagicMock(return_value=Video(
        id=VideoId(1), platform=Platform.YOUTUBE, platform_id=PlatformId("a"),
        url="https://x.y/a", created_at=datetime(2026, 1, 1, tzinfo=UTC),
    ))
    fake_uow.video_stats.latest_for_video = MagicMock(return_value=VideoStats(
        video_id=VideoId(1), captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    ))

    fake_container = MagicMock()
    fake_container.stats_stage = MagicMock()
    fake_container.stats_stage.execute = MagicMock(return_value=MagicMock(ok=True, success=True, message="ok", error=None))
    fake_container.unit_of_work = lambda: fake_uow
    fake_container.clock = MagicMock(now=lambda: datetime(2026, 1, 1, tzinfo=UTC))

    import vidscope.cli.commands.stats as stats_mod
    monkeypatch.setattr(stats_mod, "acquire_container", lambda: fake_container)

    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "1"])
    forbidden = ["\u2713", "\u2717", "\u2192", "\u2190"]
    for glyph in forbidden:
        assert glyph not in res.stdout
```

Étape 6 — Étendre `tests/unit/cli/test_app.py` :
Ajouter un test qui vérifie que `refresh-stats` apparaît dans le help :
```python
def test_app_help_lists_refresh_stats() -> None:
    from vidscope.cli.app import app
    from typer.testing import CliRunner
    res = CliRunner().invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "refresh-stats" in res.stdout.lower()
```

Étape 7 — Exécuter :
```
uv run pytest tests/unit/cli/test_stats.py tests/unit/cli/test_app.py -x -q
uv run lint-imports
```

NE PAS utiliser de glyphes Unicode en stdout (`\u2713`, `\u2717`, etc.). Utiliser `[green]OK[/green]` / `[red]FAIL[/red]` ASCII.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/cli/test_stats.py tests/unit/cli/test_app.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "def refresh_stats_command" src/vidscope/cli/commands/stats.py` matches
    - `grep -n "refresh-stats" src/vidscope/cli/app.py` matches (enregistrement)
    - `grep -n "min=1" src/vidscope/cli/commands/stats.py` matches (T-INPUT-01 Typer validation)
    - `grep -nE "(\\\\u2713|\\\\u2717|\\\\u2192)" src/vidscope/cli/commands/stats.py` returns exit 1 (no unicode glyph)
    - `grep -nE "\\[green\\]OK\\[/green\\]" src/vidscope/cli/commands/stats.py` matches (ASCII tag)
    - `uv run pytest tests/unit/cli/test_stats.py -x -q` exits 0
    - `uv run vidscope refresh-stats --help` (or `uv run python -m vidscope.cli.app refresh-stats --help`) exits 0
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - `vidscope refresh-stats <id> | --all [--since Nd] [--limit M]` fonctionnel
    - Typer valide `--limit >= 1` (T-INPUT-01 résolu)
    - `--since` parser strict (refuse `1week`, `7`)
    - ASCII-only output (compatible Windows cp1252 — KNOWLEDGE.md)
    - 6+ tests unitaires CLI verts
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI → RefreshStatsUseCase | user input (video_id, `--limit`, `--since`) entre dans l'application |
| RefreshStatsUseCase → StatsStage → StatsProbe | URL propagée vers yt-dlp — mais l'URL vient de la DB (validée à l'ingest M001) |
| StatsProbe → video_stats table | données externes yt-dlp avant écriture — déjà validées par `_int_or_none` en S01 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INPUT-01 | DoS | `vidscope refresh-stats --limit` | mitigate | Typer `Option("--limit", min=1, ...)` refuse `0` et les négatifs au parse time. Double validation dans `execute_all` via `if limit < 1: raise ValueError`. |
| T-INPUT-02 | Input Validation | `vidscope refresh-stats --since` | mitigate | Parser `_parse_since` strict format `N(h|d)`. Refuse `1week`, `7` (sans unité), formats négatifs. Erreur via `typer.BadParameter` (exit 2 avec message clair). |
| T-PIPELINE-01 | Availability | Batch mode per-video failure | mitigate | Chaque `execute_one` appelé dans `execute_all` est wrappé dans `try/except Exception` — une erreur sur une vidéo n'interrompt pas le batch. Le résumé liste les failed séparément. |
| T-DATA-01 | Tampering | yt-dlp dict → video_stats (hérité de S01) | mitigate | `_int_or_none` appliqué en S01 sur chaque champ. StatsStage ne fait que déplacer l'entité existante vers `uow.video_stats.append`. |
</threat_model>

<verification>
Après les 3 tâches :
- `uv run pytest tests/unit/pipeline/ tests/unit/application/ tests/unit/cli/ -x -q` vert
- `uv run lint-imports` vert (pipeline-has-no-adapters, application-has-no-adapters)
- `uv run vidscope refresh-stats --help` exits 0 (l'entrée `refresh-stats` apparaît dans `vidscope --help`)
- `uv run vidscope refresh-stats --all --limit 0` exit != 0 (T-INPUT-01)
- Aucun glyphe unicode (`\u2713`, `\u2717`, `\u2192`, `\u2190`) dans `src/vidscope/cli/commands/stats.py` (vérifié par grep)
- `container.stats_stage.name == "stats"` et StatsStage n'est pas dans `container.pipeline_runner.stages`
</verification>

<success_criteria>
S02 est complet quand :
- [ ] `StatsStage` livré, `is_satisfied` retourne toujours False
- [ ] Container expose `stats_stage` mais ne l'inclut PAS dans le graphe `add`
- [ ] `RefreshStatsUseCase` orchestre single + batch avec per-video error isolation
- [ ] `vidscope refresh-stats <id> | --all [--since Nd] [--limit M]` fonctionnel
- [ ] Typer `--limit min=1` (T-INPUT-01)
- [ ] Parser `--since` strict (`N(h|d)`, refuse autres formats)
- [ ] Aucun glyphe unicode en stdout (compat Windows cp1252)
- [ ] Suite tests unit verte (pipeline + application + cli)
- [ ] `lint-imports` vert (pipeline-has-no-adapters + application-has-no-adapters + cli-has-no-adapters)
- [ ] `vidscope --help` liste `refresh-stats`
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M009/M009-S02-SUMMARY.md` documentant :
- Signature exacte de `StatsStage.execute` et `StatsStage.is_satisfied`
- Signature de `RefreshStatsUseCase.execute_one` et `execute_all`
- UX de `vidscope refresh-stats` (single + batch + flags)
- Format retenu pour `--since` (N(h|d))
- Liste des fichiers créés/modifiés
</output>
