---
plan_id: S03-P01
phase: M006/S03
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/vidscope/ports/repositories.py
  - src/vidscope/adapters/sqlite/video_repository.py
  - src/vidscope/application/get_creator.py
  - src/vidscope/application/list_creators.py
  - src/vidscope/application/list_creator_videos.py
  - src/vidscope/application/__init__.py
  - tests/unit/application/test_get_creator.py
  - tests/unit/application/test_list_creators.py
  - tests/unit/application/test_list_creator_videos.py
autonomous: true
requirements: [R041]
must_haves:
  truths:
    - "GetCreatorUseCase trouve un créateur par handle (plateforme + handle) et retourne None quand absent"
    - "ListCreatorsUseCase liste avec filtres optionnels platform et min_followers"
    - "ListCreatorVideosUseCase liste les vidéos d'un créateur identifié par handle"
    - "VideoRepository.list_by_creator existe dans le Protocol et l'adapter SQLite"
    - "Les 3 use cases sont exportés dans vidscope.application.__all__"
  artifacts:
    - path: "src/vidscope/application/get_creator.py"
      provides: "GetCreatorUseCase + GetCreatorResult"
      contains: "class GetCreatorUseCase"
    - path: "src/vidscope/application/list_creators.py"
      provides: "ListCreatorsUseCase + ListCreatorsResult"
      contains: "class ListCreatorsUseCase"
    - path: "src/vidscope/application/list_creator_videos.py"
      provides: "ListCreatorVideosUseCase + ListCreatorVideosResult"
      contains: "class ListCreatorVideosUseCase"
    - path: "src/vidscope/ports/repositories.py"
      provides: "VideoRepository.list_by_creator méthode"
      contains: "def list_by_creator"
  key_links:
    - from: "src/vidscope/application/get_creator.py"
      to: "CreatorRepository.find_by_handle"
      via: "uow.creators.find_by_handle(platform, handle)"
      pattern: "find_by_handle"
    - from: "src/vidscope/application/list_creator_videos.py"
      to: "VideoRepository.list_by_creator"
      via: "uow.videos.list_by_creator(creator_id, limit=limit)"
      pattern: "list_by_creator"
---

<objective>
Livrer les 3 use cases de la couche application pour M006/S03, plus l'extension `list_by_creator` au protocole `VideoRepository`.

**Ce plan livre uniquement la couche application.** S03-P02 (CLI) et S03-P03 (MCP) consomment ces use cases en Wave 2.

Périmètre exact :
1. `GetCreatorUseCase` — trouve un créateur par `(platform, handle)`, retourne `GetCreatorResult(found, creator)`
2. `ListCreatorsUseCase` — liste avec filtres optionnels `platform: Platform | None` et `min_followers: int | None`, retourne `ListCreatorsResult(creators, total)`
3. `ListCreatorVideosUseCase` — résout le handle → créateur, puis liste ses vidéos via `VideoRepository.list_by_creator`, retourne `ListCreatorVideosResult(found, creator, videos, total)`
4. Étendre `VideoRepository` Protocol + `VideoRepositorySQLite` avec `list_by_creator(creator_id: CreatorId, *, limit: int = 50) -> list[Video]`
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/STATE.md
@.gsd/REQUIREMENTS.md
@.gsd/milestones/M006/M006-ROADMAP.md
@.gsd/milestones/M006/slices/S02/S02-P03-SUMMARY.md
@src/vidscope/ports/repositories.py
@src/vidscope/adapters/sqlite/video_repository.py
@src/vidscope/adapters/sqlite/creator_repository.py
@src/vidscope/application/list_videos.py
@src/vidscope/application/show_video.py
@src/vidscope/application/get_status.py
@src/vidscope/application/__init__.py
@tests/unit/application/conftest.py
@.importlinter

<interfaces>
<!-- Contrats existants à préserver -->

VideoRepository Protocol (src/vidscope/ports/repositories.py) — méthodes existantes à NE PAS modifier :
- add(video) -> Video
- upsert_by_platform_id(video, creator=None) -> Video
- get(video_id) -> Video | None
- get_by_platform_id(platform, platform_id) -> Video | None
- list_recent(limit=20) -> list[Video]
- count() -> int

