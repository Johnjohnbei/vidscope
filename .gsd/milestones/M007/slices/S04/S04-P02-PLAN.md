---
plan_id: S04-P02
phase: M007/S04
wave: 8
depends_on: [S04-P01]
requirements: [R046]
files_modified:
  - src/vidscope/mcp/server.py
  - src/vidscope/cli/commands/show.py
  - src/vidscope/application/show_video.py
  - tests/unit/mcp/test_server.py
  - tests/unit/cli/test_show_cmd.py
  - tests/unit/application/test_show_video.py
autonomous: true
---

## Objective

Finaliser la surface utilisateur M007 : (1) nouveau MCP tool `vidscope_list_links` qui expose les liens extraits à un agent IA via JSON-RPC, mirroring des CLI semantics (2) étendre `ShowVideoUseCase` pour retourner également hashtags, mentions, links en complément de video/transcript/frames/analysis/creator ; (3) étendre `vidscope show <id>` CLI pour afficher description, music_track/music_artist, hashtags, mentions (les liens ont déjà leur commande dédiée `vidscope links`). Les extensions de `ShowVideoResult` sont additives pour backward compat.

## Tasks

<task id="T01-show-video-enriched" tdd="true">
  <name>Étendre ShowVideoUseCase + ShowVideoResult avec hashtags/mentions/links + tests</name>

  <read_first>
    - `src/vidscope/application/show_video.py` — fichier complet (60 lignes) à étendre
    - `src/vidscope/ports/repositories.py` — `HashtagRepository.list_for_video`, `MentionRepository.list_for_video`, `LinkRepository.list_for_video` (créés en S01-P02 et S02-P01)
    - `src/vidscope/domain/entities.py` — `Hashtag`, `Mention`, `Link`
    - `.gsd/milestones/M007/M007-CONTEXT.md` §"vidscope show <id>` — affiche automatiquement description/music (sur Video)" + "affiche description + hashtags + music"
  </read_first>

  <behavior>
    - Test 1: `execute(video_id)` retourne un `ShowVideoResult` avec `hashtags`, `mentions`, `links` comme nouveaux champs tuples (vides si aucune donnée).
    - Test 2: `found=False` → les nouveaux champs sont tous `()` vides.
    - Test 3: `found=True` → `hashtags` provient de `uow.hashtags.list_for_video`, `mentions` de `uow.mentions.list_for_video`, `links` de `uow.links.list_for_video` (tous les sources).
    - Test 4: backward compat — les appelants existants qui ne consomment pas ces nouveaux champs continuent de passer (default tuple()).
  </behavior>

  <action>
  Ouvrir `src/vidscope/application/show_video.py`. Remplacer par la version étendue :

  ```python
  """Return the full record of one video — powers ``vidscope show <id>``."""

  from __future__ import annotations

  from dataclasses import dataclass, field

  from vidscope.domain import (
      Analysis,
      Creator,
      Frame,
      Hashtag,
      Link,
      Mention,
      Transcript,
      Video,
      VideoId,
  )
  from vidscope.ports import UnitOfWorkFactory

  __all__ = ["ShowVideoResult", "ShowVideoUseCase"]


  @dataclass(frozen=True, slots=True)
  class ShowVideoResult:
      """Everything known about a single video.

      ``found`` is ``False`` when no video matches the given id; the
      other fields are then empty/None.

      M007 adds ``hashtags``, ``mentions``, ``links`` as tuples; they
      default to empty on miss so existing callers keep working without
      modification.
      """

      found: bool
      video: Video | None = None
      transcript: Transcript | None = None
      frames: tuple[Frame, ...] = ()
      analysis: Analysis | None = None
      creator: Creator | None = None
      hashtags: tuple[Hashtag, ...] = ()
      mentions: tuple[Mention, ...] = ()
      links: tuple[Link, ...] = ()


  class ShowVideoUseCase:
      """Return the full domain record for a video id."""

      def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
          self._uow_factory = unit_of_work_factory

      def execute(self, video_id: int) -> ShowVideoResult:
          """Fetch the full domain record for ``video_id`` in one transaction.

          Joins video metadata + transcript + frames + latest analysis
          + creator + hashtags + mentions + links into a single
          :class:`ShowVideoResult`. Returns ``found=False`` when no
          video matches the id — never raises on missing rows.
          """
          with self._uow_factory() as uow:
              video = uow.videos.get(VideoId(video_id))
              if video is None:
                  return ShowVideoResult(found=False)
              transcript = uow.transcripts.get_for_video(video.id)  # type: ignore[arg-type]
              frames = tuple(uow.frames.list_for_video(video.id))  # type: ignore[arg-type]
              analysis = uow.analyses.get_latest_for_video(video.id)  # type: ignore[arg-type]
              creator: Creator | None = None
              if video.creator_id is not None:
                  creator = uow.creators.get(video.creator_id)
              hashtags = tuple(uow.hashtags.list_for_video(video.id))  # type: ignore[arg-type]
              mentions = tuple(uow.mentions.list_for_video(video.id))  # type: ignore[arg-type]
              links = tuple(uow.links.list_for_video(video.id))  # type: ignore[arg-type]

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
          )
  ```

  **Tests** : étendre `tests/unit/application/test_show_video.py` avec les 4 tests dans `<behavior>`. Ajouter des FakeHashtagRepo/FakeMentionRepo/FakeLinkRepo dans le FakeUoW des tests existants.
  </action>

  <acceptance_criteria>
    - `grep -q "hashtags: tuple\[Hashtag, ...\] = ()" src/vidscope/application/show_video.py` exit 0
    - `grep -q "mentions: tuple\[Mention, ...\] = ()" src/vidscope/application/show_video.py` exit 0
    - `grep -q "links: tuple\[Link, ...\] = ()" src/vidscope/application/show_video.py` exit 0
    - `grep -q "uow.hashtags.list_for_video" src/vidscope/application/show_video.py` exit 0
    - `grep -q "uow.mentions.list_for_video" src/vidscope/application/show_video.py` exit 0
    - `grep -q "uow.links.list_for_video" src/vidscope/application/show_video.py` exit 0
    - `python -m uv run pytest tests/unit/application/test_show_video.py -x -q` exit 0
    - `python -m uv run mypy src` exit 0
  </acceptance_criteria>
