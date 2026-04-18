---
phase: M009
plan: S01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - src/vidscope/domain/values.py
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/metrics.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/stats_probe.py
  - src/vidscope/ports/__init__.py
  - src/vidscope/ports/unit_of_work.py
  - src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py
  - src/vidscope/adapters/ytdlp/__init__.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/video_stats_repository.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/infrastructure/container.py
  - tests/unit/domain/test_entities.py
  - tests/unit/domain/test_metrics_property.py
  - tests/unit/adapters/ytdlp/test_stats_probe.py
  - tests/unit/adapters/sqlite/test_video_stats_repository.py
  - tests/unit/adapters/sqlite/test_schema.py
autonomous: true
requirements: [R050]
must_haves:
  truths:
    - "Une nouvelle table `video_stats` append-only existe avec UNIQUE(video_id, captured_at)"
    - "L'entité `VideoStats` expose 5 compteurs `int | None` (view/like/repost/comment/save)"
    - "`metrics.views_velocity_24h` et `metrics.engagement_rate` calculent des valeurs correctes depuis l'historique"
    - "`YtdlpStatsProbe.probe_stats(url)` retourne un `VideoStats` non-persisté via `extract_info(download=False)`"
    - "`VideoStatsRepositorySQLite.append` est append-only (INSERT ... ON CONFLICT DO NOTHING, jamais d'UPDATE)"
    - "`UnitOfWork.video_stats` est disponible dans chaque transaction"
    - "Le container instancie `YtdlpStatsProbe` et l'expose via `Container.stats_probe`"
    - "Hypothesis property-based gate vert (monotonicity, additivity, zero-bug)"
  artifacts:
    - path: "src/vidscope/domain/entities.py"
      provides: "VideoStats frozen dataclass slots=True"
      contains: "class VideoStats"
    - path: "src/vidscope/domain/metrics.py"
      provides: "views_velocity_24h + engagement_rate pure-Python"
      contains: "def views_velocity_24h"
    - path: "src/vidscope/ports/stats_probe.py"
      provides: "StatsProbe Protocol runtime_checkable"
      contains: "class StatsProbe"
    - path: "src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py"
      provides: "YtdlpStatsProbe adapter (download=False)"
      contains: "class YtdlpStatsProbe"
    - path: "src/vidscope/adapters/sqlite/video_stats_repository.py"
      provides: "VideoStatsRepositorySQLite append-only adapter"
      contains: "class VideoStatsRepositorySQLite"
    - path: "src/vidscope/adapters/sqlite/schema.py"
      provides: "video_stats Table + _ensure_video_stats_table migration"
      contains: "video_stats = Table"
    - path: "tests/unit/domain/test_metrics_property.py"
      provides: "Hypothesis property gate"
      contains: "from hypothesis import given"
  key_links:
    - from: "src/vidscope/adapters/sqlite/unit_of_work.py"
      to: "VideoStatsRepositorySQLite"
      via: "self.video_stats = VideoStatsRepositorySQLite(self._connection)"
      pattern: "VideoStatsRepositorySQLite\\(self\\._connection\\)"
    - from: "src/vidscope/ports/unit_of_work.py"
      to: "VideoStatsRepository"
      via: "Protocol attribute"
      pattern: "video_stats: VideoStatsRepository"
    - from: "src/vidscope/infrastructure/container.py"
      to: "YtdlpStatsProbe"
      via: "stats_probe=YtdlpStatsProbe(...)"
      pattern: "YtdlpStatsProbe\\("
---

<objective>
S01 pose la fondation M009 : table time-series `video_stats` append-only, entité `VideoStats`, module pure-Python `metrics.py`, port `StatsProbe`, adapter `YtdlpStatsProbe` (wrap `extract_info(download=False)`), adapter SQLite avec migration idempotente et clé UNIQUE `(video_id, captured_at)`, extension de `UnitOfWork` et `Container`. Wave 0 ajoute `hypothesis>=6.0,<7` et crée tous les stubs de tests requis par M009-VALIDATION.md.

Purpose: Sans cette fondation, S02/S03/S04 ne peuvent pas être bâtis. Ce plan livre la fondation complète pour R050 et la gate Hypothesis non-négociable.
Output: Table `video_stats`, 5 nouveaux modules, 5 nouveaux fichiers de tests, extension schema/UoW/Container.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/STATE.md
@.gsd/REQUIREMENTS.md
@.gsd/DECISIONS.md
@.gsd/KNOWLEDGE.md
@.gsd/milestones/M009/M009-ROADMAP.md
@.gsd/milestones/M009/M009-CONTEXT.md
@.gsd/milestones/M009/M009-RESEARCH.md
@.gsd/milestones/M009/M009-VALIDATION.md
@src/vidscope/domain/entities.py
@src/vidscope/domain/values.py
@src/vidscope/ports/repositories.py
@src/vidscope/ports/unit_of_work.py
@src/vidscope/adapters/sqlite/schema.py
@src/vidscope/adapters/sqlite/unit_of_work.py
@src/vidscope/adapters/sqlite/frame_text_repository.py
@src/vidscope/adapters/ytdlp/downloader.py
@src/vidscope/infrastructure/container.py
@.importlinter

<interfaces>
Patterns et signatures clés à utiliser (extraits du codebase existant) :

**Entité cible — domain/entities.py (après ajout)** :
```python
@dataclass(frozen=True, slots=True)
class VideoStats:
    video_id: VideoId
    captured_at: datetime          # UTC-aware, résolution seconde (D-01)
    view_count: int | None = None
    like_count: int | None = None
    repost_count: int | None = None   # D-02 : nom yt-dlp, PAS share_count
    comment_count: int | None = None
    save_count: int | None = None
    id: int | None = None
    created_at: datetime | None = None
```

**Port — ports/stats_probe.py (nouveau)** :
```python
from typing import Protocol, runtime_checkable
from vidscope.domain import VideoStats

@runtime_checkable
class StatsProbe(Protocol):
    def probe_stats(self, url: str) -> VideoStats | None: ...
```

**Port — ports/repositories.py (extension)** :
```python
@runtime_checkable
class VideoStatsRepository(Protocol):
    def append(self, stats: VideoStats) -> VideoStats: ...
    def list_for_video(self, video_id: VideoId, *, limit: int = 100) -> list[VideoStats]: ...
    def latest_for_video(self, video_id: VideoId) -> VideoStats | None: ...
    def has_any_for_video(self, video_id: VideoId) -> bool: ...
    def list_videos_with_min_snapshots(self, min_snapshots: int = 2, *, limit: int = 200) -> list[VideoId]: ...
```

**Pattern migration idempotente — schema.py** : suivre `_ensure_frame_texts_table(conn)` qui :
1. Liste les tables via `PRAGMA sqlite_master`
2. `return` si la table existe
3. Sinon `CREATE TABLE` avec `text(...)` paramétré + `CREATE INDEX IF NOT EXISTS`

**Pattern adapter SQLite append-only** : suivre `FrameTextRepositorySQLite` (déjà existant) pour le `_row_to_entity` / `_entity_to_row`. Utiliser `sqlalchemy.dialects.sqlite.insert as sqlite_insert` avec `.on_conflict_do_nothing(index_elements=["video_id", "captured_at"])`.

