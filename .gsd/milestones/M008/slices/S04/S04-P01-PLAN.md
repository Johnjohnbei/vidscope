---
slice: S04
plan: P01
phase: M008/S04
plan_id: S04-P01
wave: 4
depends_on: [S01-P01, S02-P01, S03-P01]
requirements: [R047, R048, R049]
files_modified:
  - src/vidscope/application/show_video.py
  - src/vidscope/application/search_library.py
  - src/vidscope/application/__init__.py
  - src/vidscope/cli/commands/show.py
  - src/vidscope/cli/commands/search.py
  - src/vidscope/mcp/server.py
  - tests/unit/application/test_show_video.py
  - tests/unit/application/test_search_library.py
  - tests/unit/cli/test_show_command.py
  - tests/unit/cli/test_search_command.py
  - tests/unit/mcp/test_frame_texts_tool.py
autonomous: true
must_haves:
  truths:
    - "ShowVideoResult DTO carries frame_texts: tuple[FrameText, ...] + thumbnail_key: str | None + content_shape: str | None"
    - "ShowVideoUseCase.execute populates frame_texts via uow.frame_texts.list_for_video AND fetches video.thumbnail_key + video.content_shape directly from the video row"
    - "vidscope show <id> CLI prints an 'on-screen text' section (first N frame_texts with confidence), a 'thumbnail' line, and a 'content_shape' line"
    - "SearchLibraryUseCase.execute accepts on_screen_text: str | None facet — when set, filters by uow.frame_texts.find_video_ids_by_text(on_screen_text) intersected with other facets"
    - "vidscope search --on-screen-text 'promo' CLI flag wires through to the on_screen_text kwarg"
    - "vidscope_get_frame_texts MCP tool exists and returns list of frame_text rows keyed by video_id"
    - "MCP tool returns {found: bool, video_id: int, frame_texts: list[{frame_id, text, confidence, timestamp_ms}]}"
    - "Existing ShowVideoUseCase and SearchLibraryUseCase callers keep working without modification (additive extensions with safe defaults)"
  artifacts:
    - path: "src/vidscope/application/show_video.py"
      provides: "ShowVideoResult + ShowVideoUseCase extended with frame_texts, thumbnail_key, content_shape"
      contains: "frame_texts:"
    - path: "src/vidscope/application/search_library.py"
      provides: "on_screen_text facet in SearchLibraryUseCase"
      contains: "on_screen_text"
    - path: "src/vidscope/cli/commands/show.py"
      provides: "vidscope show renders on-screen text + thumbnail + content_shape"
      contains: "on-screen text"
    - path: "src/vidscope/cli/commands/search.py"
      provides: "--on-screen-text CLI option"
      contains: "on-screen-text"
    - path: "src/vidscope/mcp/server.py"
      provides: "vidscope_get_frame_texts MCP tool"
      contains: "vidscope_get_frame_texts"
  key_links:
    - from: "src/vidscope/application/show_video.py"
      to: "uow.frame_texts.list_for_video"
      via: "read path inside execute()"
      pattern: "frame_texts.list_for_video"
    - from: "src/vidscope/application/search_library.py"
      to: "uow.frame_texts.find_video_ids_by_text"
      via: "facet branch when on_screen_text is not None"
      pattern: "find_video_ids_by_text"
    - from: "src/vidscope/cli/commands/search.py"
      to: "use_case.execute(..., on_screen_text=on_screen_text)"
      via: "typer option forwarding"
      pattern: "--on-screen-text"
    - from: "src/vidscope/mcp/server.py"
      to: "ShowVideoUseCase.execute (reusing existing use case)"
      via: "vidscope_get_frame_texts tool closure"
      pattern: "vidscope_get_frame_texts"
---

<objective>
Exposer les signaux M008 dans les deux surfaces utilisateur : CLI (`vidscope show`, `vidscope search`) et MCP (`vidscope_get_frame_texts`). Ce plan est purement une extension additive — aucune rupture d'interface, aucun changement de signature pour les callers existants.

**4 livrables concrets** :

1. **`vidscope show <id>`** affiche les textes OCR (top N par confiance), le chemin de la thumbnail, et le content_shape.

2. **`vidscope search --on-screen-text "promo"`** filtre les résultats par match FTS5 sur `frame_texts_fts`. Intersection implicite avec les autres facettes M007 (`--hashtag`, `--mention`, `--has-link`, `--music-track`).

3. **MCP tool `vidscope_get_frame_texts`** retourne la liste des FrameText pour un video_id donné avec text + confidence + frame_id + timestamp_ms (joint depuis la table frames).

