---
plan_id: S01-P04
phase: M006/S01
wave: 4
depends_on: [S01-P01, S01-P02, S01-P03]
requirements: [R040, R042]
files_modified:
  - src/vidscope/adapters/ytdlp/downloader.py
  - scripts/backfill_creators.py
  - scripts/verify-s01.sh
  - tests/unit/adapters/ytdlp/test_downloader.py
  - tests/unit/scripts/__init__.py
  - tests/unit/scripts/test_backfill_creators.py
autonomous: true
---

## Objective

Clore M006/S01 avec la couche runtime et le script de migration :

1. **`YtdlpDownloader.probe` populé** (moitié adaptateur de T01) — extrait `uploader`, `uploader_id`, `uploader_url`, `channel_follower_count`, `uploader_thumbnail`, `uploader_verified` depuis le `info_dict` yt-dlp et les pose sur la `ProbeResult` étendue en P01. Aucun changement de port (fait en P01). Les tests existants (`vidscope cookies test`) restent verts car ils ne lisent que `.status` et `.title`.

2. **`scripts/backfill_creators.py`** (T08) — premier script Python sous `scripts/` (convention établie ici). CLI `argparse`, défaut `--dry-run` (obligatoire per D-02, CONTEXT.md §specifics : "One-shot scripts that silently mutate user data are a no-go"). `--apply` obligatoire pour les écritures. Itère les videos avec `creator_id IS NULL`, appelle `container.downloader.probe(url)`, construit `Creator` depuis `ProbeResult`, upsert creator + set `videos.creator_id` + `videos.author` via le write-through de P03, tout dans une UoW par vidéo (per-video transaction, Ctrl-C safe). `ProbeStatus.NOT_FOUND` ou `AUTH_REQUIRED` → `is_orphan=True` avec `platform_user_id="orphan:{videos.author or 'unknown'}"`. `NETWORK_ERROR` / `ERROR` → skip + report.

3. **Tests backfill** (T09 moitié backfill) — nouveau sous-package `tests/unit/scripts/` avec fixture de DB seedée + `_FakeDownloader` retournant des `ProbeResult` pré-définies (patron `tests/unit/application/test_watchlist.py::_FakeDownloader` 213-237). Couvre dry-run-zero-writes, apply-fills-all, orphan-on-not-found, idempotence, N=0.

4. **`scripts/verify-s01.sh`** (T10) — harness bash mirror de `verify-s07.sh` : lance les 4 quality gates + un smoke backfill contre une DB fixture. Exit 0 prouve S01 shippable. Accepte `--skip-backfill-smoke` pour les runs rapides.

**Note carry-over S02** : `IngestStage.execute` devra à terme upserter le creator avant l'upsert video et passer `creator=` à `VideoRepository.upsert_by_platform_id` — documenté dans P04 output pour le planner S02 ; pas implémenté ici.

## Tasks

<task id="T12-ytdlp-probe-populate">
  <name>Populer les 6 nouveaux champs de ProbeResult dans YtdlpDownloader.probe</name>

  <read_first>
    - `src/vidscope/adapters/ytdlp/downloader.py` lignes 264-315 — `probe()` actuelle (renvoie `ProbeResult` avec seulement `status, url, detail, title`)
    - `src/vidscope/adapters/ytdlp/downloader.py` lignes 391-396 — `_info_to_outcome` extrait déjà `info.get("uploader")` pour `IngestOutcome.author` : même extraction à appliquer dans probe
    - `src/vidscope/ports/pipeline.py` — `ProbeResult` étendu (après P01)
    - `.gsd/milestones/M006/slices/S01/S01-RESEARCH.md` §"yt-dlp info_dict fields → Creator fields" — table de mapping exact
    - `src/vidscope/adapters/ytdlp/downloader.py` lignes 553-575 — helpers `_str_or_none`, `_int_or_none` à REUTILISER (pas de duplication)
    - `tests/unit/adapters/ytdlp/test_downloader.py` — tests existants de `probe` à ne pas casser
  </read_first>

  <action>
  Modifier `src/vidscope/adapters/ytdlp/downloader.py` dans la méthode `probe()` (lignes 264-315). Entre le bloc actuel qui calcule `title` (ligne 309) et le `return ProbeResult(...)` (lignes 310-315), extraire les 6 nouveaux champs depuis `info` et les passer au constructor.

  Remplacer les lignes 309-315 par :

  ```python
          if not isinstance(info, dict):
              # Safety: info might be an unexpected type on some extractors
              return ProbeResult(
                  status=ProbeStatus.OK,
                  url=url,
                  detail="resolved but info dict not available",
              )

          title = info.get("title")
          uploader = _str_or_none(info.get("uploader") or info.get("channel"))
          uploader_id = _str_or_none(
              info.get("uploader_id") or info.get("channel_id")
          )
          uploader_url = _str_or_none(
              info.get("uploader_url") or info.get("channel_url")
          )
          channel_follower_count = _int_or_none(
              info.get("channel_follower_count")
              or info.get("channel_followers")
          )
          uploader_thumbnail = _extract_uploader_thumbnail(info)
          uploader_verified = _extract_uploader_verified(info)

          return ProbeResult(
              status=ProbeStatus.OK,
              url=url,
              detail=f"resolved: {title or info.get('id', '?')}",
              title=title if isinstance(title, str) else None,
              uploader=uploader,
              uploader_id=uploader_id,
              uploader_url=uploader_url,
              channel_follower_count=channel_follower_count,
              uploader_thumbnail=uploader_thumbnail,
              uploader_verified=uploader_verified,
          )
  ```

  Ajouter DEUX nouveaux helpers privés à la fin du fichier (après `_float_or_none`, vers ligne 576) :

  ```python
  def _extract_uploader_thumbnail(info: dict[str, Any]) -> str | None:
      """Resolve the creator avatar URL from a yt-dlp info_dict.

      yt-dlp exposes avatars under several keys depending on the
      extractor: ``uploader_thumbnail`` (sometimes a URL string,
      sometimes a list of {url, ...} dicts), ``channel_thumbnail``
      (YouTube), or inside the general ``thumbnails`` list filtered
      by author context (rare). Preference order is
      explicit-single → list-first → None.
      """
      candidate = info.get("uploader_thumbnail") or info.get("channel_thumbnail")
      if isinstance(candidate, str):
          return _str_or_none(candidate)
      if isinstance(candidate, list) and candidate:
          first = candidate[0]
          if isinstance(first, dict):
              return _str_or_none(first.get("url"))
          if isinstance(first, str):
              return _str_or_none(first)
      return None


  def _extract_uploader_verified(info: dict[str, Any]) -> bool | None:
      """Resolve the verified-badge flag from a yt-dlp info_dict.

      Exposed inconsistently across extractors; ``None`` is a legit
      outcome. Tried keys: ``channel_verified``, ``uploader_verified``.
      """
      for key in ("channel_verified", "uploader_verified"):
          value = info.get(key)
          if isinstance(value, bool):
              return value
      return None
  ```

  Ne modifier aucune autre méthode. Les tests existants de `probe` doivent rester verts car les 6 nouveaux champs sont optionnels avec défaut `None`.
  </action>

  <acceptance_criteria>
    - `grep -q "uploader=uploader" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `grep -q "uploader_id=uploader_id" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `grep -q "channel_follower_count=channel_follower_count" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `grep -q "def _extract_uploader_thumbnail" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `grep -q "def _extract_uploader_verified" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py -x -q` exit 0 (tests existants probe restent verts — rétrocompatibilité)
    - Ajouter au moins 3 nouveaux tests dans `tests/unit/adapters/ytdlp/test_downloader.py` (classe `TestProbeCreatorExtraction` ou similaire) qui stubent `yt_dlp.YoutubeDL.extract_info` avec un dict contenant `uploader_id`, `channel_follower_count`, `uploader_thumbnail` et vérifient que `ProbeResult` les porte. Ces tests doivent exit 0 sur `python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py::TestProbeCreatorExtraction -x -q`.
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (contrat inchangé : downloader importe `vidscope.ports.ProbeResult` via `vidscope.ports` comme avant)
  </acceptance_criteria>
