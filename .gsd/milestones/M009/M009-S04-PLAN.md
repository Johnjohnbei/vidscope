---
phase: M009
plan: S04
type: execute
wave: 4
depends_on: [S01]
files_modified:
  - src/vidscope/application/list_trending.py
  - src/vidscope/application/show_video.py
  - src/vidscope/application/__init__.py
  - src/vidscope/cli/commands/trending.py
  - src/vidscope/cli/commands/show.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - src/vidscope/mcp/server.py
  - tests/unit/application/test_list_trending.py
  - tests/unit/application/test_show_video.py
  - tests/unit/cli/test_trending.py
  - tests/unit/cli/test_show_cmd.py
  - tests/unit/mcp/test_server.py
autonomous: true
requirements: [R052]
must_haves:
  truths:
    - "`vidscope trending --since 7d` ranke les vidéos par velocity_24h descendant"
    - "`vidscope trending` REFUSE l'absence de `--since` (pas de défaut silencieux, D-04)"
    - "`vidscope trending --platform youtube --min-velocity 100 --limit 10` filtre correctement"
    - "`metrics.views_velocity_24h` et `metrics.engagement_rate` sont calculés correctement pour chaque résultat affiché"
    - "MCP tool `vidscope_trending` exposé sur le FastMCP server, retourne une liste de dicts sérialisables"
    - "`vidscope show <id>` affiche une section stats (D-05) : dernière capture + vélocité OU message actionnable si 0 rows"
    - "ListTrendingUseCase utilise SQL avec LIMIT poussé en base (D-04 : scalabilité)"
  artifacts:
    - path: "src/vidscope/application/list_trending.py"
      provides: "ListTrendingUseCase + DTO TrendingEntry"
      contains: "class ListTrendingUseCase"
    - path: "src/vidscope/cli/commands/trending.py"
      provides: "vidscope trending command + parse_since helper"
      contains: "def trending_command"
    - path: "src/vidscope/mcp/server.py"
      provides: "vidscope_trending MCP tool registered"
      contains: "vidscope_trending"
  key_links:
    - from: "src/vidscope/cli/commands/trending.py"
      to: "ListTrendingUseCase"
      via: "trending_command -> use_case.execute(since, platform, min_velocity, limit)"
      pattern: "ListTrendingUseCase"
    - from: "src/vidscope/mcp/server.py"
      to: "ListTrendingUseCase"
      via: "@mcp.tool vidscope_trending -> use_case.execute(...)"
      pattern: "vidscope_trending"
    - from: "src/vidscope/application/show_video.py"
      to: "VideoStatsRepository + metrics.views_velocity_24h"
      via: "ShowVideoUseCase.execute extended with stats section (D-05)"
      pattern: "views_velocity_24h"
---

<objective>
S04 termine M009 : `ListTrendingUseCase` avec requête SQL optimisée (LIMIT en base, D-04), commande CLI `vidscope trending --since <window> [--platform] [--min-velocity] [--limit]`, MCP tool `vidscope_trending`, et extension de `vidscope show <id>` avec une section stats (D-05). Dépend de S01 (`metrics.py`, `VideoStatsRepository`) mais PAS de S02/S03 — peut tourner en parallèle de S03.

Purpose: Sans S04, les users n'ont aucun moyen de voir "ce qui monte" ni de consulter l'historique d'une vidéo donnée. C'est la surface utilisateur finale de M009.
Output: Use case trending, CLI, MCP tool, extension `show` — fin de M009.
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
@src/vidscope/domain/metrics.py
@src/vidscope/application/suggest_related.py
@src/vidscope/application/show_video.py
@src/vidscope/adapters/sqlite/video_stats_repository.py
@src/vidscope/cli/commands/show.py
@src/vidscope/cli/commands/suggest.py
@src/vidscope/cli/app.py
@src/vidscope/mcp/server.py

<interfaces>
**DTO `TrendingEntry`** :
```python
@dataclass(frozen=True, slots=True)
class TrendingEntry:
    video_id: int
    platform: Platform
    title: str | None
    views_velocity_24h: float       # vues/jour
    engagement_rate: float | None   # 0..1, ou None si view_count = 0/None
    last_captured_at: datetime
    latest_view_count: int | None
    latest_like_count: int | None
```

**Signature `ListTrendingUseCase.execute`** :
```python
def execute(
    self,
    *,
    since: timedelta,
    platform: Platform | None = None,
    min_velocity: float = 0.0,
    limit: int = 20,
) -> list[TrendingEntry]: ...
```

**Pattern de requête SQL (D-04 scalabilité)** : voir M009-RESEARCH "Requête trending SQL avec LIMIT en base". L'approche en 2 étapes :
1. Requête SQL qui agrège `MAX(view_count) - MIN(view_count)` par `video_id` sur la fenêtre `captured_at >= since`, filtre par platform (via JOIN videos), filtre min_velocity approximatif, order by delta DESC, LIMIT N.
2. Pour chaque video_id retourné, charger l'historique complet + calculer `views_velocity_24h` et `engagement_rate` exacts via `metrics.py` pure-domain.

**CLI `vidscope trending`** :
```
vidscope trending --since 7d [--platform instagram|tiktok|youtube] [--min-velocity 0] [--limit 20]
```
- `--since` OBLIGATOIRE (pas de défaut) — D-04
- `--min-velocity` défaut 0.0, `--limit` défaut 20
- Format `rich.Table` ASCII-only

**MCP tool `vidscope_trending`** : pattern `suggest_related` déjà en place dans `server.py`. Signature attendue :
```python
@mcp.tool
def vidscope_trending(since: str, platform: str | None = None, min_velocity: float = 0.0, limit: int = 20) -> list[dict[str, Any]]:
```

**Extension `show` (D-05)** : `ShowVideoResult` reçoit deux nouveaux champs optionnels :
```python
latest_stats: VideoStats | None = None
views_velocity_24h: float | None = None
```
Le CLI `show.py` affiche un nouveau bloc "Stats" avec les compteurs + vélocité, OU un message actionnable si aucune row : `"Aucune stat capturée — lancez: vidscope refresh-stats <id>"`.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: ListTrendingUseCase + TrendingEntry DTO + tests (SQL LIMIT en base)</name>
  <files>src/vidscope/application/list_trending.py, src/vidscope/application/__init__.py, src/vidscope/ports/repositories.py, src/vidscope/adapters/sqlite/video_stats_repository.py, tests/unit/application/test_list_trending.py, tests/unit/adapters/sqlite/test_video_stats_repository.py</files>
  <read_first>
    - src/vidscope/application/suggest_related.py (pattern use case avec DTO + ranking)
    - src/vidscope/application/__init__.py (liste __all__)
    - src/vidscope/adapters/sqlite/video_stats_repository.py (livré S01 — ajouter une méthode de ranking)
    - src/vidscope/adapters/sqlite/video_repository.py (pattern SQL avec select/where/order_by/limit)
    - src/vidscope/adapters/sqlite/schema.py (Table `videos` + Table `video_stats` livrée S01)
    - src/vidscope/domain/metrics.py (livré S01 — views_velocity_24h, engagement_rate)
    - src/vidscope/ports/repositories.py (VideoStatsRepository Protocol livré S01)
    - .gsd/milestones/M009/M009-RESEARCH.md ("Requête trending SQL avec LIMIT en base" Pattern 8)
    - .gsd/milestones/M009/M009-CONTEXT.md (D-04 défauts et formats)
  </read_first>
  <behavior>
    - Test 1 : `execute(since=timedelta(days=7))` retourne une liste de `TrendingEntry` triée par `views_velocity_24h` descendant.
    - Test 2 : Les vidéos avec < 2 snapshots dans la fenêtre sont exclues (velocity_24h non calculable).
    - Test 3 : `--platform youtube` filtre par platform (les vidéos IG/TikTok absentes du résultat).
    - Test 4 : `--min-velocity 100` exclut les vidéos avec velocity < 100.
    - Test 5 : `--limit 10` limite à 10 résultats max (LIMIT en base).
    - Test 6 : Chaque `TrendingEntry` a `engagement_rate` calculé via `metrics.engagement_rate` (peut être None).
    - Test 7 : `views_velocity_24h` dans le DTO vient de `metrics.views_velocity_24h(history)` pure-domain, pas de l'approximation SQL.
    - Test 8 : `video_stats_repo.rank_by_velocity_candidates(...)` retourne les video_ids candidats ordonnés par delta SQL approximatif (méthode nouvelle sur le repo).
  </behavior>
  <action>
