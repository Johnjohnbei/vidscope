---
plan_id: S04-P01
phase: M007/S04
wave: 7
depends_on: [S03-P02]
requirements: [R046]
files_modified:
  - src/vidscope/application/search_library.py
  - src/vidscope/application/list_links.py
  - src/vidscope/application/__init__.py
  - src/vidscope/cli/commands/search.py
  - src/vidscope/cli/commands/links.py
  - src/vidscope/cli/app.py
  - tests/unit/application/test_search_library.py
  - tests/unit/application/test_list_links.py
  - tests/unit/cli/test_search_cmd.py
  - tests/unit/cli/test_links_cmd.py
autonomous: true
---

## Objective

Surfacer M007 au CLI : (1) étendre `SearchLibraryUseCase` pour accepter 4 facettes (`hashtag`, `mention`, `has_link`, `music_track`) via EXISTS subqueries AND-implicite (D-04), préservant la FTS5 query de base et intersectant les ensembles de video_ids (2) nouveau `ListLinksUseCase` qui retourne la liste triée des `Link` d'un video (tous les sources), avec filtre optionnel sur `source` (3) étendre `vidscope search <query>` avec `--hashtag`, `--mention`, `--has-link`, `--music-track` options Typer ; appel passe les facettes au use case (4) nouveau `vidscope links <id>` command qui affiche un Rich table avec `url | source | position_ms`. Tests unitaires couvrent chaque facette isolément + AND implicite + ListLinksUseCase.

## Tasks