</task>

<task id="T13-backfill-script">
  <name>Créer scripts/backfill_creators.py (argparse, --dry-run par défaut, per-video UoW, orphan sur 404)</name>

  <read_first>
    - `.gsd/milestones/M006/slices/S01/S01-RESEARCH.md` §"Backfill script shape" lignes 295-334 — structure argparse à suivre
    - `.gsd/milestones/M006/slices/S01/S01-RESEARCH.md` §"404 / AUTH_REQUIRED path → is_orphan=true" lignes 339-349 — mapping exact ProbeStatus → comportement
    - `.gsd/milestones/M006/slices/S01/S01-CONTEXT.md` §specifics — "Backfill dry-run is mandatory. The CLI must default to dry-run; the destructive mode requires an explicit flag (e.g. `--apply`). One-shot scripts that silently mutate user data are a no-go."
    - `src/vidscope/infrastructure/container.py` — `build_container` utilisé pour obtenir downloader + UoW factory
    - `src/vidscope/adapters/sqlite/unit_of_work.py` — `uow.creators`, `uow.videos` exposés (après P03)
    - `src/vidscope/ports/pipeline.py` — `ProbeResult`, `ProbeStatus` (après P01)
    - `scripts/verify-s07.sh` — convention bash/exit-code/output à mirroir pour verify-s01.sh
    - `src/vidscope/domain/__init__.py` — `Creator`, `Platform`, `PlatformUserId` importables
  </read_first>

  <action>
  Créer `scripts/backfill_creators.py` avec ce contenu exact :

  ```python
  """Backfill videos.creator_id from existing M001-M005 rows (M006/S01).

  Default mode is --dry-run: probe every video via Downloader.probe(),
  print the creator row that would be upserted + the resulting
  videos.creator_id, write NOTHING. --apply is required to actually
  mutate the database.

  Per-video transaction: each video's creator upsert + video update
  runs in its own SqliteUnitOfWork. A mid-run Ctrl-C leaves the DB in
  a consistent state (every committed creator has a matching video FK;
  no half-written creator rows).

  Idempotent: skip videos where creator_id IS NOT NULL.

  Orphan path (D-02): ProbeStatus.NOT_FOUND or AUTH_REQUIRED produces a
  creator row with is_orphan=True and platform_user_id synthesised as
  "orphan:{author or 'unknown'}" so UNIQUE(platform, platform_user_id)
  stays satisfiable for every legacy video.

  Usage
  -----
      python -m uv run python scripts/backfill_creators.py            # dry-run (default)
      python -m uv run python scripts/backfill_creators.py --apply    # actually mutate
      python -m uv run python scripts/backfill_creators.py --apply --limit 5

  Exit codes
  ----------
      0  — completed (in dry-run mode, this is a pure report; in --apply
           mode, at least one row was processed successfully)
      1  — fatal error (bad DB path, container build failed)
      2  — partial failure (some probes raised, some succeeded — see
           the summary line)
  """

  from __future__ import annotations

  import argparse
  import sys
  from dataclasses import dataclass

  from sqlalchemy import select

  from vidscope.adapters.sqlite.schema import videos as videos_table
  from vidscope.domain import Creator, Platform, PlatformUserId
  from vidscope.infrastructure.container import Container, build_container
  from vidscope.ports import ProbeResult, ProbeStatus

  __all__ = ["main"]


  @dataclass(slots=True)
  class BackfillStats:
      total: int = 0
      ok: int = 0
      orphan: int = 0
      skipped_already_linked: int = 0
      failed: int = 0


  def main(argv: list[str] | None = None, *, container: Container | None = None) -> int:
      parser = argparse.ArgumentParser(
          description=__doc__,
          formatter_class=argparse.RawDescriptionHelpFormatter,
      )
      parser.add_argument(
          "--apply",
          action="store_true",
          help="Actually write to the DB. Default is --dry-run (zero writes).",
      )
      parser.add_argument(
          "--limit",
          type=int,
          default=None,
          help="Stop after N videos (useful for testing).",
      )
      args = parser.parse_args(argv)
      dry_run = not args.apply

      if container is None:
          try:
              container = build_container()
          except Exception as exc:  # noqa: BLE001
              sys.stderr.write(f"fatal: could not build container: {exc}\n")
              return 1

      mode_label = "DRY-RUN (no writes)" if dry_run else "APPLY (WILL MUTATE)"
      sys.stdout.write(f"backfill_creators.py :: mode = {mode_label}\n")
      if dry_run:
          sys.stdout.write("  (pass --apply to actually write)\n")

      stats = _run_backfill(container, dry_run=dry_run, limit=args.limit)

      sys.stdout.write(
          f"\n=== Summary ===\n"
          f"  Total videos scanned:        {stats.total}\n"
          f"  Already linked (skipped):    {stats.skipped_already_linked}\n"
          f"  Linked to fresh creator:     {stats.ok}\n"
          f"  Linked to orphan creator:    {stats.orphan}\n"
          f"  Failed (probe error):        {stats.failed}\n"
      )
      if stats.failed > 0 and not dry_run:
          return 2
      return 0


  def _run_backfill(
      container: Container, *, dry_run: bool, limit: int | None
  ) -> BackfillStats:
      """Iterate videos with creator_id IS NULL, probe each, upsert
      creator + set videos.creator_id (unless dry-run). Per-video UoW
      for Ctrl-C safety.
      """
      stats = BackfillStats()

      # First pass: list target videos with a READ-ONLY UoW. We release
      # this connection before opening per-video write UoWs so the writes
      # don't contend with the long-lived read.
      with container.unit_of_work() as uow:
          conn = uow._connection  # type: ignore[attr-defined]  # internal but stable
          stmt = select(
              videos_table.c.id,
              videos_table.c.platform,
              videos_table.c.platform_id,
              videos_table.c.url,
              videos_table.c.author,
              videos_table.c.creator_id,
          )
          rows = conn.execute(stmt).mappings().all()

      target_rows = [r for r in rows if r["creator_id"] is None]
      stats.total = len(rows)
      stats.skipped_already_linked = len(rows) - len(target_rows)

      if limit is not None:
          target_rows = target_rows[:limit]

      for idx, row in enumerate(target_rows, start=1):
          video_url = str(row["url"])
          platform_str = str(row["platform"])
          platform = Platform(platform_str)
          legacy_author = row["author"]

          sys.stdout.write(
              f"[{idx}/{len(target_rows)}] probing {platform_str}/"
              f"{row['platform_id']} ... "
          )
          try:
              probe = container.downloader.probe(video_url)
          except Exception as exc:  # noqa: BLE001
              # Downloader.probe is documented never to raise (every
              # failure is encoded in status), but guard anyway.
              sys.stdout.write(f"EXCEPTION: {exc}\n")
              stats.failed += 1
              continue

          creator = _creator_from_probe(
              probe=probe, platform=platform, legacy_author=legacy_author
          )
          if creator is None:
              # NETWORK_ERROR / ERROR / UNSUPPORTED — don't create orphan,
              # just report and skip this video.
              sys.stdout.write(f"SKIP ({probe.status.value}: {probe.detail[:80]})\n")
              stats.failed += 1
              continue

          label = "ORPHAN" if creator.is_orphan else "OK"
          sys.stdout.write(
              f"{label} -> {creator.platform.value}/{creator.platform_user_id}"
              f" ({creator.display_name or 'no display_name'})\n"
          )

          if dry_run:
              if creator.is_orphan:
                  stats.orphan += 1
              else:
                  stats.ok += 1
              continue

          # Per-video write transaction: creator upsert + video link.
          try:
              with container.unit_of_work() as uow:
                  stored_creator = uow.creators.upsert(creator)
                  _link_video_to_creator(
                      uow, video_row=row, creator=stored_creator
                  )
              if creator.is_orphan:
                  stats.orphan += 1
              else:
                  stats.ok += 1
          except Exception as exc:  # noqa: BLE001
              sys.stdout.write(f"    FAILED WRITE: {exc}\n")
              stats.failed += 1

      return stats


  def _creator_from_probe(
      *,
      probe: ProbeResult,
      platform: Platform,
      legacy_author: str | None,
  ) -> Creator | None:
      """Build a Creator from a ProbeResult. Returns None for transient
      failures (network / unknown error) where orphan creation would
      pollute data quality.
      """
      if probe.status == ProbeStatus.OK:
          platform_user_id = probe.uploader_id or probe.uploader
          if not platform_user_id:
              # Extractor didn't expose uploader_id AND uploader — extremely
              # rare but treat as orphan to preserve FK invariants.
              return _orphan_creator(platform=platform, legacy_author=legacy_author)
          return Creator(
              platform=platform,
              platform_user_id=PlatformUserId(str(platform_user_id)),
              handle=_handle_best_effort(probe),
              display_name=probe.uploader,
              profile_url=probe.uploader_url,
              avatar_url=probe.uploader_thumbnail,
              follower_count=probe.channel_follower_count,
              is_verified=probe.uploader_verified,
              is_orphan=False,
          )

      if probe.status in (ProbeStatus.NOT_FOUND, ProbeStatus.AUTH_REQUIRED):
          return _orphan_creator(platform=platform, legacy_author=legacy_author)

      # NETWORK_ERROR / ERROR / UNSUPPORTED — don't create an orphan,
      # so the user can retry without polluting the creator table.
      return None


  def _orphan_creator(
      *, platform: Platform, legacy_author: str | None
  ) -> Creator:
      """Orphan fallback: synthesise a stable platform_user_id from the
      legacy videos.author so UNIQUE(platform, platform_user_id) stays
      satisfiable and is_orphan=True surfaces the condition to the
      user."""
      author = legacy_author or "unknown"
      synthetic = f"orphan:{author}"
      return Creator(
          platform=platform,
          platform_user_id=PlatformUserId(synthetic),
          display_name=author,
          is_orphan=True,
      )


  def _handle_best_effort(probe: ProbeResult) -> str | None:
      """Derive a @-handle from probe fields. yt-dlp doesn't expose a
      clean "handle" field that works across all platforms; use the
      uploader name prefixed by @ as a pragmatic default (open Q2 in
      S01-RESEARCH.md)."""
      if probe.uploader:
          return f"@{probe.uploader}"
      return None


  def _link_video_to_creator(uow, *, video_row, creator: Creator) -> None:  # type: ignore[no-untyped-def]
      """Set videos.creator_id + videos.author (write-through) via a
      raw UPDATE since the existing VideoRepository.upsert_by_platform_id
      path requires the full Video entity. For backfill we already know
      the row id — a targeted UPDATE is cleaner than re-reading + re-
      upserting.
      """
      from sqlalchemy import update

      stmt = (
          update(videos_table)
          .where(videos_table.c.id == int(video_row["id"]))
          .values(
              creator_id=int(creator.id) if creator.id is not None else None,
              author=creator.display_name,  # D-03 write-through
          )
      )
      conn = uow._connection  # type: ignore[attr-defined]
      conn.execute(stmt)


  if __name__ == "__main__":
      sys.exit(main())
  ```

  **Note technique** : le script accède à `uow._connection` qui est un attribut privé. C'est acceptable ici parce que (a) `backfill_creators.py` vit sous `scripts/`, hors du package `vidscope` (donc hors de la portée de import-linter) (b) la sémantique d'UPDATE ciblé par `id` connu est plus propre qu'un re-upsert full-video pour un script de migration one-shot. Documenté dans la docstring du helper.
  </action>

  <acceptance_criteria>
    - `test -f scripts/backfill_creators.py`
    - `grep -q 'description=__doc__' scripts/backfill_creators.py` exit 0
    - `grep -q '"--apply"' scripts/backfill_creators.py` exit 0
    - `grep -q "dry_run = not args.apply" scripts/backfill_creators.py` exit 0
    - `grep -q "is_orphan=True" scripts/backfill_creators.py` exit 0
    - `grep -q 'f"orphan:{author}"' scripts/backfill_creators.py` exit 0
    - `grep -q "ProbeStatus.NOT_FOUND" scripts/backfill_creators.py` exit 0
    - `grep -q "ProbeStatus.AUTH_REQUIRED" scripts/backfill_creators.py` exit 0
    - `python -m uv run python scripts/backfill_creators.py --help` exit 0 et affiche `--apply` et `--limit`
    - `python -m uv run python -c "import scripts.backfill_creators; print('importable')"` sort `importable`
    - `python -m uv run ruff check scripts` exit 0 (le script respecte ruff)
  </acceptance_criteria>