Étape 1 — Ajouter une méthode dans le repository `VideoStatsRepository` Protocol (`src/vidscope/ports/repositories.py`) + implémentation SQLite (`src/vidscope/adapters/sqlite/video_stats_repository.py`) :
```python
# Protocol addition
def rank_candidates_by_delta(
    self,
    *,
    since: datetime,
    platform: Platform | None = None,
    limit: int = 100,
) -> list[VideoId]:
    """Return video_ids sorted by SQL-approx delta views on the window.

    Applies GROUP BY video_id + HAVING count >= 2 + LIMIT at the SQL
    level per D-04 scalability. The use case then computes the exact
    metrics on the returned subset.
    """
    ...
```

Implémentation dans `video_stats_repository.py` (extension du fichier S01) :
```python
def rank_candidates_by_delta(
    self,
    *,
    since: datetime,
    platform: "Platform | None" = None,
    limit: int = 100,
) -> list[VideoId]:
    from sqlalchemy import func, select
    from vidscope.adapters.sqlite.schema import video_stats, videos

    subq = (
        select(
            video_stats.c.video_id,
            (func.max(video_stats.c.view_count) - func.min(video_stats.c.view_count)).label("delta_views"),
            func.count(video_stats.c.id).label("snap_count"),
        )
        .where(video_stats.c.captured_at >= since)
        .where(video_stats.c.view_count.is_not(None))
    )
    if platform is not None:
        subq = subq.join(videos, videos.c.id == video_stats.c.video_id).where(videos.c.platform == platform.value)

    stmt = (
        subq.group_by(video_stats.c.video_id)
        .having(func.count(video_stats.c.id) >= 2)
        .order_by(func.max(video_stats.c.view_count) - func.min(video_stats.c.view_count))
        .limit(limit)
    )
    # NOTE: we want DESC order — swap to .order_by(... .desc()).
    # Fix:
    stmt = (
        subq.group_by(video_stats.c.video_id)
        .having(func.count(video_stats.c.id) >= 2)
        .order_by((func.max(video_stats.c.view_count) - func.min(video_stats.c.view_count)).desc())
        .limit(limit)
    )

    rows = self._conn.execute(stmt).all()
    return [VideoId(int(r[0])) for r in rows]
```

(Adapter la syntaxe SQL aux Tables réelles — vérifier les attributs exacts. Si nécessaire, utiliser `text(...)` avec params — **MAIS JAMAIS avec f-string sur user input** (T-SQL-01)).

Étape 2 — Créer `src/vidscope/application/list_trending.py` :
```python
"""ListTrendingUseCase — rank videos by views_velocity_24h on a time window.

Scalability (D-04): the candidate set is reduced via a SQL GROUP BY +
ORDER BY delta DESC + LIMIT query in the repository. Only that subset
loads its full history to compute the exact metrics (metrics.py pure
domain). No full table scan in Python.

NO INFRASTRUCTURE IMPORT (application-has-no-adapters contract).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from vidscope.domain import Platform, VideoId
from vidscope.domain.metrics import engagement_rate, views_velocity_24h
from vidscope.ports import UnitOfWorkFactory
from vidscope.ports.clock import Clock

if TYPE_CHECKING:
    from vidscope.domain import VideoStats

__all__ = ["ListTrendingUseCase", "TrendingEntry"]


@dataclass(frozen=True, slots=True)
class TrendingEntry:
    """One row in the vidscope trending output."""

    video_id: int
    platform: Platform
    title: str | None
    views_velocity_24h: float   # views per day
    engagement_rate: float | None   # 0..1 or None when view_count==0/None
    last_captured_at: datetime
    latest_view_count: int | None
    latest_like_count: int | None


class ListTrendingUseCase:
    """Rank videos by views_velocity_24h on the given window.

    Args to execute():
    - since (timedelta): mandatory window. The caller converts the CLI
      --since "7d" string to a timedelta before calling.
    - platform: optional filter.
    - min_velocity: floor on views_velocity_24h (default 0.0).
    - limit: max results (default 20).
    """

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
    ) -> None:
        self._uow = unit_of_work_factory
        self._clock = clock

    def execute(
        self,
        *,
        since: timedelta,
        platform: Platform | None = None,
        min_velocity: float = 0.0,
        limit: int = 20,
    ) -> list[TrendingEntry]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if since.total_seconds() <= 0:
            raise ValueError("since must be positive")

        cutoff = self._clock.now() - since

        with self._uow() as uow:
            # SQL-level candidate shortlist: K > limit to absorb filtering.
            candidate_ids = uow.video_stats.rank_candidates_by_delta(
                since=cutoff,
                platform=platform,
                limit=max(limit * 5, limit),
            )

            entries: list[TrendingEntry] = []
            for vid in candidate_ids:
                history = uow.video_stats.list_for_video(vid, limit=1000)
                if len(history) < 2:
                    continue
                velocity = views_velocity_24h(history)
                if velocity is None or velocity < min_velocity:
                    continue

                latest = history[-1]
                video = uow.videos.get(vid)
                if video is None:
                    continue
                entries.append(
                    TrendingEntry(
                        video_id=int(vid),
                        platform=video.platform,
                        title=video.title,
                        views_velocity_24h=velocity,
                        engagement_rate=engagement_rate(latest),
                        last_captured_at=latest.captured_at,
                        latest_view_count=latest.view_count,
                        latest_like_count=latest.like_count,
                    )
                )

        entries.sort(key=lambda e: e.views_velocity_24h, reverse=True)
        return entries[:limit]
```

Étape 3 — Étendre `src/vidscope/application/__init__.py` avec les re-exports.