4. **Extension DTO** : `ShowVideoResult` gagne les champs `frame_texts: tuple[FrameText, ...]`, `thumbnail_key: str | None`, `content_shape: str | None`. Les champs sont additifs avec des defaults sûrs.

**Contrainte de perf** : `vidscope show` doit rester une seule transaction UoW. `frame_texts.list_for_video` ajoute une query de plus. Pas de N+1 (une seule query pour toutes les frame_texts).

**Contrainte d'architecture** : la couche `application` ne touche pas aux adapters (contrat `application-has-no-adapters`). La couche `mcp` non plus. Tout passe par les ports et use cases existants.

Purpose: livrer la surface utilisateur de M008. Après ce plan, la milestone est COMPLETE — R047, R048, R049 sont tous observables via CLI et MCP.

Output: 2 use cases étendus + 2 commandes CLI étendues + 1 nouvelle tool MCP + 25+ tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M008/M008-ROADMAP.md
@.gsd/milestones/M008/M008-RESEARCH.md
@.gsd/milestones/M008/slices/S01/S01-P01-SUMMARY.md
@.gsd/milestones/M008/slices/S02/S02-P01-SUMMARY.md
@.gsd/milestones/M008/slices/S03/S03-P01-SUMMARY.md

@src/vidscope/application/show_video.py
@src/vidscope/application/search_library.py
@src/vidscope/application/__init__.py
@src/vidscope/cli/commands/show.py
@src/vidscope/cli/commands/search.py
@src/vidscope/mcp/server.py
@src/vidscope/domain/entities.py
@src/vidscope/ports/repositories.py
</context>

<interfaces>
<!-- From S01-P01 (already delivered) -->

```python
# FrameText entity
@dataclass(frozen=True, slots=True)
class FrameText:
    video_id: VideoId
    frame_id: int
    text: str
    confidence: float
    bbox: str | None = None
    id: int | None = None
    created_at: datetime | None = None

# FrameTextRepository protocol
class FrameTextRepository(Protocol):
    def add_many_for_frame(self, frame_id, video_id, texts) -> list[FrameText]: ...
    def list_for_video(self, video_id: VideoId) -> list[FrameText]: ...
    def has_any_for_video(self, video_id: VideoId) -> bool: ...
    def find_video_ids_by_text(self, query: str, *, limit: int = 50) -> list[VideoId]: ...
```

<!-- From S03-P01 (already delivered) -->

```python
# Video extended
@dataclass(frozen=True, slots=True)
class Video:
    ...
    thumbnail_key: str | None = None
    content_shape: str | None = None
```

<!-- Existing ShowVideoResult shape (must be extended) -->

```python
@dataclass(frozen=True, slots=True)
class ShowVideoResult:
    found: bool
    video: Video | None = None
    transcript: Transcript | None = None
    frames: tuple[Frame, ...] = ()
    analysis: Analysis | None = None
    creator: Creator | None = None
    hashtags: tuple[Hashtag, ...] = ()
    mentions: tuple[Mention, ...] = ()
    links: tuple[Link, ...] = ()
```

<!-- Existing SearchLibraryUseCase.execute signature to extend -->

```python
def execute(
    self,
    query: str,
    *,
    limit: int = 20,
    hashtag: str | None = None,
    mention: str | None = None,
    has_link: bool = False,
    music_track: str | None = None,
) -> SearchLibraryResult: ...
```
</interfaces>

<tasks>

