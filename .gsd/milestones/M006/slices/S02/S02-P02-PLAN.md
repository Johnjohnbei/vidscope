---
plan_id: S02-P02
phase: M006/S02
plan: 02
type: execute
wave: 2
depends_on: [S02-P01]
files_modified:
  - src/vidscope/adapters/ytdlp/downloader.py
  - tests/unit/adapters/ytdlp/test_downloader.py
autonomous: true
requirements: [R040]
must_haves:
  truths:
    - "YtdlpDownloader.download() populates IngestOutcome.creator_info from the yt-dlp info_dict"
    - "When uploader_id is absent or empty, creator_info is None (D-02)"
    - "Extraction reuses existing private helpers from S01 — no network duplication"
    - "The existing probe() method is untouched — only download() is extended"
    - "Extraction is pure dict access, zero additional network calls"
  artifacts:
    - path: "src/vidscope/adapters/ytdlp/downloader.py"
      provides: "_extract_creator_info helper + _info_to_outcome extended with creator_info"
      contains: "def _extract_creator_info"
    - path: "tests/unit/adapters/ytdlp/test_downloader.py"
      provides: "Unit tests for creator_info extraction (all-fields, partial, uploader_id absent)"
      contains: "class TestCreatorInfoExtraction"
  key_links:
    - from: "src/vidscope/adapters/ytdlp/downloader.py::_info_to_outcome"
      to: "_extract_creator_info"
      via: "creator_info= keyword argument to IngestOutcome constructor"
      pattern: "creator_info=_extract_creator_info"
    - from: "_extract_creator_info"
      to: "_extract_uploader_thumbnail / _extract_uploader_verified"
      via: "helper reuse (S01-P04 assets)"
      pattern: "_extract_uploader_thumbnail|_extract_uploader_verified"
---

<objective>
Étendre `YtdlpDownloader.download()` pour peupler `IngestOutcome.creator_info` depuis le `info_dict` yt-dlp, en réutilisant les helpers privés `_extract_uploader_thumbnail` et `_extract_uploader_verified` déjà livrés en S01-P04.

**Ce plan livre uniquement l'extraction adapter.** Le câblage pipeline (creator upsert + video creator_id) est livré par S02-P03 en parallèle.

Purpose: le `info_dict` est déjà en mémoire après `ydl.extract_info()` — extraire `creator_info` est pur accès dict, zéro appel réseau supplémentaire. Cette tâche ne change pas `probe()` (qui est déjà OK depuis S01-P04).

Output: `YtdlpDownloader.download()` renvoie maintenant systématiquement un `IngestOutcome` avec `creator_info` populé quand `uploader_id` est présent, `None` sinon (D-02). 6+ nouveaux tests unitaires (happy path, uploader_id absent, uploader_id vide, extraction partielle, extraction liste avatars, robustesse).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/STATE.md
@.gsd/milestones/M006/slices/S02/S02-CONTEXT.md
@.gsd/milestones/M006/slices/S02/S02-P01-PLAN.md
@src/vidscope/adapters/ytdlp/downloader.py
@src/vidscope/ports/pipeline.py
@tests/unit/adapters/ytdlp/test_downloader.py
@.importlinter

<interfaces>
<!-- Key helpers to reuse — DO NOT duplicate -->

From src/vidscope/adapters/ytdlp/downloader.py (already present, S01-P04):

```python
def _str_or_none(value: Any) -> str | None:
    """Strip + None-on-empty string converter."""

def _int_or_none(value: Any) -> int | None:
    """Lenient int parser, returns None on TypeError/ValueError."""

def _extract_uploader_thumbnail(info: dict[str, Any]) -> str | None:
    """Resolve avatar URL — handles str, list[dict], list[str] shapes.
    Tries ``uploader_thumbnail`` then ``channel_thumbnail``."""

def _extract_uploader_verified(info: dict[str, Any]) -> bool | None:
    """Resolve verified-badge flag — tries ``channel_verified`` then
    ``uploader_verified``. Returns None when absent (rare on most extractors)."""
```

From src/vidscope/adapters/ytdlp/downloader.py::_info_to_outcome (lines 371-416, to be extended):

