---
phase: M009
plan: S03
type: execute
wave: 3
depends_on: [S02]
files_modified:
  - src/vidscope/application/refresh_stats.py
  - src/vidscope/cli/commands/watch.py
  - tests/unit/application/test_refresh_stats.py
  - tests/unit/cli/test_watch.py
autonomous: true
requirements: [R051]
must_haves:
  truths:
    - "`vidscope watch refresh` rapporte BOTH 'N nouvelles vidéos' ET 'M stats rafraîchies'"
    - "Le refresh stats est exécuté par créateur watchlisté : toutes les vidéos connues du créateur sont re-probéed"
    - "Une erreur sur un créateur N'interrompt PAS les autres créateurs (error isolation per-creator hérité de M003)"
    - "Une erreur sur une vidéo N'interrompt PAS les autres vidéos (error isolation per-video, ajouté par S03)"
    - "Le use case existant `RefreshWatchlistUseCase` (M003) RESTE INCHANGÉ — aucun test existant ne casse"
    - "Le CLI `watch.py` orchestre successivement `RefreshWatchlistUseCase` puis `RefreshStatsForWatchlistUseCase`"
  artifacts:
    - path: "src/vidscope/application/refresh_stats.py"
      provides: "RefreshStatsForWatchlistUseCase ajouté en plus des classes S02"
      contains: "class RefreshStatsForWatchlistUseCase"
    - path: "src/vidscope/cli/commands/watch.py"
      provides: "`vidscope watch refresh` étendu avec stats loop + résumé combiné"
      contains: "stats_refreshed"
  key_links:
    - from: "src/vidscope/cli/commands/watch.py"
      to: "RefreshStatsForWatchlistUseCase"
      via: "appel successif après RefreshWatchlistUseCase dans la fonction refresh"
      pattern: "RefreshStatsForWatchlistUseCase"
    - from: "src/vidscope/application/refresh_stats.py"
      to: "WatchAccountRepository + VideoRepository"
      via: "uow.watch_accounts + uow.videos (déjà disponibles dans UoW)"
      pattern: "uow.watch_accounts"
---

<objective>
S03 étend `vidscope watch refresh` pour rafraîchir les stats des vidéos déjà ingérées de chaque créateur watchlisté, EN PLUS de l'ingestion des nouvelles vidéos. **Approche retenue (per M009-RESEARCH Open Question 1) : le use case `RefreshWatchlistUseCase` de M003 reste inchangé (23 tests préservés) ; un nouveau use case `RefreshStatsForWatchlistUseCase` est ajouté dans le même fichier que `RefreshStatsUseCase` (S02) ; le CLI `watch.py` orchestre les deux successivement avec un résumé combiné.**

Purpose: Sans S03, les users doivent lancer manuellement `vidscope refresh-stats --all` après chaque `vidscope watch refresh`. L'intégration transforme le cron/Task Scheduler M003 en source unique de refresh.
Output: Nouveau use case batch-per-creator + extension CLI `watch.py` + tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M009/M009-S02-PLAN.md
@.gsd/milestones/M009/M009-S02-SUMMARY.md
@.gsd/milestones/M009/M009-CONTEXT.md
@.gsd/milestones/M009/M009-RESEARCH.md
@.gsd/milestones/M009/M009-VALIDATION.md
@src/vidscope/application/watchlist.py
@src/vidscope/application/refresh_stats.py
@src/vidscope/cli/commands/watch.py
@src/vidscope/ports/repositories.py
@src/vidscope/adapters/sqlite/watch_account_repository.py
@src/vidscope/adapters/sqlite/video_repository.py

<interfaces>
Patterns existants clés :

**M003 — `RefreshWatchlistUseCase.execute()`** : retourne un `RefreshSummary` avec `new_videos_ingested`, `per_account`, `errors`. SIGNATURE INCHANGÉE.

**Nouveau `RefreshStatsForWatchlistUseCase`** :
```python
class RefreshStatsForWatchlistUseCase:
    def __init__(self, *, refresh_stats: RefreshStatsUseCase, unit_of_work_factory: UnitOfWorkFactory) -> None: ...

    def execute(self) -> RefreshStatsForWatchlistResult:
        """Iterate watched accounts; for each, fetch its videos (via creator_id on videos)
        and invoke refresh_stats.execute_one per video. Per-account + per-video isolation."""
```

**DTO nouveau** :
```python
@dataclass(frozen=True, slots=True)
class RefreshStatsForWatchlistResult:
    accounts_checked: int
    videos_checked: int
    stats_refreshed: int
    failed: int
    errors: tuple[str, ...]
```

