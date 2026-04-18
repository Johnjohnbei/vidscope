---
plan_id: S03-P01
phase: M007/S03
wave: 5
depends_on: [S01-P02, S02-P01]
requirements: [R043, R045]
files_modified:
  - src/vidscope/ports/pipeline.py
  - src/vidscope/adapters/ytdlp/downloader.py
  - src/vidscope/pipeline/stages/ingest.py
  - tests/unit/adapters/ytdlp/test_downloader.py
  - tests/unit/pipeline/test_ingest_stage.py
autonomous: true
---

## Objective

Étendre la chaîne ingest pour capturer les nouveaux champs yt-dlp M007 et les persister : (1) `IngestOutcome` (port) gagne 5 champs optionnels `description`, `hashtags: tuple[str, ...]`, `mentions: tuple[Mention, ...]`, `music_track`, `music_artist` — tous avec defaults pour backward compat M006 (2) `YtdlpDownloader._info_to_outcome` extrait depuis `info_dict` : `info["description"]`, `info["tags"]`, mentions regex sur description (stdlib `re`, pas `adapters.text` pour respecter contrat import-linter via adapter ytdlp), `info["track"]`, `info["artists"][0]` (3) `IngestStage.execute()` construit le `Video` avec les 3 nouvelles colonnes D-01 ET persiste les hashtags + mentions via `uow.hashtags.replace_for_video` / `uow.mentions.replace_for_video`. Tests unitaires couvrent extraction yt-dlp (stub info_dict) + persistance IngestStage (uow en stub).

**Note ciblée sur imports** : `YtdlpDownloader` extrait les `@mentions` via `re` stdlib directement (regex `@[\w.]+`), PAS via `adapters.text.RegexLinkExtractor`, parce que le contrat `ytdlp-never-imports-other-adapters` (implicite via `llm-never-imports-other-adapters` pattern — vérifier) interdit cette dépendance. Le LinkExtractor est réservé à `MetadataExtractStage` (S03-P02) qui est dans `pipeline/` et peut importer via ports.

## Tasks

