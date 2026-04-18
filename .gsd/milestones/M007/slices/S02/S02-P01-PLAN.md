---
plan_id: S02-P01
phase: M007/S02
wave: 3
depends_on: [S01-P02]
requirements: [R044]
files_modified:
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/ports/link_extractor.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/unit_of_work.py
  - src/vidscope/ports/__init__.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/link_repository.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - tests/unit/domain/test_entities.py
  - tests/unit/adapters/sqlite/test_link_repository.py
  - tests/unit/adapters/sqlite/test_schema.py
autonomous: true
---

## Objective

Livrer la fondation persistance + ports de S02 (la logique regex + corpus est livrée en S02-P02) : (1) nouvelle entité domain `Link` frozen dataclass avec `video_id`, `url`, `normalized_url`, `source`, `position_ms`, `id`, `created_at` (2) ports — `LinkExtractor` Protocol avec `RawLink` TypedDict et méthode `extract(text, *, source) -> list[RawLink]`, `LinkRepository` Protocol avec `add_many_for_video`, `list_for_video`, `has_any_for_video`, `find_video_ids_with_any_link` (3) SQL schema — nouvelle table `links` avec colonnes exactes de RESEARCH.md §"Pattern schema SQLAlchemy Core" + index sur `video_id` et `normalized_url` (4) adapter `LinkRepositorySQLite` en miroir exact de `HashtagRepositorySQLite` (5) wire UnitOfWork avec `links: LinkRepository`. Les tests unitaires couvrent CRUD + filter par `source` + cascade delete. Cette fondation déverrouille S02-P02 (où le corpus regex gate et l'implémentation RegexLinkExtractor atterrissent).

## Tasks

<task id="T01-link-entity-and-ports">
  <name>Créer Link entity + LinkExtractor port + LinkRepository port</name>

  <read_first>
    - `src/vidscope/domain/entities.py` — patron `Hashtag` et `Mention` (ajoutés dans S01-P01) à miroir pour `Link`
    - `src/vidscope/ports/pipeline.py` lignes 162-196 — patron `CreatorInfo` TypedDict pour `RawLink`
    - `src/vidscope/ports/repositories.py` — patron `HashtagRepository` Protocol (ajouté dans S01-P02) pour `LinkRepository`
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"Port (protocol)" et §"Pattern schema SQLAlchemy Core" (shape exacte de la table `links`)
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-02 (pas de HEAD-resolver en M007, `url` brute + `normalized_url` uniquement) et §"source column distingue description/transcript/ocr"
    - `.importlinter` — `domain-is-pure` et `ports-are-pure`
  </read_first>

  <action>
  **Étape A — Ajouter `Link` dans `src/vidscope/domain/entities.py`**. À la fin du fichier (après `Mention`, ajouté en S01-P01) :

  ```python
  @dataclass(frozen=True, slots=True)
  class Link:
      """A URL extracted from a video's text surfaces (description,
      transcript, OCR).

      Stored in a side table keyed by ``(video_id, normalized_url, source)``.
      ``url`` is the raw string as captured by the extractor (strip
      trailing punctuation but preserve the original case and query
      params). ``normalized_url`` is the deduplication key: lowercase
      scheme+host, strip ``utm_*`` query params, strip fragment, sorted
      query params (see M007/S02 ``URLNormalizer``). Per M007 D-02, no
      HEAD resolver runs at ingest — short URLs (t.co, bit.ly) are
      stored as-is and resolved later if and when M008/M011 adds that
      capability.

      ``source`` identifies where the URL was found: ``"description"``
      for captions captured at ingest, ``"transcript"`` for URLs
      surfaced in the transcript after TranscribeStage, and ``"ocr"``
      reserved for M008/S02 (OCR-sourced on-screen URLs). ``position_ms``
      is populated for transcript/OCR sources when a timestamp is
      available; ``None`` for caption-sourced URLs.

      ``id`` is ``None`` until the repository persists the row.
      """

      video_id: VideoId
      url: str
      normalized_url: str
      source: str
      position_ms: int | None = None
      id: int | None = None
      created_at: datetime | None = None
  ```

  Mettre à jour `__all__` du fichier pour inclure `"Link"` en respectant l'ordre alphabétique (entre `"Hashtag"` et `"Mention"` — non, l'ordre alphabétique est `Hashtag` < `Link` < `Mention`) :

  ```python
  __all__ = [
      "Analysis",
      "Creator",
      "Frame",
      "Hashtag",
      "Link",
      "Mention",
      "PipelineRun",
      "Transcript",
      "TranscriptSegment",
      "Video",
      "WatchRefresh",
      "WatchedAccount",
  ]
  ```

  Mettre à jour `src/vidscope/domain/__init__.py` pour re-exporter `Link`.

  **Étape B — Créer `src/vidscope/ports/link_extractor.py`** (nouveau fichier) :

  ```python
  """LinkExtractor port.

  Extracts URLs from arbitrary text (video description, transcript full
  text, OCR output in M008). Implementations are expected to be pure —
  no network call, no DB access. See M007/S02
  :class:`RegexLinkExtractor` for the default implementation.
  """

  from __future__ import annotations

  from typing import Protocol, TypedDict, runtime_checkable

  __all__ = ["LinkExtractor", "RawLink"]


  class RawLink(TypedDict):
      """One URL extracted from text.

      ``url`` is the raw string as captured (case preserved, trailing
      punctuation stripped). ``normalized_url`` is the deduplication
      key — see M007/S02 ``URLNormalizer`` for the exact shape
      (lowercase scheme+host, stripped utm_*, strip fragment, sorted
      query params). ``source`` is ``"description"``, ``"transcript"``,
      or ``"ocr"``. ``position_ms`` is optional per source type
      (``None`` for description-sourced URLs; transcript/OCR may
      populate it when a timestamp is known).
      """

      url: str
      normalized_url: str
      source: str
      position_ms: int | None


  @runtime_checkable
  class LinkExtractor(Protocol):
      """Pure URL extractor — no I/O.

      The default implementation in :mod:`vidscope.adapters.text`
      (M007/S02) uses a regex + a restricted TLD list to minimise
      false positives like ``hello.world`` or ``version 1.0.0``. See
      the non-negotiable fixture corpus at
      ``tests/fixtures/link_corpus.json`` for the quality gate.
      """

      def extract(self, text: str, *, source: str) -> list[RawLink]:
          """Extract URLs from ``text``. Returns empty list when none.

          ``source`` is copied verbatim into every returned
          :class:`RawLink`. Callers pass ``"description"`` at ingest
          time, ``"transcript"`` after TranscribeStage. The extractor
          MUST NOT raise on any input string — garbage in, empty out.
          """
          ...
  ```

  **Étape C — Ajouter `LinkRepository` Protocol dans `src/vidscope/ports/repositories.py`**. Ajouter l'import `Link` dans les imports depuis `vidscope.domain`. Ajouter `"LinkRepository"` dans `__all__`. Ajouter le Protocol à la fin du fichier :

  ```python
  @runtime_checkable
  class LinkRepository(Protocol):
      """Persistence for :class:`~vidscope.domain.entities.Link`.

      Links are stored in a side table keyed by
      ``(video_id, normalized_url, source)``. ``source`` is one of
      ``"description"``, ``"transcript"``, ``"ocr"``. The repository
      deduplicates on ``normalized_url`` within a single
      :meth:`add_many_for_video` call but does NOT enforce cross-call
      uniqueness — a URL may appear multiple times in the same video
      via different sources (once from description, once from
      transcript).
      """

      def add_many_for_video(
          self, video_id: VideoId, links: list[Link]
      ) -> list[Link]:
          """Insert every link for ``video_id`` atomically.

          Deduplicates by ``(normalized_url, source)`` within the call.
          Empty ``links`` is a no-op. Returns the persisted entities
          with ``id`` populated.
          """
          ...

      def list_for_video(
          self, video_id: VideoId, *, source: str | None = None
      ) -> list[Link]:
          """Return every link for ``video_id``, optionally filtered by
          ``source``. Ordered by ``id`` asc (insertion order).

          Empty list on miss — never raises.
          """
          ...

      def has_any_for_video(self, video_id: VideoId) -> bool:
          """Return ``True`` when at least one link exists for
          ``video_id``. Used by :meth:`MetadataExtractStage.is_satisfied`
          for resume-safe pipeline replay (M007/S03).
          """
          ...

      def find_video_ids_with_any_link(
          self, *, limit: int = 50
      ) -> list[VideoId]:
          """Return up to ``limit`` video ids that have at least one link.

          Used by the search facet ``--has-link`` via EXISTS subquery
          (M007/S04).
          """
          ...
  ```

  Et ajouter `Link` à l'import :

  ```python
  from vidscope.domain import (
      Analysis,
      Creator,
      CreatorId,
      Frame,
      Hashtag,
      Link,
      Mention,
      ...
  )
  ```

  **Étape D — Étendre `src/vidscope/ports/unit_of_work.py`** pour exposer `links: LinkRepository`. Ajouter `LinkRepository` dans l'import et dans le Protocol :

  ```python
  from vidscope.ports.repositories import (
      AnalysisRepository,
      CreatorRepository,
      FrameRepository,
      HashtagRepository,
      LinkRepository,
      MentionRepository,
      PipelineRunRepository,
      TranscriptRepository,
      VideoRepository,
      WatchAccountRepository,
      WatchRefreshRepository,
  )
  ```

  Dans le Protocol `UnitOfWork`, ajouter APRÈS `mentions: MentionRepository` :

  ```python
      hashtags: HashtagRepository
      mentions: MentionRepository
      links: LinkRepository
      pipeline_runs: PipelineRunRepository
  ```

  **Étape E — Mettre à jour `src/vidscope/ports/__init__.py`** pour re-exporter `LinkExtractor`, `RawLink`, `LinkRepository`.

  **Étape F — Écrire les tests domain pour `Link`.** Étendre `tests/unit/domain/test_entities.py` avec une classe `TestLink` :

  ```python
  class TestLink:
      def _minimal(self) -> Link:
          return Link(
              video_id=VideoId(1),
              url="https://example.com/path",
              normalized_url="https://example.com/path",
              source="description",
          )

      def test_minimal_link_has_defaults(self) -> None:
          ln = self._minimal()
          assert ln.video_id == VideoId(1)
          assert ln.source == "description"
          assert ln.position_ms is None
          assert ln.id is None
          assert ln.created_at is None

      def test_link_is_frozen(self) -> None:
          ln = self._minimal()
          with pytest.raises(FrozenInstanceError):
              ln.url = "other"  # type: ignore[misc]

      def test_link_uses_slots(self) -> None:
          ln = self._minimal()
          assert not hasattr(ln, "__dict__")

      def test_link_preserves_raw_url_and_normalized_distinctly(self) -> None:
          ln = Link(
              video_id=VideoId(1),
              url="https://Example.COM/Path?utm_source=x",
              normalized_url="https://example.com/Path",
              source="description",
          )
          assert ln.url == "https://Example.COM/Path?utm_source=x"
          assert ln.normalized_url == "https://example.com/Path"

      def test_link_accepts_position_ms(self) -> None:
          ln = Link(
              video_id=VideoId(1),
              url="https://example.com",
              normalized_url="https://example.com",
              source="transcript",
              position_ms=12_345,
          )
          assert ln.position_ms == 12_345
  ```

  Mettre à jour l'import `Link` dans le fichier de test.
  </action>

  <acceptance_criteria>
    - `grep -q "class Link:" src/vidscope/domain/entities.py` exit 0
    - `grep -q "normalized_url: str" src/vidscope/domain/entities.py` exit 0
    - `grep -q '"Link"' src/vidscope/domain/entities.py` exit 0 (dans `__all__`)
    - `grep -q '"Link"' src/vidscope/domain/__init__.py` exit 0
    - `test -f src/vidscope/ports/link_extractor.py`
    - `grep -q "class LinkExtractor(Protocol):" src/vidscope/ports/link_extractor.py` exit 0
    - `grep -q "class RawLink(TypedDict):" src/vidscope/ports/link_extractor.py` exit 0
    - `grep -q "class LinkRepository(Protocol):" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "def add_many_for_video" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "def has_any_for_video" src/vidscope/ports/repositories.py` exit 0
    - `grep -q "links: LinkRepository" src/vidscope/ports/unit_of_work.py` exit 0
    - `grep -q "LinkExtractor" src/vidscope/ports/__init__.py` exit 0
    - `grep -q "LinkRepository" src/vidscope/ports/__init__.py` exit 0
    - `python -m uv run python -c "from vidscope.domain import Link, VideoId; ln = Link(video_id=VideoId(1), url='u', normalized_url='u', source='description'); print(ln.source, ln.position_ms)"` affiche `description None`
    - `python -m uv run python -c "from vidscope.ports import LinkExtractor, RawLink, LinkRepository; print(LinkExtractor.__name__, LinkRepository.__name__)"` exit 0
    - `python -m uv run pytest tests/unit/domain/test_entities.py::TestLink -x -q` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (contrat `domain-is-pure` et `ports-are-pure` verts)
  </acceptance_criteria>