<task id="T01-extend-show-video-use-case" type="auto" tdd="true">
  <name>T01: Extend ShowVideoResult with frame_texts + thumbnail_key + content_shape + CLI renderer</name>

  <read_first>
    - `src/vidscope/application/show_video.py` (entire file, 91 lines) — current ShowVideoResult DTO and ShowVideoUseCase. We will ADD fields to the DTO (safe defaults preserve caller compat) and ADD one line to execute() to populate frame_texts. thumbnail_key + content_shape are already on video.thumbnail_key / video.content_shape — no extra query needed.
    - `src/vidscope/cli/commands/show.py` (entire file, 114 lines) — the rich-based renderer. We append new sections: on-screen text preview + thumbnail + content_shape.
    - `tests/unit/application/test_show_video.py` — existing use case tests.
    - `tests/unit/cli/` — check which CLI tests exist for show.
    - `src/vidscope/domain/entities.py` — `Video.thumbnail_key`, `Video.content_shape`, `FrameText` (from S01/S03).
  </read_first>

  <behavior>
    - Test 1 (DTO defaults): `ShowVideoResult(found=False)` has `frame_texts == ()`, `thumbnail_key is None`, `content_shape is None`.
    - Test 2 (use case — video without frame_texts): `ShowVideoResult.frame_texts == ()` when uow.frame_texts.list_for_video returns [].
    - Test 3 (use case — video with frame_texts): populated tuple reflects the repository output in the same order.
    - Test 4 (use case — thumbnail_key passthrough): result.thumbnail_key equals video.thumbnail_key from the DB.
    - Test 5 (use case — content_shape passthrough): result.content_shape equals video.content_shape.
    - Test 6 (CLI renders on-screen text section when frame_texts present): output contains `on-screen text` AND a line per text block (up to a cap of 5 lines with the note "...and N more" if >5).
    - Test 7 (CLI renders "none" when frame_texts empty): output contains `[dim]on-screen text: none[/dim]`.
    - Test 8 (CLI renders thumbnail line): output contains `thumbnail:` followed by the key OR `[dim]thumbnail: none[/dim]`.
    - Test 9 (CLI renders content_shape line): output contains `content_shape:` followed by the value OR `[dim]content_shape: unknown[/dim]`.
  </behavior>

  <action>
  **Step A — Extend `ShowVideoResult` in `src/vidscope/application/show_video.py`:**

  1. Add `FrameText` to the imports from `vidscope.domain`.
  2. Extend the DTO:

  ```python
  @dataclass(frozen=True, slots=True)
  class ShowVideoResult:
      """Everything known about a single video.

      ``found`` is ``False`` when no video matches the given id; the
      other fields are then empty/None.

      M007 adds ``hashtags``, ``mentions``, ``links``. M008 adds
      ``frame_texts`` (on-screen OCR), ``thumbnail_key`` (canonical
      thumbnail path), ``content_shape`` (face-count heuristic).
      All defaults are safe-empty so existing callers keep working.
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
      frame_texts: tuple[FrameText, ...] = ()
      thumbnail_key: str | None = None
      content_shape: str | None = None
  ```

  3. Extend `execute` to fetch frame_texts and pass through the two video columns. The existing function already fetches the `video` — we just read `video.thumbnail_key` and `video.content_shape` from it. ONE extra repository call for frame_texts:

  ```python
  def execute(self, video_id: int) -> ShowVideoResult:
      with self._uow_factory() as uow:
          video = uow.videos.get(VideoId(video_id))
          if video is None:
              return ShowVideoResult(found=False)
          assert video.id is not None
          vid_id: VideoId = video.id
          transcript = uow.transcripts.get_for_video(vid_id)
          frames = tuple(uow.frames.list_for_video(vid_id))
          analysis = uow.analyses.get_latest_for_video(vid_id)
          creator: Creator | None = None
          if video.creator_id is not None:
              creator = uow.creators.get(video.creator_id)
          hashtags = tuple(uow.hashtags.list_for_video(vid_id))
          mentions = tuple(uow.mentions.list_for_video(vid_id))
          links = tuple(uow.links.list_for_video(vid_id))
          frame_texts = tuple(uow.frame_texts.list_for_video(vid_id))

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
      )
  ```

  **Step B — Extend `src/vidscope/cli/commands/show.py`:**

  Add a constant near the top (below `_DESCRIPTION_PREVIEW_CHARS`):

  ```python
  _FRAME_TEXT_PREVIEW_LIMIT = 5
  ```

  After the existing `console.print(f"[bold]links:[/bold] {len(result.links)}")` line, add:

  ```python
          # M008: on-screen text + thumbnail + content_shape
          if result.frame_texts:
              count = len(result.frame_texts)
              preview = result.frame_texts[:_FRAME_TEXT_PREVIEW_LIMIT]
              console.print(f"[bold]on-screen text:[/bold] {count} block(s)")
              for ft in preview:
                  conf = f"{ft.confidence:.2f}"
                  console.print(f"  [dim]•[/dim] {ft.text} [dim](conf={conf})[/dim]")
              if count > _FRAME_TEXT_PREVIEW_LIMIT:
                  console.print(
                      f"  [dim]...and {count - _FRAME_TEXT_PREVIEW_LIMIT} more[/dim]"
                  )
          else:
              console.print("[dim]on-screen text: none[/dim]")

          if result.thumbnail_key:
              console.print(f"[bold]thumbnail:[/bold] {result.thumbnail_key}")
          else:
              console.print("[dim]thumbnail: none[/dim]")

          shape_display = result.content_shape or "unknown"
          if result.content_shape is None:
              console.print(f"[dim]content_shape: {shape_display}[/dim]")
          else:
              console.print(f"[bold]content_shape:[/bold] {shape_display}")
  ```

  **Step C — Tests:**

  1. Extend `tests/unit/application/test_show_video.py` — add test class `TestShowVideoM008Fields`:
     - `test_defaults_when_not_found`: `ShowVideoResult(found=False).frame_texts == ()` etc.
     - `test_use_case_returns_frame_texts`: FakeUoW.frame_texts.rows has 2 entries, result.frame_texts has 2 entries.
     - `test_use_case_returns_thumbnail_key`: video.thumbnail_key = "videos/yt/abc/thumb.jpg" in the fake; result.thumbnail_key equals that string.
     - `test_use_case_returns_content_shape`: video.content_shape = "talking_head" in the fake; result.content_shape equals that value.

  2. Create `tests/unit/cli/test_show_command.py` if not existing, else extend. Use `CliRunner` from typer.testing. Tests:
     - `test_show_renders_on_screen_text_section`: inject a use case that returns 3 frame_texts; output contains `on-screen text: 3 block(s)` + each text line.
     - `test_show_renders_none_when_no_frame_texts`: output contains `on-screen text: none`.
     - `test_show_renders_thumbnail_key`: output contains `thumbnail: videos/yt/abc/thumb.jpg`.
     - `test_show_renders_content_shape`: output contains `content_shape: talking_head`.
     - `test_show_preview_cap_with_more_indicator`: 10 frame_texts → output contains `...and 5 more`.

  Use the `acquire_container()` monkeypatch pattern from existing CLI tests.
  </action>

  <acceptance_criteria>
    - `grep -q 'frame_texts: tuple\[FrameText, ...\]' src/vidscope/application/show_video.py` exit 0
    - `grep -q 'thumbnail_key: str | None' src/vidscope/application/show_video.py` exit 0
    - `grep -q 'content_shape: str | None' src/vidscope/application/show_video.py` exit 0
    - `grep -q 'uow.frame_texts.list_for_video' src/vidscope/application/show_video.py` exit 0
    - `grep -q 'on-screen text' src/vidscope/cli/commands/show.py` exit 0
    - `grep -q 'thumbnail' src/vidscope/cli/commands/show.py` exit 0
    - `grep -q 'content_shape' src/vidscope/cli/commands/show.py` exit 0
    - `uv run pytest tests/unit/application/test_show_video.py -x -q` exit 0
    - `uv run pytest tests/unit/cli/test_show_command.py -x -q` exit 0 (if it exists; else create + green)
    - `uv run pytest -q` exit 0 (no regression)
    - `uv run mypy src` exit 0
    - `uv run lint-imports` exit 0 (application-has-no-adapters still green)
    <automated>uv run pytest tests/unit/application/test_show_video.py tests/unit/cli -q</automated>
  </acceptance_criteria>