Étape 4 — Créer `tests/unit/application/test_list_trending.py` :
```python
"""Unit tests for ListTrendingUseCase — ranking correctness + D-04 scalability."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from vidscope.application.list_trending import ListTrendingUseCase, TrendingEntry
from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats


class _FrozenClock:
    def __init__(self, now: datetime) -> None:
        self._now = now
    def now(self) -> datetime: return self._now


def _hist(*, view_counts: list[int], start: datetime, step_hours: int = 1) -> list[VideoStats]:
    return [
        VideoStats(
            video_id=VideoId(1),
            captured_at=start + timedelta(hours=i * step_hours),
            view_count=v,
            like_count=v // 10,
            comment_count=v // 100,
        )
        for i, v in enumerate(view_counts)
    ]


def _make_uow_factory(
    *,
    candidates: dict[int, list[VideoStats]],
    videos: dict[int, Video],
):
    class _FakeUoW:
        def __init__(self) -> None:
            self.video_stats = MagicMock()
            self.video_stats.rank_candidates_by_delta = MagicMock(return_value=[VideoId(vid) for vid in candidates])
            self.video_stats.list_for_video = MagicMock(
                side_effect=lambda vid, *, limit=1000: candidates.get(int(vid), [])
            )
            self.videos = MagicMock()
            self.videos.get = MagicMock(side_effect=lambda vid: videos.get(int(vid)))

        def __enter__(self): return self
        def __exit__(self, *_): return None

    return lambda: _FakeUoW()


def test_ranks_by_velocity_descending() -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(days=1)
    candidates = {
        1: _hist(view_counts=[100, 500], start=base),       # delta 400 / 1h
        2: _hist(view_counts=[100, 200], start=base),       # delta 100 / 1h
        3: _hist(view_counts=[100, 1000], start=base),      # delta 900 / 1h (winner)
    }
    videos = {
        i: Video(id=VideoId(i), platform=Platform.YOUTUBE, platform_id=PlatformId(f"p{i}"), url=f"https://x.y/{i}", title=f"T{i}")
        for i in (1, 2, 3)
    }
    uc = ListTrendingUseCase(unit_of_work_factory=_make_uow_factory(candidates=candidates, videos=videos), clock=_FrozenClock(now))
    results = uc.execute(since=timedelta(days=7), limit=10)
    assert [e.video_id for e in results] == [3, 1, 2]
    assert results[0].views_velocity_24h > results[1].views_velocity_24h


def test_excludes_videos_with_less_than_two_snapshots() -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(days=1)
    candidates = {
        1: _hist(view_counts=[100], start=base),       # only 1 snapshot
        2: _hist(view_counts=[50, 500], start=base),
    }
    videos = {
        i: Video(id=VideoId(i), platform=Platform.YOUTUBE, platform_id=PlatformId(f"p{i}"), url="https://x.y", title=f"T{i}")
        for i in (1, 2)
    }
    uc = ListTrendingUseCase(unit_of_work_factory=_make_uow_factory(candidates=candidates, videos=videos), clock=_FrozenClock(now))
    results = uc.execute(since=timedelta(days=7))
    assert [e.video_id for e in results] == [2]


def test_respects_min_velocity() -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(days=1)
    # Velocity approximate: (500-100)/1h * 24 = 9600 views/day  (fast)
    #                      (150-100)/1h * 24 = 1200 views/day   (slow)
    candidates = {
        1: _hist(view_counts=[100, 500], start=base),
        2: _hist(view_counts=[100, 150], start=base),
    }
    videos = {
        i: Video(id=VideoId(i), platform=Platform.YOUTUBE, platform_id=PlatformId(f"p{i}"), url="https://x.y", title=f"T{i}")
        for i in (1, 2)
    }
    uc = ListTrendingUseCase(unit_of_work_factory=_make_uow_factory(candidates=candidates, videos=videos), clock=_FrozenClock(now))
    results = uc.execute(since=timedelta(days=7), min_velocity=5000.0)
    assert [e.video_id for e in results] == [1]


def test_respects_limit() -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(days=1)
    candidates = {i: _hist(view_counts=[100, 100 + i * 10], start=base) for i in range(1, 6)}
    videos = {
        i: Video(id=VideoId(i), platform=Platform.YOUTUBE, platform_id=PlatformId(f"p{i}"), url="https://x.y", title=f"T{i}")
        for i in range(1, 6)
    }
    uc = ListTrendingUseCase(unit_of_work_factory=_make_uow_factory(candidates=candidates, videos=videos), clock=_FrozenClock(now))
    results = uc.execute(since=timedelta(days=7), limit=2)
    assert len(results) == 2


def test_engagement_rate_from_metrics_module() -> None:
    """engagement_rate uses the pure-domain metrics.engagement_rate."""
    now = datetime(2026, 1, 10, tzinfo=UTC)
    base = now - timedelta(days=1)
    hist = [
        VideoStats(video_id=VideoId(1), captured_at=base, view_count=100, like_count=5, comment_count=5),
        VideoStats(video_id=VideoId(1), captured_at=base + timedelta(hours=1), view_count=1000, like_count=50, comment_count=10),
    ]
    videos = {1: Video(id=VideoId(1), platform=Platform.YOUTUBE, platform_id=PlatformId("p1"), url="https://x.y", title="T1")}
    uc = ListTrendingUseCase(unit_of_work_factory=_make_uow_factory(candidates={1: hist}, videos=videos), clock=_FrozenClock(now))
    results = uc.execute(since=timedelta(days=7))
    assert results[0].engagement_rate == pytest.approx((50 + 10) / 1000)


def test_rejects_non_positive_since() -> None:
    uc = ListTrendingUseCase(
        unit_of_work_factory=_make_uow_factory(candidates={}, videos={}),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    with pytest.raises(ValueError, match="since"):
        uc.execute(since=timedelta(seconds=0))


def test_rejects_limit_zero() -> None:
    uc = ListTrendingUseCase(
        unit_of_work_factory=_make_uow_factory(candidates={}, videos={}),
        clock=_FrozenClock(datetime(2026, 1, 10, tzinfo=UTC)),
    )
    with pytest.raises(ValueError, match="limit"):
        uc.execute(since=timedelta(days=1), limit=0)
```

Étape 5 — Étendre `tests/unit/adapters/sqlite/test_video_stats_repository.py` avec un test qui vérifie `rank_candidates_by_delta` :
```python
def test_rank_candidates_by_delta(engine: Engine) -> None:
    from datetime import UTC, datetime, timedelta
    from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats
    with engine.begin() as conn:
        # Create 2 videos with different deltas
        vrepo = VideoRepositorySQLite(conn)
        v1 = vrepo.upsert_by_platform_id(Video(platform=Platform.YOUTUBE, platform_id=PlatformId("p1"), url="https://x.y/1"))
        v2 = vrepo.upsert_by_platform_id(Video(platform=Platform.YOUTUBE, platform_id=PlatformId("p2"), url="https://x.y/2"))
        sr = VideoStatsRepositorySQLite(conn)
        base = datetime(2026, 1, 1, tzinfo=UTC)
        # v1 delta = 900
        sr.append(VideoStats(video_id=v1.id, captured_at=base, view_count=100))
        sr.append(VideoStats(video_id=v1.id, captured_at=base + timedelta(hours=1), view_count=1000))
        # v2 delta = 100
        sr.append(VideoStats(video_id=v2.id, captured_at=base, view_count=100))
        sr.append(VideoStats(video_id=v2.id, captured_at=base + timedelta(hours=1), view_count=200))

        result = sr.rank_candidates_by_delta(since=base - timedelta(days=1), limit=10)
        assert result[0] == v1.id   # larger delta first
        assert result[1] == v2.id
```