**Récupération des vidéos d'un créateur** : via `uow.videos.list_for_creator(creator_id)` si la méthode existe, sinon via un filtre `WHERE creator_id = X`. Vérifier `ports/repositories.py` et `video_repository.py`.

**Mapping WatchedAccount → Creator** : `WatchedAccount.platform + handle` → `Creator.platform + handle`. Vérifier si `creator_repository.get_by_handle(platform, handle)` existe (M006). Sinon, scanner par `platform_user_id` si disponible sur `WatchedAccount`.

**Pattern CLI orchestration** : dans `watch.py` fonction `refresh()`, après le premier use case, appeler le second. Le résumé rich.Table combine les deux compteurs : "N nouvelles vidéos + M stats rafraîchies".
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RefreshStatsForWatchlistUseCase + DTO + tests d'application</name>
  <files>src/vidscope/application/refresh_stats.py, src/vidscope/application/__init__.py, tests/unit/application/test_refresh_stats.py</files>
  <read_first>
    - src/vidscope/application/refresh_stats.py (classes livrées en S02 — RefreshStatsUseCase + DTOs)
    - src/vidscope/application/watchlist.py (pattern M003 : itération accounts, per-account error isolation, DTO `RefreshSummary`)
    - src/vidscope/ports/repositories.py (signatures `WatchAccountRepository.list_all`, `VideoRepository.list_for_creator` ou équivalent)
    - src/vidscope/adapters/sqlite/video_repository.py (voir si `list_for_creator` existe ou s'il faut l'ajouter — M006/S01 ROADMAP a ajouté `creator_id` FK)
    - src/vidscope/adapters/sqlite/watch_account_repository.py (signature `list_all`)
    - src/vidscope/adapters/sqlite/creator_repository.py (signature `get_by_handle` ou équivalent)
    - src/vidscope/domain/entities.py (champs `WatchedAccount` : platform, handle, platform_user_id si présent)
    - tests/unit/application/test_refresh_stats.py (tests S02 — pattern à étendre)
    - tests/unit/application/test_watchlist.py (pattern M003 pour mock WatchAccountRepository + per-account iteration)
    - .gsd/milestones/M009/M009-RESEARCH.md (Open Question 1 : approche séparation retenue)
    - .gsd/milestones/M009/M009-CONTEXT.md (R051 : résumé combiné obligatoire)
  </read_first>
  <behavior>
    - Test 1 : `execute()` retourne `RefreshStatsForWatchlistResult(accounts_checked=0, videos_checked=0, stats_refreshed=0, failed=0, errors=())` quand aucun compte watchlisté.
    - Test 2 : Avec 2 comptes × 3 vidéos chacun, `videos_checked == 6`, `stats_refreshed == 6` si tous OK.
    - Test 3 : Erreur sur une vidéo → `failed++`, le batch continue. La vidéo failed ajoute un message dans `errors`.
    - Test 4 : Erreur sur un compte (ex: creator non trouvé) → `errors` contient un message avec le handle, mais les autres comptes continuent.
    - Test 5 : Pas d'impact sur `RefreshStatsUseCase.execute_one` / `execute_all` (tests S02 passent encore).
    - Test 6 : Le use case n'appelle PAS `RefreshWatchlistUseCase` (séparation stricte, orchestration côté CLI).
  </behavior>
  <action>
Étape 1 — Lire `src/vidscope/adapters/sqlite/video_repository.py` et `src/vidscope/ports/repositories.py` pour confirmer :
- Existe-t-il `VideoRepository.list_for_creator(creator_id)` ou équivalent ? Si non, CHOIX :
  - **Option A** : ajouter la méthode au Protocol + adapter SQLite (select from videos where creator_id = X limit N). Recommandé si `creator_id` existe déjà sur `Video` (M006).
  - **Option B** : filtrer en application — utiliser `list_recent(limit=very_large)` et filtrer en mémoire par `creator_id`. Moins propre mais viable si l'ajout de méthode est trop invasif.
- Existe-t-il `CreatorRepository.get_by_handle(platform, handle)` ? Sinon, vérifier si `get_by_platform_user_id` existe ; ou utiliser `list_by_platform` et filtrer.
- `WatchedAccount` entity : quels champs pour le lier au `Creator` ?

**Décision par défaut (Option A)** : ajouter `VideoRepository.list_for_creator(creator_id, *, limit=1000)` au Protocol et à l'adapter SQLite, documenté comme "petite extension M009/S03". Cela rend le use case plus propre et réutilisable par M010/M011.