</task>

<task id="T02-extend-search-with-on-screen-text-facet" type="auto" tdd="true">
  <name>T02: Add on_screen_text facet to SearchLibraryUseCase + --on-screen-text CLI flag</name>

  <read_first>
    - `src/vidscope/application/search_library.py` (entire file, 157 lines) — the EXACT facet-intersection pattern. We extend by adding one more facet, mirroring `hashtag` / `mention`.
    - `src/vidscope/cli/commands/search.py` (entire file, 101 lines) — the typer options. Add `--on-screen-text` mirroring `--hashtag`.
    - `src/vidscope/ports/repositories.py` — `FrameTextRepository.find_video_ids_by_text(query, limit)` returns `list[VideoId]` (from S01-P01).
    - `tests/unit/application/test_search_library.py` — existing use case tests; extend with new facet.
    - `tests/unit/cli/test_search.py` (or wherever the search CLI tests live).
  </read_first>

  <behavior>
    - Test 1 (use case — on_screen_text None → no change): existing behavior unaffected.
    - Test 2 (use case — on_screen_text only): returns video ids from `uow.frame_texts.find_video_ids_by_text(query, limit=1000)`, synthesised SearchResult entries.
    - Test 3 (use case — on_screen_text + query): text query drives BM25; on_screen_text restricts the set.
    - Test 4 (use case — on_screen_text + hashtag): intersection of both facets (AND semantics).
    - Test 5 (CLI — --on-screen-text forwards the kwarg): verify via mocked use case that `on_screen_text="promo"` reaches `execute`.
    - Test 6 (CLI — facet tag displayed): output contains `on-screen=promo`.
  </behavior>

  <action>
  **Step A — Extend `src/vidscope/application/search_library.py`:**

  1. Update `execute` signature:

  ```python
  def execute(
      self,
      query: str,
      *,
      limit: int = 20,
      hashtag: str | None = None,
      mention: str | None = None,
      has_link: bool = False,
      music_track: str | None = None,
      on_screen_text: str | None = None,
  ) -> SearchLibraryResult:
  ```

  2. Extend `any_facet` boolean:

  ```python
  any_facet = (
      hashtag is not None
      or mention is not None
      or has_link
      or music_track is not None
      or on_screen_text is not None
  )
  ```

  3. Inside the `with self._uow_factory() as uow:` block, after the `music_track` facet block, add:

  ```python
      if on_screen_text is not None:
          stripped = on_screen_text.strip()
          if stripped:
              ids = uow.frame_texts.find_video_ids_by_text(stripped, limit=1000)
              facet_sets.append({int(vid) for vid in ids})
          else:
              # Empty/whitespace query → no match, break intersection
              facet_sets.append(set())
  ```

  4. Update the docstring of the use case (lines 27-44) to list the new facet:

  ```
  Facets (per M007 + M008):

  - ``hashtag``  — exact match after canonicalisation
  - ``mention``  — exact match after canonicalisation
  - ``has_link`` — boolean: at least one extracted URL
  - ``music_track`` — exact match on ``videos.music_track``
  - ``on_screen_text`` — FTS5 MATCH on ``frame_texts_fts`` (M008/R047)
  ```

  **Step B — Update `src/vidscope/cli/commands/search.py`:**

  1. Add a typer option below `music_track`:

  ```python
      on_screen_text: str | None = typer.Option(
          None,
          "--on-screen-text",
          help="Filter videos whose OCR-extracted on-screen text matches "
               "this FTS5 query (e.g. 'promo' or 'link bio').",
      ),
  ```

  2. Forward to the use case:

  ```python
          result = use_case.execute(
              query,
              limit=limit,
              hashtag=hashtag,
              mention=mention,
              has_link=has_link,
              music_track=music_track,
              on_screen_text=on_screen_text,
          )
  ```

  3. Extend the facet display:

  ```python
          if on_screen_text:
              facets.append(f"on-screen={on_screen_text}")
  ```

  **Step C — Tests:**

  1. Extend `tests/unit/application/test_search_library.py`:
     - `test_on_screen_text_only_returns_matches` — FakeFrameTextRepo returns [VideoId(1), VideoId(2)] for query "promo"; result.hits has 2 synthesised entries with source="video".
     - `test_on_screen_text_empty_string_returns_no_hits` — whitespace query → empty hits.
     - `test_on_screen_text_intersects_with_hashtag` — set A (from hashtag) ∩ set B (from on_screen_text) = correct intersection.
     - `test_on_screen_text_combined_with_query` — BM25 hits from search_index filtered by the on_screen_text set.

  Note: extend the FakeUoW in this test file to include `frame_texts: _FakeFrameTextRepo` with `find_video_ids_by_text` implementation returning a configurable list.

  2. Extend `tests/unit/cli/test_search.py` (create if absent):
     - `test_on_screen_text_flag_forwarded` — invoke `vidscope search --on-screen-text promo x` via CliRunner; assert `execute` was called with `on_screen_text="promo"`.
     - `test_on_screen_text_facet_rendered_in_header` — output contains `on-screen=promo`.
  </action>

  <acceptance_criteria>
    - `grep -q 'on_screen_text: str | None' src/vidscope/application/search_library.py` exit 0
    - `grep -q 'find_video_ids_by_text' src/vidscope/application/search_library.py` exit 0
    - `grep -q '"--on-screen-text"' src/vidscope/cli/commands/search.py` exit 0
    - `grep -q 'on_screen_text=on_screen_text' src/vidscope/cli/commands/search.py` exit 0
    - `uv run pytest tests/unit/application/test_search_library.py -x -q` exit 0
    - `uv run pytest tests/unit/cli/test_search.py -x -q` exit 0 (or test_search_command.py — whichever exists)
    - `uv run pytest -q` exit 0 (no regression)
    - `uv run mypy src` exit 0
    - `uv run lint-imports` exit 0
    <automated>uv run pytest tests/unit/application/test_search_library.py tests/unit/cli -q</automated>
  </acceptance_criteria>