Étape 6 — Exécuter :
```
uv run pytest tests/unit/application/test_list_trending.py tests/unit/adapters/sqlite/test_video_stats_repository.py -x -q
uv run lint-imports
```

NE PAS importer `infrastructure/` ni `adapters/` dans le use case. NE PAS utiliser `text(f"...{user_input}...")` (T-SQL-01). UTILISER SQLAlchemy Core paramétré.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/application/test_list_trending.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class ListTrendingUseCase" src/vidscope/application/list_trending.py` matches
    - `grep -n "class TrendingEntry" src/vidscope/application/list_trending.py` matches
    - `grep -n "views_velocity_24h" src/vidscope/application/list_trending.py` matches
    - `grep -n "engagement_rate" src/vidscope/application/list_trending.py` matches
    - `grep -n "def rank_candidates_by_delta" src/vidscope/adapters/sqlite/video_stats_repository.py` matches
    - `grep -n "rank_candidates_by_delta" src/vidscope/ports/repositories.py` matches
    - `grep -nE "^from vidscope.infrastructure" src/vidscope/application/list_trending.py` returns exit 1
    - `grep -nE "^from vidscope.adapters" src/vidscope/application/list_trending.py` returns exit 1
    - `uv run pytest tests/unit/application/test_list_trending.py -x -q` exits 0
    - `uv run pytest tests/unit/adapters/sqlite/test_video_stats_repository.py -x -q` exits 0
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - ListTrendingUseCase + TrendingEntry + DTO livrés
    - rank_candidates_by_delta ajouté au Protocol + adapter SQLite
    - 7 tests application + 1 test adapter verts
    - Metrics calculées via metrics.py pure-domain
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: CLI `vidscope trending` + MCP tool `vidscope_trending` + tests</name>
  <files>src/vidscope/cli/commands/trending.py, src/vidscope/cli/commands/__init__.py, src/vidscope/cli/app.py, src/vidscope/mcp/server.py, tests/unit/cli/test_trending.py, tests/unit/cli/test_app.py, tests/unit/mcp/test_server.py</files>
  <read_first>
    - src/vidscope/cli/commands/stats.py (pattern `_parse_since` livré S02 — À RÉUTILISER ou extraire en helper)
    - src/vidscope/cli/commands/suggest.py (pattern commande simple rich.Table)
    - src/vidscope/cli/commands/__init__.py (exports)
    - src/vidscope/cli/app.py (enregistrement)
    - src/vidscope/cli/_support.py (acquire_container, handle_domain_errors)
    - src/vidscope/mcp/server.py (pattern registration tool avec FastMCP + DomainError trap)
    - src/vidscope/application/list_trending.py (livré Task 1)
    - .gsd/milestones/M009/M009-CONTEXT.md (D-04 format complet du trending)
    - .gsd/KNOWLEDGE.md (ASCII only stdout)
    - tests/unit/mcp/test_server.py (pattern tests MCP tools)
  </read_first>
  <behavior>
    - Test 1 CLI : `vidscope trending --since 7d` exit 0 avec une Table listant les top 20 vidéos.
    - Test 2 CLI : `vidscope trending` (sans --since) exit != 0 (D-04 : `--since` obligatoire).
    - Test 3 CLI : `vidscope trending --since 7d --platform youtube --min-velocity 100 --limit 5` filtre correctement.
    - Test 4 CLI : `vidscope trending --since 7d --limit 0` exit != 0 (T-INPUT-01).
    - Test 5 CLI : `vidscope trending --since 1week` exit != 0 (parser strict).
    - Test 6 CLI : La Table contient les colonnes `#`, `title`, `platform`, `velocity_24h`, `engagement%`, `last capture`.
    - Test 7 MCP : `vidscope_trending(since="7d", platform="youtube", limit=5)` retourne une liste de dicts JSON-serializables.
    - Test 8 MCP : `vidscope_trending(since="1week")` raise `ValueError` trappée par FastMCP (ou retourne erreur claire).
  </behavior>
  <action>
Étape 1 — Factoriser `_parse_since` : si la fonction `_parse_since` existe déjà dans `cli/commands/stats.py` (livré S02), l'EXTRAIRE dans `src/vidscope/cli/_support.py` comme `parse_window(raw: str) -> timedelta` pour qu'elle soit réutilisable par `trending.py`. Mettre à jour `stats.py` pour importer depuis `_support`. Alternative plus simple : répliquer le code dans `trending.py` — acceptable mais moins propre.

Étape 2 — Créer `src/vidscope/cli/commands/trending.py` :
```python
"""`vidscope trending --since <window>` — rank ingested videos by velocity.

Per M009 D-04:
- --since MANDATORY (no silent default)
- --limit default 20, min=1
- --platform optional
- --min-velocity default 0.0
- rich.Table output, ASCII tags only.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

import typer
from rich.table import Table

from vidscope.application.list_trending import ListTrendingUseCase, TrendingEntry
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)
from vidscope.domain import Platform

__all__ = ["trending_command"]


def _parse_window(raw: str) -> timedelta:
    """Strict N(h|d) parser — refuses '1week', '7', '30m'."""
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
    raise typer.BadParameter(f"invalid --since unit: {unit!r} (expected 'h' or 'd')")


def _parse_platform(raw: str | None) -> Platform | None:
    if raw is None:
        return None
    try:
        return Platform(raw.strip().lower())
    except ValueError:
        raise typer.BadParameter(
            f"invalid --platform: {raw!r} (expected instagram|tiktok|youtube)"
        )


def trending_command(
    since: Annotated[str, typer.Option("--since", help="Time window (mandatory), e.g. 7d, 24h.")],
    platform: Annotated[str | None, typer.Option("--platform", help="Filter by platform (instagram|tiktok|youtube).")] = None,
    min_velocity: Annotated[float, typer.Option("--min-velocity", help="Minimum views/day to appear.")] = 0.0,
    limit: Annotated[int, typer.Option("--limit", min=1, help="Max results (must be >= 1).")] = 20,
) -> None:
    """Rank ingested videos by views_velocity_24h descending."""
    with handle_domain_errors():
        window = _parse_window(since)
        plat = _parse_platform(platform)
        container = acquire_container()
        uc = ListTrendingUseCase(
            unit_of_work_factory=container.unit_of_work,
            clock=container.clock,
        )
        results = uc.execute(
            since=window,
            platform=plat,
            min_velocity=min_velocity,
            limit=limit,
        )
        _render_trending(results)


def _render_trending(results: list[TrendingEntry]) -> None:
    if not results:
        console.print("[dim]No trending videos in this window.[/dim]")
        return

    table = Table(title=f"Trending ({len(results)})", show_header=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("title", max_width=40)
    table.add_column("platform")
    table.add_column("velocity_24h", justify="right")
    table.add_column("engagement%", justify="right")
    table.add_column("last capture")

    for i, entry in enumerate(results, start=1):
        title = (entry.title or "?")[:40]
        velocity = f"{entry.views_velocity_24h:.0f}" if entry.views_velocity_24h else "0"
        er = (
            f"{entry.engagement_rate * 100:.1f}%"
            if entry.engagement_rate is not None
            else "-"
        )
        last = entry.last_captured_at.strftime("%Y-%m-%d %H:%M")
        table.add_row(str(i), title, entry.platform.value, velocity, er, last)

    console.print(table)
```