<task id="T01-search-library-facets" tdd="true">
  <name>Étendre SearchLibraryUseCase avec 4 facettes + tests</name>

  <read_first>
    - `src/vidscope/application/search_library.py` — fichier complet (simple : 44 lignes) — à étendre avec kwargs de filtre et intersection de video_ids
    - `src/vidscope/ports/pipeline.py` lignes 465-501 — `SearchResult` dataclass et `SearchIndex` Protocol (retourne `list[SearchResult]`)
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"SearchLibraryUseCase — extension avec facettes EXISTS subqueries"
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-04 (AND implicite, exact match : `--hashtag` lowercase canonique, `--mention` case-insensitive, `--has-link` booléen, `--music-track` exact match — LIKE au discretion Claude)
    - `src/vidscope/ports/repositories.py` — `HashtagRepository.find_video_ids_by_tag`, `MentionRepository.find_video_ids_by_handle`, `LinkRepository.find_video_ids_with_any_link`, `VideoRepository.list_recent` — à utiliser pour construire la liste des candidats par facette
  </read_first>

  <behavior>
    - Test 1 (baseline): `execute("cooking")` sans facette → comportement inchangé (retourne FTS5 hits).
    - Test 2 (hashtag): `execute("", hashtag="coding")` retourne les `SearchResult` dont `video_id` est dans `hashtags.find_video_ids_by_tag("coding")`.
    - Test 3 (hashtag canonicalisation): `execute("", hashtag="#Coding")` == `execute("", hashtag="coding")` (repo canonicalise).
    - Test 4 (mention): `execute("", mention="@alice")` retourne les hits dont `video_id` est dans `mentions.find_video_ids_by_handle("alice")`.
    - Test 5 (has_link): `execute("", has_link=True)` retourne uniquement les hits dont `video_id` est dans `links.find_video_ids_with_any_link()`.
    - Test 6 (music_track): `execute("", music_track="Original sound")` retourne les hits dont la row `videos.music_track == "Original sound"` (exact match). Nécessite une nouvelle méthode `VideoRepository.find_by_music_track` OU une query sur les facettes connues (voir Étape A pour choix d'implémentation).
    - Test 7 (AND implicite - 2 facettes): `execute("", hashtag="coding", mention="@alice")` retourne l'INTERSECTION des deux ensembles.
    - Test 8 (AND avec query): `execute("tutorial", hashtag="coding")` retourne les hits `search("tutorial")` ∩ `find_video_ids_by_tag("coding")`.
    - Test 9 (query vide + has_link): `execute("", has_link=True)` NE DOIT PAS appeler `search_index.search("")` (empty query → empty results côté FTS5) — le use case synthétise des hits ou retourne `list[SearchResult]` dégradé via `VideoRepository.get` pour chaque video_id. **Choix d'implémentation : lorsqu'aucune query n'est donnée mais au moins une facette, produire un `SearchResult` synthétique par video matchant avec `source="video"`, `snippet="<video title or 'Matched facets'>"`, `rank=1.0`.**
    - Test 10 (aucun résultat): facette qui retourne `[]` → `SearchResult` list vide.
  </behavior>

  <action>
  **Étape A — Étendre `src/vidscope/application/search_library.py`**. Remplacer le fichier complet par :

  ```python
  """Full-text search + M007 facets — ``vidscope search``."""

  from __future__ import annotations

  from dataclasses import dataclass

  from vidscope.domain import VideoId
  from vidscope.ports import SearchResult, UnitOfWorkFactory

  __all__ = ["SearchLibraryResult", "SearchLibraryUseCase"]


  @dataclass(frozen=True, slots=True)
  class SearchLibraryResult:
      """Result of :meth:`SearchLibraryUseCase.execute`.

      ``query`` is echoed back so the CLI can display "results for X".
      ``hits`` is ordered by BM25 rank (best match first) and capped at
      the use case's ``limit``. Empty tuple is a valid state and means
      no documents matched the query or facets.
      """

      query: str
      hits: tuple[SearchResult, ...]


  class SearchLibraryUseCase:
      """Run a FTS5 query + M007 facet filters through the UnitOfWork.

      Facets (per M007 CONTEXT §D-04):

      - ``hashtag``  — exact match after canonicalisation (#Coding == coding)
      - ``mention``  — exact match after canonicalisation (@Alice == alice)
      - ``has_link`` — boolean: at least one extracted URL
      - ``music_track`` — exact match on ``videos.music_track``

      Multi-facet semantics: AND implicite — each facet further narrows
      the result set (set intersection on ``video_id``).

      When ``query`` is empty AND at least one facet is set, the use case
      synthesises :class:`SearchResult` entries (source="video", rank=1.0,
      snippet=<title>) for each matched video so the CLI can still render
      a useful output.
      """

      def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
          self._uow_factory = unit_of_work_factory

      def execute(
          self,
          query: str,
          *,
          limit: int = 20,
          hashtag: str | None = None,
          mention: str | None = None,
          has_link: bool = False,
          music_track: str | None = None,
      ) -> SearchLibraryResult:
          """Search transcripts + analyses + facets. Returns up to
          ``limit`` matches ranked by BM25 (or facet order when query is
          empty). ``limit`` is clamped to [1, 200].
          """
          limit = max(1, min(limit, 200))
          any_facet = (
              hashtag is not None
              or mention is not None
              or has_link
              or music_track is not None
          )
          query_text = query.strip() if query else ""

          with self._uow_factory() as uow:
              # 1. Collect the candidate video id set per active facet.
              #    Each set is None when the facet is inactive ("no
              #    restriction") — intersection semantics below.
              facet_sets: list[set[int]] = []

              if hashtag is not None:
                  ids = uow.hashtags.find_video_ids_by_tag(hashtag, limit=1000)
                  facet_sets.append({int(vid) for vid in ids})

              if mention is not None:
                  ids = uow.mentions.find_video_ids_by_handle(
                      mention, limit=1000
                  )
                  facet_sets.append({int(vid) for vid in ids})

              if has_link:
                  ids = uow.links.find_video_ids_with_any_link(limit=1000)
                  facet_sets.append({int(vid) for vid in ids})

              if music_track is not None:
                  # Exact match on videos.music_track. No existing repo
                  # method → list_recent + filter in memory. Bounded by
                  # limit*10 to keep worst case small on libraries with
                  # many unrelated videos.
                  candidates = uow.videos.list_recent(limit=1000)
                  facet_sets.append(
                      {
                          int(v.id)
                          for v in candidates
                          if v.id is not None
                          and v.music_track == music_track
                      }
                  )

              # Intersection of all active facet sets. Empty list means
              # no facet was active — no restriction.
              if facet_sets:
                  allowed_ids: set[int] | None = facet_sets[0]
                  for s in facet_sets[1:]:
                      allowed_ids = allowed_ids & s
              else:
                  allowed_ids = None

              # 2. Dispatch on query presence:
              if query_text:
                  # Overfetch a bit so the facet filter still has room to
                  # return `limit` results after narrowing.
                  raw_hits = uow.search_index.search(
                      query_text, limit=limit * 5 if any_facet else limit
                  )
                  if allowed_ids is not None:
                      raw_hits = [
                          h for h in raw_hits if int(h.video_id) in allowed_ids
                      ]
                  hits = tuple(raw_hits[:limit])
              elif any_facet and allowed_ids is not None:
                  # Synthesise SearchResult entries (one per matched
                  # video) because the FTS5 index is empty-query-hostile.
                  synth: list[SearchResult] = []
                  for vid in list(allowed_ids)[:limit]:
                      video = uow.videos.get(VideoId(vid))
                      if video is None:
                          continue
                      synth.append(
                          SearchResult(
                              video_id=VideoId(vid),
                              source="video",
                              snippet=video.title or f"video #{vid}",
                              rank=1.0,
                          )
                      )
                  hits = tuple(synth)
              else:
                  hits = ()

          return SearchLibraryResult(query=query_text, hits=hits)
  ```

  **Étape B — Tests**. Étendre `tests/unit/application/test_search_library.py` avec les 10 tests décrits dans `<behavior>`. Pattern : `FakeUoW` avec `FakeHashtagRepo.find_video_ids_by_tag`, `FakeMentionRepo.find_video_ids_by_handle`, `FakeLinkRepo.find_video_ids_with_any_link`, `FakeVideoRepo.list_recent` + `.get`, `FakeSearchIndex.search`, chacun contrôlable par test.
  </action>

  <acceptance_criteria>
    - `grep -q "hashtag: str | None = None" src/vidscope/application/search_library.py` exit 0
    - `grep -q "mention: str | None = None" src/vidscope/application/search_library.py` exit 0
    - `grep -q "has_link: bool = False" src/vidscope/application/search_library.py` exit 0
    - `grep -q "music_track: str | None = None" src/vidscope/application/search_library.py` exit 0
    - `grep -q "find_video_ids_by_tag" src/vidscope/application/search_library.py` exit 0
    - `grep -q "find_video_ids_by_handle" src/vidscope/application/search_library.py` exit 0
    - `grep -q "find_video_ids_with_any_link" src/vidscope/application/search_library.py` exit 0
    - `grep -c "def test_" tests/unit/application/test_search_library.py` retourne un nombre ≥ 10
    - `python -m uv run pytest tests/unit/application/test_search_library.py -x -q` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (application n'importe pas d'adapter)
  </acceptance_criteria>
</task>

<task id="T02-list-links-use-case" tdd="true">
  <name>Créer ListLinksUseCase + tests</name>

  <read_first>
    - `src/vidscope/application/show_video.py` — patron use case court à miroir (ShowVideoUseCase : 60 lignes, simple DTO)
    - `src/vidscope/application/list_videos.py` — patron list use case
    - `src/vidscope/ports/repositories.py` — `LinkRepository.list_for_video(video_id, *, source=None)` (créé en S02-P01)
    - `src/vidscope/domain/entities.py` — `Link` entity
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"`vidscope links <id>` — nouvelle commande"
    - `.gsd/milestones/M007/M007-CONTEXT.md` §specifics "vidscope links <id> est la commande phare de M007"
  </read_first>

  <behavior>
    - Test 1: `execute(video_id=42)` sans filtre retourne tous les Link triés par `id` asc (ordre d'insertion).
    - Test 2: `execute(video_id=42, source="description")` filtre par source.
    - Test 3: `execute(video_id=42, source="transcript")` filtre par source.
    - Test 4: `execute(video_id=999)` sur video inexistant → `ListLinksResult(video_id=999, links=(), found=False)` (pas d'exception).
    - Test 5: `execute(video_id=42)` sur video existant sans link → `ListLinksResult(found=True, links=())`.
    - Test 6: `found` est True quand `uow.videos.get(video_id)` retourne un video, même si la liste de liens est vide.
  </behavior>

  <action>
  **Étape A — Créer `src/vidscope/application/list_links.py`** :

  ```python
  """List extracted links for a video — powers ``vidscope links <id>``."""

  from __future__ import annotations

  from dataclasses import dataclass

  from vidscope.domain import Link, VideoId
  from vidscope.ports import UnitOfWorkFactory

  __all__ = ["ListLinksResult", "ListLinksUseCase"]


  @dataclass(frozen=True, slots=True)
  class ListLinksResult:
      """Outcome of :meth:`ListLinksUseCase.execute`.

      ``found`` is ``False`` when no video matches the given id — the
      CLI surfaces a "no video" message in that case. When ``found`` is
      ``True`` but ``links`` is empty, the video exists but the
      extractor found no URL.
      """

      video_id: int
      found: bool
      links: tuple[Link, ...] = ()


  class ListLinksUseCase:
      """Return every :class:`Link` for a video, optionally filtered by source."""

      def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
          self._uow_factory = unit_of_work_factory

      def execute(
          self,
          video_id: int,
          *,
          source: str | None = None,
      ) -> ListLinksResult:
          """Fetch links for ``video_id``, optionally filtered by source
          (``"description"``, ``"transcript"``, ``"ocr"``)."""
          with self._uow_factory() as uow:
              video = uow.videos.get(VideoId(video_id))
              if video is None:
                  return ListLinksResult(video_id=video_id, found=False)
              links = tuple(
                  uow.links.list_for_video(VideoId(video_id), source=source)
              )
          return ListLinksResult(
              video_id=video_id,
              found=True,
              links=links,
          )
  ```

  **Étape B — Mettre à jour `src/vidscope/application/__init__.py`** pour re-exporter `ListLinksUseCase` et `ListLinksResult`. Ajouter à `__all__`.

  **Étape C — Tests**. Créer `tests/unit/application/test_list_links.py` avec les 6 tests. Pattern : `FakeUoW.videos.get`, `FakeUoW.links.list_for_video` contrôlables.
  </action>

  <acceptance_criteria>
    - `test -f src/vidscope/application/list_links.py`
    - `grep -q "class ListLinksUseCase:" src/vidscope/application/list_links.py` exit 0
    - `grep -q "class ListLinksResult:" src/vidscope/application/list_links.py` exit 0
    - `grep -q "source: str | None = None" src/vidscope/application/list_links.py` exit 0
    - `grep -q "ListLinksUseCase" src/vidscope/application/__init__.py` exit 0
    - `test -f tests/unit/application/test_list_links.py`
    - `grep -c "def test_" tests/unit/application/test_list_links.py` retourne un nombre ≥ 6
    - `python -m uv run pytest tests/unit/application/test_list_links.py -x -q` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0
  </acceptance_criteria>
</task>

<task id="T03-cli-commands-search-and-links" tdd="true">
  <name>Étendre vidscope search avec 4 facettes + nouvelle commande vidscope links + tests CLI</name>

  <read_first>
    - `src/vidscope/cli/commands/search.py` — fichier complet (60 lignes) — à étendre avec 4 Typer options
    - `src/vidscope/cli/commands/list.py` — patron command court, typer.Option syntax, rich Table
    - `src/vidscope/cli/commands/show.py` — patron command avec `fail_user` si video introuvable
    - `src/vidscope/cli/app.py` — localiser l'enregistrement des commands Typer (app.command()... pour `search`, `list`, etc.) pour ajouter `links`
    - `src/vidscope/cli/_support.py` (probablement) — `acquire_container`, `console`, `handle_domain_errors`, `fail_user`
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-04 (facettes options) et §specifics (`vidscope links <id>`)
    - tests CLI existants `tests/unit/cli/test_search_cmd.py` (si existe) pour pattern CliRunner
  </read_first>

  <behavior>
    - Test 1 (search): `CliRunner.invoke(app, ["search", "cooking"])` exit 0 — comportement baseline inchangé.
    - Test 2 (search --hashtag): `CliRunner.invoke(app, ["search", "cooking", "--hashtag", "recipe"])` passe `hashtag="recipe"` au use case.
    - Test 3 (search --mention): `--mention @alice` passe `mention="@alice"`.
    - Test 4 (search --has-link): `--has-link` passe `has_link=True`.
    - Test 5 (search --music-track): `--music-track "Original sound"` passe `music_track="Original sound"`.
    - Test 6 (search AND facettes): `search "cooking" --hashtag recipe --has-link` appelle `execute(query="cooking", hashtag="recipe", has_link=True)`.
    - Test 7 (links <id>): `CliRunner.invoke(app, ["links", "42"])` exit 0 et affiche une table des URLs.
    - Test 8 (links inexistant): `CliRunner.invoke(app, ["links", "999"])` sur video inexistant sort avec message d'erreur et exit != 0.
    - Test 9 (links --source): `links 42 --source description` passe `source="description"`.
  </behavior>

  <action>
  **Étape A — Étendre `src/vidscope/cli/commands/search.py`** :

  ```python
  """`vidscope search <query>` — FTS5 + M007 facets."""

  from __future__ import annotations

  import typer
  from rich.table import Table

  from vidscope.application.search_library import SearchLibraryUseCase
  from vidscope.cli._support import acquire_container, console, handle_domain_errors

  __all__ = ["search_command"]


  def search_command(
      query: str = typer.Argument(
          "",
          help="FTS5 query to run against the index. Empty when using facets only.",
      ),
      limit: int = typer.Option(
          20,
          "--limit",
          "-n",
          help="Maximum number of hits to display.",
          min=1,
          max=200,
      ),
      hashtag: str | None = typer.Option(
          None,
          "--hashtag",
          help="Filter videos carrying this hashtag (exact match after "
               "canonicalisation, #Coding == coding).",
      ),
      mention: str | None = typer.Option(
          None,
          "--mention",
          help="Filter videos mentioning this @handle (case-insensitive).",
      ),
      has_link: bool = typer.Option(
          False,
          "--has-link",
          help="Only videos with at least one extracted URL.",
      ),
      music_track: str | None = typer.Option(
          None,
          "--music-track",
          help="Filter videos whose music_track field matches exactly.",
      ),
  ) -> None:
      """Run a full-text query + optional facets through the library."""
      with handle_domain_errors():
          container = acquire_container()
          use_case = SearchLibraryUseCase(
              unit_of_work_factory=container.unit_of_work
          )
          result = use_case.execute(
              query,
              limit=limit,
              hashtag=hashtag,
              mention=mention,
              has_link=has_link,
              music_track=music_track,
          )

          facets: list[str] = []
          if hashtag:
              facets.append(f"#{hashtag.lstrip('#')}")
          if mention:
              facets.append(f"@{mention.lstrip('@')}")
          if has_link:
              facets.append("has-link")
          if music_track:
              facets.append(f"music={music_track}")
          facet_str = (" [" + ", ".join(facets) + "]") if facets else ""

          console.print(
              f"[bold]query:[/bold] {result.query!r}{facet_str}   "
              f"[bold]hits:[/bold] {len(result.hits)}"
          )

          if not result.hits:
              console.print(
                  "[dim]No matches. Try broader query or fewer facets.[/dim]"
              )
              return

          table = Table(title="Search results", show_header=True)
          table.add_column("video", justify="right", style="dim")
          table.add_column("source")
          table.add_column("rank", justify="right")
          table.add_column("snippet", overflow="fold")

          for hit in result.hits:
              table.add_row(
                  str(hit.video_id),
                  hit.source,
                  f"{hit.rank:.2f}",
                  hit.snippet,
              )

          console.print(table)
  ```

  **Étape B — Créer `src/vidscope/cli/commands/links.py`** :

  ```python
  """`vidscope links <id>` — list extracted URLs for a video."""

  from __future__ import annotations

  import typer
  from rich.table import Table

  from vidscope.application.list_links import ListLinksUseCase
  from vidscope.cli._support import (
      acquire_container,
      console,
      fail_user,
      handle_domain_errors,
  )

  __all__ = ["links_command"]


  def links_command(
      video_id: int = typer.Argument(..., help="Numeric id of the video."),
      source: str | None = typer.Option(
          None,
          "--source",
          help="Filter by source: description, transcript, or ocr.",
      ),
  ) -> None:
      """List every URL extracted from a video's description + transcript."""
      with handle_domain_errors():
          container = acquire_container()
          use_case = ListLinksUseCase(
              unit_of_work_factory=container.unit_of_work
          )
          result = use_case.execute(video_id, source=source)

          if not result.found:
              raise fail_user(f"no video with id {video_id}")

          console.print(
              f"[bold]video:[/bold] {result.video_id}   "
              f"[bold]links:[/bold] {len(result.links)}"
              + (f"   [bold]source:[/bold] {source}" if source else "")
          )

          if not result.links:
              console.print("[dim]No URLs extracted for this video.[/dim]")
              return

          table = Table(title=f"Links for video #{result.video_id}", show_header=True)
          table.add_column("id", justify="right", style="dim")
          table.add_column("source")
          table.add_column("url", overflow="fold")
          table.add_column("position", justify="right")

          for link in result.links:
              pos = f"{link.position_ms}ms" if link.position_ms is not None else "-"
              table.add_row(
                  str(link.id) if link.id is not None else "-",
                  link.source,
                  link.url,
                  pos,
              )

          console.print(table)
  ```

  **Étape C — Enregistrer la nouvelle command dans `src/vidscope/cli/app.py`**. Localiser le bloc qui enregistre les commands (`app.command()(search_command)` etc.). Ajouter :

  ```python
  from vidscope.cli.commands.links import links_command
  ...
  app.command("links")(links_command)
  ```

  **Étape D — Tests CLI**. Étendre `tests/unit/cli/test_search_cmd.py` avec les 6 tests search, et créer `tests/unit/cli/test_links_cmd.py` avec les 3 tests links. Pattern : `CliRunner` de Typer + container stub injecté via le mécanisme existant (chercher `acquire_container` patch pattern dans les tests CLI existants).
  </action>

  <acceptance_criteria>
    - `grep -q -- "--hashtag" src/vidscope/cli/commands/search.py` exit 0
    - `grep -q -- "--mention" src/vidscope/cli/commands/search.py` exit 0
    - `grep -q -- "--has-link" src/vidscope/cli/commands/search.py` exit 0
    - `grep -q -- "--music-track" src/vidscope/cli/commands/search.py` exit 0
    - `grep -q "use_case.execute(" src/vidscope/cli/commands/search.py` exit 0
    - `grep -q "hashtag=hashtag" src/vidscope/cli/commands/search.py` exit 0
    - `test -f src/vidscope/cli/commands/links.py`
    - `grep -q "def links_command" src/vidscope/cli/commands/links.py` exit 0
    - `grep -q "ListLinksUseCase" src/vidscope/cli/commands/links.py` exit 0
    - `grep -q "links_command" src/vidscope/cli/app.py` exit 0
    - `grep -q 'app.command("links")' src/vidscope/cli/app.py` exit 0
    - `python -m uv run python -c "from typer.testing import CliRunner; from vidscope.cli.app import app; r = CliRunner(); res = r.invoke(app, ['search', '--help']); assert res.exit_code == 0; assert '--hashtag' in res.stdout; assert '--has-link' in res.stdout; print('OK search')"` affiche `OK search`
    - `python -m uv run python -c "from typer.testing import CliRunner; from vidscope.cli.app import app; r = CliRunner(); res = r.invoke(app, ['links', '--help']); assert res.exit_code == 0; print('OK links')"` affiche `OK links`
    - `python -m uv run pytest tests/unit/cli/test_search_cmd.py -x -q` exit 0
    - `python -m uv run pytest tests/unit/cli/test_links_cmd.py -x -q` exit 0
    - `python -m uv run pytest -q` exit 0 (suite globale)
    - `python -m uv run ruff check src tests` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0
  </acceptance_criteria>
</task>

## Verification Criteria

```bash
# Tests
python -m uv run pytest tests/unit/application/test_search_library.py -x -q
python -m uv run pytest tests/unit/application/test_list_links.py -x -q
python -m uv run pytest tests/unit/cli/test_search_cmd.py -x -q
python -m uv run pytest tests/unit/cli/test_links_cmd.py -x -q

# Smoke CLI help
python -m uv run vidscope search --help 2>&1 | grep -E "hashtag|mention|has-link|music-track"
python -m uv run vidscope links --help 2>&1 | grep -q "source"

# Suite complète + quality gates
python -m uv run pytest -q
python -m uv run ruff check src tests
python -m uv run mypy src
python -m uv run lint-imports
```

## Must-Haves

- `SearchLibraryUseCase.execute(query, *, limit, hashtag, mention, has_link, music_track)` avec signature étendue.
- AND implicite : intersection des video_ids par facette active.
- `hashtag`/`mention` sont canonicalisés par leurs repos respectifs (D-04).
- Synthèse `SearchResult` quand query vide + facettes actives.
- Nouveau `ListLinksUseCase` avec `execute(video_id, *, source)` retournant `ListLinksResult(video_id, found, links)`.
- CLI `vidscope search` expose `--hashtag`, `--mention`, `--has-link`, `--music-track`.
- CLI `vidscope links <id>` nouvelle commande affiche les URLs en Rich table.
- Tests application (≥ 10 + ≥ 6) et CLI (≥ 6 + ≥ 3).
- Les 10 contrats `.importlinter` restent verts.

## Threat Model

| # | Catégorie STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-S04P01-01 | **Tampering (T)** — injection via `--hashtag`/`--mention` CLI | Typer → use case → repo | LOW | mitigate | Typer passe la string telle quelle ; repo utilise SQLAlchemy Core binding. Pas de concaténation. |
| T-S04P01-02 | **Denial of Service (D)** — facette avec 1M matches | `find_video_ids_by_*` limit=1000 | LOW | mitigate | `limit=1000` sur chaque facette. Pour une librairie perso (R032), 1000 > population totale. Intersection in-memory sur Python `set` — O(min(n,m)). |
| T-S04P01-03 | **Tampering (T)** — `music_track` bypass via `--music-track`  qui charge `list_recent(limit=1000)` | `SearchLibraryUseCase` | LOW | accept | 1000 videos in-memory = ~100KB, acceptable. Pour une lib future >1000, créer `VideoRepository.find_by_music_track` dédié (différé). |
| T-S04P01-04 | **Information Disclosure (I)** — CLI affiche URL en clair | Rich table | LOW | accept | Tool local single-user (R032) ; les URLs sont déjà dans la description publique de la vidéo. |
| T-S04P01-05 | **Tampering (T)** — query FTS5 avec syntax dangereuse | `SearchIndex.search` | LOW | accept | FTS5 parse la query ; input malformé → erreur parsing captée par `handle_domain_errors`. Pas de SQL injection car `search()` utilise MATCH bindé. |