</task>

<task id="T02-cli-show-enriched" tdd="true">
  <name>Étendre vidscope show pour afficher description/music/hashtags/mentions + tests</name>

  <read_first>
    - `src/vidscope/cli/commands/show.py` — fichier complet (81 lignes) à étendre avec nouveaux champs
    - `src/vidscope/application/show_video.py` — `ShowVideoResult` étendu en T01
    - tests existants `tests/unit/cli/test_show_cmd.py` (si présent) — pattern CliRunner + mock container
  </read_first>

  <behavior>
    - Test 1: `show 42` sur video avec description non-vide → stdout contient la description (tronquée si longue).
    - Test 2: `show 42` sur video avec music_track="Song", music_artist="X" → stdout contient `music: Song — X` (ou formatage similaire).
    - Test 3: `show 42` sur video avec hashtags → stdout liste les hashtags.
    - Test 4: `show 42` sur video avec mentions → stdout liste les mentions (si présentes).
    - Test 5: baseline — `show 42` sur video sans données M007 → NE DOIT PAS cracher, affiche `description: -`, `music: -`, `hashtags: -`, `mentions: -` (ou "none yet" pour chaque).
    - Test 6: `show 999` sur video inexistant → `fail_user` comme avant (pas de régression).
  </behavior>

  <action>
  Ouvrir `src/vidscope/cli/commands/show.py`. Étendre le rendu entre l'affichage `video #{id}` panel et la section transcript. Remplacer le fichier complet par :

  ```python
  """`vidscope show <id>` — show the full record for a video id."""

  from __future__ import annotations

  import typer
  from rich.panel import Panel

  from vidscope.application.show_video import ShowVideoUseCase
  from vidscope.cli._support import (
      acquire_container,
      console,
      fail_user,
      handle_domain_errors,
  )

  __all__ = ["show_command"]


  _DESCRIPTION_PREVIEW_CHARS = 240


  def show_command(
      video_id: int = typer.Argument(..., help="Numeric id of the video to show."),
  ) -> None:
      """Show the full domain record for one video id."""
      with handle_domain_errors():
          container = acquire_container()
          use_case = ShowVideoUseCase(unit_of_work_factory=container.unit_of_work)
          result = use_case.execute(video_id)

          if not result.found or result.video is None:
              raise fail_user(f"no video with id {video_id}")

          video = result.video
          lines = [
              f"[bold]id:[/bold] {video.id}",
              f"[bold]platform:[/bold] {video.platform.value}",
              f"[bold]platform_id:[/bold] {video.platform_id}",
              f"[bold]url:[/bold] {video.url}",
              f"[bold]title:[/bold] {video.title or '-'}",
              f"[bold]author:[/bold] {video.author or '-'}",
              f"[bold]duration:[/bold] "
              f"{f'{video.duration:.1f}s' if video.duration else '-'}",
              f"[bold]media_key:[/bold] {video.media_key or '-'}",
          ]
          console.print(
              Panel.fit(
                  "\n".join(lines),
                  title=f"[bold]video #{video.id}[/bold]",
                  border_style="cyan",
              )
          )

          # M007: description + music + hashtags + mentions
          if video.description:
              preview = video.description
              if len(preview) > _DESCRIPTION_PREVIEW_CHARS:
                  preview = preview[: _DESCRIPTION_PREVIEW_CHARS - 1] + "…"
              console.print(f"[bold]description:[/bold] {preview}")
          else:
              console.print("[dim]description: none[/dim]")

          if video.music_track or video.music_artist:
              track = video.music_track or "-"
              artist = video.music_artist or "-"
              console.print(f"[bold]music:[/bold] {track} — {artist}")
          else:
              console.print("[dim]music: none[/dim]")

          if result.hashtags:
              tags = ", ".join(f"#{h.tag}" for h in result.hashtags)
              console.print(f"[bold]hashtags:[/bold] {tags}")
          else:
              console.print("[dim]hashtags: none[/dim]")

          if result.mentions:
              handles = ", ".join(f"@{m.handle}" for m in result.mentions)
              console.print(f"[bold]mentions:[/bold] {handles}")
          else:
              console.print("[dim]mentions: none[/dim]")

          console.print(f"[bold]links:[/bold] {len(result.links)}")

          if result.transcript is not None:
              t = result.transcript
              console.print(
                  f"[bold]transcript:[/bold] {t.language.value}, "
                  f"{len(t.full_text)} chars, {len(t.segments)} segments"
              )
          else:
              console.print("[dim]transcript: none yet[/dim]")

          console.print(f"[bold]frames:[/bold] {len(result.frames)}")

          if result.analysis is not None:
              a = result.analysis
              console.print(
                  f"[bold]analysis:[/bold] {a.provider}, "
                  f"score={a.score if a.score is not None else '-'}, "
                  f"{len(a.keywords)} keywords, {len(a.topics)} topics"
              )
          else:
              console.print("[dim]analysis: none yet[/dim]")

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

  **Tests** : étendre `tests/unit/cli/test_show_cmd.py` avec les 6 tests dans `<behavior>`. Pattern : mock `ShowVideoUseCase.execute` pour retourner un `ShowVideoResult` configuré, CliRunner invoke, assert sur `result.stdout`.
  </action>

  <acceptance_criteria>
    - `grep -q "video.description" src/vidscope/cli/commands/show.py` exit 0
    - `grep -q "video.music_track" src/vidscope/cli/commands/show.py` exit 0
    - `grep -q "result.hashtags" src/vidscope/cli/commands/show.py` exit 0
    - `grep -q "result.mentions" src/vidscope/cli/commands/show.py` exit 0
    - `grep -q "result.links" src/vidscope/cli/commands/show.py` exit 0
    - `grep -q "_DESCRIPTION_PREVIEW_CHARS" src/vidscope/cli/commands/show.py` exit 0
    - `python -m uv run pytest tests/unit/cli/test_show_cmd.py -x -q` exit 0
    - `python -m uv run python -c "from typer.testing import CliRunner; from vidscope.cli.app import app; r = CliRunner(); res = r.invoke(app, ['show', '--help']); assert res.exit_code == 0; print('OK')"` affiche `OK`
    - `python -m uv run ruff check src tests` exit 0
    - `python -m uv run mypy src` exit 0
  </acceptance_criteria>
</task>

<task id="T03-mcp-list-links-tool" tdd="true">
  <name>Ajouter vidscope_list_links MCP tool + tests unit</name>

  <read_first>
    - `src/vidscope/mcp/server.py` — fichier complet (373 lignes) ; en particulier lignes 104-349 où chaque `@mcp.tool()` est enregistré dans `build_mcp_server`. Patron `vidscope_suggest_related` (lignes 234-270) et `vidscope_get_video` (lignes 175-216) à miroir pour le nouveau tool. Lignes 43-55 pour les imports d'use cases
    - `src/vidscope/application/list_links.py` (créé en S04-P01) — `ListLinksUseCase` à câbler
    - `src/vidscope/domain/entities.py` — `Link` entity pour construire le DTO
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"Pattern MCP tool (vidscope_list_links)"
    - `.gsd/milestones/M007/M007-CONTEXT.md` §specifics "MCP tool `vidscope_list_links` expose les liens à un agent IA"
    - tests existants `tests/unit/mcp/test_server.py` pour patron de test `FastMCP` + registry access
  </read_first>

  <behavior>
    - Test 1: appel `vidscope_list_links(video_id=42)` via le tool retourne `{"video_id": 42, "found": True, "links": [{"url": "...", "normalized_url": "...", "source": "...", "position_ms": ...}, ...]}`.
    - Test 2: video introuvable → `{"found": False, "video_id": video_id}` (pas d'exception).
    - Test 3: filtre source — `vidscope_list_links(video_id=42, source="description")` appelle `ListLinksUseCase.execute(video_id=42, source="description")`.
    - Test 4: DomainError → relevée comme `ValueError` (pattern standard).
  </behavior>

  <action>
  Ouvrir `src/vidscope/mcp/server.py`. Effectuer 2 modifications :

  **Étape A — Étendre les imports use cases** (lignes 45-53) pour inclure `ListLinksUseCase` :

  ```python
  from vidscope.application import (
      GetCreatorUseCase,
      GetStatusUseCase,
      IngestVideoUseCase,
      ListLinksUseCase,
      ListVideosUseCase,
      SearchLibraryUseCase,
      ShowVideoUseCase,
      SuggestRelatedUseCase,
  )
  ```

  **Étape B — Enregistrer le nouveau tool** APRÈS `vidscope_get_status` (vers ligne 305) et AVANT `# The closures above...` (ligne 343). Insérer :

  ```python
      @mcp.tool()
      def vidscope_list_links(
          video_id: int, source: str | None = None
      ) -> dict[str, Any]:
          """List URLs extracted from a video's description + transcript.

          Returns every :class:`Link` persisted by the
          :class:`MetadataExtractStage` (M007/S03). ``source`` optionally
          filters by origin: ``"description"`` for caption-sourced URLs,
          ``"transcript"`` for transcript-sourced, ``"ocr"`` reserved
          for M008. Omit ``source`` to get every URL.

          Returns ``{"found": False, "video_id": video_id, "links": []}``
          when no video matches the id — never raises on a miss.
          """
          try:
              use_case = ListLinksUseCase(
                  unit_of_work_factory=container.unit_of_work
              )
              result = use_case.execute(video_id, source=source)
          except DomainError as exc:
              raise ValueError(str(exc)) from exc

          if not result.found:
              return {
                  "found": False,
                  "video_id": video_id,
                  "links": [],
              }

          return {
              "found": True,
              "video_id": result.video_id,
              "source_filter": source,
              "links": [
                  {
                      "id": link.id,
                      "url": link.url,
                      "normalized_url": link.normalized_url,
                      "source": link.source,
                      "position_ms": link.position_ms,
                  }
                  for link in result.links
              ],
          }
  ```

  **Étape C — Tests**. Étendre `tests/unit/mcp/test_server.py` avec les 4 tests. Pattern : `build_mcp_server(container)` avec un container stub construit via le pattern existant (probablement `_ContainerStub` avec une uow factory qui retourne un `FakeUoW`). Appeler le tool via `mcp._tool_manager._tools["vidscope_list_links"].fn(video_id=42, source=None)` ou via la méthode call_tool publique (voir le test existant `vidscope_suggest_related` pour le pattern exact utilisé dans ce codebase).
  </action>

  <acceptance_criteria>
    - `grep -q "ListLinksUseCase" src/vidscope/mcp/server.py` exit 0
    - `grep -q "def vidscope_list_links" src/vidscope/mcp/server.py` exit 0
    - `grep -q "source_filter" src/vidscope/mcp/server.py` exit 0 (pour documenter le filtre source dans la réponse)
    - `grep -q 'key "normalized_url"' src/vidscope/mcp/server.py || grep -q '"normalized_url":' src/vidscope/mcp/server.py` exit 0
    - `python -m uv run python -c "
  from vidscope.mcp.server import build_mcp_server
  from vidscope.infrastructure.container import build_container
  c = build_container()
  server = build_mcp_server(c)
  # Ensure the tool is registered (name visible via the tool manager)
  tools = server._tool_manager.list_tools() if hasattr(server._tool_manager, 'list_tools') else server._tool_manager._tools
  names = [t.name if hasattr(t, 'name') else t for t in tools]
  assert 'vidscope_list_links' in names, names
  print('OK registered')
  "` affiche `OK registered`
    - `python -m uv run pytest tests/unit/mcp/test_server.py -x -q` exit 0
    - `python -m uv run pytest -q` exit 0 (aucune régression)
    - `python -m uv run ruff check src tests` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (contrat `mcp-has-no-adapters` reste vert)
  </acceptance_criteria>