Étape 3 — Mettre à jour `src/vidscope/cli/commands/__init__.py` pour exporter `trending_command`.

Étape 4 — Enregistrer dans `src/vidscope/cli/app.py` :
```python
# import
from vidscope.cli.commands import (..., trending_command)
# registration
app.command("trending", help="Rank ingested videos by views velocity.")(trending_command)
```

Étape 5 — Étendre `src/vidscope/mcp/server.py` pour enregistrer le tool `vidscope_trending`. Lire la fonction `build_mcp_server(container)` et ajouter :
```python
    @mcp.tool()
    def vidscope_trending(
        since: str,
        platform: str | None = None,
        min_velocity: float = 0.0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Rank ingested videos by views_velocity_24h. Mirrors `vidscope trending` CLI.

        Args:
            since: window string e.g. "7d" or "24h" (mandatory).
            platform: optional filter ("instagram", "tiktok", "youtube").
            min_velocity: minimum views/day to appear (default 0).
            limit: max results (default 20, must be >= 1).
        """
        # Inline window parser (avoid circular import of cli module)
        s = since.strip().lower()
        if len(s) < 2 or not s[:-1].isdigit():
            raise ValueError(f"invalid since window: {since!r} (expected N(h|d))")
        n = int(s[:-1])
        if n <= 0:
            raise ValueError(f"since must be positive: {since!r}")
        if s[-1] == "h":
            window = timedelta(hours=n)
        elif s[-1] == "d":
            window = timedelta(days=n)
        else:
            raise ValueError(f"invalid since unit: {s[-1]!r} (expected h or d)")

        plat: Platform | None = None
        if platform is not None:
            try:
                plat = Platform(platform.strip().lower())
            except ValueError as exc:
                raise ValueError(f"invalid platform: {platform!r}") from exc

        if limit < 1:
            raise ValueError("limit must be >= 1")

        uc = ListTrendingUseCase(
            unit_of_work_factory=container.unit_of_work,
            clock=container.clock,
        )
        try:
            results = uc.execute(since=window, platform=plat, min_velocity=min_velocity, limit=limit)
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

        return [
            {
                "video_id": e.video_id,
                "platform": e.platform.value,
                "title": e.title,
                "views_velocity_24h": e.views_velocity_24h,
                "engagement_rate": e.engagement_rate,
                "last_captured_at": e.last_captured_at.isoformat(),
                "latest_view_count": e.latest_view_count,
                "latest_like_count": e.latest_like_count,
            }
            for e in results
        ]
```

Ajouter les imports nécessaires en haut de `server.py` : `from datetime import timedelta`, `from vidscope.application.list_trending import ListTrendingUseCase`. Ajouter l'import de `Platform` s'il manque.

Étape 6 — Créer `tests/unit/cli/test_trending.py` :
```python
"""CLI tests for `vidscope trending`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

runner = CliRunner()


def _make_entries():
    from vidscope.application.list_trending import TrendingEntry
    from vidscope.domain import Platform
    return [
        TrendingEntry(
            video_id=1, platform=Platform.YOUTUBE, title="Alpha",
            views_velocity_24h=1200.0, engagement_rate=0.05,
            last_captured_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            latest_view_count=1000, latest_like_count=50,
        ),
        TrendingEntry(
            video_id=2, platform=Platform.TIKTOK, title="Beta",
            views_velocity_24h=500.0, engagement_rate=None,
            last_captured_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            latest_view_count=400, latest_like_count=None,
        ),
    ]


def _patch_container(monkeypatch, *, entries):
    import vidscope.cli.commands.trending as mod
    uc_mock = MagicMock()
    uc_mock.execute = MagicMock(return_value=entries)
    class _UC:
        def __init__(self, **kw): ...
        def execute(self, **kw): return entries
    monkeypatch.setattr(mod, "ListTrendingUseCase", _UC)
    monkeypatch.setattr(mod, "acquire_container", lambda: MagicMock(
        unit_of_work=MagicMock(),
        clock=MagicMock(now=lambda: datetime(2026, 1, 1, tzinfo=UTC)),
    ))


def test_trending_since_required(monkeypatch) -> None:
    """D-04: --since is mandatory, no silent default."""
    from vidscope.cli.app import app
    res = runner.invoke(app, ["trending"])
    assert res.exit_code != 0


def test_trending_happy_path(monkeypatch) -> None:
    _patch_container(monkeypatch, entries=_make_entries())
    from vidscope.cli.app import app
    res = runner.invoke(app, ["trending", "--since", "7d"])
    assert res.exit_code == 0, res.stdout
    assert "Alpha" in res.stdout
    assert "Beta" in res.stdout


def test_trending_limit_zero_rejected(monkeypatch) -> None:
    from vidscope.cli.app import app
    res = runner.invoke(app, ["trending", "--since", "7d", "--limit", "0"])
    assert res.exit_code != 0


def test_trending_invalid_since_format(monkeypatch) -> None:
    from vidscope.cli.app import app
    res = runner.invoke(app, ["trending", "--since", "1week"])
    assert res.exit_code != 0


def test_trending_invalid_platform(monkeypatch) -> None:
    from vidscope.cli.app import app
    res = runner.invoke(app, ["trending", "--since", "7d", "--platform", "myspace"])
    assert res.exit_code != 0


def test_trending_empty_results(monkeypatch) -> None:
    _patch_container(monkeypatch, entries=[])
    from vidscope.cli.app import app
    res = runner.invoke(app, ["trending", "--since", "7d"])
    assert res.exit_code == 0
    assert "No trending" in res.stdout or "no trending" in res.stdout.lower()


def test_trending_table_columns(monkeypatch) -> None:
    _patch_container(monkeypatch, entries=_make_entries())
    from vidscope.cli.app import app
    res = runner.invoke(app, ["trending", "--since", "7d"])
    assert res.exit_code == 0
    out = res.stdout.lower()
    # Table columns per D-04
    assert "title" in out
    assert "platform" in out
    assert "velocity" in out
    assert "engagement" in out


def test_trending_no_unicode_glyphs(monkeypatch) -> None:
    _patch_container(monkeypatch, entries=_make_entries())
    from vidscope.cli.app import app
    res = runner.invoke(app, ["trending", "--since", "7d"])
    for g in ["\u2713", "\u2717", "\u2192", "\u2190"]:
        assert g not in res.stdout
```

Étape 7 — Étendre `tests/unit/cli/test_app.py` :
```python
def test_app_help_lists_trending() -> None:
    from vidscope.cli.app import app
    from typer.testing import CliRunner
    res = CliRunner().invoke(app, ["--help"])
    assert "trending" in res.stdout.lower()
```

