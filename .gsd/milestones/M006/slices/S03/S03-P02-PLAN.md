---
plan_id: S03-P02
phase: M006/S03
plan: 02
type: execute
wave: 2
depends_on: [S03-P01]
files_modified:
  - src/vidscope/cli/commands/creators.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - src/vidscope/cli/commands/show.py
  - src/vidscope/cli/commands/list.py
  - tests/unit/cli/test_creators.py
autonomous: true
requirements: [R041]
must_haves:
  truths:
    - "vidscope creator show <handle> affiche le profil du créateur en Rich Panel"
    - "vidscope creator list [--platform] [--min-followers] affiche un tableau Rich"
    - "vidscope creator videos <handle> affiche les vidéos du créateur en tableau"
    - "vidscope show <id> affiche le bloc créateur si creator_id est défini"
    - "vidscope list affiche une colonne creator dans le tableau"
    - "9 contrats import-linter verts (cli n'importe pas adapters)"
  artifacts:
    - path: "src/vidscope/cli/commands/creators.py"
      provides: "creator_app Typer sub-app avec show, list, videos"
      contains: "creator_app"
    - path: "src/vidscope/cli/app.py"
      provides: "creator sub-app enregistré"
      contains: "creator_app"
  key_links:
    - from: "src/vidscope/cli/commands/creators.py"
      to: "GetCreatorUseCase"
      via: "import + instantiation"
      pattern: "GetCreatorUseCase"
    - from: "src/vidscope/cli/app.py"
      to: "creator_app"
      via: "app.add_typer(creator_app, name='creator')"
      pattern: "creator_app"
---

<objective>
Livrer la CLI `vidscope creator` (3 sous-commandes) et enrichir `vidscope show` + `vidscope list` avec les données créateur.

**Ce plan consomme les use cases de S03-P01.** Il ne touche pas la couche MCP (S03-P03) ni l'application.

Périmètre exact :
1. `vidscope creator show <handle> [--platform youtube|tiktok|instagram]` — Rich Panel avec tous les champs du créateur
2. `vidscope creator list [--platform …] [--min-followers N] [--limit N]` — tableau Rich
3. `vidscope creator videos <handle> [--platform …] [--limit N]` — tableau Rich des vidéos
4. `vidscope show <id>` — enrichi : affiche `creator` inline si `video.creator_id` non nul
5. `vidscope list` — enrichi : colonne `creator` dans le tableau (display_name ou `author` fallback)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M006/M006-ROADMAP.md
@.gsd/milestones/M006/slices/S03/S03-P01-SUMMARY.md
@src/vidscope/cli/app.py
@src/vidscope/cli/commands/__init__.py
@src/vidscope/cli/commands/show.py
@src/vidscope/cli/commands/list.py
@src/vidscope/cli/_support.py
@src/vidscope/application/__init__.py
@.importlinter

<interfaces>
<!-- Patterns CLI du projet à reproduire exactement -->