**Pattern probe adapter** : `YtdlpDownloader.probe()` dans `downloader.py` lignes 278-349 fait déjà `extract_info(download=False)`. `YtdlpStatsProbe` suit le même pattern mais extrait les 5 champs stats au lieu des champs creator/metadata.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (Wave 0): Dépendance hypothesis + entité VideoStats + module metrics.py + tests stub</name>
  <files>pyproject.toml, src/vidscope/domain/values.py, src/vidscope/domain/entities.py, src/vidscope/domain/metrics.py, src/vidscope/domain/__init__.py, tests/unit/domain/test_entities.py, tests/unit/domain/test_metrics_property.py</files>
  <read_first>
    - pyproject.toml (ligne ~209 `[dependency-groups]` → `dev = [...]`)
    - src/vidscope/domain/values.py (pattern `StageName` StrEnum)
    - src/vidscope/domain/entities.py (pattern frozen dataclass slots=True)
    - src/vidscope/domain/__init__.py (liste `__all__` et re-exports)
    - tests/unit/domain/test_entities.py (pattern tests existants pour FrameText)
    - .importlinter (contrat `domain-is-pure` — aucun import tiers runtime dans domain/)
    - .gsd/KNOWLEDGE.md (règle : domain = stdlib + typing ONLY)
    - .gsd/milestones/M009/M009-CONTEXT.md (D-01 seconde, D-02 5 champs, D-03 None != 0)
    - .gsd/milestones/M009/M009-RESEARCH.md (Pattern 1, Pattern 6, test Hypothesis)
  </read_first>
  <behavior>
    - Test 1 : `VideoStats` est frozen — `stats.view_count = 42` lève `FrozenInstanceError`.
    - Test 2 : `VideoStats(video_id=VideoId(1), captured_at=...)` construit avec tous les compteurs à `None` par défaut.
    - Test 3 : `VideoStats(... view_count=0)` distingue `0` de `None` (assertion `is None` vs `== 0`).
    - Test 4 (Hypothesis, monotonicity) : pour toute liste d'entiers croissants passée à `views_velocity_24h`, résultat >= 0 ou None.
    - Test 5 (Hypothesis, zero-bug) : `engagement_rate` retourne `None` quand `view_count` vaut 0 ou None (jamais division par zéro).
    - Test 6 (Hypothesis, additivity) : pour un historique [a, b, c] linéaire strict, `views_velocity_24h` est monotone (la vélocité d'une fenêtre étendue reste du même signe).
  </behavior>
  <action>
Étape 1 — Ajouter hypothesis à pyproject.toml :
Dans la section `[dependency-groups] dev = [...]` (lignes ~209-216), ajouter exactement cette ligne AVANT la fermeture `]` :
```
    "hypothesis>=6.0,<7",
```
Puis exécuter dans un bash : `uv sync --all-extras --all-groups` pour installer. Si la commande exacte diffère selon le projet, fallback sur `uv sync` simple. Vérifier ensuite `uv run python -c "import hypothesis; print(hypothesis.__version__)"` affiche une version >= 6.0.

Étape 2 — Ajouter `StageName.STATS` dans `src/vidscope/domain/values.py` :
Dans la classe `class StageName(StrEnum):` (lignes ~105-119), ajouter APRÈS `INDEX = "index"` :
```python
    STATS = "stats"
```
Cette valeur est obligatoire car `StatsStage` (S02) écrit dans `pipeline_runs.phase` (cf. M009-RESEARCH Open Question 2).

Étape 3 — Créer l'entité `VideoStats` dans `src/vidscope/domain/entities.py` :
Ajouter APRÈS la définition de `FrameText` (ou en fin de fichier juste avant les `WatchedAccount`/`WatchRefresh` si présentes), EN RESPECTANT le pattern frozen dataclass slots=True :
```python
@dataclass(frozen=True, slots=True)
class VideoStats:
    """Snapshot of platform-reported counters for a single video at an instant.

    Append-only per D031 and D-01: one new row per probe, never an UPDATE.
    Idempotence: UNIQUE(video_id, captured_at) at second resolution.
    Missing counters MUST remain None — never 0 — per D-03, otherwise
    engagement_rate is biased across platforms (Instagram has no
    repost/save, YouTube has no save).

    Field mapping per D-02 follows yt-dlp's info dict keys verbatim:
    - view_count, like_count, comment_count: standard across platforms.
    - repost_count: yt-dlp's name for TikTok shares (NOT share_count).
    - save_count: yt-dlp's TikTok-only counter.
    """

    video_id: VideoId
    captured_at: datetime   # UTC-aware, second resolution (D-01)
    view_count: int | None = None
    like_count: int | None = None
    repost_count: int | None = None
    comment_count: int | None = None
    save_count: int | None = None
    id: int | None = None
    created_at: datetime | None = None
```
Ajouter `"VideoStats"` dans `__all__` de ce fichier (ordre alphabétique).

Étape 4 — Mettre à jour `src/vidscope/domain/__init__.py` :
Ajouter l'import et l'entrée `__all__` pour `VideoStats`. Suivre exactement le pattern utilisé pour `FrameText`.

Étape 5 — Créer `src/vidscope/domain/metrics.py` (pure stdlib + typing) :
```python
"""Pure-domain metrics computed from a VideoStats history.

This module has ZERO project imports beyond TYPE_CHECKING (enforced by
the domain-is-pure import-linter contract). No SQLAlchemy, no rich,
no Typer — only stdlib and typing annotations.

Formulas per M009-RESEARCH Pattern 6 (Claude's Discretion):
- views_velocity_24h: linear delta over the elapsed window,
  projected onto 24h. Returns None when < 2 usable rows or
  elapsed_seconds <= 0.
- engagement_rate: (like + comment) / view_count on the latest
  snapshot. Returns None when view_count is None or 0. Only
  non-None fields contribute (D-03) — never substitutes 0.

viral_coefficient is intentionally omitted from M009 per
CONTEXT.md Claude's Discretion (definition too fuzzy).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vidscope.domain.entities import VideoStats

__all__ = ["engagement_rate", "views_velocity_24h"]


def views_velocity_24h(history: list["VideoStats"]) -> float | None:
    """Views gained per 24h window over the full history.

    Formula: (last.view_count - first.view_count) / elapsed_seconds * 86400.
    Returns None when fewer than 2 rows with view_count is not None
    are present, or when elapsed_seconds <= 0 (same-second rows).
    Can be negative when view_count decreased (deleted views).
    """
    rows = [r for r in history if r.view_count is not None]
    if len(rows) < 2:
        return None
    first, last = rows[0], rows[-1]
    delta_seconds = (last.captured_at - first.captured_at).total_seconds()
    if delta_seconds <= 0:
        return None
    delta_views = (last.view_count or 0) - (first.view_count or 0)
    return delta_views / delta_seconds * 86400.0


def engagement_rate(latest: "VideoStats") -> float | None:
    """(like_count + comment_count) / view_count on the latest snapshot.

    Returns None when view_count is None or 0 (avoids DivisionByZero
    and respects D-03 — no implicit 0 substitution). Only counters
    that are not None contribute to the numerator.
    """
    if latest.view_count is None or latest.view_count == 0:
        return None
    like = latest.like_count if latest.like_count is not None else 0
    comment = latest.comment_count if latest.comment_count is not None else 0
    return (like + comment) / latest.view_count
```

Étape 6 — Créer/étendre `tests/unit/domain/test_entities.py` (ajouter ces tests ; ne pas casser l'existant) :
```python
def test_video_stats_is_frozen():
    from vidscope.domain import VideoStats, VideoId
    from datetime import UTC, datetime
    stats = VideoStats(video_id=VideoId(1), captured_at=datetime.now(UTC).replace(microsecond=0))
    import pytest
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        stats.view_count = 42  # type: ignore[misc]

def test_video_stats_distinguishes_none_from_zero():
    """D-03 : champ absent → None, jamais 0 (biaise engagement_rate sinon)."""
    from vidscope.domain import VideoStats, VideoId
    from datetime import UTC, datetime
    stats = VideoStats(
        video_id=VideoId(1),
        captured_at=datetime.now(UTC).replace(microsecond=0),
        view_count=100,
        like_count=None,
        comment_count=0,
    )
    assert stats.like_count is None
    assert stats.comment_count == 0
    assert stats.like_count is not stats.comment_count

def test_video_stats_default_counters_are_none():
    from vidscope.domain import VideoStats, VideoId
    from datetime import UTC, datetime
    stats = VideoStats(video_id=VideoId(1), captured_at=datetime.now(UTC).replace(microsecond=0))
    assert stats.view_count is None
    assert stats.like_count is None
    assert stats.repost_count is None
    assert stats.comment_count is None
    assert stats.save_count is None
```

Étape 7 — Créer `tests/unit/domain/test_metrics_property.py` (gate Hypothesis non-négociable) :
```python
"""Property-based gate on metrics.py — blocks merge if any property fails."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from vidscope.domain import VideoId, VideoStats
from vidscope.domain.metrics import engagement_rate, views_velocity_24h


def _make_history(view_counts: list[int]) -> list[VideoStats]:
    """Build a VideoStats list with captured_at 1h apart."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        VideoStats(
            video_id=VideoId(1),
            captured_at=base + timedelta(hours=i),
            view_count=v,
        )
        for i, v in enumerate(view_counts)
    ]


@given(st.lists(st.integers(min_value=0, max_value=10_000_000), min_size=2, max_size=50))
@settings(deadline=None, max_examples=100)
def test_velocity_non_negative_for_monotonically_increasing_views(view_counts: list[int]) -> None:
    """Monotonicity: if view_count is non-decreasing, velocity is >= 0 (or None)."""
    history = _make_history(sorted(view_counts))
    result = views_velocity_24h(history)
    if result is not None:
        assert result >= 0.0


@given(st.lists(st.integers(min_value=0, max_value=10_000_000), min_size=2, max_size=50))
@settings(deadline=None, max_examples=100)
def test_velocity_sign_flips_when_views_decrease(view_counts: list[int]) -> None:
    """Sign-flip: reversing a monotonically increasing history gives <=0 velocity."""
    history = _make_history(sorted(view_counts, reverse=True))
    result = views_velocity_24h(history)
    if result is not None:
        assert result <= 0.0


@given(st.integers(min_value=-1_000_000, max_value=1_000_000), st.integers(min_value=0, max_value=1_000_000))
@settings(deadline=None, max_examples=100)
def test_engagement_rate_zero_bug(likes: int, views: int) -> None:
    """Zero-bug: engagement_rate never divides by zero, never returns NaN."""
    stats = VideoStats(
        video_id=VideoId(1),
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        view_count=views if views > 0 else None,
        like_count=likes,
        comment_count=0,
    )
    result = engagement_rate(stats)
    if views == 0 or views is None:
        # Actually can't pass views=None through above; separate branch:
        pass
    if result is not None:
        assert result == (likes + 0) / views


@given(
    st.lists(st.integers(min_value=0, max_value=10_000_000), min_size=2, max_size=50),
    st.integers(min_value=1, max_value=48),
)
@settings(deadline=None, max_examples=50)
def test_velocity_additivity_linear_series(view_counts: list[int], hours_per_step: int) -> None:
    """Additivity: for a strictly increasing history, velocity stays of constant sign."""
    sorted_counts = sorted(view_counts)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    history = [
        VideoStats(
            video_id=VideoId(1),
            captured_at=base + timedelta(hours=hours_per_step * i),
            view_count=v,
        )
        for i, v in enumerate(sorted_counts)
    ]
    full = views_velocity_24h(history)
    assume(full is not None)
    # Subset of the history (first half) must have velocity of the same sign
    half = views_velocity_24h(history[: len(history) // 2 + 1])
    if half is not None and full is not None:
        assert (half >= 0) == (full >= 0)
```

Étape 8 — Exécuter tous les tests ciblés :
```
uv run pytest tests/unit/domain/test_entities.py tests/unit/domain/test_metrics_property.py tests/unit/domain/test_values.py -x -q
```
Doit exiter 0.

NE PAS ajouter `view_count` sur `Video` (anti-pattern M009-RESEARCH). NE PAS importer `yt_dlp` ou `sqlalchemy` dans `domain/metrics.py` (contrat `domain-is-pure`).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/domain/test_entities.py tests/unit/domain/test_metrics_property.py tests/unit/domain/test_values.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "hypothesis>=6.0" pyproject.toml` matches une ligne dans `[dependency-groups]`
    - `grep -n "STATS = \"stats\"" src/vidscope/domain/values.py` matches
    - `grep -n "class VideoStats" src/vidscope/domain/entities.py` matches
    - `grep -n "repost_count: int | None" src/vidscope/domain/entities.py` matches (et PAS `share_count`)
    - `grep -n "save_count: int | None" src/vidscope/domain/entities.py` matches
    - `grep -n "def views_velocity_24h" src/vidscope/domain/metrics.py` matches
    - `grep -n "def engagement_rate" src/vidscope/domain/metrics.py` matches
    - `grep -n "^from hypothesis import" tests/unit/domain/test_metrics_property.py` matches
    - `grep -n "VideoStats" src/vidscope/domain/__init__.py` matches (re-export)
    - `uv run pytest tests/unit/domain/ -x -q` exits 0
    - `uv run lint-imports` exits 0 (contract `domain-is-pure` toujours vert)
  </acceptance_criteria>
  <done>
    - hypothesis>=6.0,<7 installé via uv sync
    - VideoStats + StageName.STATS + metrics.py livrés dans domain/
    - tests/unit/domain/test_entities.py étendu (3 nouveaux tests)
    - tests/unit/domain/test_metrics_property.py créé (4 properties Hypothesis)
    - Suite domain verte, lint-imports vert
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (Wave 1): Port StatsProbe + Port VideoStatsRepository + Adapter YtdlpStatsProbe + tests</name>
  <files>src/vidscope/ports/stats_probe.py, src/vidscope/ports/repositories.py, src/vidscope/ports/__init__.py, src/vidscope/ports/unit_of_work.py, src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py, src/vidscope/adapters/ytdlp/__init__.py, tests/unit/adapters/ytdlp/test_stats_probe.py</files>
  <read_first>
    - src/vidscope/ports/repositories.py (patterns Protocol runtime_checkable existants)
    - src/vidscope/ports/__init__.py (liste `__all__` + re-exports)
    - src/vidscope/ports/unit_of_work.py (attribut `video_stats: VideoStatsRepository`)
    - src/vidscope/adapters/ytdlp/downloader.py (lignes 278-349, pattern `probe()` avec `extract_info(download=False)`, helper `_int_or_none`)
    - src/vidscope/adapters/ytdlp/__init__.py (re-export adapter)
    - tests/unit/adapters/ytdlp/test_downloader.py (pattern monkeypatch yt_dlp.YoutubeDL)
    - .gsd/milestones/M009/M009-CONTEXT.md (D-02 champs, D-03 None != 0)
    - .gsd/milestones/M009/M009-RESEARCH.md (Pattern 4 StatsProbe, Pitfall 1 microseconds, T-DATA-01)
    - .importlinter (contrat `ports-are-pure` : aucun import tiers runtime dans ports/)
  </read_first>
  <behavior>
    - Test 1 : `YtdlpStatsProbe.probe_stats(url)` appelle `yt_dlp.YoutubeDL` avec `skip_download=True` et `download=False`.
    - Test 2 : Retourne `VideoStats` avec les 5 compteurs extraits du dict yt-dlp.
    - Test 3 : `captured_at` a `microsecond == 0` (truncation seconde, D-01).
    - Test 4 : Champs manquants dans le dict yt-dlp → `None` sur l'entité (pas `0` — D-03).
    - Test 5 : Retourne `None` quand `extract_info` retourne `None` ou non-dict.
    - Test 6 : Ne lève jamais — toute exception yt-dlp est catchée et mappe à `None` (probe pattern).
    - Test 7 : Valeurs non-int dans le dict (str, None, float) passent par `_int_or_none` et deviennent `None` ou `int`.
  </behavior>
  <action>
Étape 1 — Créer `src/vidscope/ports/stats_probe.py` (stdlib + typing ONLY, contrat ports-are-pure) :
```python
"""StatsProbe port — metadata-only probe for engagement counters.

Adapters implement this Protocol to fetch platform-reported counters
(view/like/repost/comment/save) WITHOUT downloading media. The concrete
yt-dlp adapter delegates to extract_info(download=False).

Contract:
- Never raises. All errors encoded as None return.
- Returns a non-persisted VideoStats with video_id=VideoId(0) — the
  caller (StatsStage) substitutes the real video_id before append().
- captured_at MUST be truncated to second resolution (D-01) so the
  UNIQUE(video_id, captured_at) constraint deduplicates correctly.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from vidscope.domain import VideoStats

__all__ = ["StatsProbe"]


@runtime_checkable
class StatsProbe(Protocol):
    def probe_stats(self, url: str) -> VideoStats | None:
        """Probe platform for engagement counters without downloading media.

        Returns VideoStats with video_id=VideoId(0) (placeholder — the
        caller fills it from PipelineContext). Returns None on any
        failure (network, parsing, missing metadata). Never raises.
        """
        ...
```

Étape 2 — Étendre `src/vidscope/ports/repositories.py` :
Ajouter l'import de `VideoStats` dans le bloc `from vidscope.domain import (...)`. Ajouter `"VideoStatsRepository"` dans `__all__` (ordre alphabétique). Ajouter la classe APRÈS `VideoRepository` :
```python
@runtime_checkable
class VideoStatsRepository(Protocol):
    """Persistence for VideoStats — append-only time-series (D031).

    Implementations MUST reject UPDATEs: every call to append() writes a
    new row or no-ops (ON CONFLICT DO NOTHING on the (video_id,
    captured_at) UNIQUE index). The repository never mutates an existing
    row. This is structurally enforced by adapter tests.
    """

    def append(self, stats: VideoStats) -> VideoStats:
        """INSERT a new row. ON CONFLICT(video_id, captured_at) DO NOTHING.

        Returns the persisted entity with id populated. If the conflict
        is hit, returns the existing matching row (same (video_id,
        captured_at) key) — callers can rely on at-least-one row being
        present after this call.
        """
        ...

    def list_for_video(
        self, video_id: VideoId, *, limit: int = 100
    ) -> list[VideoStats]:
        """Return rows for video_id ordered by captured_at ASC, capped."""
        ...

    def latest_for_video(self, video_id: VideoId) -> VideoStats | None:
        """Return the most recent row by captured_at, or None."""
        ...

    def has_any_for_video(self, video_id: VideoId) -> bool:
        """True if at least one row exists for video_id."""
        ...

    def list_videos_with_min_snapshots(
        self, min_snapshots: int = 2, *, limit: int = 200
    ) -> list[VideoId]:
        """Return video_ids having >= min_snapshots rows. Used by trending."""
        ...
```

Étape 3 — Étendre `src/vidscope/ports/__init__.py` :
Re-exporter `StatsProbe` et `VideoStatsRepository` (suivre l'ordre alphabétique du `__all__`).

Étape 4 — Étendre `src/vidscope/ports/unit_of_work.py` :
Ajouter `VideoStatsRepository` dans l'import depuis `vidscope.ports.repositories` et ajouter l'attribut `video_stats: VideoStatsRepository` dans la classe `UnitOfWork(Protocol)` APRÈS `search_index: SearchIndex`.

Étape 5 — Créer `src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py` (T-DATA-01 : `_int_or_none` systématique) :
```python
"""YtdlpStatsProbe — metadata-only probe via yt_dlp.YoutubeDL.

Reuses the same extract_info(download=False) pattern already vetted in
YtdlpDownloader.probe() (lines ~278-349). The implementation lives in
its own file per the one-adapter-per-file rule established in M004.

Never raises — every failure mode maps to None (probe pattern, M005).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

from vidscope.domain import VideoId, VideoStats

__all__ = ["YtdlpStatsProbe"]

_logger = logging.getLogger(__name__)


def _int_or_none(value: Any) -> int | None:
    """Coerce an arbitrary value to int, or None on any failure (T-DATA-01).

    Mirrors the helper in downloader.py. yt-dlp sometimes returns strings,
    floats, or None for numeric-looking fields — we never store 0 when the
    platform did not expose the counter (D-03).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _truncate_to_second(dt: datetime) -> datetime:
    """Strip microseconds so UNIQUE(video_id, captured_at) works at 1s res."""
    return dt.replace(microsecond=0)


class YtdlpStatsProbe:
    """Concrete StatsProbe backed by yt_dlp.YoutubeDL.extract_info(download=False)."""

    def __init__(self, *, cookies_file: str | None = None) -> None:
        self._cookies_file = cookies_file

    def probe_stats(self, url: str) -> VideoStats | None:
        if not url or not url.strip():
            return None

        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "skip_download": True,
            "ignoreerrors": False,
        }
        if self._cookies_file is not None:
            options["cookiefile"] = str(self._cookies_file)

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except (DownloadError, ExtractorError) as exc:
            _logger.info("stats probe failed (yt-dlp): %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 — probe never raises
            _logger.warning("stats probe failed (unexpected): %s", exc)
            return None

        if info is None or not isinstance(info, dict):
            return None

        return VideoStats(
            video_id=VideoId(0),   # placeholder — StatsStage substitutes
            captured_at=_truncate_to_second(datetime.now(UTC)),
            view_count=_int_or_none(info.get("view_count")),
            like_count=_int_or_none(info.get("like_count")),
            repost_count=_int_or_none(info.get("repost_count")),
            comment_count=_int_or_none(info.get("comment_count")),
            save_count=_int_or_none(info.get("save_count")),
        )
```

Étape 6 — Mettre à jour `src/vidscope/adapters/ytdlp/__init__.py` :
Ajouter `from vidscope.adapters.ytdlp.ytdlp_stats_probe import YtdlpStatsProbe` et `"YtdlpStatsProbe"` dans `__all__`.

Étape 7 — Créer `tests/unit/adapters/ytdlp/test_stats_probe.py` :
```python
"""Unit tests for YtdlpStatsProbe — stub yt_dlp.YoutubeDL."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from vidscope.adapters.ytdlp.ytdlp_stats_probe import YtdlpStatsProbe
from vidscope.domain import VideoStats


class _FakeYdl:
    def __init__(self, *, info: dict[str, Any] | None, captured_options: dict[str, Any]) -> None:
        self._info = info
        captured_options.clear()
        captured_options.update({})
        self._captured = captured_options

    def __enter__(self) -> "_FakeYdl":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def extract_info(self, url: str, download: bool = True) -> Any:
        self._captured["url"] = url
        self._captured["download"] = download
        return self._info


def _patch_ydl(monkeypatch: pytest.MonkeyPatch, info: dict[str, Any] | None, capture: dict[str, Any]) -> None:
    import vidscope.adapters.ytdlp.ytdlp_stats_probe as mod

    def factory(options: dict[str, Any]) -> _FakeYdl:
        capture["options"] = options
        return _FakeYdl(info=info, captured_options=capture)

    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", factory)


def test_probe_forces_download_false(monkeypatch: pytest.MonkeyPatch) -> None:
    capture: dict[str, Any] = {}
    _patch_ydl(monkeypatch, {"view_count": 1}, capture)
    YtdlpStatsProbe().probe_stats("https://example.com/v")
    assert capture["download"] is False
    assert capture["options"]["skip_download"] is True


def test_probe_extracts_all_five_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    capture: dict[str, Any] = {}
    _patch_ydl(
        monkeypatch,
        {
            "view_count": 1000, "like_count": 50, "repost_count": 5,
            "comment_count": 10, "save_count": 3,
        },
        capture,
    )
    stats = YtdlpStatsProbe().probe_stats("https://example.com/v")
    assert isinstance(stats, VideoStats)
    assert stats.view_count == 1000
    assert stats.like_count == 50
    assert stats.repost_count == 5
    assert stats.comment_count == 10
    assert stats.save_count == 3


def test_probe_truncates_captured_at_to_second(monkeypatch: pytest.MonkeyPatch) -> None:
    capture: dict[str, Any] = {}
    _patch_ydl(monkeypatch, {"view_count": 1}, capture)
    stats = YtdlpStatsProbe().probe_stats("https://example.com/v")
    assert stats is not None
    assert stats.captured_at.microsecond == 0


def test_probe_missing_fields_map_to_none_not_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-03: Instagram has no save_count → None, never 0."""
    capture: dict[str, Any] = {}
    _patch_ydl(
        monkeypatch,
        {"view_count": 500, "like_count": 20, "comment_count": 3},   # No repost/save
        capture,
    )
    stats = YtdlpStatsProbe().probe_stats("https://example.com/v")
    assert stats is not None
    assert stats.repost_count is None
    assert stats.save_count is None
    assert stats.repost_count is not 0


def test_probe_returns_none_when_info_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    capture: dict[str, Any] = {}
    _patch_ydl(monkeypatch, None, capture)
    assert YtdlpStatsProbe().probe_stats("https://example.com/v") is None


def test_probe_returns_none_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import vidscope.adapters.ytdlp.ytdlp_stats_probe as mod

    class _Boom:
        def __enter__(self) -> "_Boom":
            return self
        def __exit__(self, *_: Any) -> None:
            return None
        def extract_info(self, *_a: Any, **_k: Any) -> Any:
            raise RuntimeError("network down")

    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", lambda opts: _Boom())
    # Never raises
    assert YtdlpStatsProbe().probe_stats("https://example.com/v") is None


def test_probe_non_int_values_coerced_or_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-DATA-01: string 'abc' for view_count → None, not a crash."""
    capture: dict[str, Any] = {}
    _patch_ydl(
        monkeypatch,
        {"view_count": "abc", "like_count": "500", "comment_count": None},
        capture,
    )
    stats = YtdlpStatsProbe().probe_stats("https://example.com/v")
    assert stats is not None
    assert stats.view_count is None       # "abc" coerces to None
    assert stats.like_count == 500        # "500" coerces to 500
    assert stats.comment_count is None


def test_probe_empty_url_returns_none() -> None:
    assert YtdlpStatsProbe().probe_stats("") is None
    assert YtdlpStatsProbe().probe_stats("   ") is None
```

Étape 8 — Exécuter les tests :
```
uv run pytest tests/unit/adapters/ytdlp/test_stats_probe.py tests/unit/domain/ -x -q
uv run lint-imports
```

NE PAS importer `vidscope.adapters.*` depuis le port. NE PAS stocker 0 à la place de None (D-03).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/adapters/ytdlp/test_stats_probe.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class StatsProbe" src/vidscope/ports/stats_probe.py` matches
    - `grep -n "class VideoStatsRepository" src/vidscope/ports/repositories.py` matches
    - `grep -n "video_stats: VideoStatsRepository" src/vidscope/ports/unit_of_work.py` matches
    - `grep -n "class YtdlpStatsProbe" src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py` matches
    - `grep -n "download=False" src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py` matches
    - `grep -n "microsecond=0" src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py` matches (D-01)
    - `grep -n "_int_or_none" src/vidscope/adapters/ytdlp/ytdlp_stats_probe.py` matches (T-DATA-01)
    - `grep -n "StatsProbe" src/vidscope/ports/__init__.py` matches
    - `grep -n "YtdlpStatsProbe" src/vidscope/adapters/ytdlp/__init__.py` matches
    - `uv run pytest tests/unit/adapters/ytdlp/test_stats_probe.py -x -q` exits 0
    - `uv run lint-imports` exits 0 (ports-are-pure vert, ytdlp isolé)
  </acceptance_criteria>
  <done>
    - Port StatsProbe créé (pure Python)
    - VideoStatsRepository Protocol ajouté dans repositories.py
    - UnitOfWork étendu avec video_stats attribute
    - YtdlpStatsProbe adapter créé avec truncation seconde + _int_or_none
    - 8 tests unitaires verts
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3 (Wave 1): Table SQLite video_stats + migration + repository append-only + extension UoW + wiring Container + tests</name>
  <files>src/vidscope/adapters/sqlite/schema.py, src/vidscope/adapters/sqlite/video_stats_repository.py, src/vidscope/adapters/sqlite/unit_of_work.py, src/vidscope/infrastructure/container.py, tests/unit/adapters/sqlite/test_video_stats_repository.py, tests/unit/adapters/sqlite/test_schema.py</files>
  <read_first>
    - src/vidscope/adapters/sqlite/schema.py (pattern `frame_texts` Table + `_ensure_frame_texts_table` migration idempotente + `init_db`)
    - src/vidscope/adapters/sqlite/frame_text_repository.py (pattern `_row_to_entity` / `_entity_to_row` + insertion)
    - src/vidscope/adapters/sqlite/video_repository.py (pattern `sqlite_insert` avec `on_conflict_do_nothing`)
    - src/vidscope/adapters/sqlite/unit_of_work.py (pattern câblage repos dans `__enter__`)
    - src/vidscope/infrastructure/container.py (pattern instanciation adapter + Container dataclass frozen)
    - tests/unit/adapters/sqlite/conftest.py (fixture `engine` / `connection`)
    - tests/unit/adapters/sqlite/test_frame_text_repository.py (pattern tests adapter)
    - tests/unit/adapters/sqlite/test_schema.py (pattern tests migration)
    - .gsd/milestones/M009/M009-RESEARCH.md (Pattern 3 table, Pattern 7 UoW, Pitfall 3)
  </read_first>
  <behavior>
    - Test 1 (schema) : `init_db` crée `video_stats` table sur une DB vide, avec colonnes attendues et UNIQUE constraint.
    - Test 2 (schema) : `_ensure_video_stats_table` est idempotent (second run no-op) sur une DB pré-M009.
    - Test 3 (repo) : `append(stats)` persiste et retourne l'entité avec `id` populé.
    - Test 4 (repo) : `append(stats)` deux fois avec le même `(video_id, captured_at)` → une seule row en base (ON CONFLICT DO NOTHING).
    - Test 5 (repo) : `append` ne MET PAS À JOUR une row existante (le second append avec des compteurs différents laisse la row originale intacte).
    - Test 6 (repo) : `list_for_video(id, limit=10)` retourne les rows ordonnées par `captured_at` ASC.
    - Test 7 (repo) : `latest_for_video(id)` retourne la row la plus récente ou None.
    - Test 8 (repo) : `has_any_for_video(id)` retourne True/False correctement.
    - Test 9 (repo) : `list_videos_with_min_snapshots(2)` retourne les video_ids avec >=2 rows.
    - Test 10 (repo) : `None` est préservé sur les compteurs au round-trip (pas converti en 0).
  </behavior>
  <action>
Étape 1 — Étendre `src/vidscope/adapters/sqlite/schema.py` :

(a) Ajouter dans `__all__` la chaîne `"video_stats"` (ordre alphabétique).

(b) Définir la Table APRÈS `links` et AVANT le bloc FTS5 :
```python
# M009: video_stats time-series — append-only (D031). UNIQUE(video_id,
# captured_at) at second resolution enforces idempotence per D-01.
# Missing counters MUST stay NULL (D-03) — never substituted with 0.
video_stats = Table(
    "video_stats",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("view_count", Integer, nullable=True),
    Column("like_count", Integer, nullable=True),
    Column("repost_count", Integer, nullable=True),
    Column("comment_count", Integer, nullable=True),
    Column("save_count", Integer, nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    ),
    UniqueConstraint(
        "video_id", "captured_at",
        name="uq_video_stats_video_id_captured_at",
    ),
)
Index("idx_video_stats_video_id", video_stats.c.video_id)
Index("idx_video_stats_captured_at", video_stats.c.captured_at)
```

(c) Ajouter la fonction de migration idempotente APRÈS `_ensure_frame_texts_table` :
```python
def _ensure_video_stats_table(conn: Connection) -> None:
    """Create video_stats on upgraded databases. Idempotent.

    Mirrors _ensure_frame_texts_table. Fresh installs get the table via
    metadata.create_all; pre-M009 databases hit this path.
    """
    tables = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }
    if "video_stats" in tables:
        return
    conn.execute(
        text(
            "CREATE TABLE video_stats ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE, "
            "captured_at DATETIME NOT NULL, "
            "view_count INTEGER, like_count INTEGER, "
            "repost_count INTEGER, comment_count INTEGER, save_count INTEGER, "
            "created_at DATETIME NOT NULL, "
            "CONSTRAINT uq_video_stats_video_id_captured_at "
            "UNIQUE (video_id, captured_at)"
            ")"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_stats_video_id "
            "ON video_stats(video_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_stats_captured_at "
            "ON video_stats(captured_at)"
        )
    )
```

(d) Appeler `_ensure_video_stats_table(conn)` à l'intérieur de `init_db()` APRÈS `_ensure_frame_texts_table(conn)`.

Étape 2 — Créer `src/vidscope/adapters/sqlite/video_stats_repository.py` :
```python
"""VideoStatsRepository — SQLite adapter (append-only per D031)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import video_stats
from vidscope.domain import VideoId, VideoStats

__all__ = ["VideoStatsRepositorySQLite"]


def _row_to_entity(row: object) -> VideoStats:
    m = row._mapping  # type: ignore[attr-defined]
    captured = m["captured_at"]
    if isinstance(captured, datetime) and captured.tzinfo is None:
        captured = captured.replace(tzinfo=UTC)
    created = m["created_at"]
    if isinstance(created, datetime) and created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return VideoStats(
        id=int(m["id"]),
        video_id=VideoId(int(m["video_id"])),
        captured_at=captured,
        view_count=m["view_count"],
        like_count=m["like_count"],
        repost_count=m["repost_count"],
        comment_count=m["comment_count"],
        save_count=m["save_count"],
        created_at=created,
    )


class VideoStatsRepositorySQLite:
    """Append-only time-series repository.

    append() uses INSERT ... ON CONFLICT(video_id, captured_at) DO NOTHING.
    There is NO update() method — the API shape is the structural
    guarantee that no row is ever mutated after creation (D031).
    """

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    def append(self, stats: VideoStats) -> VideoStats:
        payload = {
            "video_id": int(stats.video_id),
            "captured_at": stats.captured_at,
            "view_count": stats.view_count,
            "like_count": stats.like_count,
            "repost_count": stats.repost_count,
            "comment_count": stats.comment_count,
            "save_count": stats.save_count,
        }
        stmt = sqlite_insert(video_stats).values(**payload)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["video_id", "captured_at"],
        )
        self._conn.execute(stmt)

        # Fetch either the just-inserted row or the one that blocked the insert.
        existing = self._conn.execute(
            select(video_stats)
            .where(video_stats.c.video_id == int(stats.video_id))
            .where(video_stats.c.captured_at == stats.captured_at)
        ).one_or_none()
        if existing is None:
            return stats
        return _row_to_entity(existing)

    def list_for_video(
        self, video_id: VideoId, *, limit: int = 100
    ) -> list[VideoStats]:
        rows = self._conn.execute(
            select(video_stats)
            .where(video_stats.c.video_id == int(video_id))
            .order_by(video_stats.c.captured_at.asc())
            .limit(limit)
        ).all()
        return [_row_to_entity(r) for r in rows]

    def latest_for_video(self, video_id: VideoId) -> VideoStats | None:
        row = self._conn.execute(
            select(video_stats)
            .where(video_stats.c.video_id == int(video_id))
            .order_by(video_stats.c.captured_at.desc())
            .limit(1)
        ).one_or_none()
        return _row_to_entity(row) if row is not None else None

    def has_any_for_video(self, video_id: VideoId) -> bool:
        row = self._conn.execute(
            select(video_stats.c.id)
            .where(video_stats.c.video_id == int(video_id))
            .limit(1)
        ).one_or_none()
        return row is not None

    def list_videos_with_min_snapshots(
        self, min_snapshots: int = 2, *, limit: int = 200
    ) -> list[VideoId]:
        from sqlalchemy import func
        rows = self._conn.execute(
            select(video_stats.c.video_id)
            .group_by(video_stats.c.video_id)
            .having(func.count(video_stats.c.id) >= min_snapshots)
            .limit(limit)
        ).all()
        return [VideoId(int(r[0])) for r in rows]
```

Étape 3 — Étendre `src/vidscope/adapters/sqlite/unit_of_work.py` :

(a) Ajouter l'import : `from vidscope.adapters.sqlite.video_stats_repository import VideoStatsRepositorySQLite`.

(b) Ajouter dans l'import `from vidscope.ports import (...)` : `VideoStatsRepository`.

(c) Dans `SqliteUnitOfWork.__init__`, ajouter après `self.watch_refreshes: WatchRefreshRepository` : `self.video_stats: VideoStatsRepository`.

(d) Dans `SqliteUnitOfWork.__enter__`, ajouter après `self.watch_refreshes = WatchRefreshRepositorySQLite(self._connection)` : `self.video_stats = VideoStatsRepositorySQLite(self._connection)`.

Étape 4 — Étendre `src/vidscope/infrastructure/container.py` :

(a) Importer `YtdlpStatsProbe` et `StatsProbe` :
```python
from vidscope.adapters.ytdlp import YtdlpDownloader, YtdlpStatsProbe
from vidscope.ports.pipeline import Analyzer, Downloader, FrameExtractor, Transcriber
# Add:
from vidscope.ports.stats_probe import StatsProbe
```

(b) Étendre le dataclass `Container` avec le champ `stats_probe: StatsProbe` (après `analyzer`, avant `pipeline_runner`).

(c) Dans `build_container()` :
- Instancier `stats_probe = YtdlpStatsProbe(cookies_file=resolved_config.cookies_file)` APRÈS `downloader = YtdlpDownloader(...)`.
- NE PAS ajouter de stage dans `pipeline_runner.stages` — `StatsStage` est standalone (S02).
- Retourner `stats_probe=stats_probe` dans le constructeur `Container(...)`.

Étape 5 — Créer `tests/unit/adapters/sqlite/test_video_stats_repository.py` :
```python
"""Unit tests for VideoStatsRepositorySQLite — append-only invariant + idempotence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import init_db, video_stats as video_stats_table
from vidscope.adapters.sqlite.video_stats_repository import VideoStatsRepositorySQLite
from vidscope.adapters.sqlite.video_repository import VideoRepositorySQLite
from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats


@pytest.fixture()
def engine() -> Engine:
    eng = create_engine("sqlite:///:memory:")
    init_db(eng)
    return eng


def _persist_video(conn: Connection) -> VideoId:
    repo = VideoRepositorySQLite(conn)
    persisted = repo.upsert_by_platform_id(
        Video(platform=Platform.YOUTUBE, platform_id=PlatformId("abc"), url="https://x.y/abc")
    )
    assert persisted.id is not None
    return persisted.id


def test_append_persists_and_returns_id(engine: Engine) -> None:
    with engine.begin() as conn:
        vid = _persist_video(conn)
        repo = VideoStatsRepositorySQLite(conn)
        stats = VideoStats(
            video_id=vid,
            captured_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            view_count=100,
            like_count=10,
        )
        result = repo.append(stats)
        assert result.id is not None
        assert result.view_count == 100


def test_append_is_idempotent_on_same_captured_at(engine: Engine) -> None:
    """D-01: UNIQUE(video_id, captured_at) at second resolution."""
    with engine.begin() as conn:
        vid = _persist_video(conn)
        repo = VideoStatsRepositorySQLite(conn)
        t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        repo.append(VideoStats(video_id=vid, captured_at=t, view_count=100))
        repo.append(VideoStats(video_id=vid, captured_at=t, view_count=999))
        rows = repo.list_for_video(vid)
        assert len(rows) == 1


def test_append_does_not_update_on_conflict(engine: Engine) -> None:
    """Append-only (D031): second append with same key does NOT mutate."""
    with engine.begin() as conn:
        vid = _persist_video(conn)
        repo = VideoStatsRepositorySQLite(conn)
        t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        repo.append(VideoStats(video_id=vid, captured_at=t, view_count=100, like_count=5))
        repo.append(VideoStats(video_id=vid, captured_at=t, view_count=999, like_count=888))
        latest = repo.latest_for_video(vid)
        assert latest is not None
        assert latest.view_count == 100   # original preserved
        assert latest.like_count == 5


def test_list_for_video_orders_by_captured_at_asc(engine: Engine) -> None:
    with engine.begin() as conn:
        vid = _persist_video(conn)
        repo = VideoStatsRepositorySQLite(conn)
        base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        for i in [3, 1, 2]:
            repo.append(VideoStats(video_id=vid, captured_at=base + timedelta(hours=i), view_count=i * 100))
        rows = repo.list_for_video(vid)
        assert [r.view_count for r in rows] == [100, 200, 300]


def test_latest_for_video_returns_most_recent(engine: Engine) -> None:
    with engine.begin() as conn:
        vid = _persist_video(conn)
        repo = VideoStatsRepositorySQLite(conn)
        base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        repo.append(VideoStats(video_id=vid, captured_at=base, view_count=100))
        repo.append(VideoStats(video_id=vid, captured_at=base + timedelta(hours=1), view_count=200))
        latest = repo.latest_for_video(vid)
        assert latest is not None
        assert latest.view_count == 200


def test_latest_for_video_none_when_empty(engine: Engine) -> None:
    with engine.begin() as conn:
        vid = _persist_video(conn)
        repo = VideoStatsRepositorySQLite(conn)
        assert repo.latest_for_video(vid) is None


def test_has_any_for_video(engine: Engine) -> None:
    with engine.begin() as conn:
        vid = _persist_video(conn)
        repo = VideoStatsRepositorySQLite(conn)
        assert repo.has_any_for_video(vid) is False
        repo.append(VideoStats(video_id=vid, captured_at=datetime(2026, 1, 1, tzinfo=UTC)))
        assert repo.has_any_for_video(vid) is True


def test_list_videos_with_min_snapshots(engine: Engine) -> None:
    with engine.begin() as conn:
        vid = _persist_video(conn)
        repo = VideoStatsRepositorySQLite(conn)
        base = datetime(2026, 1, 1, tzinfo=UTC)
        repo.append(VideoStats(video_id=vid, captured_at=base))
        # Only one snapshot -> should not appear
        assert repo.list_videos_with_min_snapshots(2) == []
        repo.append(VideoStats(video_id=vid, captured_at=base + timedelta(hours=1)))
        ids = repo.list_videos_with_min_snapshots(2)
        assert vid in ids


def test_none_counters_preserved_on_roundtrip(engine: Engine) -> None:
    """D-03: None MUST NOT be converted to 0 through persistence."""
    with engine.begin() as conn:
        vid = _persist_video(conn)
        repo = VideoStatsRepositorySQLite(conn)
        repo.append(VideoStats(
            video_id=vid,
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
            view_count=1000,
            like_count=None,
            repost_count=None,
            save_count=None,
        ))
        latest = repo.latest_for_video(vid)
        assert latest is not None
        assert latest.like_count is None
        assert latest.repost_count is None
        assert latest.save_count is None
```

Étape 6 — Étendre `tests/unit/adapters/sqlite/test_schema.py` (ajouter en fin de fichier) :
```python
def test_init_db_creates_video_stats_table(tmp_path):
    from sqlalchemy import create_engine, text
    from vidscope.adapters.sqlite.schema import init_db
    eng = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_db(eng)
    with eng.connect() as conn:
        tables = {
            row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        assert "video_stats" in tables


def test_init_db_is_idempotent_on_video_stats(tmp_path):
    from sqlalchemy import create_engine, text
    from vidscope.adapters.sqlite.schema import init_db
    db_path = tmp_path / "t.db"
    eng = create_engine(f"sqlite:///{db_path}")
    init_db(eng)
    init_db(eng)   # second call must not raise
    with eng.connect() as conn:
        indexes = {
            row[0] for row in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='video_stats'"
            ))
        }
        assert "idx_video_stats_video_id" in indexes
        assert "idx_video_stats_captured_at" in indexes


def test_ensure_video_stats_table_on_pre_m009_db(tmp_path):
    """Simulate a pre-M009 DB: create videos + other tables, then init_db adds video_stats."""
    from sqlalchemy import create_engine, text
    from vidscope.adapters.sqlite.schema import _ensure_video_stats_table
    db_path = tmp_path / "t.db"
    eng = create_engine(f"sqlite:///{db_path}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE videos (id INTEGER PRIMARY KEY)"))
        _ensure_video_stats_table(conn)
        tables = {
            row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        assert "video_stats" in tables
```

Étape 7 — Lancer les tests :
```
uv run pytest tests/unit/adapters/sqlite/test_video_stats_repository.py tests/unit/adapters/sqlite/test_schema.py tests/unit/adapters/sqlite/test_unit_of_work.py -x -q
uv run lint-imports
```

NE PAS écrire de méthode `update()` sur `VideoStatsRepositorySQLite` (append-only invariant). NE PAS utiliser `text()` avec f-string pour des user inputs (T-SQL-01).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/adapters/sqlite/test_video_stats_repository.py tests/unit/adapters/sqlite/test_schema.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "video_stats = Table" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "uq_video_stats_video_id_captured_at" src/vidscope/adapters/sqlite/schema.py` matches (2 occurrences : Table + migration DDL)
    - `grep -n "_ensure_video_stats_table" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "class VideoStatsRepositorySQLite" src/vidscope/adapters/sqlite/video_stats_repository.py` matches
    - `grep -n "on_conflict_do_nothing" src/vidscope/adapters/sqlite/video_stats_repository.py` matches
    - Le fichier `video_stats_repository.py` ne contient AUCUNE méthode `def update`. `grep -nE "def update" src/vidscope/adapters/sqlite/video_stats_repository.py` returns exit code 1 (no match)
    - `grep -n "self.video_stats" src/vidscope/adapters/sqlite/unit_of_work.py` matches
    - `grep -n "stats_probe: StatsProbe" src/vidscope/infrastructure/container.py` matches
    - `grep -n "YtdlpStatsProbe(" src/vidscope/infrastructure/container.py` matches
    - `uv run pytest tests/unit/adapters/sqlite/test_video_stats_repository.py -x -q` exits 0
    - `uv run pytest tests/unit/adapters/sqlite/test_schema.py -x -q` exits 0
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - Table video_stats créée avec UNIQUE + 2 Index
    - Migration idempotente _ensure_video_stats_table ajoutée à init_db
    - VideoStatsRepositorySQLite livré sans update() (append-only structurel)
    - UoW étendu avec video_stats repo
    - Container expose stats_probe, YtdlpStatsProbe instancié
    - 10+ tests unitaires verts
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| yt-dlp → YtdlpStatsProbe | Données externes non validées entrent dans l'application |
| yt-dlp info dict → VideoStats entity | Valeurs potentiellement non-int, None, ou types inattendus |
| Caller → VideoStatsRepository.append | video_id et captured_at viennent du pipeline — mais via SQLAlchemy Core paramétré |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-DATA-01 | Tampering | `YtdlpStatsProbe.probe_stats` | mitigate | Helper `_int_or_none()` appliqué sur les 5 champs (`view_count`, `like_count`, `repost_count`, `comment_count`, `save_count`). Toute valeur non-int → `None`, jamais stockée telle quelle. `captured_at` tronqué à la seconde via `replace(microsecond=0)`. |
| T-SQL-01 | Tampering | `VideoStatsRepositorySQLite` | mitigate | SQLAlchemy Core parameterized queries uniquement. `select(video_stats).where(video_stats.c.video_id == int(video_id))` — jamais de `text(f"... {value}")`. `int(video_id)` cast explicite pour éviter qu'un caller passe un objet non-int. |
| T-INPUT-01 | Denial of Service | `VideoStatsRepository.list_for_video` / `list_videos_with_min_snapshots` | mitigate | Paramètres `limit: int = 100` et `limit: int = 200` en kwarg obligatoire — bornes par défaut. Pas de support de `limit=0` ou négatif dans S01 (le caller S04 ajoutera la validation CLI Typer `min=1`). |
| T-PROBE-01 | Availability | `YtdlpStatsProbe` (failures externes) | accept | Toute exception yt-dlp est catchée et retourne `None`. L'absence de stats n'est pas critique — le probe pattern (M005) garantit que la pipeline continue. |
</threat_model>

<verification>
Après les 3 tâches :
- `uv run pytest tests/unit/ -x -q` verte (domain, adapters/ytdlp, adapters/sqlite)
- `uv run pytest tests/unit/domain/test_metrics_property.py -x -q` verte (gate Hypothesis non-négociable)
- `uv run lint-imports` verte (domain-is-pure, ports-are-pure, adapters-never-cross)
- `grep -rn "hypothesis" pyproject.toml` matches
- `uv run python -c "from vidscope.domain import VideoStats; from vidscope.domain.metrics import views_velocity_24h, engagement_rate; from vidscope.ports import StatsProbe, VideoStatsRepository; print('ok')"` imprime `ok`
- `uv run python -c "from vidscope.adapters.ytdlp import YtdlpStatsProbe; from vidscope.adapters.sqlite.video_stats_repository import VideoStatsRepositorySQLite; print('ok')"` imprime `ok`
</verification>

<success_criteria>
S01 est complet quand :
- [ ] `hypothesis>=6.0,<7` présent dans `[dependency-groups] dev` de pyproject.toml
- [ ] `StageName.STATS = "stats"` ajouté dans values.py
- [ ] `VideoStats` dataclass frozen slots=True avec 5 compteurs `int | None`
- [ ] `metrics.py` livré dans `domain/` avec zéro import runtime projet (TYPE_CHECKING uniquement)
- [ ] `StatsProbe` Protocol runtime_checkable dans `ports/stats_probe.py`
- [ ] `VideoStatsRepository` Protocol ajouté dans `ports/repositories.py`
- [ ] `UnitOfWork.video_stats` exposé dans le Protocol
- [ ] `YtdlpStatsProbe` adapter avec truncation seconde + `_int_or_none` + probe-never-raises
- [ ] Table `video_stats` avec UNIQUE(video_id, captured_at) + 2 Index
- [ ] `_ensure_video_stats_table` idempotente appelée par `init_db`
- [ ] `VideoStatsRepositorySQLite` append-only (pas de `def update`) avec ON CONFLICT DO NOTHING
- [ ] `SqliteUnitOfWork.video_stats` câblé
- [ ] `Container.stats_probe` exposé
- [ ] Suite tests unit verte (domain + adapters/ytdlp + adapters/sqlite)
- [ ] Gate Hypothesis `test_metrics_property.py` verte (4 propriétés)
- [ ] `lint-imports` vert (9 contrats respectés)
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M009/M009-S01-SUMMARY.md` documentant les artifacts livrés, les décisions techniques (formules metrics, pattern migration, pattern append-only), et la liste des fichiers créés/modifiés.
</output>