</task>

<task id="T03-mcp-get-frame-texts-tool" type="auto" tdd="true">
  <name>T03: Add vidscope_get_frame_texts MCP tool</name>

  <read_first>
    - `src/vidscope/mcp/server.py` (entire file, 420 lines) — specifically the `build_mcp_server` factory (lines 105-396). Every tool is defined as `@mcp.tool() def tool_name(...) -> dict[str, Any]: ...` and follows the try/except DomainError → ValueError pattern. The pattern to mirror most closely is `vidscope_list_links` (lines 344-388) because it's also a per-video listing.
    - `src/vidscope/application/show_video.py` (from T01) — `ShowVideoResult.frame_texts` + `ShowVideoResult.video` (for timestamp_ms lookup).
    - `src/vidscope/domain/entities.py` — `FrameText` + `Frame` fields.
    - `tests/integration/test_mcp_server.py` — pattern for MCP tool integration tests if they exist.
    - `tests/unit/mcp/` — existing unit tests for MCP tools (look for one patterned after `vidscope_list_links`).
  </read_first>

  <behavior>
    - Test 1 (tool returns found=False on unknown id): `vidscope_get_frame_texts(video_id=999)` on an empty DB returns `{"found": False, "video_id": 999, "frame_texts": []}`.
    - Test 2 (tool returns populated list): seed 2 frame_texts, tool returns `found=True` + `frame_texts` list with text, confidence, frame_id, timestamp_ms fields.
    - Test 3 (tool includes timestamp_ms joined from frames): each result entry has `timestamp_ms` pulled from `Frame.timestamp_ms` via JOIN. If the frame doesn't exist (orphan FK, should not happen but defensive), timestamp_ms is None.
    - Test 4 (DomainError wrapped): if the underlying use case raises `StorageError`, the tool re-raises `ValueError`.
  </behavior>

  <action>
  **Step A — Add `vidscope_get_frame_texts` tool in `src/vidscope/mcp/server.py`:**

  Insert the new tool inside `build_mcp_server` (after `vidscope_list_links`, before the `_ = VideoId` assignment at line 394). Use the existing `ShowVideoUseCase` — it already exposes `frame_texts` and `frames` (after T01). The tool extracts both and joins in-memory to produce the JSON shape:

  ```python
      @mcp.tool()
      def vidscope_get_frame_texts(video_id: int) -> dict[str, Any]:
          """Return OCR-extracted on-screen text for a video's frames
          (M008/R047).

          Each entry carries the raw text, OCR confidence score, the
          parent frame id, and its timestamp in milliseconds (joined
          from the ``frames`` table). Results are ordered by
          ``frame_id`` ascending then insertion order.

          Returns ``{"found": False, "video_id": video_id, "frame_texts": []}``
          when no video matches the id — never raises on a miss.
          """
          try:
              use_case = ShowVideoUseCase(
                  unit_of_work_factory=container.unit_of_work
              )
              result = use_case.execute(video_id)
          except DomainError as exc:
              raise ValueError(str(exc)) from exc

          if not result.found:
              return {
                  "found": False,
                  "video_id": video_id,
                  "frame_texts": [],
              }

          # Build a frame_id → timestamp_ms lookup for the JOIN.
          frame_ts: dict[int, int] = {}
          for f in result.frames:
              if f.id is not None:
                  frame_ts[int(f.id)] = int(f.timestamp_ms)

          return {
              "found": True,
              "video_id": video_id,
              "frame_texts": [
                  {
                      "id": int(ft.id) if ft.id is not None else None,
                      "frame_id": int(ft.frame_id),
                      "text": ft.text,
                      "confidence": float(ft.confidence),
                      "timestamp_ms": frame_ts.get(int(ft.frame_id)),
                  }
                  for ft in result.frame_texts
              ],
          }
  ```

  No new imports needed — `ShowVideoUseCase` and `DomainError` are already imported at the top of server.py.

  **Step B — Tests:**

  Create `tests/unit/mcp/test_frame_texts_tool.py` (mirror the pattern of existing MCP unit tests — they inject a mock container with stubbed use cases, OR use a real SqliteUnitOfWork with in-memory engine). Pattern to mirror: `tests/unit/mcp/` already hosts tool tests (e.g. test for `vidscope_list_links`). Inspect one of them to see the injection style.

  Sketch:

  ```python
  """Unit tests for the vidscope_get_frame_texts MCP tool."""

  from __future__ import annotations

  from pathlib import Path
  from typing import Any

  import pytest
  from sqlalchemy import create_engine

  from vidscope.adapters.sqlite.schema import init_db
  from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
  from vidscope.domain import (
      Frame,
      FrameText,
      Platform,
      PlatformId,
      Video,
      VideoId,
  )
  from vidscope.infrastructure.container import Container, SystemClock
  from vidscope.mcp.server import build_mcp_server


  def _build_container_for_test(tmp_path: Path) -> Container:
      """Build a minimal Container with a fresh in-memory SQLite
      engine. Enough for the read-only vidscope_get_frame_texts tool.
      """
      from vidscope.adapters.fs.local_media_storage import LocalMediaStorage  # noqa: PLC0415
      from vidscope.adapters.heuristic import HeuristicAnalyzer  # noqa: PLC0415
      from vidscope.adapters.text import RegexLinkExtractor  # noqa: PLC0415
      from vidscope.infrastructure.config import get_config  # noqa: PLC0415

      engine = create_engine("sqlite:///:memory:")
      init_db(engine)

      def _uow_factory() -> SqliteUnitOfWork:
          return SqliteUnitOfWork(engine)

      # We only exercise the ShowVideoUseCase path; the other container
      # fields can be MagicMocks or omitted. But Container is a frozen
      # dataclass with required fields. Use dataclasses.replace or
      # construct from scratch with MagicMock for irrelevant deps.
      from unittest.mock import MagicMock  # noqa: PLC0415
      return Container(
          config=get_config(),
          engine=engine,
          media_storage=LocalMediaStorage(tmp_path),
          unit_of_work=_uow_factory,
          downloader=MagicMock(),
          transcriber=MagicMock(),
          frame_extractor=MagicMock(),
          analyzer=HeuristicAnalyzer(),
          pipeline_runner=MagicMock(),
          clock=SystemClock(),
      )


  def _get_tool(mcp_server: Any, name: str) -> Any:
      """Retrieve a registered tool's callable from FastMCP."""
      # FastMCP exposes tools via _tool_manager._tools in the current SDK.
      # If the internal layout differs, inspect the server instance.
      return mcp_server._tool_manager._tools[name].fn


  class TestVidscopeGetFrameTexts:
      def test_found_false_on_unknown_id(self, tmp_path: Path) -> None:
          container = _build_container_for_test(tmp_path)
          server = build_mcp_server(container)
          tool = _get_tool(server, "vidscope_get_frame_texts")
          out = tool(video_id=999)
          assert out == {"found": False, "video_id": 999, "frame_texts": []}

      def test_returns_frame_texts_when_present(self, tmp_path: Path) -> None:
          container = _build_container_for_test(tmp_path)

          # Seed: one video + 2 frames + 2 frame_texts
          with container.unit_of_work() as uow:
              video = uow.videos.add(
                  Video(
                      platform=Platform.YOUTUBE,
                      platform_id=PlatformId("abc"),
                      url="https://youtube.com/shorts/abc",
                  )
              )
              assert video.id is not None
              vid_id = video.id
              stored_frames = uow.frames.add_many(
                  [
                      Frame(video_id=vid_id, image_key="f/0.jpg", timestamp_ms=1000),
                      Frame(video_id=vid_id, image_key="f/1.jpg", timestamp_ms=3000),
                  ]
              )
              frame_0, frame_1 = stored_frames
              assert frame_0.id is not None and frame_1.id is not None
              uow.frame_texts.add_many_for_frame(
                  frame_0.id,
                  vid_id,
                  [
                      FrameText(
                          video_id=vid_id,
                          frame_id=frame_0.id,
                          text="Link in bio",
                          confidence=0.95,
                      )
                  ],
              )
              uow.frame_texts.add_many_for_frame(
                  frame_1.id,
                  vid_id,
                  [
                      FrameText(
                          video_id=vid_id,
                          frame_id=frame_1.id,
                          text="Promo code XYZ",
                          confidence=0.88,
                      )
                  ],
              )

          server = build_mcp_server(container)
          tool = _get_tool(server, "vidscope_get_frame_texts")
          out = tool(video_id=int(vid_id))

          assert out["found"] is True
          assert out["video_id"] == int(vid_id)
          assert len(out["frame_texts"]) == 2
          texts = {item["text"] for item in out["frame_texts"]}
          assert texts == {"Link in bio", "Promo code XYZ"}
          # timestamp_ms is populated via the join
          ts_values = {item["timestamp_ms"] for item in out["frame_texts"]}
          assert ts_values == {1000, 3000}
          # confidence is a float
          for item in out["frame_texts"]:
              assert isinstance(item["confidence"], float)
              assert isinstance(item["frame_id"], int)
  ```

  If the `_get_tool` helper fails because the FastMCP internal attribute name differs, inspect `build_mcp_server`'s existing unit tests in `tests/unit/mcp/` and mirror their pattern. If no unit-test pattern exists for FastMCP tools, consolidate the test into a subprocess integration test under `tests/integration/test_mcp_server.py` instead, using the `@pytest.mark.integration` marker and the existing ClientSession pattern.

  **Step C — Update `src/vidscope/application/__init__.py`:**

  Verify that `ShowVideoResult` and `ShowVideoUseCase` are exported (they already should be per the existing `__init__.py` read in context). No changes needed unless absent.
  </action>

  <acceptance_criteria>
    - `grep -q 'def vidscope_get_frame_texts' src/vidscope/mcp/server.py` exit 0
    - `grep -q 'frame_texts' src/vidscope/mcp/server.py` exit 0
    - `uv run python -c "from vidscope.mcp.server import build_mcp_server; from unittest.mock import MagicMock; mcp = build_mcp_server(MagicMock()); print('built')"` prints `built`
    - `uv run pytest tests/unit/mcp/test_frame_texts_tool.py -x -q` exit 0 (or the integration variant)
    - `uv run pytest -q` exit 0 (no regression)
    - `uv run mypy src` exit 0
    - `uv run lint-imports` exit 0 (mcp-has-no-adapters still green — we only use use cases and container)
    <automated>uv run pytest tests/unit/mcp -q</automated>
  </acceptance_criteria>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI input `--on-screen-text "query"` → SQLite FTS5 MATCH | User-provided query string is passed to FTS5 with parameter binding |