<task id="T01-ingest-outcome-extension" tdd="true">
  <name>Étendre IngestOutcome (port) avec 5 champs M007 (additive, zéro breaking change)</name>

  <read_first>
    - `src/vidscope/ports/pipeline.py` lignes 198-222 — définition actuelle de `IngestOutcome` (10 champs incluant `creator_info`)
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"Risk 2 : IngestOutcome — frozen dataclass" (ajouts backward-compatible via defaults)
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-01 (description + music sur Video) et §D-03 (Mention sans creator_id)
    - `src/vidscope/domain/entities.py` — `Mention` entity (créée en S01-P01)
    - `.importlinter` — `ports-are-pure` (aucun import third-party, aucun import adapter)
  </read_first>

  <behavior>
    - Test 1: `IngestOutcome(platform=Platform.YOUTUBE, platform_id=PlatformId("x"), url="u", media_path="p")` construit sans les nouveaux champs (backward compat) ; tous les nouveaux champs ont leur valeur par défaut.
    - Test 2: `outcome.description is None`, `outcome.hashtags == ()`, `outcome.mentions == ()`, `outcome.music_track is None`, `outcome.music_artist is None`.
    - Test 3: construction complète avec tous les nouveaux champs + round-trip des valeurs.
    - Test 4: frozen — mutation lève `FrozenInstanceError`.
  </behavior>

  <action>
  Ouvrir `src/vidscope/ports/pipeline.py`. Localiser `IngestOutcome` (lignes 198-222). Mettre à jour l'import depuis `vidscope.domain` pour inclure `Mention` :

  ```python
  from vidscope.domain import (
      Analysis,
      Frame,
      Language,
      Mention,
      Platform,
      PlatformId,
      Transcript,
      VideoId,
  )
  ```

  Remplacer le dataclass `IngestOutcome` par la version étendue :

  ```python
  @dataclass(frozen=True, slots=True)
  class IngestOutcome:
      """Result of a successful ingest operation.

      ``media_path`` is a real on-disk path produced by the downloader.
      The ingest stage copies it into :class:`MediaStorage` and discards
      the original.

      ``creator_info`` is populated when yt-dlp exposes ``uploader_id``
      (the D-01 canonical UNIQUE key on ``creators``). ``None`` is a
      legitimate outcome for compilations, playlists without a single
      uploader, and extractors that don't expose an uploader (M006 D-02:
      ingest succeeds with ``creator_id=NULL``).

      ``description``, ``hashtags``, ``mentions``, ``music_track``,
      ``music_artist`` are M007 additions (R043, R045). Every field is
      optional with a safe default so M006 callers keep working without
      modification. Per M007 D-01 the caption + music are persisted on
      the ``videos`` row directly (no side entity); per D-05 the
      hashtags and mentions land in side tables. Each field is ``None``
      / empty tuple when the platform does not expose it — NEVER a
      synthesised placeholder (per R045).
      """

      platform: Platform
      platform_id: PlatformId
      url: str
      media_path: str
      title: str | None = None
      author: str | None = None
      duration: float | None = None
      upload_date: str | None = None
      view_count: int | None = None
      creator_info: CreatorInfo | None = None
      description: str | None = None
      hashtags: tuple[str, ...] = ()
      mentions: tuple[Mention, ...] = ()
      music_track: str | None = None
      music_artist: str | None = None
  ```

  Aucune autre modification dans `pipeline.py`. `__all__` (lignes 52-67) inclut déjà `"IngestOutcome"`.

  **Tests** : étendre `tests/unit/ports/test_probe_result.py` OU créer `tests/unit/ports/test_ingest_outcome.py` (plus propre) avec les 4 tests décrits dans `<behavior>`.
  </action>

  <acceptance_criteria>
    - `grep -q "description: str | None = None" src/vidscope/ports/pipeline.py` retourne au moins 1 occurrence
    - `grep -q "hashtags: tuple\[str, ...\] = ()" src/vidscope/ports/pipeline.py` exit 0
    - `grep -q "mentions: tuple\[Mention, ...\] = ()" src/vidscope/ports/pipeline.py` exit 0
    - `grep -q "music_track: str | None = None" src/vidscope/ports/pipeline.py` exit 0
    - `grep -q "music_artist: str | None = None" src/vidscope/ports/pipeline.py` exit 0
    - `python -m uv run python -c "from vidscope.ports import IngestOutcome; from vidscope.domain import Platform, PlatformId; o = IngestOutcome(platform=Platform.YOUTUBE, platform_id=PlatformId('x'), url='u', media_path='p'); assert o.description is None and o.hashtags == () and o.music_track is None; print('OK')"` affiche `OK`
    - `python -m uv run python -c "from vidscope.ports import IngestOutcome; from vidscope.domain import Platform, PlatformId, Mention, VideoId; o = IngestOutcome(platform=Platform.YOUTUBE, platform_id=PlatformId('x'), url='u', media_path='p', description='d', hashtags=('a','b'), mentions=(Mention(video_id=VideoId(0), handle='alice'),), music_track='t', music_artist='y'); print(o.description, o.hashtags, o.music_track)"` affiche `d ('a', 'b') t`
    - `python -m uv run pytest tests/unit/adapters/ytdlp -x -q` exit 0 (tests existants de downloader.py restent verts — zéro breaking change)
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (contrat `ports-are-pure` reste vert)
  </acceptance_criteria>
</task>