```python
def _info_to_outcome(
    info: dict[str, Any],
    *,
    url: str,
    destination_dir: Path,
) -> IngestOutcome:
    platform = _platform_from_info(info)
    raw_id = info.get("id")
    # ... (existing logic preserved)
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
        # Add: creator_info=_extract_creator_info(info)
    )
```

From src/vidscope/ports (available since P01):

```python
from vidscope.ports import CreatorInfo, IngestOutcome
```

Mapping yt-dlp info_dict → CreatorInfo (same keys as ProbeResult lines 309-335 in downloader.py):

| CreatorInfo key       | yt-dlp key (primary)           | yt-dlp key (fallback)         | Shape            |
|-----------------------|--------------------------------|-------------------------------|------------------|
| platform_user_id      | `uploader_id`                  | `channel_id`                  | str (required)   |
| handle                | `uploader`                     | `channel`                     | str / None       |
| display_name          | `uploader`                     | `channel`                     | str / None       |
| profile_url           | `uploader_url`                 | `channel_url`                 | str / None       |
| avatar_url            | via `_extract_uploader_thumbnail` | —                          | str / None       |
| follower_count        | `channel_follower_count`       | `channel_followers`           | int / None       |
| is_verified           | via `_extract_uploader_verified` | —                           | bool / None      |

D-02: if `uploader_id` AND `channel_id` are both absent/empty → return `None` (creator_info not populated).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
<name>Task 1: Ajouter _extract_creator_info helper et étendre _info_to_outcome</name>

<read_first>
- `src/vidscope/adapters/ytdlp/downloader.py` lignes 39-49 (imports) — ajouter `CreatorInfo` depuis `vidscope.ports`
- `src/vidscope/adapters/ytdlp/downloader.py` lignes 371-416 (`_info_to_outcome`) — ajouter `creator_info=` à la construction de `IngestOutcome`
- `src/vidscope/adapters/ytdlp/downloader.py` lignes 573-596 (`_str_or_none`, `_int_or_none`, `_float_or_none`) — réutiliser TEL QUEL
- `src/vidscope/adapters/ytdlp/downloader.py` lignes 598-630 (`_extract_uploader_thumbnail`, `_extract_uploader_verified`) — réutiliser TEL QUEL
- `src/vidscope/adapters/ytdlp/downloader.py` lignes 309-335 (bloc `probe()` qui peuple `ProbeResult`) — le nouveau `_extract_creator_info` mirroir LA MÊME logique d'extraction, mais produit un `CreatorInfo` TypedDict au lieu d'un `ProbeResult`
- `.gsd/milestones/M006/slices/S02/S02-CONTEXT.md` §D-01 et §D-02 — spec et cas uploader absent
- `.gsd/milestones/M006/slices/S02/S02-P01-PLAN.md` §interfaces — shape de `CreatorInfo`
- `tests/unit/adapters/ytdlp/test_downloader.py` lignes 74-114 (`TestHappyPath::test_youtube_returns_ingest_outcome`) — le pattern de test à étendre pour couvrir `creator_info`
</read_first>

<behavior>
- Test 1 (happy path): `info_dict` avec `uploader_id='UC_alice'`, `uploader='Alice'`, `uploader_url='https://y/c/alice'`, `channel_follower_count=1234`, `uploader_thumbnail='https://y/img.jpg'`, `channel_verified=True` → `outcome.creator_info` est un dict avec tous ces champs mappés correctement
- Test 2 (D-02 uploader_id absent): `info_dict` sans `uploader_id` ni `channel_id` → `outcome.creator_info is None`, `outcome` par ailleurs valide (ingest réussi)
- Test 3 (D-02 uploader_id vide string): `info_dict` avec `uploader_id=''` → `outcome.creator_info is None`
- Test 4 (extraction partielle): `info_dict` avec SEULEMENT `uploader_id='UC_bob'` (tous les autres champs absents) → `creator_info['platform_user_id']='UC_bob'`, tous les autres champs sont `None`
- Test 5 (fallback channel_id): `info_dict` avec `uploader_id` absent mais `channel_id='UC_chan'` → `creator_info['platform_user_id']='UC_chan'`
- Test 6 (fallback uploader → channel pour handle/display_name): `info_dict` sans `uploader` mais avec `channel='ChannelName'` → `creator_info['handle']='ChannelName'`, `creator_info['display_name']='ChannelName'`
- Test 7 (avatar liste): `info_dict` avec `uploader_thumbnail=[{'url': 'https://y/img1.jpg'}]` → `creator_info['avatar_url']='https://y/img1.jpg'` (délègue à `_extract_uploader_thumbnail`)
- Test 8 (follower_count non-int): `info_dict` avec `channel_follower_count='not_an_int'` → `creator_info['follower_count'] is None` (délègue à `_int_or_none`)
- Test 9 (rétrocompat): les tests existants de `TestHappyPath::test_youtube_returns_ingest_outcome` continuent de passer — `outcome.creator_info` est présent mais n'est vérifié que par les nouveaux tests
</behavior>