</task>

<task id="T02-links-table-and-sqlite-repo" tdd="true">
  <name>Créer la table links + LinkRepositorySQLite + wire UnitOfWork + tests</name>

  <read_first>
    - `src/vidscope/adapters/sqlite/schema.py` — localiser la section tables ajoutée en S01-P02 (après `mentions`, avant la section FTS5) ; patron existant pour `hashtags`/`mentions` à miroir pour `links`
    - `src/vidscope/adapters/sqlite/hashtag_repository.py` — patron complet à miroir pour `LinkRepositorySQLite`
    - `src/vidscope/adapters/sqlite/unit_of_work.py` — lignes étendues en S01-P02 avec hashtags/mentions ; ajouter `links` selon le même patron
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"Pattern schema SQLAlchemy Core" (shape `links` table exacte)
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-02 (pas de HEAD-resolver, `url` brute + `normalized_url` uniquement)
  </read_first>

  <behavior>
    - Test 1: `add_many_for_video(vid, [Link(url="https://a.com", normalized_url="https://a.com", source="description")])` insère 1 row ; `list_for_video(vid)` retourne la liste avec `id` populé.
    - Test 2: dedup dans le même call — `add_many_for_video(vid, [Link(..., normalized_url="https://a.com", source="description"), Link(..., normalized_url="https://a.com", source="description")])` insère 1 row unique (dedup par `(normalized_url, source)`).
    - Test 3: même URL via deux sources différentes (description + transcript) = 2 rows distincts (pas de dedup cross-source).
    - Test 4: `list_for_video(vid, source="description")` filtre correctement ; `list_for_video(vid, source="transcript")` = sous-ensemble.
    - Test 5: `list_for_video(vid)` (pas de filtre) retourne tout dans l'ordre d'insertion (`id` asc).
    - Test 6: `has_any_for_video(vid)` retourne `True` après insert, `False` sur video sans link.
    - Test 7: cascade delete — delete video row supprime toutes les rows `links` FK (ondelete=CASCADE).
    - Test 8: `position_ms` nullable — round-trip `None` et entier positif.
    - Test 9: `find_video_ids_with_any_link(limit=10)` retourne la liste de video ids ayant ≥ 1 link.
    - Test 10: `add_many_for_video(vid, [])` no-op (empty list → no rows).
  </behavior>

  <action>
  **Étape A — Ajouter la table `links` dans `schema.py`.** Après la définition de `mentions` (ajoutée en S01-P02) et AVANT `# FTS5 virtual table DDL`, insérer :

  ```python
  # M007: link side table (R044, D-02). url is the raw verbatim extract;
  # normalized_url is the dedup key (lowercase scheme+host, strip utm_*,
  # sorted query params). source ∈ {"description", "transcript", "ocr"}.
  links = Table(
      "links",
      metadata,
      Column("id", Integer, primary_key=True, autoincrement=True),
      Column(
          "video_id",
          Integer,
          ForeignKey("videos.id", ondelete="CASCADE"),
          nullable=False,
      ),
      Column("url", Text, nullable=False),
      Column("normalized_url", Text, nullable=False),
      Column("source", String(32), nullable=False),
      Column("position_ms", Integer, nullable=True),
      Column(
          "created_at",
          DateTime(timezone=True),
          nullable=False,
          default=_utc_now,
      ),
  )
  Index("idx_links_video_id", links.c.video_id)
  Index("idx_links_normalized_url", links.c.normalized_url)
  Index("idx_links_source", links.c.source)
  ```

  Mettre à jour `__all__` (lignes 57-68) pour inclure `"links"` :

  ```python
  __all__ = [
      "analyses",
      "creators",
      "frames",
      "hashtags",
      "init_db",
      "links",
      "mentions",
      "metadata",
      "pipeline_runs",
      "transcripts",
      "videos",
      "watch_refreshes",
      "watched_accounts",
  ]
  ```

  **Étape B — Créer `src/vidscope/adapters/sqlite/link_repository.py`** (miroir de `hashtag_repository.py`) :

  ```python
  """SQLite implementation of :class:`LinkRepository`.

  Uses SQLAlchemy Core exclusively. Links are stored with dedup on
  ``(video_id, normalized_url, source)`` — the same URL from description
  and from transcript is TWO rows (intentional per R044 "source origin").
  """

  from __future__ import annotations

  from datetime import UTC, datetime
  from typing import Any, cast

  from sqlalchemy import func, select
  from sqlalchemy.engine import Connection

  from vidscope.adapters.sqlite.schema import links as links_table
  from vidscope.domain import Link, VideoId
  from vidscope.domain.errors import StorageError

  __all__ = ["LinkRepositorySQLite"]


  class LinkRepositorySQLite:
      """Repository for :class:`Link` backed by SQLite."""

      def __init__(self, connection: Connection) -> None:
          self._conn = connection

      # ------------------------------------------------------------------
      # Writes
      # ------------------------------------------------------------------

      def add_many_for_video(
          self, video_id: VideoId, links: list[Link]
      ) -> list[Link]:
          """Insert every link atomically with dedup on
          ``(normalized_url, source)`` within the call."""
          if not links:
              return []
          try:
              seen: set[tuple[str, str]] = set()
              payloads: list[dict[str, Any]] = []
              now = datetime.now(UTC)
              for ln in links:
                  key = (ln.normalized_url, ln.source)
                  if key in seen:
                      continue
                  seen.add(key)
                  payloads.append(
                      {
                          "video_id": int(video_id),
                          "url": ln.url,
                          "normalized_url": ln.normalized_url,
                          "source": ln.source,
                          "position_ms": ln.position_ms,
                          "created_at": now,
                      }
                  )
              if not payloads:
                  return []
              self._conn.execute(links_table.insert().values(payloads))
          except Exception as exc:
              raise StorageError(
                  f"add_many_for_video failed for links of video "
                  f"{int(video_id)}: {exc}",
                  cause=exc,
              ) from exc
          # Return the stored rows with id populated (query back by
          # video_id — cheap because idx_links_video_id indexes it)
          return self.list_for_video(video_id)

      # ------------------------------------------------------------------
      # Reads
      # ------------------------------------------------------------------

      def list_for_video(
          self, video_id: VideoId, *, source: str | None = None
      ) -> list[Link]:
          query = (
              select(links_table)
              .where(links_table.c.video_id == int(video_id))
              .order_by(links_table.c.id.asc())
          )
          if source is not None:
              query = query.where(links_table.c.source == source)
          rows = self._conn.execute(query).mappings().all()
          return [_row_to_link(row) for row in rows]

      def has_any_for_video(self, video_id: VideoId) -> bool:
          count = self._conn.execute(
              select(func.count())
              .select_from(links_table)
              .where(links_table.c.video_id == int(video_id))
          ).scalar()
          return bool(count and int(count) > 0)

      def find_video_ids_with_any_link(
          self, *, limit: int = 50
      ) -> list[VideoId]:
          rows = (
              self._conn.execute(
                  select(links_table.c.video_id)
                  .distinct()
                  .order_by(links_table.c.video_id.desc())
                  .limit(limit)
              )
              .all()
          )
          return [VideoId(int(row[0])) for row in rows]


  # ---------------------------------------------------------------------------
  # Row <-> entity translation
  # ---------------------------------------------------------------------------


  def _row_to_link(row: Any) -> Link:
      data = cast("dict[str, Any]", dict(row))
      return Link(
          id=int(data["id"]) if data.get("id") is not None else None,
          video_id=VideoId(int(data["video_id"])),
          url=str(data["url"]),
          normalized_url=str(data["normalized_url"]),
          source=str(data["source"]),
          position_ms=(
              int(data["position_ms"])
              if data.get("position_ms") is not None
              else None
          ),
          created_at=_ensure_utc(data.get("created_at")),
      )


  def _ensure_utc(value: datetime | None) -> datetime | None:
      if value is None:
          return None
      if value.tzinfo is None:
          return value.replace(tzinfo=UTC)
      return value.astimezone(UTC)
  ```

  **Étape C — Étendre `src/vidscope/adapters/sqlite/unit_of_work.py`** pour wire `LinkRepositorySQLite`. Ajouter l'import :

  ```python
  from vidscope.adapters.sqlite.link_repository import LinkRepositorySQLite
  ```

  Ajouter `LinkRepository` dans l'import depuis `vidscope.ports`. Ajouter la déclaration de slot après `mentions` :

  ```python
          self.hashtags: HashtagRepository
          self.mentions: MentionRepository
          self.links: LinkRepository
          self.pipeline_runs: PipelineRunRepository
  ```

  Et l'instantiation dans `__enter__` après `self.mentions = ...` :

  ```python
          self.links = LinkRepositorySQLite(self._connection)
  ```

  **Étape D — Écrire les tests (TDD).** Créer `tests/unit/adapters/sqlite/test_link_repository.py` avec les 10 tests décrits dans `<behavior>`. Pattern : engine in-memory, `init_db`, créer un `Video` parent via `VideoRepositorySQLite.add`, puis exercer `LinkRepositorySQLite` sur la même `Connection`.

  Étendre `tests/unit/adapters/sqlite/test_schema.py` avec un test vérifiant que `links` est créée après `init_db` et a les indices attendus.
  </action>

  <acceptance_criteria>
    - `grep -q 'links = Table(' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'Column("normalized_url", Text, nullable=False)' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'Column("source", String(32), nullable=False)' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'Column("position_ms", Integer, nullable=True)' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'Index("idx_links_video_id"' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q 'Index("idx_links_normalized_url"' src/vidscope/adapters/sqlite/schema.py` exit 0
    - `grep -q '"links"' src/vidscope/adapters/sqlite/schema.py` exit 0 (dans `__all__`)
    - `test -f src/vidscope/adapters/sqlite/link_repository.py`
    - `grep -q "class LinkRepositorySQLite:" src/vidscope/adapters/sqlite/link_repository.py` exit 0
    - `grep -q "def add_many_for_video" src/vidscope/adapters/sqlite/link_repository.py` exit 0
    - `grep -q "def has_any_for_video" src/vidscope/adapters/sqlite/link_repository.py` exit 0
    - `grep -q "self.links = LinkRepositorySQLite" src/vidscope/adapters/sqlite/unit_of_work.py` exit 0
    - `test -f tests/unit/adapters/sqlite/test_link_repository.py`
    - `grep -c "def test_" tests/unit/adapters/sqlite/test_link_repository.py` retourne un nombre ≥ 10
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_link_repository.py -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py -x -q` exit 0
    - `python -m uv run python -c "from sqlalchemy import create_engine, text; from vidscope.adapters.sqlite.schema import init_db; e = create_engine('sqlite:///:memory:'); init_db(e); c = e.connect(); assert c.execute(text('SELECT sql FROM sqlite_master WHERE name=\"links\"')).scalar() is not None; print('OK')"` affiche `OK`
    - `python -m uv run pytest -q` exit 0 (aucune régression)
    - `python -m uv run ruff check src tests` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (9 contrats verts)
  </acceptance_criteria>
</task>

## Verification Criteria

```bash
# Tests
python -m uv run pytest tests/unit/domain/test_entities.py::TestLink -x -q
python -m uv run pytest tests/unit/adapters/sqlite/test_link_repository.py -x -q