Étape 2 — Si Option A : étendre `src/vidscope/ports/repositories.py` dans `VideoRepository` Protocol :
```python
    def list_for_creator(
        self, creator_id: CreatorId, *, limit: int = 1000
    ) -> list[Video]:
        """Return videos linked to the given creator_id (FK), capped."""
        ...
```
Et dans `src/vidscope/adapters/sqlite/video_repository.py` (suivre le pattern existant `list_recent` si présent, ou inspirer de `creator_repository.py`) :
```python
def list_for_creator(self, creator_id: CreatorId, *, limit: int = 1000) -> list[Video]:
    rows = self._conn.execute(
        select(videos)
        .where(videos.c.creator_id == int(creator_id))
        .order_by(videos.c.created_at.desc())
        .limit(limit)
    ).all()
    return [_row_to_video(r) for r in rows]
```

Étape 3 — Étendre `src/vidscope/application/refresh_stats.py` : ajouter à la fin du fichier :
```python
@dataclass(frozen=True, slots=True)
class RefreshStatsForWatchlistResult:
    """Outcome of refresh-stats-for-watchlist (M009/S03)."""

    accounts_checked: int
    videos_checked: int
    stats_refreshed: int
    failed: int
    errors: tuple[str, ...]


class RefreshStatsForWatchlistUseCase:
    """Refresh video_stats for every video of every watched account.

    For each WatchedAccount:
    1. Resolve the matching Creator via (platform, handle).
    2. List videos via uow.videos.list_for_creator(creator.id).
    3. For each video, call refresh_stats.execute_one(video.id).
    Per-account + per-video error isolation (M003 + S02 patterns).
    """

    def __init__(
        self,
        *,
        refresh_stats: RefreshStatsUseCase,
        unit_of_work_factory: UnitOfWorkFactory,
    ) -> None:
        self._refresh = refresh_stats
        self._uow = unit_of_work_factory

    def execute(self) -> RefreshStatsForWatchlistResult:
        errors: list[str] = []
        videos_checked = 0
        stats_refreshed = 0
        failed = 0

        # Collect accounts + resolve creators + collect video ids in one read scope
        work: list[tuple[str, VideoId]] = []  # (label, video_id)
        with self._uow() as uow:
            accounts = uow.watch_accounts.list_all()
            for account in accounts:
                try:
                    creator = uow.creators.get_by_handle(account.platform, account.handle)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"lookup failed for {account.platform.value}/{account.handle}: {exc}")
                    continue
                if creator is None or creator.id is None:
                    errors.append(
                        f"no creator found for {account.platform.value}/{account.handle} (orphan watchlist?)"
                    )
                    continue
                try:
                    videos = uow.videos.list_for_creator(creator.id, limit=1000)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"list videos failed for {account.handle}: {exc}")
                    continue
                for v in videos:
                    if v.id is None:
                        continue
                    label = f"{account.platform.value}/{account.handle}#{int(v.id)}"
                    work.append((label, v.id))

        # Execute refresh per video OUTSIDE the read scope (each uses its own tx)
        for label, vid in work:
            videos_checked += 1
            try:
                res = self._refresh.execute_one(vid)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                errors.append(f"{label}: unexpected error: {exc}")
                continue
            if res.success:
                stats_refreshed += 1
            else:
                failed += 1
                errors.append(f"{label}: {res.message}")

        return RefreshStatsForWatchlistResult(
            accounts_checked=len(accounts),
            videos_checked=videos_checked,
            stats_refreshed=stats_refreshed,
            failed=failed,
            errors=tuple(errors),
        )
```

**CRITIQUE** : adapter le nom exact de `uow.creators.get_by_handle(platform, handle)` selon ce qui existe réellement. Si la méthode s'appelle `get_by_platform_handle` ou `get_by_handle_and_platform`, utiliser ce nom. Si aucune méthode équivalente n'existe, utiliser `list_by_platform(platform)` + filtrer par handle en mémoire, ou ajouter la méthode au Protocol (comme pour `list_for_creator`).

Étape 4 — Étendre `__all__` dans `src/vidscope/application/refresh_stats.py` avec `"RefreshStatsForWatchlistResult"` et `"RefreshStatsForWatchlistUseCase"`.

Étape 5 — Étendre `src/vidscope/application/__init__.py` : ajouter les re-exports.