</task>

<task id="T14-backfill-tests">
  <name>Tests backfill : dry-run, apply, orphan, idempotence, N=0 (_FakeDownloader stub)</name>

  <read_first>
    - `tests/unit/application/test_watchlist.py` lignes 213-237 — patron `_FakeDownloader` qui retourne des réponses pré-seedées
    - `tests/unit/adapters/sqlite/conftest.py` — fixture `engine`
    - `scripts/backfill_creators.py` — fonction `main(argv, container=)` qui accepte un container injecté (pour les tests)
    - `src/vidscope/ports/pipeline.py` — `ProbeResult`, `ProbeStatus`, `Downloader` Protocol
    - `src/vidscope/infrastructure/container.py` — shape de `Container` (dataclass frozen)
  </read_first>

  <action>
  Créer le sous-package `tests/unit/scripts/` puis un fichier de tests.

  **1. Créer `tests/unit/scripts/__init__.py` (fichier vide)** :

  Fichier contenant uniquement une docstring :
  ```python
  """Tests for one-shot maintenance scripts under scripts/."""
  ```

  **2. Créer `tests/unit/scripts/test_backfill_creators.py`** :

  ```python
  """Tests for scripts/backfill_creators.py (M006/S01)."""

  from __future__ import annotations

  from dataclasses import dataclass, field, replace
  from pathlib import Path
  from typing import Any

  import pytest
  from sqlalchemy import Engine, text

  from vidscope.adapters.sqlite.schema import init_db
  from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
  from vidscope.infrastructure.config import Config
  from vidscope.infrastructure.container import Container, SystemClock
  from vidscope.infrastructure.sqlite_engine import build_engine
  from vidscope.ports import (
      ChannelEntry,
      IngestOutcome,
      ProbeResult,
      ProbeStatus,
  )

  # Import the script module to test its main() entry point directly.
  # scripts/ is not a package by default; add it to sys.path via a
  # conftest-style pattern.
  import importlib.util
  import sys

  _SCRIPT_PATH = (
      Path(__file__).resolve().parents[3] / "scripts" / "backfill_creators.py"
  )
  _spec = importlib.util.spec_from_file_location(
      "backfill_creators_module", _SCRIPT_PATH
  )
  assert _spec is not None and _spec.loader is not None
  backfill_module = importlib.util.module_from_spec(_spec)
  sys.modules["backfill_creators_module"] = backfill_module
  _spec.loader.exec_module(backfill_module)


  # ---------------------------------------------------------------------------
  # Test doubles
  # ---------------------------------------------------------------------------


  @dataclass
  class _FakeDownloader:
      """Stub Downloader for backfill tests. Returns pre-seeded
      ProbeResult keyed by URL.
      """

      probe_map: dict[str, ProbeResult] = field(default_factory=dict)

      def probe(self, url: str) -> ProbeResult:
          if url in self.probe_map:
              return self.probe_map[url]
          return ProbeResult(
              status=ProbeStatus.ERROR, url=url, detail="no stub seeded"
          )

      def download(self, url: str, destination_dir: str) -> IngestOutcome:
          raise NotImplementedError("unused by backfill")

      def list_channel_videos(
          self, url: str, *, limit: int = 10
      ) -> list[ChannelEntry]:
          raise NotImplementedError("unused by backfill")


  # ---------------------------------------------------------------------------
  # Fixtures
  # ---------------------------------------------------------------------------


  @pytest.fixture()
  def seeded_engine(tmp_path: Path) -> Engine:
      """Pre-M006-style DB with 3 videos, creator_id all NULL."""
      db_path = tmp_path / "seed.db"
      eng = build_engine(db_path)
      init_db(eng)

      with eng.begin() as conn:
          conn.execute(
              text(
                  "INSERT INTO videos (platform, platform_id, url, author) "
                  "VALUES "
                  "('youtube', 'yt_ok_1', 'https://y/ok_1', 'Alice'), "
                  "('tiktok',  'tt_ok_2', 'https://t/ok_2', 'Bob'), "
                  "('youtube', 'yt_404_3','https://y/404_3','Charlie')"
              )
          )
      return eng


  def _fake_container(engine: Engine, downloader: _FakeDownloader) -> Container:
      """Build a minimal Container backed by the seeded engine + stub
      downloader. Only fields backfill_creators.py touches are wired.
      """
      # We can't easily construct a real Container without all repos,
      # but Container is a frozen dataclass so we can use a small
      # ad-hoc stand-in. The script only uses .downloader and
      # .unit_of_work.
      @dataclass(frozen=True)
      class _BackfillContainer:
          downloader: Any
          unit_of_work: Any

      def _uow_factory() -> SqliteUnitOfWork:
          return SqliteUnitOfWork(engine)

      return _BackfillContainer(  # type: ignore[return-value]
          downloader=downloader, unit_of_work=_uow_factory
      )


  # ---------------------------------------------------------------------------
  # Tests — R042
  # ---------------------------------------------------------------------------


  class TestBackfillDryRun:
      def test_dry_run_writes_nothing(
          self, seeded_engine: Engine
      ) -> None:
          """Default mode (no --apply) must not mutate the DB."""
          downloader = _FakeDownloader(
              probe_map={
                  "https://y/ok_1": ProbeResult(
                      status=ProbeStatus.OK,
                      url="https://y/ok_1",
                      detail="ok",
                      title="Ok1",
                      uploader="AliceChannel",
                      uploader_id="UC_alice",
                  ),
                  "https://t/ok_2": ProbeResult(
                      status=ProbeStatus.OK,
                      url="https://t/ok_2",
                      detail="ok",
                      title="Ok2",
                      uploader="BobTok",
                      uploader_id="123456",
                  ),
                  "https://y/404_3": ProbeResult(
                      status=ProbeStatus.NOT_FOUND,
                      url="https://y/404_3",
                      detail="gone",
                  ),
              }
          )
          container = _fake_container(seeded_engine, downloader)

          exit_code = backfill_module.main([], container=container)
          assert exit_code == 0

          with SqliteUnitOfWork(seeded_engine) as uow:
              assert uow.creators.count() == 0
              # Every video still has creator_id IS NULL
              conn = uow._connection  # type: ignore[attr-defined]
              rows = conn.execute(
                  text("SELECT creator_id FROM videos")
              ).all()
              assert all(r[0] is None for r in rows)


  class TestBackfillApply:
      def test_apply_fills_creator_id_for_every_video(
          self, seeded_engine: Engine
      ) -> None:
          downloader = _FakeDownloader(
              probe_map={
                  "https://y/ok_1": ProbeResult(
                      status=ProbeStatus.OK,
                      url="https://y/ok_1",
                      detail="ok",
                      title="Ok1",
                      uploader="AliceChannel",
                      uploader_id="UC_alice",
                  ),
                  "https://t/ok_2": ProbeResult(
                      status=ProbeStatus.OK,
                      url="https://t/ok_2",
                      detail="ok",
                      title="Ok2",
                      uploader="BobTok",
                      uploader_id="123456",
                  ),
                  "https://y/404_3": ProbeResult(
                      status=ProbeStatus.NOT_FOUND,
                      url="https://y/404_3",
                      detail="gone",
                  ),
              }
          )
          container = _fake_container(seeded_engine, downloader)

          exit_code = backfill_module.main(["--apply"], container=container)
          assert exit_code == 0

          with SqliteUnitOfWork(seeded_engine) as uow:
              assert uow.creators.count() == 3  # 2 OK + 1 orphan
              conn = uow._connection  # type: ignore[attr-defined]
              rows = conn.execute(
                  text(
                      "SELECT platform_id, creator_id, author FROM videos "
                      "ORDER BY platform_id"
                  )
              ).all()
              for row in rows:
                  assert row[1] is not None, f"video {row[0]} still unlinked"

      def test_apply_orphan_on_not_found(
          self, seeded_engine: Engine
      ) -> None:
          downloader = _FakeDownloader(
              probe_map={
                  "https://y/ok_1": ProbeResult(
                      status=ProbeStatus.OK,
                      url="https://y/ok_1",
                      detail="ok",
                      title="Ok1",
                      uploader="Alice",
                      uploader_id="UC_alice",
                  ),
                  "https://t/ok_2": ProbeResult(
                      status=ProbeStatus.OK,
                      url="https://t/ok_2",
                      detail="ok",
                      uploader="Bob",
                      uploader_id="123",
                  ),
                  "https://y/404_3": ProbeResult(
                      status=ProbeStatus.NOT_FOUND,
                      url="https://y/404_3",
                      detail="gone",
                  ),
              }
          )
          container = _fake_container(seeded_engine, downloader)
          backfill_module.main(["--apply"], container=container)

          with SqliteUnitOfWork(seeded_engine) as uow:
              conn = uow._connection  # type: ignore[attr-defined]
              orphans = conn.execute(
                  text("SELECT COUNT(*) FROM creators WHERE is_orphan = 1")
              ).scalar()
              assert orphans == 1
              orphan_row = conn.execute(
                  text(
                      "SELECT platform_user_id FROM creators WHERE is_orphan = 1"
                  )
              ).first()
              assert orphan_row is not None
              assert orphan_row[0].startswith("orphan:")

      def test_apply_twice_is_idempotent(self, seeded_engine: Engine) -> None:
          downloader = _FakeDownloader(
              probe_map={
                  "https://y/ok_1": ProbeResult(
                      status=ProbeStatus.OK,
                      url="https://y/ok_1",
                      detail="ok",
                      uploader="Alice",
                      uploader_id="UC_alice",
                  ),
                  "https://t/ok_2": ProbeResult(
                      status=ProbeStatus.OK,
                      url="https://t/ok_2",
                      detail="ok",
                      uploader="Bob",
                      uploader_id="123",
                  ),
                  "https://y/404_3": ProbeResult(
                      status=ProbeStatus.NOT_FOUND,
                      url="https://y/404_3",
                      detail="gone",
                  ),
              }
          )
          container = _fake_container(seeded_engine, downloader)
          backfill_module.main(["--apply"], container=container)

          # Snapshot state
          with SqliteUnitOfWork(seeded_engine) as uow:
              first_count = uow.creators.count()

          # Second run should be a no-op (videos have creator_id set)
          backfill_module.main(["--apply"], container=container)

          with SqliteUnitOfWork(seeded_engine) as uow:
              assert uow.creators.count() == first_count


  class TestBackfillEdgeCases:
      def test_empty_db_exits_cleanly(self, tmp_path: Path) -> None:
          db_path = tmp_path / "empty.db"
          eng = build_engine(db_path)
          init_db(eng)

          downloader = _FakeDownloader()
          container = _fake_container(eng, downloader)

          exit_code = backfill_module.main(["--apply"], container=container)
          assert exit_code == 0

          with SqliteUnitOfWork(eng) as uow:
              assert uow.creators.count() == 0

      def test_help_prints_and_exits_zero(
          self, capsys: pytest.CaptureFixture[str]
      ) -> None:
          with pytest.raises(SystemExit) as excinfo:
              backfill_module.main(["--help"])
          assert excinfo.value.code == 0
          out = capsys.readouterr().out
          assert "--apply" in out
          assert "--limit" in out
  ```
  </action>

  <acceptance_criteria>
    - `test -f tests/unit/scripts/__init__.py`
    - `test -f tests/unit/scripts/test_backfill_creators.py`
    - `python -m uv run pytest tests/unit/scripts/test_backfill_creators.py -x -q` exit 0
    - `python -m uv run pytest tests/unit/scripts/test_backfill_creators.py::TestBackfillDryRun::test_dry_run_writes_nothing -x -q` exit 0
    - `python -m uv run pytest tests/unit/scripts/test_backfill_creators.py::TestBackfillApply::test_apply_fills_creator_id_for_every_video -x -q` exit 0
    - `python -m uv run pytest tests/unit/scripts/test_backfill_creators.py::TestBackfillApply::test_apply_orphan_on_not_found -x -q` exit 0
    - `python -m uv run pytest tests/unit/scripts/test_backfill_creators.py::TestBackfillApply::test_apply_twice_is_idempotent -x -q` exit 0
    - `python -m uv run pytest tests/unit/scripts/test_backfill_creators.py::TestBackfillEdgeCases -x -q` exit 0
    - `python -m uv run pytest -q` exit 0 (suite complète verte)
    - `python -m uv run ruff check src tests scripts` exit 0
    - `python -m uv run mypy src` exit 0 (le script sous scripts/ n'est pas dans `files = ["src/vidscope"]` donc mypy ne l'analyse pas, ok)
  </acceptance_criteria>