| MCP tool argument `video_id: int` → use case execute | int-typed argument, no cast-from-string at the tool layer |
| ShowVideoResult DTO → CLI renderer | Trusted domain data from the UoW; rendered via rich — XSS-equivalent not applicable (CLI) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-M008-S04-01 | **Denial of Service (D)** | Malformed FTS5 query via `--on-screen-text` crashes the search | mitigate | `FrameTextRepositorySQLite.find_video_ids_by_text` (from S01-P01) wraps FTS5 MATCH execution in try/except and raises StorageError on SQL parse failure. The SearchLibraryUseCase doesn't catch StorageError — it propagates to the CLI which has a top-level `handle_domain_errors()` context manager that converts DomainError to a user-friendly message + exit code. Consistent with M007 --hashtag behaviour. |
| T-M008-S04-02 | **Injection (T)** | FTS5 MATCH query built from user input | mitigate | `find_video_ids_by_text` uses SQLAlchemy `text("... MATCH :q")` with parameter binding. No string concatenation. SQLite's FTS5 MATCH has its own query syntax (phrase queries, boolean operators) — the user CAN craft advanced queries, which is a feature, not a vulnerability. |
| T-M008-S04-03 | **Information Disclosure (I)** | CLI renders OCR text verbatim, which may include PII (phone numbers, emails captured on-screen) | accept | Same rationale as S01-P01 T-M008-S01-04: single-user local tool (R032). The user chose to ingest the video; displaying its on-screen content is the explicit goal. |
| T-M008-S04-04 | **Denial of Service (D)** | `vidscope show <id>` on a video with 1000+ frame_texts renders a huge list | mitigate | CLI caps rendered lines at `_FRAME_TEXT_PREVIEW_LIMIT = 5` with an "...and N more" indicator. The underlying DB query still fetches all rows — acceptable because M001/S04 caps frames to 30 per video; with maybe 10 text blocks per frame → 300 rows worst case, trivially small. |
| T-M008-S04-05 | **Tampering (T)** | MCP tool argument shadowing (tool accepts `video_id: int` but caller sends a string) | mitigate | FastMCP SDK performs JSON schema validation on tool arguments based on the type annotation. An invalid type (string where int expected) becomes a validation error before the closure runs. Defensive in-closure: any `int(video_id)` call would TypeError on a string — the try/except DomainError wrapper doesn't catch TypeError, so a bad arg propagates to FastMCP as an internal error — acceptable. |
| T-M008-S04-06 | **Information Disclosure (I)** | MCP tool returns full OCR text including PII to the LLM client | accept | Same reasoning: single-user local; the user is the MCP client operator. |