Étape 6 — Étendre `tests/unit/application/test_refresh_stats.py` (ajouter à la fin) :
```python
# ---------------------------------------------------------------------------
# S03 — RefreshStatsForWatchlistUseCase
# ---------------------------------------------------------------------------

def _make_watched_account(*, platform, handle: str):
    from vidscope.domain import WatchedAccount
    return WatchedAccount(
        platform=platform,
        handle=handle,
        url=f"https://x.y/@{handle}",
    )


def _make_creator(*, cid: int, platform, handle: str):
    from vidscope.domain import Creator, CreatorId, PlatformUserId
    return Creator(
        id=CreatorId(cid),
        platform=platform,
        platform_user_id=PlatformUserId(f"uid_{handle}"),
        handle=handle,
    )


def test_refresh_stats_watchlist_empty() -> None:
    """No watched accounts => all counters zero."""
    from unittest.mock import MagicMock
    from vidscope.application.refresh_stats import RefreshStatsForWatchlistUseCase

    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.watch_accounts.list_all = MagicMock(return_value=[])

    refresh_mock = MagicMock()
    uc = RefreshStatsForWatchlistUseCase(
        refresh_stats=refresh_mock,
        unit_of_work_factory=lambda: fake_uow,
    )
    result = uc.execute()
    assert result.accounts_checked == 0
    assert result.videos_checked == 0
    assert result.stats_refreshed == 0
    refresh_mock.execute_one.assert_not_called()


def test_refresh_stats_watchlist_happy_path() -> None:
    from unittest.mock import MagicMock
    from vidscope.application.refresh_stats import (
        RefreshStatsForWatchlistUseCase,
        RefreshStatsResult,
    )
    from vidscope.domain import Platform, PlatformId, Video, VideoId

    account = _make_watched_account(platform=Platform.YOUTUBE, handle="alice")
    creator = _make_creator(cid=1, platform=Platform.YOUTUBE, handle="alice")
    videos = [
        Video(id=VideoId(i), platform=Platform.YOUTUBE, platform_id=PlatformId(f"p{i}"), url=f"https://x.y/{i}")
        for i in (10, 11, 12)
    ]

    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.watch_accounts.list_all = MagicMock(return_value=[account])
    fake_uow.creators.get_by_handle = MagicMock(return_value=creator)
    fake_uow.videos.list_for_creator = MagicMock(return_value=videos)

    refresh_mock = MagicMock()
    refresh_mock.execute_one = MagicMock(return_value=RefreshStatsResult(
        success=True, video_id=1, stats=None, message="ok",
    ))

    uc = RefreshStatsForWatchlistUseCase(
        refresh_stats=refresh_mock,
        unit_of_work_factory=lambda: fake_uow,
    )
    result = uc.execute()
    assert result.accounts_checked == 1
    assert result.videos_checked == 3
    assert result.stats_refreshed == 3
    assert result.failed == 0
    assert refresh_mock.execute_one.call_count == 3


def test_refresh_stats_watchlist_per_video_error_isolation() -> None:
    from unittest.mock import MagicMock
    from vidscope.application.refresh_stats import (
        RefreshStatsForWatchlistUseCase,
        RefreshStatsResult,
    )
    from vidscope.domain import Platform, PlatformId, Video, VideoId

    account = _make_watched_account(platform=Platform.YOUTUBE, handle="alice")
    creator = _make_creator(cid=1, platform=Platform.YOUTUBE, handle="alice")
    videos = [
        Video(id=VideoId(10), platform=Platform.YOUTUBE, platform_id=PlatformId("p10"), url="https://x.y/10"),
        Video(id=VideoId(11), platform=Platform.YOUTUBE, platform_id=PlatformId("p11"), url="https://x.y/11"),
    ]

    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.watch_accounts.list_all = MagicMock(return_value=[account])
    fake_uow.creators.get_by_handle = MagicMock(return_value=creator)
    fake_uow.videos.list_for_creator = MagicMock(return_value=videos)

    refresh_mock = MagicMock()
    call_n = {"n": 0}
    def _exec(vid):
        call_n["n"] += 1
        if call_n["n"] == 1:
            raise RuntimeError("network down")
        return RefreshStatsResult(success=True, video_id=int(vid), stats=None, message="ok")
    refresh_mock.execute_one = _exec

    uc = RefreshStatsForWatchlistUseCase(
        refresh_stats=refresh_mock,
        unit_of_work_factory=lambda: fake_uow,
    )
    result = uc.execute()
    assert result.videos_checked == 2
    assert result.stats_refreshed == 1
    assert result.failed == 1
    assert any("network down" in e for e in result.errors)


def test_refresh_stats_watchlist_per_account_error_isolation() -> None:
    """Account A creator lookup fails → account B still processed."""
    from unittest.mock import MagicMock
    from vidscope.application.refresh_stats import (
        RefreshStatsForWatchlistUseCase,
        RefreshStatsResult,
    )
    from vidscope.domain import Platform, PlatformId, Video, VideoId

    account_a = _make_watched_account(platform=Platform.YOUTUBE, handle="ghost")
    account_b = _make_watched_account(platform=Platform.YOUTUBE, handle="bob")
    creator_b = _make_creator(cid=2, platform=Platform.YOUTUBE, handle="bob")

    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.watch_accounts.list_all = MagicMock(return_value=[account_a, account_b])

    def _get_by_handle(platform, handle):
        if handle == "ghost":
            return None
        return creator_b
    fake_uow.creators.get_by_handle = _get_by_handle
    fake_uow.videos.list_for_creator = MagicMock(return_value=[
        Video(id=VideoId(20), platform=Platform.YOUTUBE, platform_id=PlatformId("p20"), url="https://x.y/20")
    ])

    refresh_mock = MagicMock()
    refresh_mock.execute_one = MagicMock(return_value=RefreshStatsResult(
        success=True, video_id=20, stats=None, message="ok"
    ))

    uc = RefreshStatsForWatchlistUseCase(
        refresh_stats=refresh_mock,
        unit_of_work_factory=lambda: fake_uow,
    )
    result = uc.execute()
    assert result.accounts_checked == 2
    assert result.videos_checked == 1
    assert result.stats_refreshed == 1
    assert any("ghost" in e for e in result.errors)


def test_s02_refresh_stats_use_case_unchanged() -> None:
    """Regression: existing RefreshStatsUseCase tests still pass — done implicitly by test_refresh_stats.py suite staying green."""
    # Sanity: the class still exports execute_one and execute_all.
    from vidscope.application.refresh_stats import RefreshStatsUseCase
    assert hasattr(RefreshStatsUseCase, "execute_one")
    assert hasattr(RefreshStatsUseCase, "execute_all")
```