Étape 8 — Étendre `tests/unit/mcp/test_server.py` (ou créer `tests/unit/mcp/test_trending_tool.py`) :
```python
def test_vidscope_trending_tool_returns_list() -> None:
    from datetime import UTC, datetime
    from unittest.mock import MagicMock
    from vidscope.application.list_trending import TrendingEntry
    from vidscope.domain import Platform
    from vidscope.mcp.server import build_mcp_server

    entry = TrendingEntry(
        video_id=7, platform=Platform.YOUTUBE, title="Alpha",
        views_velocity_24h=1500.0, engagement_rate=0.08,
        last_captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        latest_view_count=2000, latest_like_count=100,
    )

    container = MagicMock()
    container.unit_of_work = MagicMock()
    container.clock = MagicMock(now=lambda: datetime(2026, 1, 10, tzinfo=UTC))

    # Monkey-patch ListTrendingUseCase at server module scope
    import vidscope.mcp.server as srv
    import vidscope.application.list_trending as lt_mod

    class _UC:
        def __init__(self, **kw): ...
        def execute(self, **kw): return [entry]

    from pytest import MonkeyPatch
    mp = MonkeyPatch()
    try:
        mp.setattr(srv, "ListTrendingUseCase", _UC)
        server = build_mcp_server(container)
        # Navigate FastMCP internals to invoke the tool handler directly.
        # The pattern from test_server.py should be reused here.
        tool = server._tool_manager._tools.get("vidscope_trending")
        assert tool is not None
        result = tool.fn(since="7d", limit=10)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["video_id"] == 7
        assert result[0]["platform"] == "youtube"
        assert result[0]["views_velocity_24h"] == 1500.0
        # timestamps MUST be JSON-serializable
        import json
        json.dumps(result)
    finally:
        mp.undo()


def test_vidscope_trending_tool_rejects_invalid_since() -> None:
    from unittest.mock import MagicMock
    from vidscope.mcp.server import build_mcp_server
    container = MagicMock()
    container.unit_of_work = MagicMock()
    container.clock = MagicMock()
    server = build_mcp_server(container)
    tool = server._tool_manager._tools.get("vidscope_trending")
    assert tool is not None
    import pytest
    with pytest.raises(ValueError):
        tool.fn(since="1week")
```

**Adaptation** : la navigation exacte dans `FastMCP._tool_manager._tools` dépend de la version MCP. Vérifier le pattern utilisé dans `test_server.py` existant et l'adapter. Si la structure diffère, utiliser `server.list_tools()` ou l'API documentée.

Étape 9 — Exécuter :
```
uv run pytest tests/unit/cli/test_trending.py tests/unit/cli/test_app.py tests/unit/mcp/ -x -q
uv run vidscope trending --help
uv run lint-imports
```

NE PAS utiliser de glyphes Unicode en stdout. NE PAS importer `vidscope.infrastructure` depuis le MCP tool au-delà de `container` déjà injecté.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/cli/test_trending.py tests/unit/mcp/ -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "def trending_command" src/vidscope/cli/commands/trending.py` matches
    - `grep -n "min=1" src/vidscope/cli/commands/trending.py` matches (T-INPUT-01)
    - `grep -nE "Option\\(\"--since\"" src/vidscope/cli/commands/trending.py` matches (pas de défaut sur `--since`)
    - `grep -n "trending_command" src/vidscope/cli/app.py` matches
    - `grep -n "vidscope_trending" src/vidscope/mcp/server.py` matches
    - `grep -nE "(\\\\u2713|\\\\u2717|\\\\u2192)" src/vidscope/cli/commands/trending.py` returns exit 1
    - `uv run pytest tests/unit/cli/test_trending.py -x -q` exits 0
    - `uv run pytest tests/unit/mcp/ -x -q` exits 0
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - `vidscope trending --since <window>` fonctionnel avec tous les filtres D-04
    - MCP tool `vidscope_trending` enregistré et testé
    - 7+ tests CLI + 2 tests MCP verts
    - ASCII-only stdout
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Extension D-05 — `vidscope show <id>` section stats + tests</name>
  <files>src/vidscope/application/show_video.py, src/vidscope/cli/commands/show.py, tests/unit/application/test_show_video.py, tests/unit/cli/test_show_cmd.py</files>
  <read_first>
    - src/vidscope/application/show_video.py (ShowVideoResult + ShowVideoUseCase existants)
    - src/vidscope/cli/commands/show.py (rendu CLI existant)
    - src/vidscope/domain/metrics.py (livré S01)
    - src/vidscope/ports/repositories.py (VideoStatsRepository livré S01 + rank_candidates_by_delta livré Task 1)
    - tests/unit/application/test_show_video.py (pattern tests existants)
    - tests/unit/cli/test_show_cmd.py si existant, sinon chercher le test show
    - .gsd/milestones/M009/M009-CONTEXT.md (D-05 spec complète)
  </read_first>
  <behavior>
    - Test 1 : `ShowVideoResult` a deux nouveaux champs : `latest_stats: VideoStats | None` et `views_velocity_24h: float | None`.
    - Test 2 : `ShowVideoUseCase.execute(video_id)` peuple `latest_stats` depuis `uow.video_stats.latest_for_video(id)`.
    - Test 3 : `views_velocity_24h` est calculée via `metrics.views_velocity_24h` sur l'historique complet si ≥ 2 rows, sinon None.
    - Test 4 : Quand aucune row dans `video_stats`, les deux champs restent None.
    - Test 5 CLI : `vidscope show 42` affiche une section "Stats" avec la dernière capture + velocity.
    - Test 6 CLI : Quand 0 rows stats, affiche le message actionnable : `Aucune stat capturée — lancez: vidscope refresh-stats 42`.
    - Test 7 : Les tests existants de `ShowVideoUseCase` passent toujours (rétro-compatible par défauts None).
  </behavior>
  <action>
Étape 1 — Étendre `src/vidscope/application/show_video.py` : ajouter deux champs au `ShowVideoResult` dataclass :
```python
    # D-05: Last captured stats snapshot + computed velocity over full history.
    latest_stats: "VideoStats | None" = None
    views_velocity_24h: float | None = None
```
Ajouter `VideoStats` dans les imports : `from vidscope.domain import (..., VideoStats)`. Ajouter `from vidscope.domain.metrics import views_velocity_24h as _compute_velocity` (renommage pour éviter conflit avec le champ).

Modifier `ShowVideoUseCase.execute` pour charger les stats :
```python
def execute(self, video_id: int) -> ShowVideoResult:
    with self._uow_factory() as uow:
        video = uow.videos.get(VideoId(video_id))
        if video is None:
            return ShowVideoResult(found=False)
        # ... existing loads ...

        # D-05: latest stats + full-history velocity
        latest_stats = uow.video_stats.latest_for_video(vid_id)
        history = uow.video_stats.list_for_video(vid_id, limit=1000)
        velocity = _compute_velocity(history) if len(history) >= 2 else None

    return ShowVideoResult(
        found=True,
        video=video,
        transcript=transcript,
        frames=frames,
        analysis=analysis,
        creator=creator,
        hashtags=hashtags,
        mentions=mentions,
        links=links,
        frame_texts=frame_texts,
        thumbnail_key=video.thumbnail_key,
        content_shape=video.content_shape,
        latest_stats=latest_stats,
        views_velocity_24h=velocity,
    )