</threat_model>

<verification>
```bash
# Unit tests
uv run pytest tests/unit/application/test_show_video.py -x -q
uv run pytest tests/unit/application/test_search_library.py -x -q
uv run pytest tests/unit/cli -x -q
uv run pytest tests/unit/mcp -x -q

# Full suite
uv run pytest -q

# CLI smoke (end-to-end)
uv run vidscope --help | grep -q "show"
uv run vidscope search --help | grep -q "on-screen-text"

# Quality gates
uv run ruff check src tests
uv run mypy src
uv run lint-imports
```
</verification>

<success_criteria>
- `vidscope show <id>` displays an "on-screen text" section, a "thumbnail" line, and a "content_shape" line.
- `vidscope search --on-screen-text "query"` filters results by FTS5 MATCH on frame_texts_fts.
- MCP tool `vidscope_get_frame_texts` returns the full FrameText list joined with frame timestamps.
- `ShowVideoResult` DTO exposes `frame_texts`, `thumbnail_key`, `content_shape` as additive fields with safe defaults.
- All existing callers of `ShowVideoUseCase` / `SearchLibraryUseCase` / `vidscope show` / `vidscope search` keep working without code changes.
- 25+ new tests green (application + CLI + MCP).
- All 10 import-linter contracts green.
- Zero regression on existing 735+ tests.
- After this plan: R047, R048, R049 are fully observable end-to-end via CLI + MCP. M008 is COMPLETE.
</success_criteria>

<output>
After completion, create `.gsd/milestones/M008/slices/S04/S04-P01-SUMMARY.md` following the standard summary template.
</output>