Étape 7 — Si on a ajouté `VideoRepository.list_for_creator`, créer/étendre `tests/unit/adapters/sqlite/test_video_repository.py` avec un test de cette méthode.

Étape 8 — Exécuter :
```
uv run pytest tests/unit/application/test_refresh_stats.py tests/unit/application/test_watchlist.py tests/unit/adapters/sqlite/ -x -q
uv run lint-imports
```

NE PAS modifier `RefreshWatchlistUseCase` (M003 — 23 tests existants doivent rester verts).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/application/test_refresh_stats.py tests/unit/application/test_watchlist.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class RefreshStatsForWatchlistUseCase" src/vidscope/application/refresh_stats.py` matches
    - `grep -n "class RefreshStatsForWatchlistResult" src/vidscope/application/refresh_stats.py` matches
    - `grep -n "videos_checked" src/vidscope/application/refresh_stats.py` matches
    - `grep -n "stats_refreshed" src/vidscope/application/refresh_stats.py` matches
    - `grep -nE "class RefreshWatchlistUseCase" src/vidscope/application/watchlist.py` matches (classe M003 inchangée — présent = bon)
    - `grep -nE "^from vidscope.infrastructure" src/vidscope/application/refresh_stats.py` returns exit 1
    - `uv run pytest tests/unit/application/test_watchlist.py -x -q` exits 0 (23 tests M003 toujours verts)
    - `uv run pytest tests/unit/application/test_refresh_stats.py -x -q` exits 0 (tests S02 + 5 nouveaux S03)
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - RefreshStatsForWatchlistUseCase + DTO livrés sans toucher RefreshWatchlistUseCase M003
    - `VideoRepository.list_for_creator` ajouté (si pas déjà présent)
    - Per-account + per-video error isolation
    - 5 nouveaux tests S03 verts, suite M003 verte
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extension CLI `vidscope watch refresh` — orchestration + résumé combiné + tests</name>
  <files>src/vidscope/cli/commands/watch.py, tests/unit/cli/test_watch.py</files>
  <read_first>
    - src/vidscope/cli/commands/watch.py (fonction `refresh` actuelle — uniquement M003)
    - src/vidscope/application/refresh_stats.py (RefreshStatsForWatchlistUseCase livré en Task 1)
    - src/vidscope/application/watchlist.py (RefreshSummary DTO inchangé M003)
    - src/vidscope/cli/_support.py (acquire_container, console, handle_domain_errors)
    - tests/unit/cli/test_watch.py si existe, sinon chercher dans tests/unit/cli/
    - tests/unit/cli/test_cookies.py (pattern CliRunner + mock container)
    - .gsd/milestones/M009/M009-CONTEXT.md (D-05 message "N nouvelles vidéos + M stats rafraîchies")
    - .gsd/KNOWLEDGE.md (ASCII only stdout — `[green]OK[/green]`)
  </read_first>
  <behavior>
    - Test 1 : `vidscope watch refresh` appelle d'abord `RefreshWatchlistUseCase.execute()` puis `RefreshStatsForWatchlistUseCase.execute()`.
    - Test 2 : Le résumé stdout contient BOTH "nouvelles vidéos: N" ET "stats rafraîchies: M" (compteurs visibles).
    - Test 3 : Si `RefreshStatsForWatchlistUseCase` échoue globalement (exception non catchée), le CLI rapporte l'erreur mais `RefreshWatchlistUseCase` a déjà produit son résumé (resilience).
    - Test 4 : Quand ZÉRO compte watchlisté, le résumé montre `0 nouvelles / 0 stats`.
    - Test 5 : Pas de glyphes Unicode dans stdout.
    - Test 6 : Exit code 0 quand les deux use cases retournent sans exception, même si certaines vidéos ont échoué individuellement.
  </behavior>
  <action>