</task>

## Verification Criteria

```bash
# Tests
python -m uv run pytest tests/unit/application/test_show_video.py -x -q
python -m uv run pytest tests/unit/cli/test_show_cmd.py -x -q
python -m uv run pytest tests/unit/mcp/test_server.py -x -q

# Smoke test : le tool MCP est enregistré
python -m uv run python -c "
from vidscope.mcp.server import build_mcp_server
from vidscope.infrastructure.container import build_container
c = build_container()
server = build_mcp_server(c)
tools = server._tool_manager._tools
assert 'vidscope_list_links' in tools, list(tools.keys())
print('OK tools:', list(tools.keys()))
"

# Suite complète + quality gates
python -m uv run pytest -q
python -m uv run ruff check src tests
python -m uv run mypy src
python -m uv run lint-imports
```

## Must-Haves

- `ShowVideoResult` gagne 3 champs tuples : `hashtags: tuple[Hashtag, ...]`, `mentions: tuple[Mention, ...]`, `links: tuple[Link, ...]`, defaults `()`.
- `ShowVideoUseCase.execute` lit les 3 nouvelles relations via `uow.*.list_for_video` dans la même transaction.
- `vidscope show <id>` CLI affiche description (avec tronquage 240 chars), music track/artist, hashtags (avec `#` prefix), mentions (avec `@` prefix), total links count.
- Nouveau MCP tool `vidscope_list_links(video_id, source=None)` enregistré via `build_mcp_server`.
- Pattern DomainError trap identique aux autres tools (re-raise as ValueError).
- Retour JSON contient `{"found": bool, "video_id": int, "links": [{"url", "normalized_url", "source", "position_ms", "id"}...]}`.
- Tests application + CLI + MCP green (≥ 4 tests par composant).
- Les 10 contrats `.importlinter` restent verts.