<action>
**Modifier `src/vidscope/adapters/ytdlp/downloader.py`**

1. **Lignes 39-49** (imports existants) — ajouter `CreatorInfo` dans l'import depuis `vidscope.ports`. L'import actuel est :
   ```python
   from vidscope.ports import ChannelEntry, IngestOutcome, ProbeResult, ProbeStatus
   ```
   Le remplacer par (ordre alphabétique préservé) :
   ```python
   from vidscope.ports import (
       ChannelEntry,
       CreatorInfo,
       IngestOutcome,
       ProbeResult,
       ProbeStatus,
   )
   ```

2. **Modifier `_info_to_outcome`** (actuellement lignes 371-416) — ajouter `creator_info=_extract_creator_info(info)` comme dernier paramètre de la construction `IngestOutcome(...)`. Nouveau bloc `return` à la fin de la fonction :
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
       )
   ```

3. **Ajouter le helper `_extract_creator_info`** — placer juste AVANT `_extract_uploader_thumbnail` (actuellement ligne ~598) pour garder les helpers creator-related groupés. Contenu exact :

   ```python
   def _extract_creator_info(info: dict[str, Any]) -> CreatorInfo | None:
       """Extract creator metadata from a yt-dlp ``info_dict``.

       Returns ``None`` when no stable creator id is available — D-02:
       ingest must still succeed on compilations, playlists without a
       single uploader, and extractors that don't expose one. A caller
       (``IngestStage``) treats ``None`` as "skip creator upsert, save
       video with creator_id=NULL, log a WARNING".

       Field mapping (same as ``ProbeResult`` lines 309-335 in this file):

       - ``platform_user_id`` ← ``uploader_id`` (fallback ``channel_id``)
       - ``handle`` / ``display_name`` ← ``uploader`` (fallback ``channel``)
       - ``profile_url`` ← ``uploader_url`` (fallback ``channel_url``)
       - ``avatar_url`` ← via :func:`_extract_uploader_thumbnail`
       - ``follower_count`` ← ``channel_follower_count`` (fallback ``channel_followers``)
       - ``is_verified`` ← via :func:`_extract_uploader_verified`

       Zero network calls — pure dict access on the already-extracted
       ``info_dict``.
       """
       platform_user_id = _str_or_none(
           info.get("uploader_id") or info.get("channel_id")
       )
       if platform_user_id is None:
           # D-02: uploader_id absent or empty → no creator_info.
           # IngestStage will log a WARNING and save video with
           # creator_id=NULL.
           return None

       uploader = _str_or_none(info.get("uploader") or info.get("channel"))
       return CreatorInfo(
           platform_user_id=platform_user_id,
           handle=uploader,
           display_name=uploader,
           profile_url=_str_or_none(
               info.get("uploader_url") or info.get("channel_url")
           ),
           avatar_url=_extract_uploader_thumbnail(info),
           follower_count=_int_or_none(
               info.get("channel_follower_count")
               or info.get("channel_followers")
           ),
           is_verified=_extract_uploader_verified(info),
       )
   ```

Ne pas modifier `probe()`, `download()`, `list_channel_videos()`, les helpers existants, ni les translators d'erreur. Le seul changement fonctionnel est : `_info_to_outcome` passe maintenant `creator_info=...`.
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py -x -q</automated>
</verify>

<acceptance_criteria>
- `grep -q "def _extract_creator_info" src/vidscope/adapters/ytdlp/downloader.py` exit 0
- `grep -q "creator_info=_extract_creator_info(info)" src/vidscope/adapters/ytdlp/downloader.py` exit 0
- `grep -q "CreatorInfo" src/vidscope/adapters/ytdlp/downloader.py` exit 0
- `grep -q "from vidscope.ports import" src/vidscope/adapters/ytdlp/downloader.py` exit 0 (import existant préservé)
- `grep -c "_extract_uploader_thumbnail" src/vidscope/adapters/ytdlp/downloader.py` renvoie >= 3 (1 définition + 1 usage existant dans `probe` + 1 nouveau usage dans `_extract_creator_info`)
- `grep -c "_extract_uploader_verified" src/vidscope/adapters/ytdlp/downloader.py` renvoie >= 3
- `python -m uv run mypy src` exit 0 (le `TypedDict` constructor accepte les arguments nommés)
- `python -m uv run lint-imports` exit 0 (9 contrats — `ports-are-pure` non affecté, `pipeline-has-no-adapters` non affecté)
- `python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py -x -q` exit 0
</acceptance_criteria>

<done>
`_extract_creator_info` défini, branché dans `_info_to_outcome`, tests existants toujours verts (rétrocompat).
</done>
</task>

<task type="auto" tdd="true">
<name>Task 2: Tests unitaires TestCreatorInfoExtraction (happy + D-02 + partiels)</name>

<read_first>
- `tests/unit/adapters/ytdlp/test_downloader.py` lignes 1-67 (imports, `FakeYoutubeDL`, `_install_fake`) — pattern à réutiliser
- `tests/unit/adapters/ytdlp/test_downloader.py` lignes 74-114 (`TestHappyPath::test_youtube_returns_ingest_outcome`) — pattern du test happy path à mirroir
- `src/vidscope/adapters/ytdlp/downloader.py` lignes 598-630 (`_extract_uploader_thumbnail`, `_extract_uploader_verified`) — comprendre les shapes yt-dlp multiples (str vs list[dict] vs list[str])
</read_first>

<action>
**Ajouter une nouvelle classe de tests à la fin de `tests/unit/adapters/ytdlp/test_downloader.py`** (après la dernière classe existante). Ne MODIFIER aucun test existant — ajouter uniquement.

```python
# ---------------------------------------------------------------------------
# M006/S02-P02 — Creator info extraction (D-01 / D-02)
# ---------------------------------------------------------------------------