Pattern commande CLI (tous les fichiers commands/*.py) :
```python
from vidscope.cli._support import acquire_container, console, fail_user, handle_domain_errors

def some_command(...) -> None:
    with handle_domain_errors():
        container = acquire_container()
        use_case = SomeUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(...)
        # Rich formatting
```

Pattern Typer sub-app (watch_app, cookies_app, mcp_app) — voir commands/watch.py pour référence :
```python
creator_app = typer.Typer(name="creator", help="...", no_args_is_help=True)

@creator_app.command("show")
def show_command(...) -> None:
    ...
```

Pattern Rich Panel (commands/show.py) :
```python
console.print(Panel.fit("\n".join(lines), title="...", border_style="cyan"))
```

Pattern Rich Table (commands/list.py) :
```python
table = Table(title="...", show_header=True)
table.add_column("col", ...)
table.add_row(...)
console.print(table)
```

Platform enum valid values : `"youtube"`, `"tiktok"`, `"instagram"` (via Platform.value).

Architecture constraint (.importlinter) :
- `vidscope.cli` NE DOIT PAS importer `vidscope.adapters`, `vidscope.infrastructure` directement
- `_support.acquire_container()` est le seul point d'entrée vers l'infra
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
<name>Task 1: Créer src/vidscope/cli/commands/creators.py — sub-app creator avec 3 sous-commandes</name>

<read_first>
- `src/vidscope/cli/commands/show.py` — pattern Panel.fit pour `creator show`
- `src/vidscope/cli/commands/list.py` — pattern Table pour `creator list` et `creator videos`
- `src/vidscope/cli/commands/watch.py` (ou `cookies.py`) — pattern sub-app Typer avec add_typer
- `src/vidscope/cli/_support.py` — tous les helpers : `acquire_container`, `console`, `fail_user`, `handle_domain_errors`
- `src/vidscope/application/get_creator.py` — `GetCreatorUseCase`, `GetCreatorResult` (livré P01)
- `src/vidscope/application/list_creators.py` — `ListCreatorsUseCase` (livré P01)
- `src/vidscope/application/list_creator_videos.py` — `ListCreatorVideosUseCase` (livré P01)
- `src/vidscope/domain/values.py` — `Platform` enum pour `--platform` option
</read_first>

<action>
**Fichier : `src/vidscope/cli/commands/creators.py`** (nouveau fichier) :

```python
"""`vidscope creator` sub-commands — show, list, videos."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from vidscope.application.get_creator import GetCreatorUseCase
from vidscope.application.list_creator_videos import ListCreatorVideosUseCase
from vidscope.application.list_creators import ListCreatorsUseCase
from vidscope.cli._support import acquire_container, console, fail_user, handle_domain_errors
from vidscope.domain.values import Platform

__all__ = ["creator_app"]


creator_app = typer.Typer(
    name="creator",
    help="Inspect and list creators in the library.",
    no_args_is_help=True,
)

_PLATFORM_CHOICES = ["youtube", "tiktok", "instagram"]

PlatformArg = Annotated[
    str | None,
    typer.Option(
        "--platform",
        "-p",
        help="Filter by platform: youtube, tiktok, or instagram.",
        case_sensitive=False,
    ),
]


def _parse_platform(value: str | None) -> Platform | None:
    if value is None:
        return None
    v = value.lower()
    try:
        return Platform(v)
    except ValueError:
        raise typer.BadParameter(
            f"'{value}' is not a valid platform. Choose from: {', '.join(_PLATFORM_CHOICES)}"
        )


@creator_app.command("show")
def show_creator(
    handle: str = typer.Argument(..., help="Creator handle (e.g. @alice)."),
    platform_str: PlatformArg = None,
) -> None:
    """Show the full profile for a creator identified by handle."""
    platform = _parse_platform(platform_str) or Platform.YOUTUBE

    with handle_domain_errors():
        container = acquire_container()
        use_case = GetCreatorUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(platform, handle)

    if not result.found or result.creator is None:
        raise fail_user(f"no creator '{handle}' found on {platform.value}")

    c = result.creator
    lines = [
        f"[bold]id:[/bold] {int(c.id) if c.id is not None else '-'}",
        f"[bold]platform:[/bold] {c.platform.value}",
        f"[bold]handle:[/bold] {c.handle or '-'}",
        f"[bold]display_name:[/bold] {c.display_name or '-'}",
        f"[bold]followers:[/bold] {c.follower_count:,}" if c.follower_count else "[bold]followers:[/bold] -",
        f"[bold]verified:[/bold] {'yes' if c.is_verified else 'no' if c.is_verified is False else '-'}",
        f"[bold]profile_url:[/bold] {c.profile_url or '-'}",
        f"[bold]first_seen:[/bold] {c.first_seen_at.strftime('%Y-%m-%d') if c.first_seen_at else '-'}",
        f"[bold]last_seen:[/bold] {c.last_seen_at.strftime('%Y-%m-%d') if c.last_seen_at else '-'}",
    ]
    console.print(
        Panel.fit(
            "\n".join(lines),
            title=f"[bold]creator — {c.handle or handle}[/bold]",
            border_style="cyan",
        )
    )


@creator_app.command("list")
def list_creators(
    platform_str: PlatformArg = None,
    min_followers: int | None = typer.Option(
        None,
        "--min-followers",
        "-f",
        help="Only show creators with at least N followers.",
        min=0,
    ),
    limit: int = typer.Option(
        20, "--limit", "-n", help="Number of creators to display.", min=1, max=200
    ),
) -> None:
    """List creators in the library."""
    platform = _parse_platform(platform_str)

    with handle_domain_errors():
        container = acquire_container()
        use_case = ListCreatorsUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(platform=platform, min_followers=min_followers, limit=limit)

    console.print(f"[bold]total creators:[/bold] {result.total}")

    if not result.creators:
        console.print("[dim]No creators yet. Run [bold]vidscope add <url>[/bold] to ingest a video.[/dim]")
        return

    table = Table(title=f"Creators ({len(result.creators)})", show_header=True)
    table.add_column("id", justify="right", style="dim")
    table.add_column("platform")
    table.add_column("handle")
    table.add_column("display_name", overflow="fold")
    table.add_column("followers", justify="right")
    table.add_column("verified")
    table.add_column("last_seen")

    for c in result.creators:
        followers = f"{c.follower_count:,}" if c.follower_count is not None else "-"
        verified = "yes" if c.is_verified else "no" if c.is_verified is False else "-"
        last_seen = c.last_seen_at.strftime("%Y-%m-%d") if c.last_seen_at else "-"
        table.add_row(
            str(int(c.id)) if c.id else "-",
            c.platform.value,
            (c.handle or "-")[:30],
            (c.display_name or "-")[:40],
            followers,
            verified,
            last_seen,
        )

    console.print(table)


@creator_app.command("videos")
def creator_videos(
    handle: str = typer.Argument(..., help="Creator handle (e.g. @alice)."),
    platform_str: PlatformArg = None,
    limit: int = typer.Option(
        20, "--limit", "-n", help="Number of videos to display.", min=1, max=200
    ),
) -> None:
    """List videos ingested from a specific creator."""
    platform = _parse_platform(platform_str) or Platform.YOUTUBE

    with handle_domain_errors():
        container = acquire_container()
        use_case = ListCreatorVideosUseCase(unit_of_work_factory=container.unit_of_work)
        result = use_case.execute(platform, handle, limit=limit)

    if not result.found or result.creator is None:
        raise fail_user(f"no creator '{handle}' found on {platform.value}")

    creator = result.creator
    console.print(
        f"[bold]creator:[/bold] {creator.handle or handle} "
        f"([dim]{creator.platform.value}[/dim])"
    )
    console.print(f"[bold]total videos:[/bold] {result.total}")

    if not result.videos:
        console.print("[dim]No videos yet for this creator.[/dim]")
        return

    table = Table(title=f"Videos by {creator.handle or handle} ({len(result.videos)})", show_header=True)
    table.add_column("id", justify="right", style="dim")
    table.add_column("platform")
    table.add_column("title", overflow="fold")
    table.add_column("duration", justify="right")
    table.add_column("ingested")

    for video in result.videos:
        duration = f"{video.duration:.0f}s" if video.duration is not None else "-"
        table.add_row(
            str(int(video.id)) if video.id else "-",
            video.platform.value,
            (video.title or "")[:60],
            duration,
            video.created_at.strftime("%Y-%m-%d") if video.created_at else "-",
        )

    console.print(table)
```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/cli/test_creators.py -x -q 2>/dev/null || echo "tests not created yet — proceed to Task 2"</automated>
</verify>

<acceptance_criteria>
- `test -f src/vidscope/cli/commands/creators.py` exit 0
- `grep -q "^creator_app = typer.Typer" src/vidscope/cli/commands/creators.py` exit 0
- `grep -q "GetCreatorUseCase" src/vidscope/cli/commands/creators.py` exit 0
- `grep -q "ListCreatorsUseCase" src/vidscope/cli/commands/creators.py` exit 0
- `grep -q "ListCreatorVideosUseCase" src/vidscope/cli/commands/creators.py` exit 0
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0 (cli n'importe pas adapters)
</acceptance_criteria>

<done>
`creator_app` Typer sub-app créé avec `show`, `list`, `videos`. mypy + import-linter verts.
</done>
</task>

<task type="auto" tdd="true">
<name>Task 2: Enregistrer creator_app dans app.py et commands/__init__.py</name>

<read_first>
- `src/vidscope/cli/app.py` — voir comment `watch_app` et `cookies_app` sont enregistrés (add_typer pattern)
- `src/vidscope/cli/commands/__init__.py` — voir la liste complète des imports/exports actuels
</read_first>

<action>
**Fichier 1 : `src/vidscope/cli/commands/__init__.py`**

Ajouter l'import de `creator_app` depuis `creators` et l'ajouter à `__all__` :

```python
from vidscope.cli.commands.creators import creator_app
```

Dans `__all__`, ajouter `"creator_app"` en ordre alphabétique.

**Fichier 2 : `src/vidscope/cli/app.py`**

1. Ajouter `creator_app` dans l'import depuis `vidscope.cli.commands` :
   ```python
   from vidscope.cli.commands import (
       add_command,
       cookies_app,
       creator_app,   # <-- nouveau
       doctor_command,
       list_command,
       mcp_app,
       search_command,
       show_command,
       status_command,
       suggest_command,
       watch_app,
   )
   ```

2. Ajouter l'enregistrement après `app.add_typer(watch_app, name="watch")` :
   ```python
   app.add_typer(creator_app, name="creator")
   ```
</action>

<verify>
  <automated>python -m uv run python -m vidscope.cli.app --help 2>&1 | grep -q "creator" && echo "creator subcommand registered"</automated>
</verify>

<acceptance_criteria>
- `grep -q "creator_app" src/vidscope/cli/commands/__init__.py` exit 0
- `grep -q "creator_app" src/vidscope/cli/app.py` exit 0
- `grep -q "add_typer(creator_app" src/vidscope/cli/app.py` exit 0
- `python -m uv run python -c "from vidscope.cli.app import app; print('ok')"` sort `ok`
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0
</acceptance_criteria>

<done>
`creator_app` enregistré dans la CLI principale. `vidscope creator --help` accessible.
</done>
</task>

<task type="auto" tdd="true">
<name>Task 3: Enrichir vidscope show avec le bloc créateur inline</name>

<read_first>
- `src/vidscope/cli/commands/show.py` (complet) — la fonction `show_command` à modifier
- `src/vidscope/application/show_video.py` — `ShowVideoResult.video` a `video.creator_id` si S01 est livré... Attention : `Video` n'a pas de champ `creator_id` dans le domain entity. La jointure creator doit se faire via `uow.creators.get(video.creator_id)` dans le use case ou dans la commande.
- `src/vidscope/adapters/sqlite/video_repository.py` — vérifier si `_row_to_video` retourne `creator_id` dans le Video (le schéma a `creator_id` mais la Video entity ne l'a pas — voir ci-dessous)
- `src/vidscope/domain/entities.py` lignes 48-73 — `Video` dataclass : N'A PAS de champ `creator_id`. Le FK est en DB mais pas exposé dans l'entity.
</read_first>

<action>
**Stratégie :** `Video` entity n'expose pas `creator_id`. Pour enrichir `vidscope show`, on doit accéder au créateur séparément. La solution la plus simple : utiliser `GetCreatorUseCase` n'est pas idéale car on n'a que le video_id, pas le handle. La bonne approche : étendre `ShowVideoResult` avec un `creator: Creator | None` optionnel, et charger le créateur dans le use case `ShowVideoUseCase` via `uow.creators.get(creator_id_from_db)`.

**Problème :** `creator_id` n'est pas dans `Video` entity. La Video entity est immuable — on ne peut pas l'enrichir sans casser le domain.

**Solution adoptée (minimale) :** Lire le `creator_id` directement depuis la table `videos` dans `ShowVideoUseCase` en ajoutant une méthode `get_creator_id_for_video(video_id)` à `VideoRepository`, ou plus simplement : accéder à `uow.creators.find_by_handle` n'est pas applicable ici. La vraie solution est d'ajouter un champ `creator_id: CreatorId | None = None` à `Video` entity et mettre à jour `_row_to_video`.

**Alternative plus simple sans toucher l'entity :** Ajouter une méthode `get_creator_for_video(video_id: VideoId) -> Creator | None` à `CreatorRepository` (ou utiliser une requête brute). Mais cela ajoute au Protocol.

**Décision implémentation :** Ajouter `creator_id: CreatorId | None = None` à `Video` entity (champ optionnel — rétrocompat totale). Mettre à jour `_row_to_video` dans `VideoRepositorySQLite` pour le lire. Mettre à jour `ShowVideoUseCase` pour charger le créateur. Mettre à jour `show_command` pour afficher le créateur.

**Fichier 1 : `src/vidscope/domain/entities.py`**

Ajouter `creator_id: CreatorId | None = None` à `Video` dataclass, après `view_count: int | None = None` :
```python
    creator_id: CreatorId | None = None
```

Aussi s'assurer que `CreatorId` est dans les imports de `values` — vérifier `from vidscope.domain.values import (CreatorId, ...)`.

**Fichier 2 : `src/vidscope/adapters/sqlite/video_repository.py`**

Dans `_row_to_video`, ajouter la lecture du `creator_id` :
```python
    creator_id=(
        CreatorId(int(data["creator_id"]))
        if data.get("creator_id") is not None
        else None
    ),
```

Ajouter `CreatorId` dans l'import domain si pas déjà présent.

**Fichier 3 : `src/vidscope/application/show_video.py`**

1. Étendre `ShowVideoResult` avec `creator: Creator | None = None`
2. Dans `execute`, après `video = uow.videos.get(VideoId(video_id))`, si `video.creator_id` n'est pas None : `creator = uow.creators.get(video.creator_id)`, sinon `creator = None`
3. Retourner `creator=creator` dans `ShowVideoResult`

Import à ajouter : `from vidscope.domain import Analysis, Creator, Frame, Transcript, Video, VideoId`

**Fichier 4 : `src/vidscope/cli/commands/show.py`**

Après le bloc transcript, ajouter l'affichage du créateur :
```python
if result.creator is not None:
    c = result.creator
    followers = f"{c.follower_count:,}" if c.follower_count else "-"
    console.print(
        f"[bold]creator:[/bold] {c.handle or c.display_name or '-'} "
        f"([dim]{c.platform.value}[/dim], {followers} followers)"
    )
else:
    console.print("[dim]creator: unknown[/dim]")
```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/application/ tests/unit/adapters/sqlite/test_video_repository.py -x -q</automated>
</verify>

<acceptance_criteria>
- `grep -q "creator_id: CreatorId | None = None" src/vidscope/domain/entities.py` exit 0
- `grep -q "creator_id" src/vidscope/adapters/sqlite/video_repository.py` exit 0
- `grep -q "creator: Creator | None = None" src/vidscope/application/show_video.py` exit 0
- `grep -q "creator.handle" src/vidscope/cli/commands/show.py` exit 0
- `python -m uv run pytest tests/unit/application/ -x -q` exit 0
- `python -m uv run pytest tests/unit/adapters/sqlite/test_video_repository.py -x -q` exit 0
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0
</acceptance_criteria>

<done>
`vidscope show <id>` affiche le bloc créateur inline. `Video.creator_id` propagé depuis DB → entity → use case → CLI.
</done>
</task>

<task type="auto" tdd="true">
<name>Task 4: Enrichir vidscope list avec la colonne creator</name>

<read_first>
- `src/vidscope/cli/commands/list.py` (complet) — la fonction `list_command` à modifier
- `src/vidscope/domain/entities.py` — `Video.creator_id` (ajouté Task 3) + `Video.author` (cache D-03)
</read_first>

<action>
**Fichier : `src/vidscope/cli/commands/list.py`**

Enrichir le tableau Rich existant avec une colonne `creator`. La `Video` entity a `author` (le cache D-03 write-through) — c'est la source d'affichage la plus simple sans requête supplémentaire (creator name déjà dénormalisé dans `author`).

Modifier `list_command` pour ajouter la colonne `creator` après `author` :

1. Dans la définition du tableau, ajouter après la colonne `author` :
   ```python
   table.add_column("creator_id", justify="right", style="dim")
   ```
   Ou plus précisément, remplacer la colonne `author` par `creator` affichant `video.author` (déjà là) et ajouter `creator_id` :

   **Stratégie :** La colonne `author` existante affiche déjà le nom. Ajouter une colonne `creator_id` qui affiche `str(int(video.creator_id))` si non nul, sinon `-`. Cela confirme visuellement que le FK est peuplé.

2. Dans `table.add_row(...)`, ajouter l'argument `creator_id` :
   ```python
   str(int(video.creator_id)) if video.creator_id is not None else "-",
   ```

Le tableau final aura ces colonnes dans l'ordre : `id`, `platform`, `title`, `author`, `creator_id`, `duration`, `ingested`.
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/cli/ -x -q 2>/dev/null || echo "ok — CLI snapshot tests in Task 5"</automated>
</verify>

<acceptance_criteria>
- `grep -q "creator_id" src/vidscope/cli/commands/list.py` exit 0
- `python -m uv run mypy src` exit 0
- `python -m uv run pytest -x -q` exit 0 (suite complète)
</acceptance_criteria>

<done>
`vidscope list` affiche la colonne `creator_id` confirmant le FK peuplé.
</done>
</task>

<task type="auto" tdd="true">
<name>Task 5: Tests CLI creator sub-app (Typer CliRunner)</name>

<read_first>
- `tests/unit/cli/test_app.py` et `tests/unit/cli/test_cookies.py` — pattern CliRunner pour tests CLI
- `src/vidscope/cli/commands/creators.py` (livré Task 1) — les 3 commandes à tester
- `tests/unit/application/conftest.py` — voir comment le `uow_factory` est construit pour réutiliser dans les tests CLI
- `src/vidscope/cli/_support.py` — `acquire_container` est le point d'entrée à mocker
</read_first>

<action>
**Fichier : `tests/unit/cli/test_creators.py`** (nouveau fichier) :

```python
"""Snapshot tests for `vidscope creator` sub-commands (M006/S03-P02).

Uses Typer's CliRunner with a real SQLite container (same pattern as
tests/unit/cli/test_app.py) to verify output shape without asserting
exact string formatting.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.cli.app import app
from vidscope.domain import Creator, Platform
from vidscope.domain.values import PlatformUserId
from vidscope.infrastructure.container import Container
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.ports import UnitOfWork, UnitOfWorkFactory

runner = CliRunner()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def container(db_path: Path) -> Container:
    engine = build_engine(db_path)
    init_db(engine)

    def uow_factory() -> UnitOfWork:
        return SqliteUnitOfWork(engine)

    c = Container.__new__(Container)
    c._uow_factory = uow_factory  # type: ignore[attr-defined]
    c.unit_of_work = uow_factory  # type: ignore[attr-defined]
    return c


def _insert_creator(
    container: Container,
    handle: str = "@alice",
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str = "UC_alice",
    follower_count: int | None = 42000,
) -> Creator:
    creator = Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id),
        handle=handle,
        display_name=handle.lstrip("@").title(),
        follower_count=follower_count,
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with container.unit_of_work() as uow:
        return uow.creators.upsert(creator)


class TestCreatorShowCommand:
    def test_show_found(self, container: Container) -> None:
        _insert_creator(container, "@alice", Platform.YOUTUBE)
        with patch("vidscope.cli._support.build_container", return_value=container):
            result = runner.invoke(app, ["creator", "show", "@alice"])
        assert result.exit_code == 0
        assert "@alice" in result.output

    def test_show_not_found(self, container: Container) -> None:
        with patch("vidscope.cli._support.build_container", return_value=container):
            result = runner.invoke(app, ["creator", "show", "@ghost"])
        assert result.exit_code == 1
        assert "no creator" in result.output.lower()

    def test_show_with_platform_flag(self, container: Container) -> None:
        _insert_creator(container, "@tiktokuser", Platform.TIKTOK, "TT_user")
        with patch("vidscope.cli._support.build_container", return_value=container):
            result = runner.invoke(
                app, ["creator", "show", "@tiktokuser", "--platform", "tiktok"]
            )
        assert result.exit_code == 0
        assert "@tiktokuser" in result.output

    def test_show_displays_followers(self, container: Container) -> None:
        _insert_creator(container, "@rich", Platform.YOUTUBE, "UC_rich", follower_count=100000)
        with patch("vidscope.cli._support.build_container", return_value=container):
            result = runner.invoke(app, ["creator", "show", "@rich"])
        assert result.exit_code == 0
        assert "100" in result.output  # follower count present


class TestCreatorListCommand:
    def test_list_empty(self, container: Container) -> None:
        with patch("vidscope.cli._support.build_container", return_value=container):
            result = runner.invoke(app, ["creator", "list"])
        assert result.exit_code == 0
        assert "total creators: 0" in result.output

    def test_list_shows_creators(self, container: Container) -> None:
        _insert_creator(container, "@alice", platform_user_id="alice")
        _insert_creator(container, "@bob", platform_user_id="bob")
        with patch("vidscope.cli._support.build_container", return_value=container):
            result = runner.invoke(app, ["creator", "list"])
        assert result.exit_code == 0
        assert "total creators: 2" in result.output

    def test_list_platform_filter(self, container: Container) -> None:
        _insert_creator(container, "@yt", Platform.YOUTUBE, "yt")
        _insert_creator(container, "@tt", Platform.TIKTOK, "tt")
        with patch("vidscope.cli._support.build_container", return_value=container):
            result = runner.invoke(app, ["creator", "list", "--platform", "youtube"])
        assert result.exit_code == 0
        assert "@yt" in result.output
        assert "@tt" not in result.output


class TestCreatorVideosCommand:
    def test_videos_not_found_creator(self, container: Container) -> None:
        with patch("vidscope.cli._support.build_container", return_value=container):
            result = runner.invoke(app, ["creator", "videos", "@ghost"])
        assert result.exit_code == 1
        assert "no creator" in result.output.lower()

    def test_videos_empty_for_existing_creator(self, container: Container) -> None:
        _insert_creator(container, "@empty")
        with patch("vidscope.cli._support.build_container", return_value=container):
            result = runner.invoke(app, ["creator", "videos", "@empty"])
        assert result.exit_code == 0
        assert "total videos: 0" in result.output
```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/cli/test_creators.py -x -q</automated>
</verify>

<acceptance_criteria>
- `test -f tests/unit/cli/test_creators.py` exit 0
- `python -m uv run pytest tests/unit/cli/test_creators.py -x -q` exit 0
- `python -m uv run pytest -q` exit 0 (suite complète sans régression)
- `python -m uv run ruff check src tests` exit 0
- `python -m uv run mypy src` exit 0
- `python -m uv run lint-imports` exit 0
</acceptance_criteria>

<done>
Tests CLI snapshot verts. `vidscope creator show/list/videos` testés avec CliRunner + container réel.
</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User input → CLI | `handle` et `--platform` viennent de l'utilisateur en clair |
| CLI → Use cases | Le handle est passé tel quel aux use cases (validation SQL via SQLAlchemy) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-S03P02-01 | **Tampering (T)** — handle malveillant injecté | `creator show <handle>` → `find_by_handle` | LOW | accept | SQLAlchemy Core paramétrise. Le handle est une valeur SQL liée, jamais interpolée. Pas de shell expansion. |
| T-S03P02-02 | **DoS (D)** — `--limit` trop élevé | `creator list --limit 9999` | LOW | mitigated | `limit` est clampé à 200 dans le use case + typer Option `max=200`. |
| T-S03P02-03 | **Information Disclosure** — `avatar_url` externe affiché | `creator show` imprime `profile_url` | INFO | accept | C'est une URL stockée depuis yt-dlp — déjà publique. Pas de secret. |
</threat_model>

<verification>
```bash
# Tests CLI creator
python -m uv run pytest tests/unit/cli/test_creators.py -x -q

# Non-régression
python -m uv run pytest -q

# Architecture
python -m uv run lint-imports

# Vérification fonctionnelle (avec vraie DB si disponible)
python -m uv run vidscope creator --help
python -m uv run vidscope creator list --help
python -m uv run vidscope creator show --help
python -m uv run vidscope creator videos --help

# Quality gates
python -m uv run ruff check src tests
python -m uv run mypy src
```
</verification>

<success_criteria>
- `creator_app` Typer sub-app avec 3 commandes : `show`, `list`, `videos`
- `vidscope creator` apparaît dans `vidscope --help`
- `vidscope show <id>` affiche le bloc créateur si `video.creator_id` non nul
- `vidscope list` affiche `creator_id` column
- Tests CLI snapshot verts (≥ 8 tests)
- Suite complète pytest verte
- 9 contrats import-linter verts (cli n'importe pas adapters)
- mypy strict vert, ruff vert
</success_criteria>

<output>
À la fin du plan, créer `.gsd/milestones/M006/slices/S03/S03-P02-SUMMARY.md` résumant :
- Fichiers créés/modifiés
- 3 sous-commandes livrées
- `Video.creator_id` ajouté à l'entity + propagé
- Enrichissement show/list
- Handoff pour P03 (MCP) : les use cases application sont câblés et testés
</output>
</content>
</invoke>