```

Étape 2 — Étendre `src/vidscope/cli/commands/show.py` avec une section "Stats" APRÈS l'affichage actuel (lire le fichier existant pour trouver le point d'insertion idéal, probablement après la section analysis ou frames).
```python
def _render_stats(result: ShowVideoResult) -> None:
    """D-05: display latest stats snapshot + computed velocity.

    If no stats row exists, print an actionable message pointing at
    `vidscope refresh-stats <id>`.
    """
    video_id = result.video.id if result.video is not None else None
    if result.latest_stats is None:
        console.print(
            "[dim]Stats:[/dim] "
            f"Aucune stat capturée — lancez: vidscope refresh-stats {video_id}"
        )
        return

    s = result.latest_stats
    parts = [
        f"captured_at={s.captured_at.strftime('%Y-%m-%d %H:%M')}",
        f"views={s.view_count if s.view_count is not None else '-'}",
        f"likes={s.like_count if s.like_count is not None else '-'}",
        f"reposts={s.repost_count if s.repost_count is not None else '-'}",
        f"comments={s.comment_count if s.comment_count is not None else '-'}",
        f"saves={s.save_count if s.save_count is not None else '-'}",
    ]
    console.print(f"[bold]Stats[/bold]: " + "  ".join(parts))

    if result.views_velocity_24h is not None:
        console.print(
            f"  velocity_24h: {result.views_velocity_24h:.1f} views/day"
        )
    else:
        console.print(
            "  velocity_24h: n/a (need >= 2 snapshots — "
            f"run vidscope refresh-stats {video_id} again)"
        )
```
Appeler `_render_stats(result)` à la fin de la fonction `show_command`.

Étape 3 — Étendre `tests/unit/application/test_show_video.py` :
```python
def test_show_video_includes_latest_stats_when_present() -> None:
    from datetime import UTC, datetime
    from unittest.mock import MagicMock
    from vidscope.application.show_video import ShowVideoUseCase
    from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats

    video = Video(id=VideoId(1), platform=Platform.YOUTUBE, platform_id=PlatformId("p1"), url="https://x.y/1")
    latest = VideoStats(
        video_id=VideoId(1),
        captured_at=datetime(2026, 1, 5, tzinfo=UTC),
        view_count=1000, like_count=50,
    )
    history = [
        VideoStats(video_id=VideoId(1), captured_at=datetime(2026, 1, 1, tzinfo=UTC), view_count=100),
        latest,
    ]

    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.videos.get = MagicMock(return_value=video)
    fake_uow.transcripts.get_for_video = MagicMock(return_value=None)
    fake_uow.frames.list_for_video = MagicMock(return_value=[])
    fake_uow.analyses.get_latest_for_video = MagicMock(return_value=None)
    fake_uow.creators.get = MagicMock(return_value=None)
    fake_uow.hashtags.list_for_video = MagicMock(return_value=[])
    fake_uow.mentions.list_for_video = MagicMock(return_value=[])
    fake_uow.links.list_for_video = MagicMock(return_value=[])
    fake_uow.frame_texts.list_for_video = MagicMock(return_value=[])
    fake_uow.video_stats.latest_for_video = MagicMock(return_value=latest)
    fake_uow.video_stats.list_for_video = MagicMock(return_value=history)

    uc = ShowVideoUseCase(unit_of_work_factory=lambda: fake_uow)
    result = uc.execute(1)
    assert result.found is True
    assert result.latest_stats is not None
    assert result.latest_stats.view_count == 1000
    assert result.views_velocity_24h is not None
    assert result.views_velocity_24h > 0


def test_show_video_no_stats_rows() -> None:
    from unittest.mock import MagicMock
    from vidscope.application.show_video import ShowVideoUseCase
    from vidscope.domain import Platform, PlatformId, Video, VideoId

    video = Video(id=VideoId(1), platform=Platform.YOUTUBE, platform_id=PlatformId("p1"), url="https://x.y/1")

    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.videos.get = MagicMock(return_value=video)
    fake_uow.transcripts.get_for_video = MagicMock(return_value=None)
    fake_uow.frames.list_for_video = MagicMock(return_value=[])
    fake_uow.analyses.get_latest_for_video = MagicMock(return_value=None)
    fake_uow.creators.get = MagicMock(return_value=None)
    fake_uow.hashtags.list_for_video = MagicMock(return_value=[])
    fake_uow.mentions.list_for_video = MagicMock(return_value=[])
    fake_uow.links.list_for_video = MagicMock(return_value=[])
    fake_uow.frame_texts.list_for_video = MagicMock(return_value=[])
    fake_uow.video_stats.latest_for_video = MagicMock(return_value=None)
    fake_uow.video_stats.list_for_video = MagicMock(return_value=[])

    uc = ShowVideoUseCase(unit_of_work_factory=lambda: fake_uow)
    result = uc.execute(1)
    assert result.found is True
    assert result.latest_stats is None
    assert result.views_velocity_24h is None


def test_show_video_single_snapshot_velocity_is_none() -> None:
    from datetime import UTC, datetime
    from unittest.mock import MagicMock
    from vidscope.application.show_video import ShowVideoUseCase
    from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats

    video = Video(id=VideoId(1), platform=Platform.YOUTUBE, platform_id=PlatformId("p1"), url="https://x.y/1")
    only = VideoStats(video_id=VideoId(1), captured_at=datetime(2026, 1, 1, tzinfo=UTC), view_count=100)

    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.videos.get = MagicMock(return_value=video)
    for name in ("transcripts.get_for_video", "analyses.get_latest_for_video", "creators.get"):
        obj, meth = name.split(".")
        setattr(getattr(fake_uow, obj), meth, MagicMock(return_value=None))
    for name in ("frames.list_for_video", "hashtags.list_for_video", "mentions.list_for_video",
                 "links.list_for_video", "frame_texts.list_for_video"):
        obj, meth = name.split(".")
        setattr(getattr(fake_uow, obj), meth, MagicMock(return_value=[]))
    fake_uow.video_stats.latest_for_video = MagicMock(return_value=only)
    fake_uow.video_stats.list_for_video = MagicMock(return_value=[only])

    uc = ShowVideoUseCase(unit_of_work_factory=lambda: fake_uow)
    result = uc.execute(1)
    assert result.latest_stats == only
    assert result.views_velocity_24h is None  # < 2 snapshots
```

Étape 4 — Étendre `tests/unit/cli/test_show_cmd.py` (ou créer si absent) avec :
```python
def test_show_stats_section_when_present(monkeypatch) -> None:
    """D-05: show CLI prints a Stats section when latest_stats is not None."""
    from datetime import UTC, datetime
    from unittest.mock import MagicMock
    from typer.testing import CliRunner

    from vidscope.application.show_video import ShowVideoResult
    from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats

    video = Video(id=VideoId(1), platform=Platform.YOUTUBE, platform_id=PlatformId("p1"), url="https://x.y/1", title="T")
    latest = VideoStats(video_id=VideoId(1), captured_at=datetime(2026, 1, 5, tzinfo=UTC), view_count=1000, like_count=50)
    result = ShowVideoResult(
        found=True, video=video, latest_stats=latest, views_velocity_24h=450.0,
    )

    import vidscope.cli.commands.show as show_mod
    class _UC:
        def __init__(self, **kw): ...
        def execute(self, video_id): return result
    monkeypatch.setattr(show_mod, "ShowVideoUseCase", _UC)
    monkeypatch.setattr(show_mod, "acquire_container", lambda: MagicMock(unit_of_work=MagicMock()))

    from vidscope.cli.app import app
    res = CliRunner().invoke(app, ["show", "1"])
    assert res.exit_code == 0, res.stdout
    assert "Stats" in res.stdout
    assert "views=1000" in res.stdout or "1000" in res.stdout
    assert "velocity_24h" in res.stdout.lower() or "450" in res.stdout