class TestCreatorInfoExtraction:
    """Creator metadata extraction from yt-dlp info_dict.

    S02-P02 (D-01): ``YtdlpDownloader.download()`` populates
    ``IngestOutcome.creator_info`` when ``uploader_id`` is available.

    S02-P02 (D-02): When ``uploader_id`` is absent or empty, ingest
    still succeeds and ``outcome.creator_info is None`` (the downstream
    IngestStage will log a WARNING and save the video with
    ``creator_id=NULL``).
    """

    def test_populates_creator_info_when_uploader_id_present(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        destination = tmp_path / "d"
        expected_file = destination / "v1.mp4"
        info = {
            "id": "v1",
            "extractor_key": "Youtube",
            "title": "hi",
            "uploader": "Alice Channel",
            "uploader_id": "UC_alice",
            "uploader_url": "https://youtube.com/c/alice",
            "channel_follower_count": 1234,
            "uploader_thumbnail": "https://yt3.ggpht.com/alice.jpg",
            "channel_verified": True,
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_a, **_k: FakeYoutubeDL(info=info, touch_file=expected_file),
        )

        outcome = YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=v1", str(destination)
        )

        assert outcome.creator_info is not None
        assert outcome.creator_info["platform_user_id"] == "UC_alice"
        assert outcome.creator_info["handle"] == "Alice Channel"
        assert outcome.creator_info["display_name"] == "Alice Channel"
        assert (
            outcome.creator_info["profile_url"]
            == "https://youtube.com/c/alice"
        )
        assert (
            outcome.creator_info["avatar_url"]
            == "https://yt3.ggpht.com/alice.jpg"
        )
        assert outcome.creator_info["follower_count"] == 1234
        assert outcome.creator_info["is_verified"] is True

    def test_creator_info_none_when_uploader_id_absent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """D-02 canonical case: yt-dlp extractor did not expose
        uploader_id. Ingest must still succeed; creator_info is None."""
        destination = tmp_path / "d"
        expected_file = destination / "v2.mp4"
        info = {
            "id": "v2",
            "extractor_key": "Youtube",
            "title": "compilation",
            # NO uploader_id, NO channel_id
            "uploader": "Some Compilation",
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_a, **_k: FakeYoutubeDL(info=info, touch_file=expected_file),
        )

        outcome = YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=v2", str(destination)
        )

        # Ingest succeeded — outcome is valid
        assert outcome.platform is Platform.YOUTUBE
        assert outcome.title == "compilation"
        # But creator_info is None (D-02)
        assert outcome.creator_info is None

    def test_creator_info_none_when_uploader_id_empty_string(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Empty string uploader_id is treated as absent (D-02)."""
        destination = tmp_path / "d"
        expected_file = destination / "v3.mp4"
        info = {
            "id": "v3",
            "extractor_key": "Youtube",
            "uploader_id": "",  # empty — same as absent
            "uploader": "x",
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_a, **_k: FakeYoutubeDL(info=info, touch_file=expected_file),
        )

        outcome = YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=v3", str(destination)
        )
        assert outcome.creator_info is None

    def test_creator_info_only_platform_user_id_when_others_absent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Minimal happy path — uploader_id alone is enough to build
        CreatorInfo; all other fields degrade to None."""
        destination = tmp_path / "d"
        expected_file = destination / "v4.mp4"
        info = {
            "id": "v4",
            "extractor_key": "Youtube",
            "uploader_id": "UC_minimal",
            # no uploader, no uploader_url, no follower_count, no thumbnail
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_a, **_k: FakeYoutubeDL(info=info, touch_file=expected_file),
        )

        outcome = YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=v4", str(destination)
        )

        assert outcome.creator_info is not None
        assert outcome.creator_info["platform_user_id"] == "UC_minimal"
        assert outcome.creator_info["handle"] is None
        assert outcome.creator_info["display_name"] is None
        assert outcome.creator_info["profile_url"] is None
        assert outcome.creator_info["avatar_url"] is None
        assert outcome.creator_info["follower_count"] is None
        assert outcome.creator_info["is_verified"] is None

    def test_creator_info_falls_back_to_channel_id(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When ``uploader_id`` is absent, ``channel_id`` is used
        (YouTube extractor variant)."""
        destination = tmp_path / "d"
        expected_file = destination / "v5.mp4"
        info = {
            "id": "v5",
            "extractor_key": "Youtube",
            # uploader_id absent — fallback to channel_id
            "channel_id": "UC_channel_fallback",
            "channel": "Fallback Channel",
            "channel_url": "https://youtube.com/channel/UC_channel_fallback",
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_a, **_k: FakeYoutubeDL(info=info, touch_file=expected_file),
        )

        outcome = YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=v5", str(destination)
        )

        assert outcome.creator_info is not None
        assert outcome.creator_info["platform_user_id"] == "UC_channel_fallback"
        assert outcome.creator_info["display_name"] == "Fallback Channel"
        assert (
            outcome.creator_info["profile_url"]
            == "https://youtube.com/channel/UC_channel_fallback"
        )

    def test_creator_info_avatar_from_list_shape(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """yt-dlp sometimes returns uploader_thumbnail as a list of dicts.
        _extract_uploader_thumbnail handles it; delegation must work."""
        destination = tmp_path / "d"
        expected_file = destination / "v6.mp4"
        info = {
            "id": "v6",
            "extractor_key": "Tiktok",
            "uploader_id": "123456",
            "uploader": "tokker",
            "uploader_thumbnail": [
                {"url": "https://tiktokcdn/avatar1.jpg", "width": 480},
                {"url": "https://tiktokcdn/avatar2.jpg", "width": 100},
            ],
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_a, **_k: FakeYoutubeDL(info=info, touch_file=expected_file),
        )

        outcome = YtdlpDownloader().download(
            "https://www.tiktok.com/@tokker/video/v6", str(destination)
        )

        assert outcome.creator_info is not None
        assert (
            outcome.creator_info["avatar_url"]
            == "https://tiktokcdn/avatar1.jpg"
        )

    def test_creator_info_follower_count_non_int_degrades_to_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """_int_or_none delegation — bad follower count doesn't crash."""
        destination = tmp_path / "d"
        expected_file = destination / "v7.mp4"
        info = {
            "id": "v7",
            "extractor_key": "Youtube",
            "uploader_id": "UC_noint",
            "uploader": "x",
            "channel_follower_count": "not_an_int",
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_a, **_k: FakeYoutubeDL(info=info, touch_file=expected_file),
        )

        outcome = YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=v7", str(destination)
        )

        assert outcome.creator_info is not None
        assert outcome.creator_info["follower_count"] is None

    def test_creator_info_follower_count_fallback_channel_followers(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Some extractors use ``channel_followers`` instead of
        ``channel_follower_count`` — fallback must work."""
        destination = tmp_path / "d"
        expected_file = destination / "v8.mp4"
        info = {
            "id": "v8",
            "extractor_key": "Tiktok",
            "uploader_id": "999",
            "uploader": "t",
            # channel_follower_count ABSENT, channel_followers PRESENT
            "channel_followers": 50000,
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_a, **_k: FakeYoutubeDL(info=info, touch_file=expected_file),
        )

        outcome = YtdlpDownloader().download(
            "https://www.tiktok.com/@t/video/v8", str(destination)
        )

        assert outcome.creator_info is not None
        assert outcome.creator_info["follower_count"] == 50000

    def test_existing_happy_path_test_still_passes_with_creator_info(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Regression: the original TestHappyPath::test_youtube_returns_ingest_outcome
        fixture (uploader='Test Channel', no uploader_id) must still
        produce a valid outcome; creator_info is None because uploader_id
        was absent from that fixture."""
        destination = tmp_path / "d"
        expected_file = destination / "abc123.mp4"
        info = {
            "id": "abc123",
            "extractor_key": "Youtube",
            "webpage_url": "https://www.youtube.com/watch?v=abc123",
            "title": "Hello world",
            "uploader": "Test Channel",
            # uploader_id ABSENT — same as original TestHappyPath fixture
            "duration": 120.5,
            "upload_date": "20260401",
            "view_count": 1234,
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_a, **_k: FakeYoutubeDL(info=info, touch_file=expected_file),
        )

        outcome = YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=abc123", str(destination)
        )

        # Original assertions still hold
        assert outcome.platform is Platform.YOUTUBE
        assert outcome.title == "Hello world"
        assert outcome.author == "Test Channel"
        assert outcome.view_count == 1234
        # D-02: uploader_id absent → creator_info None
        assert outcome.creator_info is None