Étape 1 — Lire `src/vidscope/cli/commands/watch.py` et localiser la fonction `refresh` (probablement décorée `@watch_app.command("refresh")`). Comprendre la structure actuelle : appel à `RefreshWatchlistUseCase`, affichage du `RefreshSummary` via rich.Table.

Étape 2 — Modifier la fonction `refresh` pour orchestrer les deux use cases :
```python
@watch_app.command("refresh")
def refresh() -> None:
    """Refresh every watched account and the stats of already-ingested videos."""
    with handle_domain_errors():
        container = acquire_container()

        # Step 1 — M003: ingest new videos
        watch_uc = RefreshWatchlistUseCase(
            pipeline_runner=container.pipeline_runner,
            downloader=container.downloader,
            clock=container.clock,
            unit_of_work_factory=container.unit_of_work,
        )
        watch_summary = watch_uc.execute()

        # Step 2 — M009/S03: refresh stats for every video of every watched creator
        # Isolated try: a stats failure must NOT hide the watch summary above.
        stats_result = None
        stats_error: str | None = None
        try:
            stats_uc = RefreshStatsForWatchlistUseCase(
                refresh_stats=RefreshStatsUseCase(
                    stats_stage=container.stats_stage,
                    unit_of_work_factory=container.unit_of_work,
                    clock=container.clock,
                ),
                unit_of_work_factory=container.unit_of_work,
            )
            stats_result = stats_uc.execute()
        except Exception as exc:  # noqa: BLE001 — resilience
            stats_error = f"stats refresh failed: {exc}"

        _render_combined_summary(watch_summary, stats_result, stats_error)


def _render_combined_summary(watch_summary, stats_result, stats_error: str | None) -> None:
    """Pretty-print the combined watch+stats refresh summary.

    Matches D-05 requirement: both counters visible in one output.
    """
    console.print(
        f"[bold]watch refresh:[/bold] "
        f"accounts={watch_summary.accounts_checked} "
        f"new_videos={watch_summary.new_videos_ingested}"
    )
    if stats_result is not None:
        console.print(
            f"[bold]stats refresh:[/bold] "
            f"videos={stats_result.videos_checked} "
            f"refreshed={stats_result.stats_refreshed} "
            f"failed={stats_result.failed}"
        )
    if stats_error is not None:
        console.print(f"[red]stats error:[/red] {stats_error}")

    # Detailed per-account table reused from M003
    if watch_summary.per_account:
        table = Table(title="Per-account outcome", show_header=True)
        table.add_column("platform")
        table.add_column("handle")
        table.add_column("new videos", justify="right")
        table.add_column("error")
        for acc in watch_summary.per_account:
            table.add_row(
                acc.platform.value,
                acc.handle,
                str(acc.new_videos),
                acc.error or "",
            )
        console.print(table)

    # Display first N errors from the stats batch
    if stats_result is not None and stats_result.errors:
        console.print(f"[dim]stats errors (first 5):[/dim]")
        for e in stats_result.errors[:5]:
            console.print(f"  - {e}")
```

Ajouter les imports nécessaires en haut du fichier :
```python
from vidscope.application.refresh_stats import (
    RefreshStatsForWatchlistUseCase,
    RefreshStatsUseCase,
)
```