def test_show_stats_actionable_message_when_no_rows(monkeypatch) -> None:
    from unittest.mock import MagicMock
    from typer.testing import CliRunner
    from vidscope.application.show_video import ShowVideoResult
    from vidscope.domain import Platform, PlatformId, Video, VideoId

    video = Video(id=VideoId(42), platform=Platform.YOUTUBE, platform_id=PlatformId("p42"), url="https://x.y/42", title="T")
    result = ShowVideoResult(found=True, video=video, latest_stats=None, views_velocity_24h=None)

    import vidscope.cli.commands.show as show_mod
    class _UC:
        def __init__(self, **kw): ...
        def execute(self, video_id): return result
    monkeypatch.setattr(show_mod, "ShowVideoUseCase", _UC)
    monkeypatch.setattr(show_mod, "acquire_container", lambda: MagicMock(unit_of_work=MagicMock()))

    from vidscope.cli.app import app
    res = CliRunner().invoke(app, ["show", "42"])
    assert res.exit_code == 0
    assert "refresh-stats 42" in res.stdout
```

Étape 5 — Vérifier que les tests existants de `test_show_video.py` et `test_show_cmd.py` passent toujours (les deux nouveaux champs ont des defaults None, rétro-compatible).

Étape 6 — Exécuter la suite complète :
```
uv run pytest tests/unit/ -x -q
uv run lint-imports
```

**CRUCIAL** : les tests M008 de `ShowVideoUseCase` (frame_texts, thumbnail_key, content_shape) doivent rester verts. La signature de `execute` reste inchangée — seul le résultat gagne deux champs optionnels.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/application/test_show_video.py tests/unit/cli/test_show_cmd.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "latest_stats" src/vidscope/application/show_video.py` matches
    - `grep -n "views_velocity_24h" src/vidscope/application/show_video.py` matches
    - `grep -n "from vidscope.domain.metrics" src/vidscope/application/show_video.py` matches
    - `grep -n "latest_for_video" src/vidscope/application/show_video.py` matches
    - `grep -n "refresh-stats" src/vidscope/cli/commands/show.py` matches (message actionnable)
    - `grep -n "Stats" src/vidscope/cli/commands/show.py` matches (label de section)
    - `uv run pytest tests/unit/application/test_show_video.py -x -q` exits 0 (tests existants + 3 nouveaux)
    - `uv run pytest tests/unit/cli/ -x -q` exits 0 (tests existants + 2 nouveaux)
    - `uv run pytest tests/unit/ -x -q` exits 0 (suite complète M009)
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - ShowVideoResult étendu avec latest_stats + views_velocity_24h (rétro-compatible)
    - ShowVideoUseCase charge les stats + calcule la vélocité
    - CLI affiche une section Stats ou un message actionnable
    - Tests : 3 application + 2 CLI nouveaux verts, tous les tests existants toujours verts
    - Suite complète M009 verte
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI `vidscope trending` → ListTrendingUseCase | user inputs : `--since`, `--platform`, `--min-velocity`, `--limit` |
| MCP tool `vidscope_trending` → ListTrendingUseCase | agent inputs via JSON-RPC : `since`, `platform`, `limit` |
| ListTrendingUseCase → video_stats (SQL query) | paramètres convertis et passés en SQLAlchemy Core paramétré |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INPUT-01 | DoS | CLI `--limit` | mitigate | Typer `Option("--limit", min=1, ...)` + validation backend `if limit < 1: raise ValueError` dans `ListTrendingUseCase.execute`. Idem dans MCP tool. |
| T-INPUT-02 | Input Validation | CLI `--since` | mitigate | `_parse_window` strict `N(h|d)` — refuse `1week`, `7`, `-5d`. `typer.BadParameter` exit 2. |
| T-INPUT-03 | Input Validation | CLI `--platform` | mitigate | `_parse_platform` délégué à l'enum `Platform(value)` — ValueError trap en `typer.BadParameter`. MCP tool fait la même validation. |
| T-SQL-01 | Tampering | `rank_candidates_by_delta` | mitigate | SQLAlchemy Core paramétré : `select(...)`, `.where(col == value)`, `.limit(int)`. JAMAIS de `text(f"...{user_input}...")`. `platform.value` passe par `.where(videos.c.platform == platform.value)` — bind param. `int(video_id)` cast explicite. |
| T-DATA-01 | Tampering (hérité S01) | yt-dlp → video_stats | mitigate | Hérité S01, non répété. |
| T-MCP-01 | Input Validation | MCP tool bounds | mitigate | Validation `since`/`platform`/`limit` IDENTIQUES au CLI (strict format, bounds). Les erreurs remontent en `ValueError` que FastMCP rend en tool error côté client. |
</threat_model>

<verification>
Après les 3 tâches :
- `uv run pytest tests/unit/ -x -q` vert (suite complète M009)
- `uv run lint-imports` vert (9 contrats)
- `uv run vidscope trending --since 7d` affiche une Table ou "No trending videos" selon la DB
- `uv run vidscope trending` (sans --since) exit 2 avec message clair
- `uv run vidscope show 1` affiche la section Stats (ou le message actionnable)
- Les tests MCP `test_server.py` + `test_trending_tool` (si créé) passent
- Aucun glyphe unicode dans `trending.py`, `show.py`
- `grep -c "ListTrendingUseCase" src/vidscope/mcp/server.py` >= 2 (import + usage)
</verification>

<success_criteria>
S04 est complet quand :
- [ ] `ListTrendingUseCase` + `TrendingEntry` livrés (requirements R052)
- [ ] `VideoStatsRepository.rank_candidates_by_delta` ajouté (LIMIT SQL en base, D-04)
- [ ] `vidscope trending --since <window>` fonctionnel avec tous les filtres
- [ ] `--since` obligatoire (D-04), `--limit min=1` (T-INPUT-01)
- [ ] MCP tool `vidscope_trending` enregistré et testé
- [ ] `vidscope show <id>` affiche section Stats avec dernière capture + vélocité (D-05)
- [ ] `vidscope show <id>` affiche le message actionnable si 0 rows (D-05)
- [ ] ASCII-only stdout (pas de glyphe unicode)
- [ ] Suite tests unit verte (application + CLI + MCP, tests existants préservés)
- [ ] `lint-imports` vert — `application-has-no-adapters`, `mcp-has-no-adapters`, etc.
- [ ] Toutes les requirements M009 (R050, R051, R052) sont couvertes par les 4 plans
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M009/M009-S04-SUMMARY.md` documentant :
- Formule exacte retenue pour `views_velocity_24h` (delta / elapsed * 86400)
- Formule `engagement_rate` ((like + comment) / view_count)
- Omission explicite de `viral_coefficient` (justifié par Claude's Discretion)
- Structure finale de `TrendingEntry`
- Format complet de la Table `vidscope trending`
- Format de la section Stats de `vidscope show`
- Signature de `vidscope_trending` MCP tool
- Liste des fichiers créés/modifiés

**Et créer un M009-SUMMARY.md cumulatif** regroupant les 4 slices pour le gate `/gsd-verify-work`.
</output>