```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py::TestCreatorInfoExtraction -x -q</automated>
</verify>

<acceptance_criteria>
- `grep -q "class TestCreatorInfoExtraction" tests/unit/adapters/ytdlp/test_downloader.py` exit 0
- `grep -q "test_populates_creator_info_when_uploader_id_present" tests/unit/adapters/ytdlp/test_downloader.py` exit 0
- `grep -q "test_creator_info_none_when_uploader_id_absent" tests/unit/adapters/ytdlp/test_downloader.py` exit 0
- `grep -q "test_creator_info_none_when_uploader_id_empty_string" tests/unit/adapters/ytdlp/test_downloader.py` exit 0
- `grep -q "test_creator_info_falls_back_to_channel_id" tests/unit/adapters/ytdlp/test_downloader.py` exit 0
- `grep -q "test_creator_info_avatar_from_list_shape" tests/unit/adapters/ytdlp/test_downloader.py` exit 0
- `grep -q "test_creator_info_follower_count_non_int_degrades_to_none" tests/unit/adapters/ytdlp/test_downloader.py` exit 0
- `grep -q "test_creator_info_follower_count_fallback_channel_followers" tests/unit/adapters/ytdlp/test_downloader.py` exit 0
- `python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py::TestCreatorInfoExtraction -x -q` exit 0 (9 nouveaux tests verts)
- `python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py -x -q` exit 0 (tous les tests downloader verts, y compris les existants)
- `python -m uv run pytest -q` exit 0 (suite complète — aucune régression)
- `python -m uv run ruff check src tests` exit 0
- `python -m uv run mypy src` exit 0
</acceptance_criteria>

<done>
9 nouveaux tests `TestCreatorInfoExtraction` verts couvrent happy path, D-02 absent, D-02 empty, fallback `channel_id`, liste d'avatars, fallback `channel_followers`, non-int follower_count, et non-régression du test happy path historique. Aucun test existant modifié.
</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| yt-dlp info_dict → adapter | yt-dlp renvoie des données hors contrôle (MITM, extractor compromis, plateforme hostile) qui transitent ensuite vers la DB |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-S02P02-01 | **Tampering (T)** — valeurs malicieuses (ex: `uploader_id=<script>alert(1)</script>`) | `_extract_creator_info` → `CreatorInfo` dict | LOW | mitigate (accept data-at-rest) | Les valeurs ne sont jamais interprétées en HTML (vidscope est CLI-only) ni concaténées en SQL brut (P03 passe par `sqlite_insert().values(**payload)` bind-parameters, même chemin que S01-P04 T-P04-01). `_str_or_none` strip + trunque l'espace — préserve la string literale. Pas de XSS (pas de HTML), pas de SQLi (bind params), pas de command injection (pas d'eval/exec). |
| T-S02P02-02 | **Tampering (T)** — shape inattendue (liste au lieu de string, int négatif pour follower_count) | `_extract_creator_info` delegation vers helpers existants | LOW | mitigate | Délégation à `_extract_uploader_thumbnail` (gère str, list[dict], list[str]) et `_int_or_none` (try/except sur la conversion) — ces helpers sont déjà testés en S01-P04 et ce plan ajoute explicitement des tests de robustesse (avatar list, follower_count non-int). |
| T-S02P02-03 | **DoS** — `uploader_id` très long qui remplit la DB | `CreatorRepositorySQLite.upsert` en aval (P03) | LOW | accept | Limite SQLite par défaut TEXT unlimited, mais la colonne `platform_user_id` a UNIQUE donc un attaquant remplissant 100k de lignes distinctes est plausible seulement s'il contrôle un compte de création YouTube — coût élevé pour un tool personnel local. Accepted (YAGNI quota). |
| T-S02P02-04 | **Information Disclosure (I)** — leak d'`uploader_id` via logs yt-dlp | `YtdlpDownloader.download()` | LOW | accept | yt-dlp est en mode `quiet=True` — pas de leak stdout. Les erreurs contiennent l'URL publique (déjà le cas avant ce plan). |
</threat_model>

<verification>
```bash
# Plan 02 spécifique
python -m uv run pytest tests/unit/adapters/ytdlp/test_downloader.py::TestCreatorInfoExtraction -x -q