**Adaptation** : si le `RefreshWatchlistUseCase` actuel a une signature constructeur différente (arguments manquants ou supplémentaires), ADAPTER SANS CHANGER sa signature — simplement lire le code et passer les bonnes dépendances depuis le container. La signature vue dans `watchlist.py` imports est : `pipeline_runner + downloader + clock + unit_of_work_factory`. Si le réel diffère, utiliser la réalité.

Étape 3 — Créer ou étendre `tests/unit/cli/test_watch.py` :
```python
"""CLI tests for `vidscope watch refresh` — combined watch+stats summary (S03)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

runner = CliRunner()


def _make_watch_summary(*, new_videos: int = 0, accounts: int = 0):
    from vidscope.application.watchlist import RefreshSummary
    return RefreshSummary(
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, tzinfo=UTC),
        accounts_checked=accounts,
        new_videos_ingested=new_videos,
        errors=(),
        per_account=(),
    )


def _make_stats_result(*, videos: int = 0, refreshed: int = 0, failed: int = 0, errors: tuple[str, ...] = ()):
    from vidscope.application.refresh_stats import RefreshStatsForWatchlistResult
    return RefreshStatsForWatchlistResult(
        accounts_checked=0,
        videos_checked=videos,
        stats_refreshed=refreshed,
        failed=failed,
        errors=errors,
    )


def _patch_watch(monkeypatch, *, watch_summary, stats_result, stats_raises: Exception | None = None):
    import vidscope.cli.commands.watch as watch_mod

    class _Uc:
        def __init__(self, **kw: Any) -> None: ...
        def execute(self) -> Any: return watch_summary
    monkeypatch.setattr(watch_mod, "RefreshWatchlistUseCase", _Uc)

    class _StatsUc:
        def __init__(self, **kw: Any) -> None: ...
        def execute(self) -> Any:
            if stats_raises is not None:
                raise stats_raises
            return stats_result
    monkeypatch.setattr(watch_mod, "RefreshStatsForWatchlistUseCase", _StatsUc)

    class _RefreshStats:
        def __init__(self, **kw: Any) -> None: ...
    monkeypatch.setattr(watch_mod, "RefreshStatsUseCase", _RefreshStats)

    fake_container = MagicMock()
    fake_container.pipeline_runner = MagicMock()
    fake_container.downloader = MagicMock()
    fake_container.clock = MagicMock(now=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    fake_container.unit_of_work = MagicMock()
    fake_container.stats_stage = MagicMock()
    monkeypatch.setattr(watch_mod, "acquire_container", lambda: fake_container)


def test_watch_refresh_shows_both_counters(monkeypatch) -> None:
    _patch_watch(
        monkeypatch,
        watch_summary=_make_watch_summary(new_videos=2, accounts=1),
        stats_result=_make_stats_result(videos=5, refreshed=4, failed=1),
    )
    from vidscope.cli.app import app
    res = runner.invoke(app, ["watch", "refresh"])
    assert res.exit_code == 0, res.stdout
    out = res.stdout.lower()
    assert "new_videos=2" in out or "new videos" in out or "nouvelles" in out.lower()
    assert "refreshed=4" in out or "4" in out
    assert "videos=5" in out or "5" in out


def test_watch_refresh_empty_watchlist(monkeypatch) -> None:
    _patch_watch(
        monkeypatch,
        watch_summary=_make_watch_summary(new_videos=0, accounts=0),
        stats_result=_make_stats_result(),
    )
    from vidscope.cli.app import app
    res = runner.invoke(app, ["watch", "refresh"])
    assert res.exit_code == 0


def test_watch_refresh_resilient_to_stats_failure(monkeypatch) -> None:
    """If the stats step raises, the watch summary still prints and exit=0."""
    _patch_watch(
        monkeypatch,
        watch_summary=_make_watch_summary(new_videos=1, accounts=1),
        stats_result=None,
        stats_raises=RuntimeError("catastrophic"),
    )
    from vidscope.cli.app import app
    res = runner.invoke(app, ["watch", "refresh"])
    assert res.exit_code == 0, res.stdout
    assert "new_videos=1" in res.stdout or "new videos" in res.stdout.lower() or "1" in res.stdout
    assert "catastrophic" in res.stdout or "stats error" in res.stdout.lower()


def test_watch_refresh_no_unicode_glyphs(monkeypatch) -> None:
    _patch_watch(
        monkeypatch,
        watch_summary=_make_watch_summary(new_videos=0, accounts=0),
        stats_result=_make_stats_result(),
    )
    from vidscope.cli.app import app
    res = runner.invoke(app, ["watch", "refresh"])
    for glyph in ["\u2713", "\u2717", "\u2192", "\u2190"]:
        assert glyph not in res.stdout
```