</task>

<task id="T15-verify-s01-script">
  <name>Harness bash scripts/verify-s01.sh : 4 quality gates + backfill smoke contre fixture DB</name>

  <read_first>
    - `scripts/verify-s07.sh` — template bash avec `set -euo pipefail`, `run_step()`, `trap cleanup`, couleurs TTY, summary final. Mirroir exact à adapter.
    - `scripts/backfill_creators.py` — le script créé par T13 (accepte `--apply`, `--limit`, `--help`)
  </read_first>

  <action>
  Créer `scripts/verify-s01.sh`. Il DOIT être exécutable sur Windows git-bash, macOS et Linux (D018 cross-platform). Couvre :

  1. `uv sync`
  2. `ruff check src tests scripts`
  3. `mypy src`
  4. `lint-imports` (les 9 contrats)
  5. `pytest -q` (suite complète)
  6. Backfill smoke : création d'une DB fixture vide → seed 2 vidéos M001-M005 style → `python scripts/backfill_creators.py --help` → `python scripts/backfill_creators.py` (dry-run, assert zéro écriture) → puis `python scripts/backfill_creators.py --apply` avec un `VIDSCOPE_DATA_DIR` isolé (la commande dépendra d'une vraie probe réseau ; pour le smoke on se contente du --help + dry-run qui sont offline)

  Contenu exact à créer :

  ```bash
  #!/usr/bin/env bash
  # End-to-end verification of M006/S01 — Creator domain foundation.
  #
  # Runs every check that proves S01's success criteria hold on a
  # clean environment plus an offline backfill smoke.
  #
  # Usage
  # -----
  #     bash scripts/verify-s01.sh                       # full run
  #     bash scripts/verify-s01.sh --skip-backfill-smoke # quality gates only
  #
  # Exit codes
  # ----------
  # 0 — every required step passed
  # 1 — at least one required step failed
  #
  # Portability
  # -----------
  # Works on Windows git-bash, macOS, and Linux via `python -m uv run`.

  set -euo pipefail

  SKIP_BACKFILL=false
  for arg in "$@"; do
      case "${arg}" in
          --skip-backfill-smoke) SKIP_BACKFILL=true ;;
          -h|--help)
              sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
              exit 0
              ;;
          *)
              echo "unknown argument: ${arg}" >&2
              exit 1
              ;;
      esac
  done

  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
  cd "${REPO_ROOT}"

  if [[ -t 1 ]]; then
      BOLD="\033[1m" GREEN="\033[0;32m" RED="\033[0;31m"
      YELLOW="\033[0;33m" CYAN="\033[0;36m" DIM="\033[2m" RESET="\033[0m"
  else
      BOLD="" GREEN="" RED="" YELLOW="" CYAN="" DIM="" RESET=""
  fi

  step_count=0
  failed_steps=()

  run_step() {
      local name="$1"
      shift
      step_count=$((step_count + 1))
      printf "\n${CYAN}${BOLD}[%02d] %s${RESET}\n" "${step_count}" "${name}"
      printf "${DIM}\$ %s${RESET}\n" "$*"
      if "$@"; then
          printf "${GREEN}✓${RESET} %s\n" "${name}"
      else
          local exit_code=$?
          printf "${RED}✗${RESET} %s (exit %d)\n" "${name}" "${exit_code}"
          failed_steps+=("${name}")
      fi
  }

  TMP_DATA_DIR="$(mktemp -d -t vidscope-verify-s01-XXXXXX)"
  trap 'rm -rf "${TMP_DATA_DIR}"' EXIT

  export VIDSCOPE_DATA_DIR="${TMP_DATA_DIR}"

  printf "${BOLD}Repo:${RESET}     %s\n" "${REPO_ROOT}"
  printf "${BOLD}Sandbox:${RESET}  %s\n" "${TMP_DATA_DIR}"

  # --- 1. Dependency sync ---
  run_step "uv sync" python -m uv sync

  # --- 2. Quality gates ---
  run_step "ruff check" python -m uv run ruff check src tests scripts
  run_step "mypy strict" python -m uv run mypy src
  run_step "import-linter (9 contracts)" python -m uv run lint-imports
  run_step "pytest unit suite" python -m uv run pytest -q

  # --- 3. M006/S01 targeted tests ---
  run_step "creator repo tests" \
      python -m uv run pytest tests/unit/adapters/sqlite/test_creator_repository.py -x -q
  run_step "schema creators tests" \
      python -m uv run pytest tests/unit/adapters/sqlite/test_schema.py::TestCreatorsSchema tests/unit/adapters/sqlite/test_schema.py::TestVideosCreatorIdAlter -x -q
  run_step "write-through regression" \
      python -m uv run pytest tests/unit/adapters/sqlite/test_video_repository.py::TestWriteThroughAuthor -x -q
  run_step "UoW creator-txn tests" \
      python -m uv run pytest tests/unit/adapters/sqlite/test_unit_of_work.py::TestCreatorInTransaction -x -q
  run_step "backfill tests" \
      python -m uv run pytest tests/unit/scripts/test_backfill_creators.py -x -q

  # --- 4. Backfill script smoke (offline: --help + dry-run on empty sandbox) ---
  if [[ "${SKIP_BACKFILL}" = true ]]; then
      printf "\n${YELLOW}${BOLD}[backfill smoke] skipped${RESET}\n"
  else
      run_step "backfill --help" \
          python -m uv run python scripts/backfill_creators.py --help
      # Dry-run on an empty sandbox: nothing to probe, exits 0, zero writes.
      run_step "backfill dry-run on empty sandbox" \
          python -m uv run python scripts/backfill_creators.py
  fi

  # --- Summary ---
  printf "\n${BOLD}=== Summary ===${RESET}\n"
  printf "Total steps: %d\n" "${step_count}"
  printf "Failed:      %d\n" "${#failed_steps[@]}"

  if [[ "${#failed_steps[@]}" -eq 0 ]]; then
      printf "\n${GREEN}${BOLD}✓ S01 verification PASSED${RESET}\n"
      printf "${DIM}M006/S01 foundations shippable: Creator domain + CreatorRepository + SqlCreatorRepository + schema migration + backfill script.${RESET}\n"
      exit 0
  else
      printf "\n${RED}${BOLD}✗ S01 verification FAILED${RESET}\n"
      for step in "${failed_steps[@]}"; do
          printf "${RED}  - %s${RESET}\n" "${step}"
      done
      exit 1
  fi
  ```

  Rendre le fichier exécutable (permission Unix) : marquer dans le commit. Sur Windows git-bash la permission d'exécution passe par `git update-index --chmod=+x`. Le test d'acceptance n'a pas besoin de vérifier `+x` (on peut invoquer via `bash scripts/verify-s01.sh`).
  </action>

  <acceptance_criteria>
    - `test -f scripts/verify-s01.sh`
    - `grep -q "set -euo pipefail" scripts/verify-s01.sh` exit 0
    - `grep -q "lint-imports" scripts/verify-s01.sh` exit 0
    - `grep -q "backfill_creators.py" scripts/verify-s01.sh` exit 0
    - `grep -q "TestCreatorsSchema" scripts/verify-s01.sh` exit 0
    - `grep -q "TestWriteThroughAuthor" scripts/verify-s01.sh` exit 0
    - `bash scripts/verify-s01.sh --help` exit 0 et affiche l'aide
    - `bash scripts/verify-s01.sh --skip-backfill-smoke` exit 0 (les 4 quality gates + targeted tests tous verts)
  </acceptance_criteria>