# Non-régression downloader
python -m uv run pytest tests/unit/adapters/ytdlp/ -x -q

# Non-régression globale
python -m uv run pytest -q

# 9 contrats architecture
python -m uv run lint-imports

# Quality gates
python -m uv run ruff check src tests
python -m uv run mypy src
```
</verification>

<success_criteria>
- `_extract_creator_info` défini dans `downloader.py`, réutilise `_extract_uploader_thumbnail`, `_extract_uploader_verified`, `_str_or_none`, `_int_or_none` (aucune duplication)
- `_info_to_outcome` appelle `_extract_creator_info(info)` et passe le résultat à `IngestOutcome(creator_info=...)`
- 9 nouveaux tests `TestCreatorInfoExtraction` couvrent tous les cas de D-01 et D-02
- Test historique `TestHappyPath::test_youtube_returns_ingest_outcome` reste vert (rétrocompat)
- Suite complète pytest verte
- 9 contrats import-linter verts (`pipeline-has-no-adapters` et autres inchangés)
- mypy strict vert, ruff vert
</success_criteria>

<output>
À la fin du plan, créer `.gsd/milestones/M006/slices/S02/S02-P02-SUMMARY.md` résumant :
- Fichiers modifiés (`adapters/ytdlp/downloader.py` + `tests/unit/adapters/ytdlp/test_downloader.py`)
- Ligne exacte où `_extract_creator_info` est inséré
- Liste des 9 nouveaux tests et ce qu'ils couvrent
- Confirmation rétrocompat downloader (tests existants inchangés verts)
- Handoff pour P03 : le downloader produit maintenant `IngestOutcome.creator_info` prêt à être consommé par `IngestStage`
</output>
</content>
</invoke>