Étape 4 — Exécuter :
```
uv run pytest tests/unit/cli/test_watch.py tests/unit/application/ -x -q
uv run lint-imports
```

NE PAS toucher la signature ni la logique interne de `RefreshWatchlistUseCase` (M003). NE PAS faire crasher le CLI quand le stats step échoue — resilience obligatoire.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/cli/test_watch.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "RefreshStatsForWatchlistUseCase" src/vidscope/cli/commands/watch.py` matches
    - `grep -n "RefreshStatsUseCase" src/vidscope/cli/commands/watch.py` matches
    - `grep -n "stats refresh" src/vidscope/cli/commands/watch.py` matches (au moins une des deux lignes "stats refresh" ou label équivalent)
    - `grep -nE "(\\\\u2713|\\\\u2717|\\\\u2192)" src/vidscope/cli/commands/watch.py` returns exit 1
    - `uv run pytest tests/unit/cli/test_watch.py -x -q` exits 0
    - `uv run pytest tests/unit/application/test_watchlist.py -x -q` exits 0 (M003 toujours vert)
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - `vidscope watch refresh` affiche les deux compteurs ("new_videos=X" et "refreshed=Y")
    - CLI resilient : erreur du stats step n'empêche pas l'affichage du watch summary
    - ASCII-only stdout
    - 4+ tests CLI S03 verts
    - Tests M003 toujours verts
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI `watch refresh` → 2 use cases successifs | orchestration séquentielle — failure du 2nd ne doit pas hide le 1er |
| watch_accounts → creators → videos | chaînage de lookups — chacun peut échouer indépendamment |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-ISO-01 | Availability | Per-account error isolation | mitigate | try/except autour de `get_by_handle` et `list_for_creator` — un compte cassé enregistre une erreur dans `errors` et passe au suivant. |
| T-ISO-02 | Availability | Per-video error isolation | mitigate | try/except autour de `refresh_stats.execute_one` — une vidéo cassée incrémente `failed` et passe à la suivante. |
| T-ISO-03 | Availability | Stats step vs watch step | mitigate | Le CLI wrappe `RefreshStatsForWatchlistUseCase.execute()` dans un try/except distinct — une exception globale du stats step ne masque pas le résultat M003. Exit code reste 0 (non-bloquant). |
| T-DATA-01 | Tampering (hérité S01) | yt-dlp → video_stats via StatsProbe | mitigate | `_int_or_none` + truncation seconde sur chaque champ — hérité de S01, non répété. |
| T-INPUT-01 | DoS (hérité S02) | Limits CLI refresh-stats | accept | `vidscope watch refresh` n'accepte pas `--limit` — elle itère tous les watched accounts. Risque négligeable pour un outil single-user (R032). |
</threat_model>

<verification>
Après les 2 tâches :
- `uv run pytest tests/unit/ -x -q` vert (y compris les 23 tests M003 préservés)
- `uv run lint-imports` vert
- `vidscope watch refresh` affiche les deux compteurs ("new_videos=X" ET "refreshed=Y")
- CLI resilient à une exception globale du stats step (exit 0, message d'erreur rouge mais lisible)
- Aucun glyphe unicode dans stdout
</verification>

<success_criteria>
S03 est complet quand :
- [ ] `RefreshStatsForWatchlistUseCase` + DTO livrés sans toucher `RefreshWatchlistUseCase` M003
- [ ] Per-account + per-video error isolation
- [ ] `VideoRepository.list_for_creator` ajouté si absent
- [ ] `vidscope watch refresh` orchestre successivement les deux use cases
- [ ] Résumé combiné visible (new_videos + stats_refreshed + failed)
- [ ] Resilience CLI : failure globale du stats step n'empêche pas l'affichage du watch summary
- [ ] ASCII-only stdout
- [ ] Suite tests unit verte (23 tests M003 + 5 tests S03 + 4 tests CLI)
- [ ] `lint-imports` vert
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M009/M009-S03-SUMMARY.md` documentant :
- Signature `RefreshStatsForWatchlistUseCase.execute()`
- Structure du DTO `RefreshStatsForWatchlistResult`
- Format du résumé combiné affiché par `vidscope watch refresh`
- Liste des fichiers créés/modifiés
- Confirmation que `RefreshWatchlistUseCase` M003 reste inchangé
</output>