</task>

## Verification Criteria

```bash
# Tests par couche (spécifique → large)
python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py -x -q
python -m uv run pytest tests/unit/scripts/test_backfill_creators.py -x -q

# Suite complète + aucune régression
python -m uv run pytest -q

# 4 quality gates
python -m uv run ruff check src tests scripts
python -m uv run mypy src
python -m uv run lint-imports

# Harness complet M006/S01
bash scripts/verify-s01.sh

# Backfill smoke explicite
python -m uv run python scripts/backfill_creators.py --help
python -m uv run python scripts/backfill_creators.py  # dry-run, zero writes
```

## Must-Haves

- `YtdlpDownloader.probe` extrait `uploader`, `uploader_id`, `uploader_url`, `channel_follower_count`, `uploader_thumbnail`, `uploader_verified` depuis `info_dict` et les pose sur la `ProbeResult` étendue ; les tests existants `probe()` restent verts (backward-compat)
- `scripts/backfill_creators.py` existe, fichier Python sous `scripts/` (premier du genre — établit la convention)
- Mode par défaut = dry-run ; `--apply` obligatoire pour muter la DB ; `--limit N` pour les tests
- Per-video UoW : chaque vidéo obtient sa transaction individuelle (Ctrl-C safe, pas de rows half-written)
- Script idempotent : `creator_id IS NULL` filter + re-run = no-op
- Orphan path : `ProbeStatus.NOT_FOUND` et `AUTH_REQUIRED` → `Creator(is_orphan=True, platform_user_id=f"orphan:{legacy_author}")` (chaque vidéo obtient un FK peuplé, pas de perte de données)
- Non-orphan path : `ProbeStatus.NETWORK_ERROR` / `ERROR` / `UNSUPPORTED` → skip + report (pas d'orphan créé — préserve la qualité des données)
- Tests backfill (`tests/unit/scripts/test_backfill_creators.py`) couvrent : dry-run-zero-writes, apply-fills-all, orphan-on-not-found, idempotence (2e run = no-op), empty DB, `--help`
- `scripts/verify-s01.sh` existe ; lance uv sync + 4 quality gates + tests ciblés M006/S01 + backfill smoke ; exit 0 atteste que S01 est shippable
- 9 contrats import-linter verts après l'entièreté de S01 ; mypy strict vert ; ruff vert
- **Carry-over documenté pour S02** : `IngestStage.execute` devra upserter creator avant video et passer `creator=` à `VideoRepository.upsert_by_platform_id` ; le test de régression D-03 existe déjà (P03).

## Threat Model

Surface de menace : backfill écrit dans la DB utilisateur à partir de données réseau externes. Risques principaux identifiés dans la consigne de planification.

| # | STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-P04-01 | **Tampering (T)** — yt-dlp response tampering (MITM, malicious extractor, compromised platform response) | `YtdlpDownloader.probe` → `ProbeResult.uploader*` → backfill write | MEDIUM | mitigate | Les valeurs issues de yt-dlp ne sont JAMAIS concaténées dans du SQL : elles transitent par les `Creator` dataclass (type-safe), puis par `sqlite_insert().values(**payload)` (bind parameters). Un `uploader_id` contenant `'; DROP TABLE creators;--` est stocké tel quel comme string — pas interprété. Les `handle`/`display_name` sont stockés en UTF-8 sans échappement ni HTML-rendering (on est CLI-only, pas HTML). Résidu de risque : si l'attaquant fournit un `uploader_id` très long pour remplir la DB, la contrainte SQLite `String(255)` limite la taille — acceptable. |
| T-P04-02 | **Tampering (T) / SQL injection** — handle, display_name | `CreatorRepositorySQLite.upsert` (P03) via backfill | LOW | mitigate (déjà fait en P03) | Voir T-P03-01 : tous les writes passent par bind parameters. Répété ici pour la traçabilité. |
| T-P04-03 | **Data loss (Repudiation/Integrity)** — `--apply` accidentel | backfill CLI | HIGH | mitigate | `--dry-run` est le défaut ABSOLU. `--apply` est un flag explicite obligatoire, le script affiche `mode = DRY-RUN (no writes)` ou `mode = APPLY (WILL MUTATE)` en gras dès le démarrage. Documenté dans la docstring. Test `test_dry_run_writes_nothing` verrouille le défaut. CONTEXT.md §specifics : "One-shot scripts that silently mutate user data are a no-go". Mitigation supplémentaire : chaque write est en UoW séparée — un Ctrl-C laisse la DB cohérente (les creators déjà committed ont leur video lié ; aucune moitié de transaction ne survit). |
| T-P04-04 | **Denial of Service (D)** — rate-limit yt-dlp sur grosses collections | `container.downloader.probe` dans boucle | MEDIUM | accept (carry-over S02/S03) | Pour S01, on accepte qu'une collection de 1000+ vidéos puisse trigger un 429. Le script est idempotent donc l'utilisateur peut `--apply` par batches avec `--limit 50` puis attendre. L'ajout d'un délai `VIDSCOPE_BACKFILL_DELAY_MS` est listé comme risque #4 dans S01-RESEARCH (deferred — YAGNI tant qu'aucun utilisateur ne rapporte le problème). |
| T-P04-05 | **Information Disclosure (I)** — leak de données via logs | stdout du script | LOW | accept | Le script loggue `platform/platform_user_id` + `display_name` en stdout. Ces données sont publiques (yt-dlp les a récupérées depuis les plateformes publiques). Pas de PII, pas de tokens, pas de cookies leakés. |
| T-P04-06 | **Tampering (T)** — accès à `uow._connection` attribut privé | `scripts/backfill_creators.py::_link_video_to_creator` | LOW | accept | Acceptable : le script est hors du package `vidscope` (import-linter ne l'inspecte pas), et accéder à `_connection` est idiomatique pour un script de migration one-shot qui a besoin d'émettre un UPDATE ciblé par id. Alternative (re-upsert full Video) serait plus lourde et ouvrirait son propre risque (réordonnancement de colonnes existantes). |

**Note carry-over** : D-02 dit que la migration doit être "lossless and reversible". La réversibilité en S01 est assurée structurellement (voir S01-RESEARCH §Migration Strategy : `videos.author` reste intact ; dropper `creator_id` laisse la DB valide). Un script `scripts/rollback_m006_s01.sh` n'est PAS livré en S01 (Open Q5) — reporté en scope facultatif.