CreatorRepository Protocol (src/vidscope/ports/repositories.py) — méthodes clés déjà livrées par S01 :
- find_by_handle(platform: Platform, handle: str) -> Creator | None
- list_by_platform(platform: Platform, *, limit: int = 50) -> list[Creator]
- list_by_min_followers(min_count: int, *, limit: int = 50) -> list[Creator]
- count() -> int

Domain Creator dataclass champs pertinents (src/vidscope/domain/entities.py) :
- platform: Platform
- platform_user_id: PlatformUserId
- id: CreatorId | None
- handle: str | None
- display_name: str | None
- follower_count: int | None
- is_verified: bool | None

Pattern use case standard du projet (tous les fichiers application/*.py) :
```python
@dataclass(frozen=True, slots=True)
class XxxResult:
    ...

class XxxUseCase:
    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, ...) -> XxxResult:
        with self._uow_factory() as uow:
            ...
        return XxxResult(...)
```

Pattern test application (tests/unit/application/conftest.py) :
- fixture `uow_factory` : UnitOfWorkFactory réelle sur SQLite tmp
- Pas de mocks — tests sur vraie DB SQLite en mémoire
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
<name>Task 1: Étendre VideoRepository Protocol + VideoRepositorySQLite avec list_by_creator</name>

<read_first>
- `src/vidscope/ports/repositories.py` lignes 61-118 (VideoRepository Protocol complet) — ajouter `list_by_creator` après `list_recent`
- `src/vidscope/adapters/sqlite/video_repository.py` lignes 124-140 (`list_recent` + `count`) — pattern à dupliquer pour `list_by_creator`
- `src/vidscope/adapters/sqlite/schema.py` — vérifier que `videos_table.c.creator_id` existe (ajouté S01)
- `src/vidscope/domain/values.py` — `CreatorId` est un `NewType(int)` — `int(creator_id)` pour la comparaison SQL
</read_first>

<action>
**Fichier 1 : `src/vidscope/ports/repositories.py`**

Après la méthode `list_recent` (ligne ~114) et avant `count()`, insérer dans `VideoRepository` Protocol :

```python
    def list_by_creator(
        self, creator_id: CreatorId, *, limit: int = 50
    ) -> list[Video]:
        """Return up to ``limit`` videos whose ``creator_id`` FK matches
        ``creator_id``, ordered most recently ingested first.

        Returns an empty list when no videos are linked to this creator.
        Callers should resolve the creator by handle first via
        :meth:`CreatorRepository.find_by_handle`.
        """
        ...
```

Aussi ajouter `CreatorId` aux imports si pas déjà présent (il l'est déjà ligne ~34 — vérifier).

**Fichier 2 : `src/vidscope/adapters/sqlite/video_repository.py`**

Après la méthode `list_recent` (ligne ~134), ajouter :

```python
    def list_by_creator(
        self, creator_id: CreatorId, *, limit: int = 50
    ) -> list[Video]:
        """Return up to ``limit`` videos for ``creator_id``, newest first."""
        rows = (
            self._conn.execute(
                select(videos_table)
                .where(videos_table.c.creator_id == int(creator_id))
                .order_by(videos_table.c.created_at.desc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [_row_to_video(row) for row in rows]
```

Aussi s'assurer que `CreatorId` est importé dans le fichier. L'import existant est :
```python
from vidscope.domain import Creator, Platform, PlatformId, Video, VideoId
```
Ajouter `CreatorId` :
```python
from vidscope.domain import Creator, CreatorId, Platform, PlatformId, Video, VideoId
```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/adapters/sqlite/test_video_repository.py -x -q</automated>
</verify>

<acceptance_criteria>
- `grep -q "def list_by_creator" src/vidscope/ports/repositories.py` exit 0
- `grep -q "def list_by_creator" src/vidscope/adapters/sqlite/video_repository.py` exit 0
- `grep -q "creator_id == int(creator_id)" src/vidscope/adapters/sqlite/video_repository.py` exit 0
- `grep -q "CreatorId" src/vidscope/adapters/sqlite/video_repository.py` exit 0
- `python -m uv run pytest tests/unit/adapters/sqlite/test_video_repository.py -x -q` exit 0 (tests existants ne régressent pas)
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0
</acceptance_criteria>

<done>
`VideoRepository.list_by_creator` disponible dans le Protocol et l'adapter SQLite. Tests adapter verts. mypy + import-linter verts.
</done>
</task>

<task type="auto" tdd="true">
<name>Task 2: GetCreatorUseCase — trouver un créateur par handle</name>

<read_first>
- `src/vidscope/application/show_video.py` — pattern ShowVideoUseCase à miroir pour GetCreatorUseCase
- `src/vidscope/ports/repositories.py` lignes 334-344 — `CreatorRepository.find_by_handle(platform, handle)` signature
- `src/vidscope/domain/entities.py` lignes 214-247 — Creator dataclass champs
- `src/vidscope/domain/values.py` — `Platform` enum (YOUTUBE, TIKTOK, INSTAGRAM)
- `tests/unit/application/conftest.py` — fixtures `uow_factory` + pattern test
- `tests/unit/adapters/sqlite/test_creator_repository.py` — voir comment on crée des Creator dans les tests (via `uow.creators.upsert`)
</read_first>

<action>
**Fichier 1 : `src/vidscope/application/get_creator.py`** (nouveau fichier) :

```python
"""Return the full record of one creator — powers ``vidscope creator show``.

The use case resolves a creator by ``(platform, handle)``. It does NOT
raise on miss — callers check ``result.found`` and display an error.
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Creator, Platform
from vidscope.ports import UnitOfWorkFactory

__all__ = ["GetCreatorResult", "GetCreatorUseCase"]


@dataclass(frozen=True, slots=True)
class GetCreatorResult:
    """Result of :meth:`GetCreatorUseCase.execute`.

    ``found`` is ``False`` when no creator matches ``(platform, handle)``.
    ``creator`` is ``None`` iff ``found`` is ``False``.
    """

    found: bool
    creator: Creator | None = None


class GetCreatorUseCase:
    """Return the full domain record for a creator identified by handle."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, platform: Platform, handle: str) -> GetCreatorResult:
        """Fetch the creator matching ``(platform, handle)``.

        ``handle`` is the human-facing @-name. Since handles are
        platform-enforced unique at any point in time, this lookup is
        unambiguous. Returns ``found=False`` — never raises — when no
        creator matches.
        """
        with self._uow_factory() as uow:
            creator = uow.creators.find_by_handle(platform, handle)

        if creator is None:
            return GetCreatorResult(found=False)
        return GetCreatorResult(found=True, creator=creator)
```

**Fichier 2 : `tests/unit/application/test_get_creator.py`** (nouveau fichier) :

```python
"""Tests for GetCreatorUseCase (M006/S03-P01)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vidscope.application.get_creator import GetCreatorResult, GetCreatorUseCase
from vidscope.domain import Creator, Platform
from vidscope.domain.values import PlatformUserId
from vidscope.ports import UnitOfWorkFactory


def _make_creator(
    handle: str = "@alice",
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str = "UC_abc",
) -> Creator:
    return Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id),
        handle=handle,
        display_name="Alice",
        follower_count=1000,
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestGetCreatorUseCaseFound:
    def test_returns_found_true_when_creator_exists(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        creator = _make_creator()
        with uow_factory() as uow:
            uow.creators.upsert(creator)

        uc = GetCreatorUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@alice")

        assert result.found is True
        assert result.creator is not None
        assert result.creator.handle == "@alice"
        assert result.creator.display_name == "Alice"

    def test_returns_creator_with_follower_count(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        creator = _make_creator(handle="@bob", platform_user_id="UC_bob")
        creator = Creator(**{**creator.__dict__, "follower_count": 42000})
        with uow_factory() as uow:
            uow.creators.upsert(creator)

        uc = GetCreatorUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@bob")

        assert result.found is True
        assert result.creator is not None
        assert result.creator.follower_count == 42000

    def test_result_is_frozen(self, uow_factory: UnitOfWorkFactory) -> None:
        result = GetCreatorResult(found=False)
        with pytest.raises(Exception):  # frozen=True raises FrozenInstanceError
            object.__setattr__(result, "found", True)


class TestGetCreatorUseCaseNotFound:
    def test_returns_found_false_when_no_creator(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = GetCreatorUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@nobody")

        assert result.found is False
        assert result.creator is None

    def test_returns_found_false_for_wrong_platform(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        creator = _make_creator(handle="@charlie", platform=Platform.YOUTUBE)
        with uow_factory() as uow:
            uow.creators.upsert(creator)

        uc = GetCreatorUseCase(unit_of_work_factory=uow_factory)
        # Same handle but on TikTok — different creator
        result = uc.execute(Platform.TIKTOK, "@charlie")
        assert result.found is False

    def test_not_found_does_not_raise(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = GetCreatorUseCase(unit_of_work_factory=uow_factory)
        # Must return, not raise
        result = uc.execute(Platform.YOUTUBE, "@ghost")
        assert not result.found
```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/application/test_get_creator.py -x -q</automated>
</verify>

<acceptance_criteria>
- `test -f src/vidscope/application/get_creator.py` exit 0
- `test -f tests/unit/application/test_get_creator.py` exit 0
- `grep -q "class GetCreatorUseCase" src/vidscope/application/get_creator.py` exit 0
- `grep -q "class GetCreatorResult" src/vidscope/application/get_creator.py` exit 0
- `grep -q "find_by_handle" src/vidscope/application/get_creator.py` exit 0
- `python -m uv run pytest tests/unit/application/test_get_creator.py -x -q` exit 0
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0 (cli/mcp ne sont pas importés ici — `get_creator.py` importe uniquement domain + ports)
</acceptance_criteria>

<done>
`GetCreatorUseCase` livré avec tests. find_by_handle délégué à CreatorRepository via UoW. Suite verte.
</done>
</task>

<task type="auto" tdd="true">
<name>Task 3: ListCreatorsUseCase — lister avec filtres platform et min_followers</name>

<read_first>
- `src/vidscope/application/list_videos.py` — pattern ListVideosUseCase à miroir
- `src/vidscope/ports/repositories.py` lignes 346-363 (CreatorRepository.list_by_platform, list_by_min_followers, count)
- `src/vidscope/domain/values.py` — `Platform` enum
- `tests/unit/application/conftest.py` — fixture `uow_factory`
</read_first>

<action>
**Fichier 1 : `src/vidscope/application/list_creators.py`** (nouveau fichier) :

```python
"""List creators with optional filters — powers ``vidscope creator list``.

Supports three query modes:
- No filter: returns all creators ordered by last_seen_at desc (via platform scan on all platforms)
- ``platform`` only: returns creators on that platform
- ``min_followers`` only: returns creators with follower_count >= min_followers
- Both: platform filter applied first, then min_followers applied client-side
  (the adapter only exposes list_by_platform and list_by_min_followers separately;
  the use case combines for the dual-filter case)

``limit`` is capped at 200 to prevent unbounded result sets.
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Creator, Platform
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ListCreatorsResult", "ListCreatorsUseCase"]


@dataclass(frozen=True, slots=True)
class ListCreatorsResult:
    """Result of :meth:`ListCreatorsUseCase.execute`.

    ``creators`` is the filtered, limited list. ``total`` is the
    unfiltered count so the CLI can show "showing N of M".
    """

    creators: tuple[Creator, ...]
    total: int


class ListCreatorsUseCase:
    """Return creators matching optional ``platform`` and ``min_followers`` filters."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        *,
        platform: Platform | None = None,
        min_followers: int | None = None,
        limit: int = 20,
    ) -> ListCreatorsResult:
        """Return creators matching the given filters.

        ``limit`` is clamped to [1, 200]. When both ``platform`` and
        ``min_followers`` are provided, ``list_by_platform`` is called
        first with a generous internal limit (200) and the
        ``min_followers`` threshold is applied in Python — this avoids
        adding a compound query to the adapter while keeping the
        user-visible ``limit`` respected.
        """
        limit = max(1, min(limit, 200))

        with self._uow_factory() as uow:
            total = uow.creators.count()

            if platform is not None and min_followers is not None:
                # Dual filter: fetch more than needed from DB, filter in Python
                candidates = uow.creators.list_by_platform(platform, limit=200)
                creators = [
                    c for c in candidates
                    if c.follower_count is not None and c.follower_count >= min_followers
                ][:limit]
            elif platform is not None:
                creators = uow.creators.list_by_platform(platform, limit=limit)
            elif min_followers is not None:
                creators = uow.creators.list_by_min_followers(min_followers, limit=limit)
            else:
                # No filter — return most recently seen across all platforms
                creators = uow.creators.list_by_platform(
                    Platform.YOUTUBE, limit=limit
                ) + uow.creators.list_by_platform(
                    Platform.TIKTOK, limit=limit
                ) + uow.creators.list_by_platform(
                    Platform.INSTAGRAM, limit=limit
                )
                creators = sorted(
                    creators,
                    key=lambda c: c.last_seen_at or c.created_at,  # type: ignore[return-value]
                    reverse=True,
                )[:limit]

        return ListCreatorsResult(creators=tuple(creators), total=total)
```

**Fichier 2 : `tests/unit/application/test_list_creators.py`** (nouveau fichier) :

```python
"""Tests for ListCreatorsUseCase (M006/S03-P01)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vidscope.application.list_creators import ListCreatorsResult, ListCreatorsUseCase
from vidscope.domain import Creator, Platform
from vidscope.domain.values import PlatformUserId
from vidscope.ports import UnitOfWorkFactory


def _creator(
    handle: str,
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str | None = None,
    follower_count: int | None = None,
) -> Creator:
    return Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id or f"uid_{handle}"),
        handle=handle,
        display_name=handle.lstrip("@").title(),
        follower_count=follower_count,
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestListCreatorsNoFilter:
    def test_empty_db_returns_empty(self, uow_factory: UnitOfWorkFactory) -> None:
        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute()
        assert result.creators == ()
        assert result.total == 0

    def test_returns_inserted_creators(self, uow_factory: UnitOfWorkFactory) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator("@alice"))
            uow.creators.upsert(_creator("@bob"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute()
        handles = {c.handle for c in result.creators}
        assert "@alice" in handles
        assert "@bob" in handles

    def test_total_reflects_all_creators(self, uow_factory: UnitOfWorkFactory) -> None:
        with uow_factory() as uow:
            for i in range(5):
                uow.creators.upsert(_creator(f"@user{i}", platform_user_id=f"uid{i}"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute()
        assert result.total == 5

    def test_result_is_frozen_tuple(self, uow_factory: UnitOfWorkFactory) -> None:
        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute()
        assert isinstance(result.creators, tuple)
        result2 = ListCreatorsResult(creators=(), total=0)
        with pytest.raises(Exception):
            object.__setattr__(result2, "total", 99)


class TestListCreatorsByPlatform:
    def test_platform_filter_excludes_other_platforms(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator("@yt1", platform=Platform.YOUTUBE, platform_user_id="yt1"))
            uow.creators.upsert(_creator("@tt1", platform=Platform.TIKTOK, platform_user_id="tt1"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(platform=Platform.YOUTUBE)
        handles = {c.handle for c in result.creators}
        assert "@yt1" in handles
        assert "@tt1" not in handles


class TestListCreatorsByMinFollowers:
    def test_min_followers_filter(self, uow_factory: UnitOfWorkFactory) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator("@big", follower_count=100000, platform_user_id="big"))
            uow.creators.upsert(_creator("@small", follower_count=500, platform_user_id="small"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(min_followers=10000)
        handles = {c.handle for c in result.creators}
        assert "@big" in handles
        assert "@small" not in handles

    def test_null_follower_count_excluded(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator("@unknown", follower_count=None, platform_user_id="unk"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(min_followers=1)
        handles = {c.handle for c in result.creators}
        assert "@unknown" not in handles


class TestListCreatorsDualFilter:
    def test_platform_and_min_followers(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator("@yt_big", platform=Platform.YOUTUBE, follower_count=50000, platform_user_id="ytbig"))
            uow.creators.upsert(_creator("@yt_small", platform=Platform.YOUTUBE, follower_count=100, platform_user_id="ytsmall"))
            uow.creators.upsert(_creator("@tt_big", platform=Platform.TIKTOK, follower_count=50000, platform_user_id="ttbig"))

        uc = ListCreatorsUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(platform=Platform.YOUTUBE, min_followers=10000)
        handles = {c.handle for c in result.creators}
        assert "@yt_big" in handles
        assert "@yt_small" not in handles
        assert "@tt_big" not in handles
```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/application/test_list_creators.py -x -q</automated>
</verify>

<acceptance_criteria>
- `test -f src/vidscope/application/list_creators.py` exit 0
- `test -f tests/unit/application/test_list_creators.py` exit 0
- `grep -q "class ListCreatorsUseCase" src/vidscope/application/list_creators.py` exit 0
- `grep -q "class ListCreatorsResult" src/vidscope/application/list_creators.py` exit 0
- `python -m uv run pytest tests/unit/application/test_list_creators.py -x -q` exit 0
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0
</acceptance_criteria>

<done>
`ListCreatorsUseCase` livré avec filtres platform et min_followers. Tests verts.
</done>
</task>

<task type="auto" tdd="true">
<name>Task 4: ListCreatorVideosUseCase — lister les vidéos d'un créateur</name>

<read_first>
- `src/vidscope/application/list_videos.py` — pattern ListVideosUseCase à miroir
- `src/vidscope/ports/repositories.py` — `VideoRepository.list_by_creator` (ajouté Task 1) + `CreatorRepository.find_by_handle`
- `src/vidscope/adapters/sqlite/video_repository.py` — `list_by_creator` (ajouté Task 1)
- `src/vidscope/domain/entities.py` — Creator (champs id, handle) + Video
- `tests/unit/application/conftest.py` — fixtures `uow_factory`
- `tests/unit/adapters/sqlite/test_video_repository.py` — voir comment insérer des vidéos avec creator_id dans les tests
</read_first>

<action>
**Fichier 1 : `src/vidscope/application/list_creator_videos.py`** (nouveau fichier) :

```python
"""List videos for a creator — powers ``vidscope creator videos <handle>``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Creator, Platform, Video
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ListCreatorVideosResult", "ListCreatorVideosUseCase"]


@dataclass(frozen=True, slots=True)
class ListCreatorVideosResult:
    """Result of :meth:`ListCreatorVideosUseCase.execute`.

    ``found`` is ``False`` when no creator matches ``(platform, handle)``.
    When ``found`` is ``True``, ``creator`` is populated and ``videos``
    holds the creator's videos ordered newest-first.
    """

    found: bool
    creator: Creator | None = None
    videos: tuple[Video, ...] = ()
    total: int = 0


class ListCreatorVideosUseCase:
    """Return videos linked to a creator identified by handle."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        platform: Platform,
        handle: str,
        *,
        limit: int = 20,
    ) -> ListCreatorVideosResult:
        """Fetch videos for the creator matching ``(platform, handle)``.

        Resolution flow:
        1. Resolve creator via :meth:`CreatorRepository.find_by_handle`.
        2. If not found: return ``found=False``.
        3. List videos via :meth:`VideoRepository.list_by_creator(creator.id)`
           ordered newest-first, capped at ``limit``.
        4. Return total count of linked videos (unbounded) alongside the page.

        ``limit`` is clamped to [1, 200].
        """
        limit = max(1, min(limit, 200))

        with self._uow_factory() as uow:
            creator = uow.creators.find_by_handle(platform, handle)
            if creator is None or creator.id is None:
                return ListCreatorVideosResult(found=False)

            videos = uow.videos.list_by_creator(creator.id, limit=limit)
            # Count: list full set to get total — we cap list_by_creator
            # at limit for the page, fetch count separately via large limit
            all_videos = uow.videos.list_by_creator(creator.id, limit=10000)
            total = len(all_videos)

        return ListCreatorVideosResult(
            found=True,
            creator=creator,
            videos=tuple(videos),
            total=total,
        )
```

**Fichier 2 : `tests/unit/application/test_list_creator_videos.py`** (nouveau fichier) :

```python
"""Tests for ListCreatorVideosUseCase (M006/S03-P01)."""

from __future__ import annotations

from datetime import UTC, datetime

from vidscope.application.list_creator_videos import (
    ListCreatorVideosResult,
    ListCreatorVideosUseCase,
)
from vidscope.domain import Creator, Platform, Video
from vidscope.domain.values import PlatformId, PlatformUserId
from vidscope.ports import UnitOfWorkFactory


def _creator(
    handle: str = "@alice",
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str = "UC_alice",
) -> Creator:
    return Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id),
        handle=handle,
        display_name=handle.lstrip("@").title(),
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _video(
    platform_id: str = "vid1",
    url: str = "https://y/watch?v=vid1",
    platform: Platform = Platform.YOUTUBE,
) -> Video:
    return Video(
        platform=platform,
        platform_id=PlatformId(platform_id),
        url=url,
        title=f"Video {platform_id}",
        created_at=datetime(2026, 4, 1, tzinfo=UTC),
    )


class TestListCreatorVideosFound:
    def test_returns_videos_for_creator(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            creator = uow.creators.upsert(_creator())
            vid = _video()
            uow.videos.upsert_by_platform_id(vid, creator=creator)

        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@alice")

        assert result.found is True
        assert result.creator is not None
        assert result.creator.handle == "@alice"
        assert len(result.videos) == 1
        assert result.videos[0].platform_id == PlatformId("vid1")

    def test_returns_multiple_videos(self, uow_factory: UnitOfWorkFactory) -> None:
        with uow_factory() as uow:
            creator = uow.creators.upsert(_creator())
            for i in range(3):
                uow.videos.upsert_by_platform_id(
                    _video(platform_id=f"v{i}", url=f"https://y/v{i}"),
                    creator=creator,
                )

        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@alice")

        assert result.found is True
        assert len(result.videos) == 3
        assert result.total == 3

    def test_total_reflects_all_videos(self, uow_factory: UnitOfWorkFactory) -> None:
        with uow_factory() as uow:
            creator = uow.creators.upsert(_creator())
            for i in range(5):
                uow.videos.upsert_by_platform_id(
                    _video(platform_id=f"v{i}", url=f"https://y/v{i}"),
                    creator=creator,
                )

        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@alice", limit=2)

        assert len(result.videos) == 2  # page capped
        assert result.total == 5       # total unbounded


class TestListCreatorVideosNotFound:
    def test_not_found_when_creator_absent(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@ghost")

        assert result.found is False
        assert result.creator is None
        assert result.videos == ()
        assert result.total == 0

    def test_empty_videos_for_existing_creator(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            uow.creators.upsert(_creator(handle="@lonely"))

        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@lonely")

        assert result.found is True
        assert result.videos == ()
        assert result.total == 0

    def test_excludes_videos_from_other_creator(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        with uow_factory() as uow:
            alice = uow.creators.upsert(_creator("@alice", platform_user_id="alice"))
            bob = uow.creators.upsert(_creator("@bob", platform_user_id="bob"))
            uow.videos.upsert_by_platform_id(_video("v1", "https://y/v1"), creator=alice)
            uow.videos.upsert_by_platform_id(_video("v2", "https://y/v2"), creator=bob)

        uc = ListCreatorVideosUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(Platform.YOUTUBE, "@alice")

        assert result.found is True
        assert len(result.videos) == 1
        assert result.videos[0].platform_id == PlatformId("v1")
```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/application/test_list_creator_videos.py -x -q</automated>
</verify>

<acceptance_criteria>
- `test -f src/vidscope/application/list_creator_videos.py` exit 0
- `test -f tests/unit/application/test_list_creator_videos.py` exit 0
- `grep -q "class ListCreatorVideosUseCase" src/vidscope/application/list_creator_videos.py` exit 0
- `grep -q "list_by_creator" src/vidscope/application/list_creator_videos.py` exit 0
- `python -m uv run pytest tests/unit/application/test_list_creator_videos.py -x -q` exit 0
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0
</acceptance_criteria>

<done>
`ListCreatorVideosUseCase` livré avec tests. Résolution handle → creator → videos. Suite verte.
</done>
</task>

<task type="auto" tdd="false">
<name>Task 5: Exporter les 3 nouveaux use cases dans application/__init__.py</name>

<read_first>
- `src/vidscope/application/__init__.py` — liste complète des exports actuels à étendre
</read_first>

<action>
**Fichier : `src/vidscope/application/__init__.py`**

Ajouter les 3 nouveaux imports et exports. Le fichier final doit contenir :

```python
from vidscope.application.get_creator import GetCreatorResult, GetCreatorUseCase
from vidscope.application.list_creators import ListCreatorsResult, ListCreatorsUseCase
from vidscope.application.list_creator_videos import (
    ListCreatorVideosResult,
    ListCreatorVideosUseCase,
)
```

Et dans `__all__`, ajouter en ordre alphabétique :
- `"GetCreatorResult"`
- `"GetCreatorUseCase"`
- `"ListCreatorVideosResult"`
- `"ListCreatorVideosUseCase"`
- `"ListCreatorsResult"`
- `"ListCreatorsUseCase"`
</action>

<verify>
  <automated>python -m uv run pytest -q</automated>
</verify>

<acceptance_criteria>
- `grep -q "GetCreatorUseCase" src/vidscope/application/__init__.py` exit 0
- `grep -q "ListCreatorsUseCase" src/vidscope/application/__init__.py` exit 0
- `grep -q "ListCreatorVideosUseCase" src/vidscope/application/__init__.py` exit 0
- `python -m uv run python -c "from vidscope.application import GetCreatorUseCase, ListCreatorsUseCase, ListCreatorVideosUseCase; print('ok')"` sort `ok`
- `python -m uv run pytest -q` exit 0 (suite complète)
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0
</acceptance_criteria>

<done>
3 use cases publics via `vidscope.application`. Suite complète verte.
</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI/MCP → use cases | Les use cases reçoivent des inputs (handle, platform) venant de l'utilisateur final |
| Use cases → DB | Les use cases lisent via le UoW — pas d'injection SQL possible via SQLAlchemy Core |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-S03P01-01 | **Tampering (T)** — handle utilisateur injecté dans SQL | `find_by_handle(platform, handle)` | LOW | accept | SQLAlchemy Core paramétrise automatiquement toutes les requêtes. Le handle est passé comme valeur liée, jamais interpolé dans le SQL. |
| T-S03P01-02 | **DoS (D)** — `limit` non borné retourne toutes les vidéos | `ListCreatorVideosUseCase.execute` | LOW | mitigated | `limit` est clampé à `max(1, min(limit, 200))` dans le use case avant toute requête. |
</threat_model>

<verification>
```bash
# Tests spécifiques S03-P01
python -m uv run pytest tests/unit/application/test_get_creator.py -x -q
python -m uv run pytest tests/unit/application/test_list_creators.py -x -q
python -m uv run pytest tests/unit/application/test_list_creator_videos.py -x -q

# Non-régression globale
python -m uv run pytest -q

# Architecture
python -m uv run lint-imports

# Quality gates
python -m uv run ruff check src tests
python -m uv run mypy src
```
</verification>

<success_criteria>
- `VideoRepository.list_by_creator` dans Protocol + adapter SQLite
- `GetCreatorUseCase` + `GetCreatorResult` dans `application/get_creator.py`
- `ListCreatorsUseCase` + `ListCreatorsResult` dans `application/list_creators.py`
- `ListCreatorVideosUseCase` + `ListCreatorVideosResult` dans `application/list_creator_videos.py`
- 3 use cases exportés dans `vidscope.application.__all__`
- Tests : ≥ 8 tests par use case, tous verts
- Suite complète pytest verte (aucune régression)
- 9 contrats import-linter verts
- mypy strict vert, ruff vert
</success_criteria>

<output>
À la fin du plan, créer `.gsd/milestones/M006/slices/S03/S03-P01-SUMMARY.md` résumant :
- Fichiers créés/modifiés
- Shape finale de chaque use case (signature `execute`, champs du result)
- `VideoRepository.list_by_creator` ajouté au Protocol + adapter
- Handoff pour P02 (CLI) et P03 (MCP) : les 3 use cases sont importables depuis `vidscope.application`
</output>
</content>
</invoke>