# Smoke test UoW expose links
python -m uv run python -c "
from sqlalchemy import create_engine
from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
e = create_engine('sqlite:///:memory:'); init_db(e)
with SqliteUnitOfWork(e) as uow:
    assert hasattr(uow, 'links')
    assert uow.links.has_any_for_video.__name__ == 'has_any_for_video'
print('OK')
"

# Suite complète + quality gates
python -m uv run pytest -q
python -m uv run ruff check src tests
python -m uv run mypy src
python -m uv run lint-imports
```

## Must-Haves

- `Link` frozen dataclass avec `slots=True` dans `vidscope.domain.entities`, champs `video_id`, `url`, `normalized_url`, `source`, `position_ms: int | None = None`, `id: int | None = None`, `created_at`.
- `LinkExtractor` Protocol + `RawLink` TypedDict dans `vidscope.ports.link_extractor`.
- `LinkRepository` Protocol dans `vidscope.ports.repositories` avec 4 méthodes (`add_many_for_video`, `list_for_video`, `has_any_for_video`, `find_video_ids_with_any_link`).
- Table SQLite `links` existe avec colonnes + 3 indices (`video_id`, `normalized_url`, `source`), FK CASCADE.
- `LinkRepositorySQLite` dédup par `(normalized_url, source)` dans `add_many_for_video`.
- `SqliteUnitOfWork` expose `uow.links`.
- ≥ 10 tests sur `LinkRepositorySQLite`.
- Les 9 contrats `.importlinter` restent verts.

## Threat Model

| # | Catégorie STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-S02P01-01 | **Tampering (T)** — SQL injection via `url`/`normalized_url` | `LinkRepositorySQLite.add_many_for_video` | LOW | mitigate | SQLAlchemy Core `.values(payloads)` bindé — jamais de concaténation. Test : url contenant `"'; DROP TABLE links; --"` stockée verbatim. |
| T-S02P01-02 | **Information Disclosure (I)** | `links.url` column (caption/transcript URLs) | LOW | accept | Les URLs sont extraites de descriptions publiques ou de transcripts locaux. Aucune PII au-delà. Stockage single-user (R032). |
| T-S02P01-03 | **Tampering (T)** — homograph/IDN URL confusables | `links.normalized_url` | MEDIUM | mitigate | La normalisation lowercase host limite les variations. Les IDN sont encodés en Punycode par `urllib.parse.urlparse`. S02-P02 teste les homographs via le corpus. Affichage CLI n'interprète pas les URLs (pas de clic). |
| T-S02P01-04 | **Denial of Service (D)** — explosion de liens par vidéo | `add_many_for_video` | LOW | mitigate | Dédup in-memory avant insertion. Typical caption < 5 URLs ; transcripts de shorts < 10. Pas de limite hard imposée en M007 — si nécessaire, caller tronque en amont (MetadataExtractStage). |
| T-S02P01-05 | **Repudiation (R)** | timestamp `created_at` | NONE | accept | Pas de besoin audit multi-user (R032). |