<task id="T02-ytdlp-extract-metadata" tdd="true">
  <name>Étendre YtdlpDownloader._info_to_outcome pour extraire description/hashtags/mentions/music</name>

  <read_first>
    - `src/vidscope/adapters/ytdlp/downloader.py` lignes 377-423 — fonction `_info_to_outcome` à étendre (ajouter les 5 nouveaux champs dans le return)
    - `src/vidscope/adapters/ytdlp/downloader.py` lignes 580-595 — helpers `_str_or_none`, `_int_or_none` existants à réutiliser
    - `src/vidscope/adapters/ytdlp/downloader.py` lignes 605-672 — `_extract_creator_info` montre le patron d'extraction depuis info_dict à miroir
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"Champs yt-dlp confirmes" (tableau clés yt-dlp) et §"IngestStage — extension"
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-03 (Mention handle lowercase + lstrip '@', platform optionnelle)
    - `src/vidscope/domain/entities.py` — Mention entity (video_id + handle + platform optionnelle)
    - `.importlinter` — ne PAS importer `vidscope.adapters.text` depuis `vidscope.adapters.ytdlp` (le contrat ne le permet pas — ytdlp est un adapter séparé)
  </read_first>

  <behavior>
    - Test 1: `info_to_outcome` avec `info["description"]="Check #Cooking @alice https://shop.com"` → `outcome.description == "Check #Cooking @alice https://shop.com"`.
    - Test 2: `info["tags"]=["cooking", "recipe", "#Dessert"]` → `outcome.hashtags == ("cooking", "recipe", "#Dessert")` (tuple des tags verbatim ; canonicalisation au repo).
    - Test 3: `info["description"]="@alice @bob @charlie_xyz and @d.e"` → `outcome.mentions` a exactement 4 Mention, handles = ("alice","bob","charlie_xyz","d.e"), chaque Mention a `video_id=VideoId(0)` (placeholder), `platform=None`.
    - Test 4: `info["description"]=""` → `outcome.mentions == ()` et `outcome.description is None` (ou `""` ; doc explicite).
    - Test 5: `info["track"]="Original sound", info["artists"]=["@creator123"]` → `outcome.music_track == "Original sound"`, `outcome.music_artist == "@creator123"`.
    - Test 6: `info["artist"]="Fallback"` (pas `artists`) → `outcome.music_artist == "Fallback"` (fallback sur la clé dépréciée).
    - Test 7: `info["artists"]=["A", "B"]` → `outcome.music_artist == "A"` (premier artiste uniquement, per RESEARCH.md Q-03).
    - Test 8: `info` sans aucune clé M007 → `outcome.description is None`, `outcome.hashtags == ()`, `outcome.mentions == ()`, `outcome.music_track is None`, `outcome.music_artist is None`.
    - Test 9: dedup mentions dans la regex — `"@alice @alice"` → 1 Mention.
  </behavior>

  <action>
  Ouvrir `src/vidscope/adapters/ytdlp/downloader.py`. Effectuer 3 modifications :

  **Étape A — Ajouter un helper `_extract_mentions`** APRÈS `_extract_creator_info` (vers la ligne 638) et AVANT `_extract_uploader_thumbnail`. Utilise stdlib `re` uniquement :

  ```python
  import re as _re  # scope-local import added at top; OR if `import re` is already there, skip

  # At module top, near the other imports:
  # import re

  # The pattern matches a "@" followed by a word-character run that may
  # contain dots or underscores. Used on the description caption. Keep
  # the regex simple here (not in adapters/text) because the ytdlp
  # adapter must stay self-contained per import-linter contracts.
  _MENTION_PATTERN = _re.compile(r"@([\w][\w.]{0,63})")


  def _extract_mentions(
      description: str | None, platform: Platform
  ) -> tuple[Mention, ...]:
      """Extract ``@handle`` mentions from a video description.

      Handles are canonicalised lowercase and stripped of the leading
      ``@`` at the side-table write layer (M007 S01-P02
      ``MentionRepositorySQLite._canonicalise_handle``). This adapter
      returns raw-ish handles to keep the canonicalisation in ONE place.

      Returns ``()`` for falsy input. Deduplicates by lowercased handle.
      Every :class:`Mention` carries ``video_id=VideoId(0)`` as a
      placeholder — the ingest stage replaces it with the persisted
      video id before calling ``uow.mentions.replace_for_video``.
      """
      if not description:
          return ()

      seen: set[str] = set()
      mentions: list[Mention] = []
      for match in _MENTION_PATTERN.finditer(description):
          handle = match.group(1)
          key = handle.lower()
          if key in seen:
              continue
          seen.add(key)
          mentions.append(
              Mention(
                  video_id=VideoId(0),  # placeholder — filled in by IngestStage
                  handle=handle,
                  platform=None,  # per D-03: platform optional, none inferred here
              )
          )
      return tuple(mentions)
  ```

  Ajouter `import re` en haut du fichier (s'il n'est pas déjà présent) et étendre l'import depuis `vidscope.domain` :

  ```python
  from vidscope.domain import (
      CookieAuthError,
      IngestError,
      Mention,
      Platform,
      PlatformId,
      VideoId,
  )
  ```

  **Étape B — Étendre `_info_to_outcome`** (lignes 377-423). Remplacer le bloc `return IngestOutcome(...)` pour inclure les 5 nouveaux champs :

  ```python
      return IngestOutcome(
          platform=platform,
          platform_id=platform_id,
          url=str(info.get("webpage_url") or url),
          media_path=str(media_path),
          title=_str_or_none(info.get("title")),
          author=_str_or_none(info.get("uploader") or info.get("channel")),
          duration=_float_or_none(info.get("duration")),
          upload_date=_str_or_none(info.get("upload_date")),
          view_count=_int_or_none(info.get("view_count")),
          creator_info=_extract_creator_info(info),
          description=_str_or_none(info.get("description")),
          hashtags=_extract_hashtags(info),
          mentions=_extract_mentions(
              info.get("description") if isinstance(info.get("description"), str) else None,
              platform,
          ),
          music_track=_str_or_none(info.get("track")),
          music_artist=_extract_music_artist(info),
      )
  ```

  **Étape C — Ajouter deux helpers supplémentaires** `_extract_hashtags` et `_extract_music_artist` APRÈS `_extract_mentions` :

  ```python
  def _extract_hashtags(info: dict[str, Any]) -> tuple[str, ...]:
      """Extract hashtags from a yt-dlp ``info_dict``.

      yt-dlp exposes hashtags as ``info["tags"]`` — a list of bare
      strings (no leading ``#``). The list may be missing, ``None``,
      or contain non-string entries on pathological platforms: we
      coerce to ``tuple[str, ...]`` and drop falsy entries. The
      repository layer (M007 S01-P02 ``HashtagRepositorySQLite``) is
      responsible for the canonical lowercase + lstrip '#' — this
      helper preserves whatever yt-dlp returned verbatim.
      """
      raw = info.get("tags")
      if not raw or not isinstance(raw, list):
          return ()
      cleaned = [str(t).strip() for t in raw if t]
      return tuple(t for t in cleaned if t)


  def _extract_music_artist(info: dict[str, Any]) -> str | None:
      """Resolve the music artist from a yt-dlp ``info_dict``.

      Preference order (per RESEARCH §A1, Q-03):
      1. ``info["artists"]`` (list) — first entry only in M007; multi-
         artist concatenation is deferred.
      2. ``info["artist"]`` (deprecated singular) — fallback.

      Returns ``None`` when the platform exposes neither.
      """
      artists = info.get("artists")
      if isinstance(artists, list) and artists:
          first = artists[0]
          if first is not None:
              text = str(first).strip()
              if text:
                  return text
      return _str_or_none(info.get("artist"))
  ```

  **Étape D — Tests**. Créer / étendre `tests/unit/adapters/ytdlp/test_downloader.py` avec les 9 tests décrits dans `<behavior>`. Utiliser des stubs simples : `info_dict = {"id": "abc", "extractor_key": "Youtube", "description": "...", "tags": [...], "track": "...", "artists": [...]}` et appeler `_info_to_outcome(info, url="...", destination_dir=tmpdir)`. Pour contourner le check de media_path, créer un fichier factice `{tmpdir}/abc.mp4` via tmp_path fixture.
  </action>

  <acceptance_criteria>
    - `grep -q "def _extract_mentions" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `grep -q "def _extract_hashtags" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `grep -q "def _extract_music_artist" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `grep -q "_MENTION_PATTERN" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `grep -q "description=_str_or_none(info.get" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `grep -q "hashtags=_extract_hashtags(info)" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `grep -q "music_track=_str_or_none(info.get" src/vidscope/adapters/ytdlp/downloader.py` exit 0
    - `python -m uv run python -c "from vidscope.adapters.ytdlp.downloader import _extract_mentions; from vidscope.domain import Platform; ms = _extract_mentions('@alice and @bob_x @alice', Platform.TIKTOK); assert len(ms) == 2; assert {m.handle.lower() for m in ms} == {'alice', 'bob_x'}; print('OK')"` affiche `OK`
    - `python -m uv run python -c "from vidscope.adapters.ytdlp.downloader import _extract_hashtags; t = _extract_hashtags({'tags': ['a', 'b', '#c']}); assert t == ('a', 'b', '#c'); print('OK')"` affiche `OK`
    - `python -m uv run python -c "from vidscope.adapters.ytdlp.downloader import _extract_music_artist; assert _extract_music_artist({'artists': ['First', 'Second']}) == 'First'; assert _extract_music_artist({'artist': 'Fb'}) == 'Fb'; assert _extract_music_artist({}) is None; print('OK')"` affiche `OK`
    - `python -m uv run pytest tests/unit/adapters/ytdlp/ -x -q` exit 0
    - `python -m uv run lint-imports` exit 0 (ytdlp adapter n'importe PAS `vidscope.adapters.text`)
    - `python -m uv run mypy src` exit 0
  </acceptance_criteria>
</task>

<task id="T03-ingest-stage-persist-hashtags-mentions" tdd="true">
  <name>Étendre IngestStage pour persister description/music sur Video + hashtags/mentions via UoW</name>

  <read_first>
    - `src/vidscope/pipeline/stages/ingest.py` lignes 157-197 — construction de `Video` et persistance — à étendre pour ajouter les 3 colonnes M007 et les 2 side tables
    - `src/vidscope/pipeline/stages/ingest.py` lignes 211-230 — helper `_creator_from_info` (patron de translation TypedDict → domain entity)
    - `src/vidscope/ports/pipeline.py` — `IngestOutcome` étendu en T01
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"Hashtags/mentions persistance dans IngestStage"
    - `.gsd/milestones/M007/M007-CONTEXT.md` §D-01 (description/music sur Video entity)
  </read_first>

  <behavior>
    - Test 1: outcome avec `description="caption"`, `music_track="Song"`, `music_artist="X"` → `uow.videos.upsert_by_platform_id` reçoit un `Video` dont `.description == "caption"`, `.music_track == "Song"`, `.music_artist == "X"`.
    - Test 2: outcome avec `hashtags=("coding", "tutorial")` → `uow.hashtags.replace_for_video` appelé avec `(persisted.id, ["coding", "tutorial"])`.
    - Test 3: outcome avec `mentions=(Mention(video_id=VideoId(0), handle="alice"), Mention(video_id=VideoId(0), handle="bob"))` → `uow.mentions.replace_for_video` appelé avec `persisted.id` et une liste de 2 `Mention` dont `video_id` a été remplacé par `persisted.id`.
    - Test 4: outcome SANS hashtags/mentions (défauts `()`) → `uow.hashtags.replace_for_video` et `uow.mentions.replace_for_video` NE SONT PAS APPELÉS (optimisation : pas d'écriture inutile) OU sont appelés avec liste vide (idempotent — D-05). **Choix retenu : appeler toujours avec la liste (même vide)** pour garantir que re-ingesting d'une vidéo qui avait auparavant des hashtags supprime les anciens. DELETE-INSERT pattern oblige.
    - Test 5: outcome avec hashtags + mentions + description → l'ordre des appels est : `videos.upsert_by_platform_id` → `hashtags.replace_for_video` → `mentions.replace_for_video`, TOUT DANS LA MÊME UoW transaction.
  </behavior>

  <action>
  Ouvrir `src/vidscope/pipeline/stages/ingest.py`. Dans `IngestStage.execute()` (ligne 103), modifier 2 sections :

  **Étape A — Construire le `Video` avec les 3 nouvelles colonnes** (lignes 159-169). Remplacer :

  ```python
              # 4. Build the domain Video entity with every piece of
              #    metadata the downloader gave us plus the storage key.
              video = Video(
                  platform=outcome.platform,
                  platform_id=outcome.platform_id,
                  url=outcome.url,
                  author=outcome.author,
                  title=outcome.title,
                  duration=outcome.duration,
                  upload_date=outcome.upload_date,
                  view_count=outcome.view_count,
                  media_key=stored_key,
              )
  ```

  Par :

  ```python
              # 4. Build the domain Video entity with every piece of
              #    metadata the downloader gave us plus the storage key.
              #    M007 D-01: description, music_track, music_artist are
              #    direct columns on the ``videos`` table.
              video = Video(
                  platform=outcome.platform,
                  platform_id=outcome.platform_id,
                  url=outcome.url,
                  author=outcome.author,
                  title=outcome.title,
                  duration=outcome.duration,
                  upload_date=outcome.upload_date,
                  view_count=outcome.view_count,
                  media_key=stored_key,
                  description=outcome.description,
                  music_track=outcome.music_track,
                  music_artist=outcome.music_artist,
              )
  ```

  **Étape B — Après `persisted = uow.videos.upsert_by_platform_id(video, creator=creator)`** (ligne 189), ajouter la persistance des hashtags + mentions AVANT la mutation du ctx (ligne 191-197) :

  ```python
              # 6. Upsert the videos row. Passing creator= triggers the
              #    D-03 write-through cache in VideoRepository: author +
              #    creator_id are set atomically in the same SQL statement.
              persisted = uow.videos.upsert_by_platform_id(video, creator=creator)

              # 6.b M007 D-05: persist hashtags and mentions in side
              # tables. replace_for_video uses DELETE-then-INSERT so
              # re-ingesting a video whose caption/hashtags changed
              # replaces the old rows cleanly (idempotent).
              assert persisted.id is not None
              uow.hashtags.replace_for_video(
                  persisted.id, list(outcome.hashtags)
              )
              # Mentions come from the downloader with video_id=VideoId(0)
              # as a placeholder. Re-instantiate each with the persisted
              # video id before writing.
              rebound_mentions = [
                  Mention(
                      video_id=persisted.id,
                      handle=m.handle,
                      platform=m.platform,
                  )
                  for m in outcome.mentions
              ]
              uow.mentions.replace_for_video(persisted.id, rebound_mentions)

              # 7. Mutate the pipeline context so downstream stages
              #    (transcribe, frames, analyze) can read what we
              #    produced.
              ctx.video_id = persisted.id
              ctx.platform = persisted.platform
              ctx.platform_id = persisted.platform_id
              ctx.media_key = persisted.media_key
  ```

  Renuméroter le commentaire "6. Mutate" → "7. Mutate" dans le code (voir ci-dessus).

  Ajouter `Mention` à l'import existant :

  ```python
  from vidscope.domain import (
      Creator,
      IngestError,
      Mention,
      Platform,
      PlatformUserId,
      StageName,
      Video,
      detect_platform,
  )
  ```

  **Étape C — Tests**. Étendre `tests/unit/pipeline/test_ingest_stage.py` avec les 5 tests décrits dans `<behavior>`. Pattern : `FakeDownloader` qui retourne un `IngestOutcome` contrôlé ; `FakeUoW` avec des `FakeVideoRepo`, `FakeHashtagRepo`, `FakeMentionRepo`, `FakeCreatorRepo` qui enregistrent les appels (list[args]) ; exercer `stage.execute(ctx, uow)` et vérifier les appels + leurs arguments.
  </action>

  <acceptance_criteria>
    - `grep -q "description=outcome.description" src/vidscope/pipeline/stages/ingest.py` exit 0
    - `grep -q "music_track=outcome.music_track" src/vidscope/pipeline/stages/ingest.py` exit 0
    - `grep -q "music_artist=outcome.music_artist" src/vidscope/pipeline/stages/ingest.py` exit 0
    - `grep -q "uow.hashtags.replace_for_video" src/vidscope/pipeline/stages/ingest.py` exit 0
    - `grep -q "uow.mentions.replace_for_video" src/vidscope/pipeline/stages/ingest.py` exit 0
    - `grep -q "rebound_mentions" src/vidscope/pipeline/stages/ingest.py` exit 0
    - `python -m uv run pytest tests/unit/pipeline/test_ingest_stage.py -x -q` exit 0
    - `python -m uv run pytest -q` exit 0 (aucune régression)
    - `python -m uv run ruff check src tests` exit 0
    - `python -m uv run mypy src` exit 0
    - `python -m uv run lint-imports` exit 0 (pipeline reste self-contained)
  </acceptance_criteria>
</task>

## Verification Criteria

```bash
# Tests
python -m uv run pytest tests/unit/adapters/ytdlp/ -x -q
python -m uv run pytest tests/unit/pipeline/test_ingest_stage.py -x -q

# Smoke test : IngestOutcome backward compat
python -m uv run python -c "
from vidscope.ports import IngestOutcome
from vidscope.domain import Platform, PlatformId
o = IngestOutcome(platform=Platform.YOUTUBE, platform_id=PlatformId('x'), url='u', media_path='/tmp/x.mp4')
assert o.description is None and o.hashtags == () and o.mentions == ()
assert o.music_track is None and o.music_artist is None
print('OK backward compat')
"

# Suite complète + quality gates
python -m uv run pytest -q
python -m uv run ruff check src tests
python -m uv run mypy src
python -m uv run lint-imports
```

## Must-Haves

- `IngestOutcome` (port) a 5 champs optionnels : `description`, `hashtags: tuple[str, ...]`, `mentions: tuple[Mention, ...]`, `music_track`, `music_artist`. Backward compat avec M006 garanti via defaults.
- `YtdlpDownloader._info_to_outcome` extrait les 5 champs depuis `info_dict` : `info["description"]`, `info["tags"]`, mentions via regex `@([\w][\w.]{0,63})` sur description, `info["track"]`, `info["artists"][0]` ou `info["artist"]` fallback.
- `IngestStage.execute()` construit le `Video` avec les 3 nouvelles colonnes D-01.
- `IngestStage.execute()` appelle `uow.hashtags.replace_for_video(persisted.id, list(outcome.hashtags))` et `uow.mentions.replace_for_video(persisted.id, rebound_mentions)` dans la même transaction que le `videos.upsert_by_platform_id`.
- `Mention` objets du downloader ont `video_id=VideoId(0)` placeholder ; IngestStage remplace par `persisted.id` avant l'écriture.
- Les 10 contrats `.importlinter` restent verts — `adapters.ytdlp` n'importe PAS `adapters.text`.

## Threat Model

| # | Catégorie STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-S03P01-01 | **Denial of Service (D)** — description très longue | `IngestStage` → `videos.description` Text column | LOW | accept | SQLite Text column n'a pas de limite ; TikTok/IG cap descriptions à ~2200 chars, YouTube ~5000. Pas de risque pratique. Si un futur extractor passait un document de 1MB, la transaction serait bornée par SQLite page size (par défaut, 4KB blob chain ok). |
| T-S03P01-02 | **Denial of Service (D)** — regex ReDoS sur description | `_MENTION_PATTERN = r"@([\w][\w.]{0,63})"` | LOW | mitigate | Borné par `{0,63}` — pas de nested quantifiers, pas de `(a+)+`. Test de perf : `_extract_mentions("@" * 10000)` retourne en < 10ms. |
| T-S03P01-03 | **Tampering (T)** — SQL injection via hashtag/mention | `uow.hashtags.replace_for_video` | LOW | mitigate | Bindings SQLAlchemy Core (mitigé en S01-P02 T-S01P02-01). |
| T-S03P01-04 | **Information Disclosure (I)** — description/mentions/music stockés | tables `videos`, `mentions` | LOW | accept | Données publiques plateforme, stockage single-user (R032). |
| T-S03P01-05 | **Tampering (T)** — Mention avec `video_id=VideoId(0)` placeholder oubli de rebind | `IngestStage.execute` | MEDIUM | mitigate | Test dédié (Test 3 dans `<behavior>`) vérifie que `rebound_mentions` ont `video_id == persisted.id`. Rater le rebind corromprait la FK mais SQLite ON DELETE CASCADE protégerait contre les orphelins immédiats. |