## Threat Model

| # | Catégorie STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-S04P02-01 | **Information Disclosure (I)** — MCP expose URLs à un agent IA externe | `vidscope_list_links` tool | LOW | accept | Local MCP server stdio (R020, R032). Les URLs sont déjà publiques (venant de captions) ; agent IA = assistant utilisateur par design. Single-user local (R032). |
| T-S04P02-02 | **Tampering (T)** — `video_id` négatif/injection depuis MCP | `vidscope_list_links(video_id=...)` | LOW | mitigate | Typing `int` côté signature MCP ; si `video_id < 0`, le repo retourne `None` (video not found). SQLAlchemy binding protège contre injection. |
| T-S04P02-03 | **Denial of Service (D)** — description très longue dans `vidscope show` stdout | `show_command` | LOW | mitigate | Troncature à `_DESCRIPTION_PREVIEW_CHARS = 240` avant affichage. La description complète reste en DB, accessible via d'autres moyens. |
| T-S04P02-04 | **Information Disclosure (I)** — `show` affiche toutes les mentions | CLI output | LOW | accept | Les @handles sont publics dans la caption. Pas de PII ajoutée. |
| T-S04P02-05 | **Repudiation (R)** — MCP tool ne log pas qui a appelé quoi | `vidscope_list_links` | NONE | accept | Single-user (R032), no audit trail needed. |
