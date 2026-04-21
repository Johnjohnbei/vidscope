---
phase: M012
plan: S03
type: execute
wave: 1
depends_on: [M012/S01, M012/S02]
files_modified:
  - src/vidscope/mcp/server.py
  - tests/unit/mcp/test_server.py
autonomous: true
requirements: [R064, R065]
tags: [mcp, server, vidscope_get_video, description, engagement, ocr_preview, carousel]
must_haves:
  truths:
    - "`_video_to_dict(video)` retourne un dict contenant la clé `\"description\"` avec la valeur `video.description` (str ou null)"
    - "`vidscope_get_video` retourne `latest_engagement: dict | null` dans le dict racine — dict contient exactement les clés `view_count`, `like_count`, `comment_count`, `repost_count`, `save_count`, `captured_at` (ISO-8601 UTC) si des stats existent, ou `null` si `result.latest_stats is None`"
    - "Pour un carousel (`result.video.content_shape == \"carousel\"`), `vidscope_get_video` retourne dans le dict racine : `ocr_preview` (str) = les `text` des 5 premiers `FrameText` triés `(frame_id ASC, id ASC)` concaténés avec `\\n`, et `ocr_full_tool: \"vidscope_get_frame_texts\"` (str)"
    - "Pour un non-carousel (reel, vidéo), `ocr_preview` et `ocr_full_tool` sont ABSENTS du dict racine (omis, pas null)"
    - "`vidscope_list_videos` expose désormais `description` dans chaque video via `_video_to_dict` — effet automatique de D-05"
    - "Suite `pytest tests/unit -q` : 0 failed, baseline 1673 → ≥1683 tests (10 nouveaux tests MCP)"
  artifacts:
    - path: "src/vidscope/mcp/server.py"
      provides: "_video_to_dict enrichi (description) + vidscope_get_video enrichi (latest_engagement, ocr_preview, ocr_full_tool)"
      contains: "\"description\": video.description"
    - path: "tests/unit/mcp/test_server.py"
      provides: "Tests R064 + R065 : description, latest_engagement (null + populated), ocr_preview carousel, non-carousel absence"
      contains: "test_get_video_includes_description_in_video_dict"
  key_links:
    - from: "src/vidscope/mcp/server.py::_video_to_dict"
      to: "Video.description"
      via: "champ directement mappé dans le dict"
      pattern: "\"description\": video\\.description"
    - from: "src/vidscope/mcp/server.py::vidscope_get_video"
      to: "ShowVideoResult.latest_stats (VideoStats)"
      via: "result.latest_stats — already fetched by ShowVideoUseCase.execute"
      pattern: "latest_stats"
    - from: "src/vidscope/mcp/server.py::vidscope_get_video"
      to: "ShowVideoResult.frame_texts (tuple[FrameText, ...])"
      via: "result.frame_texts — already fetched by ShowVideoUseCase.execute"
      pattern: "frame_texts"
    - from: "src/vidscope/mcp/server.py::vidscope_get_video"
      to: "Video.content_shape"
      via: "result.video.content_shape == \"carousel\" (champ déjà dans _video_to_dict)"
      pattern: "content_shape"
---

<objective>
M012/S03 — MCP output enrichi.

Un agent obtient un portrait complet d'un contenu en un seul appel `vidscope_get_video` :

1. **R064** — `vidscope_get_video` retourne `description` (dans le sous-dict `video`) et `latest_engagement` (dict ou null dans le dict racine) contenant les 5 compteurs + `captured_at`.

2. **R065** — Pour les carousels, `vidscope_get_video` retourne en plus `ocr_preview` (5 premiers blocs OCR concaténés avec `\n`) et `ocr_full_tool: "vidscope_get_frame_texts"` dans le dict racine. Pour les non-carousels, ces deux champs sont absents (omis, pas null).

Le travail est exclusivement du câblage dans `server.py` : toutes les données nécessaires sont déjà disponibles dans `ShowVideoResult` (`latest_stats`, `frame_texts`, `video.description`, `video.content_shape`). Aucune modification des entités, repositories, use cases, ni pipeline.

Output : 1 fichier source patché (`server.py`) + 1 fichier de test étendu (`test_server.py`), ~10 nouveaux tests, zéro régression sur les 1673 tests existants.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M012/M012-ROADMAP.md
@.gsd/milestones/M012/M012-S03-CONTEXT.md

# Fichier source à modifier
@src/vidscope/mcp/server.py

# Fichier de test à étendre
@tests/unit/mcp/test_server.py

<interfaces>
<!-- Contrats essentiels à l'exécuteur — extraits du code existant -->

From src/vidscope/mcp/server.py — état actuel :

```python
# _video_to_dict ligne 66 — retourne actuellement :
{
    "id": ..., "platform": ..., "platform_id": ..., "url": ...,
    "title": ..., "author": ..., "duration": ..., "upload_date": ...,
    "view_count": ..., "media_key": ..., "media_type": ...,
    "thumbnail_key": ..., "content_shape": ..., "created_at": ...
    # "description" MANQUANT — doit être ajouté ici (D-05)
}

# vidscope_get_video ligne 242 — retourne actuellement :
{
    "found": True,
    "video": video_dict,
    "transcript": transcript_dict,
    "frame_count": len(result.frames),
    "analysis": analysis_dict,
    # "latest_engagement" MANQUANT
    # "ocr_preview" MANQUANT pour carousels
    # "ocr_full_tool" MANQUANT pour carousels
}
```

From src/vidscope/application/show_video.py — ShowVideoResult (frozen dataclass) :
```python
@dataclass(frozen=True, slots=True)
class ShowVideoResult:
    found: bool
    video: Video | None = None
    transcript: Transcript | None = None
    frames: tuple[Frame, ...] = ()
    analysis: Analysis | None = None
    latest_stats: VideoStats | None = None   # D-01 source
    frame_texts: tuple[FrameText, ...] = ()  # D-06 source
    # ...
```

From src/vidscope/domain/entities.py — VideoStats (frozen dataclass) :
```python
@dataclass(frozen=True, slots=True)
class VideoStats:
    video_id: VideoId
    captured_at: datetime   # UTC, toujours present
    view_count: int | None = None
    like_count: int | None = None
    repost_count: int | None = None
    comment_count: int | None = None
    save_count: int | None = None
    id: int | None = None
    created_at: datetime | None = None
```

From src/vidscope/domain/entities.py — FrameText (frozen dataclass) :
```python
@dataclass(frozen=True, slots=True)
class FrameText:
    video_id: VideoId
    frame_id: int          # tri ASC pour ocr_preview
    text: str
    confidence: float
    bbox: str | None = None
    id: int | None = None  # tri ASC secondaire (None → 0)
    created_at: datetime | None = None
```

From src/vidscope/domain/entities.py — Video.description :
```python
description: str | None = None  # ligne 84
```

From tests/unit/mcp/test_server.py — infrastructure réutilisable :
```python
# sandboxed_container : Container avec SQLite dans tmp_path
# _seed_library(container) : insère 1 video YouTube avec transcript + analysis
# _call_tool(server, name, args) : appelle un MCP tool et retourne le dict résultat

# Pour seeder VideoStats dans un test :
with container.unit_of_work() as uow:
    uow.video_stats.append(VideoStats(
        video_id=video_id,
        captured_at=datetime(..., tzinfo=UTC),
        like_count=42,
        ...
    ))

# Pour seeder FrameText (carousel), il faut d'abord un Frame :
# 1. uow.frames.add_many([Frame(...)]) → list[Frame]
# 2. uow.frame_texts.add_many_for_frame(frame.id, video_id, [FrameText(...)])
# (pattern identique à test_analyze.py::_seed_carousel_with_frame_texts)
```

From src/vidscope/adapters/sqlite/unit_of_work.py :
- `uow.video_stats: VideoStatsRepository` — méthode `append(VideoStats) -> VideoStats`
- `uow.frame_texts: FrameTextRepository` — méthode `add_many_for_frame(frame_id, video_id, [FrameText])`
- `uow.frames: FrameRepository` — méthode `add_many([Frame]) -> list[Frame]`

Décisions CONTEXT.md en vigueur :
- D-01 : `latest_engagement` = null si `latest_stats is None`, dict avec les 5 champs + `captured_at` sinon
- D-02 : `ocr_full_tool: "vidscope_get_frame_texts"` champ séparé
- D-03 : `ocr_preview` et `ocr_full_tool` ABSENTS (pas null) pour non-carousels
- D-04 : détection via `video.content_shape == "carousel"`
- D-05 : `description` dans `_video_to_dict()` (exposé aussi dans `vidscope_list_videos`)
- D-06 : 5 premiers FrameText triés `(frame_id ASC, id ASC)`, concaténés avec `\n`
</interfaces>
</context>

<tasks>

<!-- ====================================================================== -->
<!-- WAVE 1 — RED tests + implementation (fichiers disjoints → parallèles)  -->
<!-- T01 écrit les tests RED ; T02 implémente le GREEN dans server.py        -->
<!-- Ordre recommandé : T01 d'abord (TDD), T02 ensuite. Mais les fichiers   -->
<!-- étant disjoints l'exécuteur peut les faire en parallèle si souhaité.   -->
<!-- ====================================================================== -->

<task type="auto" tdd="true">
  <name>T01: RED — tests R064 + R065 (description, latest_engagement, ocr_preview, ocr_full_tool)</name>
  <files>tests/unit/mcp/test_server.py</files>
  <read_first>
    - tests/unit/mcp/test_server.py (intégralité — pour réutiliser sandboxed_container, _seed_library, _call_tool et comprendre le pattern de seeding)
    - src/vidscope/application/show_video.py (ShowVideoResult — confirmer que latest_stats et frame_texts sont bien dans le résultat)
    - src/vidscope/domain/entities.py lignes 253-276 (VideoStats), lignes 368-384 (FrameText)
    - src/vidscope/adapters/sqlite/unit_of_work.py lignes 100-140 (accès uow.video_stats + uow.frames + uow.frame_texts)
  </read_first>
  <behavior>
    R064 — description :
    - `vidscope_list_videos` : chaque video du résultat contient `description` (null si non seedée)
    - `vidscope_get_video` : `result["video"]["description"]` est null si description non seedée, string si seedée

    R064 — latest_engagement :
    - `vidscope_get_video` : `result["latest_engagement"]` est null si aucune VideoStats pour ce video
    - `vidscope_get_video` avec VideoStats seedée : `result["latest_engagement"]` est un dict avec `like_count`, `comment_count`, `view_count`, `repost_count`, `save_count`, `captured_at` (ISO-8601 string)

    R065 — ocr_preview carousel :
    - `vidscope_get_video` pour un carousel avec ≥1 FrameText : `result["ocr_preview"]` existe, `result["ocr_full_tool"] == "vidscope_get_frame_texts"`
    - `vidscope_get_video` pour une vidéo non-carousel : `"ocr_preview"` ABSENT du dict, `"ocr_full_tool"` ABSENT du dict
    - `ocr_preview` contient les 5 premiers blocs OCR (max) concaténés avec `\n`
    - Pour un carousel avec exactement 2 FrameTexts, `ocr_preview` contient les 2 textes séparés par `\n`
  </behavior>
  <action>
Ajouter à la fin de `tests/unit/mcp/test_server.py` les imports manquants en haut du fichier si absents, puis deux nouvelles classes de tests.

**Étape 1 — vérifier les imports** :
Ajouter dans le bloc d'imports existant si absents :
```python
from datetime import UTC, datetime  # datetime déjà importé si test_get_status utilise datetime
from vidscope.domain import Frame, FrameText, VideoStats  # Frame et FrameText probablement absents
```

**Étape 2 — ajouter deux helpers de seeding** (avant les nouvelles classes) :

```python
def _seed_video_with_description(container: Container) -> tuple[VideoId, str]:
    """Seed a video with a description and return (video_id, description)."""
    from datetime import datetime

    description = "A test video with a meaningful caption"
    with container.unit_of_work() as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("desc-test"),
                url="https://www.youtube.com/shorts/desc-test",
                title="Description Test Video",
                description=description,
                media_key="videos/youtube/desc-test/media.mp4",
            )
        )
        assert video.id is not None
        return video.id, description


def _seed_video_stats(container: Container, video_id: VideoId) -> VideoStats:
    """Append a VideoStats row for the given video and return it."""
    stats = VideoStats(
        video_id=video_id,
        captured_at=datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC),
        like_count=42,
        comment_count=7,
        view_count=1000,
        repost_count=3,
        save_count=15,
    )
    with container.unit_of_work() as uow:
        return uow.video_stats.append(stats)


def _seed_carousel_video(
    container: Container,
    *,
    frame_texts: tuple[str, ...] = ("First block", "Second block"),
) -> VideoId:
    """Seed a carousel video with FrameText rows and return its VideoId."""
    with container.unit_of_work() as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.INSTAGRAM,
                platform_id=PlatformId("carousel-mcp-test"),
                url="https://www.instagram.com/p/carousel-mcp-test/",
                title="Carousel MCP Test",
                content_shape="carousel",
                media_key="videos/instagram/carousel-mcp-test/items/0000.jpg",
            )
        )
        assert video.id is not None
        frames = uow.frames.add_many(
            [
                Frame(
                    video_id=video.id,
                    image_key=f"videos/instagram/carousel-mcp-test/items/{i:04d}.jpg",
                    timestamp_ms=i * 1000,
                    is_keyframe=True,
                )
                for i in range(len(frame_texts))
            ]
        )
        for frame, text in zip(frames, frame_texts):
            assert frame.id is not None
            uow.frame_texts.add_many_for_frame(
                frame.id,
                video.id,
                [
                    FrameText(
                        video_id=video.id,
                        frame_id=frame.id,
                        text=text,
                        confidence=0.95,
                    )
                ],
            )
        return video.id
```

**Étape 3 — ajouter la classe TestVidscopeGetVideoR064** :

```python
# ---------------------------------------------------------------------------
# vidscope_get_video — R064 (description + latest_engagement)
# ---------------------------------------------------------------------------


class TestVidscopeGetVideoR064:
    """R064 — vidscope_get_video exposes description and latest_engagement."""

    def test_get_video_includes_description_in_video_dict(
        self, sandboxed_container: Container
    ) -> None:
        """description field is present (null) even when not seeded."""
        video_id = _seed_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_video", {"video_id": int(video_id)})
        assert result["found"] is True
        # description key must exist in video sub-dict (value may be null)
        assert "description" in result["video"]

    def test_get_video_description_populated_when_seeded(
        self, sandboxed_container: Container
    ) -> None:
        video_id, expected_desc = _seed_video_with_description(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_video", {"video_id": int(video_id)})
        assert result["found"] is True
        assert result["video"]["description"] == expected_desc

    def test_list_videos_includes_description(
        self, sandboxed_container: Container
    ) -> None:
        """D-05 — description exposed via _video_to_dict, available in list_videos too."""
        _seed_video_with_description(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_list_videos", {"limit": 10})
        assert result["total"] >= 1
        video = result["videos"][0]
        assert "description" in video

    def test_get_video_latest_engagement_null_when_no_stats(
        self, sandboxed_container: Container
    ) -> None:
        video_id = _seed_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_video", {"video_id": int(video_id)})
        assert result["found"] is True
        assert "latest_engagement" in result
        assert result["latest_engagement"] is None

    def test_get_video_latest_engagement_populated_when_stats_seeded(
        self, sandboxed_container: Container
    ) -> None:
        video_id = _seed_library(sandboxed_container)
        _seed_video_stats(sandboxed_container, video_id)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_video", {"video_id": int(video_id)})
        assert result["found"] is True
        eng = result["latest_engagement"]
        assert eng is not None
        assert eng["like_count"] == 42
        assert eng["comment_count"] == 7
        assert eng["view_count"] == 1000
        assert eng["repost_count"] == 3
        assert eng["save_count"] == 15
        # captured_at must be an ISO-8601 string
        assert isinstance(eng["captured_at"], str)
        assert "2026-04-21" in eng["captured_at"]

    def test_get_video_latest_engagement_has_all_required_keys(
        self, sandboxed_container: Container
    ) -> None:
        """D-01 — all 6 keys must be present when stats exist."""
        video_id = _seed_library(sandboxed_container)
        _seed_video_stats(sandboxed_container, video_id)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_video", {"video_id": int(video_id)})
        eng = result["latest_engagement"]
        assert eng is not None
        for key in ("view_count", "like_count", "comment_count",
                    "repost_count", "save_count", "captured_at"):
            assert key in eng, f"missing key: {key}"
```

**Étape 4 — ajouter la classe TestVidscopeGetVideoR065** :

```python
# ---------------------------------------------------------------------------
# vidscope_get_video — R065 (ocr_preview + ocr_full_tool for carousels)
# ---------------------------------------------------------------------------


class TestVidscopeGetVideoR065:
    """R065 — vidscope_get_video exposes ocr_preview for carousels only."""

    def test_carousel_includes_ocr_preview_and_ocr_full_tool(
        self, sandboxed_container: Container
    ) -> None:
        video_id = _seed_carousel_video(
            sandboxed_container,
            frame_texts=("Build in public. 5 tips", "Slide 2: workflow"),
        )
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_video", {"video_id": int(video_id)})
        assert result["found"] is True
        assert "ocr_preview" in result
        assert "ocr_full_tool" in result
        assert result["ocr_full_tool"] == "vidscope_get_frame_texts"

    def test_carousel_ocr_preview_contains_first_blocks(
        self, sandboxed_container: Container
    ) -> None:
        texts = ("Block 1", "Block 2", "Block 3")
        video_id = _seed_carousel_video(sandboxed_container, frame_texts=texts)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_video", {"video_id": int(video_id)})
        preview = result["ocr_preview"]
        assert "Block 1" in preview
        assert "Block 2" in preview
        assert "Block 3" in preview

    def test_carousel_ocr_preview_capped_at_five_blocks(
        self, sandboxed_container: Container
    ) -> None:
        """D-06 — at most 5 blocks in ocr_preview."""
        texts = ("A", "B", "C", "D", "E", "F", "G")
        video_id = _seed_carousel_video(sandboxed_container, frame_texts=texts)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_video", {"video_id": int(video_id)})
        preview = result["ocr_preview"]
        # Only 5 blocks at most — "F" and "G" must not appear
        blocks_in_preview = preview.split("\n")
        assert len(blocks_in_preview) <= 5
        assert "F" not in blocks_in_preview
        assert "G" not in blocks_in_preview

    def test_non_carousel_has_no_ocr_preview_or_ocr_full_tool(
        self, sandboxed_container: Container
    ) -> None:
        """D-03 — ocr_preview and ocr_full_tool ABSENT (not null) for non-carousel."""
        video_id = _seed_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_video", {"video_id": int(video_id)})
        assert result["found"] is True
        assert "ocr_preview" not in result
        assert "ocr_full_tool" not in result
```

Tous ces tests sont RED tant que T02 n'a pas modifié `server.py`.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/mcp/test_server.py::TestVidscopeGetVideoR064 tests/unit/mcp/test_server.py::TestVidscopeGetVideoR065 -x -v 2>&1 | tail -30</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class TestVidscopeGetVideoR064\|class TestVidscopeGetVideoR065" tests/unit/mcp/test_server.py` retourne exactement 2 lignes
    - `grep -n "test_get_video_includes_description_in_video_dict\|test_get_video_description_populated_when_seeded\|test_list_videos_includes_description\|test_get_video_latest_engagement_null_when_no_stats\|test_get_video_latest_engagement_populated_when_stats_seeded\|test_get_video_latest_engagement_has_all_required_keys" tests/unit/mcp/test_server.py` retourne exactement 6 lignes
    - `grep -n "test_carousel_includes_ocr_preview_and_ocr_full_tool\|test_carousel_ocr_preview_contains_first_blocks\|test_carousel_ocr_preview_capped_at_five_blocks\|test_non_carousel_has_no_ocr_preview_or_ocr_full_tool" tests/unit/mcp/test_server.py` retourne exactement 4 lignes
    - `grep -n "_seed_video_with_description\|_seed_video_stats\|_seed_carousel_video" tests/unit/mcp/test_server.py` retourne au moins 6 lignes (3 définitions + usages)
    - En l'état (avant T02), `pytest tests/unit/mcp/test_server.py::TestVidscopeGetVideoR064::test_get_video_latest_engagement_null_when_no_stats` échoue avec KeyError ou AssertionError (RED — le champ n'existe pas encore)
    - En l'état (avant T02), `pytest tests/unit/mcp/test_server.py::TestVidscopeGetVideoR065::test_non_carousel_has_no_ocr_preview_or_ocr_full_tool` passe déjà (le dict ne contient pas ces clés) — ce test sera GREEN immédiatement
  </acceptance_criteria>
  <done>
    Classes `TestVidscopeGetVideoR064` (6 tests) et `TestVidscopeGetVideoR065` (4 tests) ajoutées avec helpers de seeding. Tests R064 sont RED ; tests R065 pour non-carousel passent déjà ; tests R065 pour carousel sont RED.
  </done>
</task>

<task type="auto" tdd="true">
  <name>T02: GREEN — enrichir _video_to_dict + vidscope_get_video dans server.py</name>
  <files>src/vidscope/mcp/server.py</files>
  <read_first>
    - src/vidscope/mcp/server.py (intégralité — 524 lignes ; en particulier _video_to_dict ligne 66-83 et vidscope_get_video ligne 208-248)
    - src/vidscope/domain/entities.py lignes 61-90 (Video — confirmer champ description ligne 84)
    - src/vidscope/domain/entities.py lignes 253-276 (VideoStats — tous les champs)
    - src/vidscope/domain/entities.py lignes 368-384 (FrameText — frame_id, text, id)
    - .gsd/milestones/M012/M012-S03-CONTEXT.md (D-01 à D-06 — décisions d'implémentation)
  </read_first>
  <behavior>
    Modification 1 — `_video_to_dict` (ligne 66) :
    - Ajouter `"description": video.description` dans le dict retourné (entre `"upload_date"` et `"view_count"` ou à la fin, peu importe l'ordre)

    Modification 2 — `vidscope_get_video` (ligne 208) :
    - Construire `latest_engagement_dict` : si `result.latest_stats is not None`, dict avec les 5 compteurs + `captured_at.isoformat()` ; sinon None
    - Pour les carousels (`result.video.content_shape == "carousel"`) ET quand `result.frame_texts` est non-vide : trier les FrameTexts par `(ft.frame_id, ft.id or 0)` ASC, prendre les 5 premiers, concaténer avec `"\n"` → `ocr_preview`
    - Construire le dict de retour final avec les nouveaux champs
    - `ocr_preview` et `ocr_full_tool` ABSENTS du dict pour non-carousels (D-03)
  </behavior>
  <action>
**Modification 1 — `_video_to_dict` (ligne 66-83)** :

Remplacer le corps de la fonction `_video_to_dict` pour inclure `description`. Remplacer l'intégralité du bloc `return { ... }` (lignes 68-83) par :

```python
    return {
        "id": int(video.id) if video.id is not None else None,
        "platform": video.platform.value,
        "platform_id": str(video.platform_id),
        "url": video.url,
        "title": video.title,
        "author": video.author,
        "description": video.description,
        "duration": video.duration,
        "upload_date": video.upload_date,
        "view_count": video.view_count,
        "media_key": video.media_key,
        "media_type": video.media_type.value,
        "thumbnail_key": video.thumbnail_key,
        "content_shape": video.content_shape,
        "created_at": video.created_at.isoformat() if video.created_at else None,
    }
```

**Modification 2 — `vidscope_get_video` (lignes 208-248)** :

Remplacer le bloc `return { ... }` final (lignes 242-248) par les lignes suivantes, insérées APRÈS la construction de `analysis_dict` et AVANT le `return` :

```python
        # R064 — latest_engagement: null if no stats, dict otherwise (D-01)
        latest_engagement: dict[str, Any] | None = None
        if result.latest_stats is not None:
            s = result.latest_stats
            latest_engagement = {
                "view_count": s.view_count,
                "like_count": s.like_count,
                "comment_count": s.comment_count,
                "repost_count": s.repost_count,
                "save_count": s.save_count,
                "captured_at": s.captured_at.isoformat(),
            }

        response: dict[str, Any] = {
            "found": True,
            "video": video_dict,
            "transcript": transcript_dict,
            "frame_count": len(result.frames),
            "analysis": analysis_dict,
            "latest_engagement": latest_engagement,
        }

        # R065 — ocr_preview: carousel only; absent (not null) for non-carousels (D-03, D-04)
        if result.video.content_shape == "carousel" and result.frame_texts:
            sorted_fts = sorted(
                result.frame_texts,
                key=lambda ft: (ft.frame_id, ft.id or 0),
            )
            response["ocr_preview"] = "\n".join(
                ft.text for ft in sorted_fts[:5]
            )
            response["ocr_full_tool"] = "vidscope_get_frame_texts"

        return response
```

**Vérification de cohérence** : l'ancien `return { "found": True, ... }` (lignes 242-248) doit être intégralement REMPLACÉ par le nouveau bloc `response = ...` + `return response`. Ne pas laisser deux blocs `return` à la fin de `vidscope_get_video`.

Aucun autre changement dans `server.py`. Les imports existants sont suffisants (`from typing import Any` déjà présent).
  </action>
  <verify>
    <automated>python -m pytest tests/unit/mcp/test_server.py::TestVidscopeGetVideoR064 tests/unit/mcp/test_server.py::TestVidscopeGetVideoR065 -x -v 2>&1 | tail -30</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n '"description": video.description' src/vidscope/mcp/server.py` retourne exactement 1 ligne (dans `_video_to_dict`)
    - `grep -n "latest_engagement" src/vidscope/mcp/server.py` retourne au moins 4 lignes (variable, if, dict clé, réponse)
    - `grep -n 'content_shape == "carousel"' src/vidscope/mcp/server.py` retourne exactement 1 ligne
    - `grep -n '"ocr_preview"' src/vidscope/mcp/server.py` retourne exactement 1 ligne (dans `response["ocr_preview"] = ...`)
    - `grep -n '"ocr_full_tool"' src/vidscope/mcp/server.py` retourne exactement 1 ligne
    - `grep -n 's\.captured_at\.isoformat()' src/vidscope/mcp/server.py` retourne exactement 1 ligne
    - `pytest tests/unit/mcp/test_server.py::TestVidscopeGetVideoR064` : 6/6 tests passent (GREEN)
    - `pytest tests/unit/mcp/test_server.py::TestVidscopeGetVideoR065` : 4/4 tests passent (GREEN)
    - `pytest tests/unit/mcp/test_server.py::TestVidscopeGetVideo` : 2/2 tests existants passent (pas de régression)
    - `pytest tests/unit/mcp/test_server.py::TestVidscopeListVideos` : 2/2 tests existants passent (pas de régression sur list_videos)
    - `python -c "from vidscope.mcp.server import _video_to_dict; print('import OK')"` passe
  </acceptance_criteria>
  <done>
    `_video_to_dict` expose `description` ; `vidscope_get_video` expose `latest_engagement` (null ou dict) et `ocr_preview`/`ocr_full_tool` pour les carousels uniquement. Les 10 nouveaux tests R064+R065 passent (GREEN). Tests existants non régressés.
  </done>
</task>

<!-- ====================================================================== -->
<!-- WAVE 2 — Regression gate (dépend de Wave 1 complète)                   -->
<!-- ====================================================================== -->

<task type="auto">
  <name>T03: Full suite regression gate — baseline 1673 → ≥1683 tests all green</name>
  <files>tests/unit/ (lecture seule)</files>
  <read_first>
    - tests/unit/mcp/test_server.py (état post-T01+T02 — confirmer le nombre de tests MCP)
  </read_first>
  <action>
Exécuter la suite unit complète :

```bash
python -m pytest tests/unit -q 2>&1 | tail -20
```

**Cas attendus** :

1. **Tous passent** (≥1683 tests, 0 failed) : T03 terminé.

2. **Régression dans un test MCP existant** (`TestVidscopeGetVideo`, `TestVidscopeListVideos`, etc.) : diagnostiquer. Le plus probable est une clé ajoutée par T02 qui casse une assertion de type `assert result == { exact_dict }`. Dans ce cas, corriger l'assertion dans le test (non-breaking change — nouveaux champs sont additifs).

3. **Autre régression** : imprimer le traceback complet, identifier la source. NE PAS modifier `src/` — toute modification doit rester dans les tests si nécessaire, avec commentaire `# R064` ou `# R065`.

**Deliverable** : `python -m pytest tests/unit -q` se termine avec `X passed` où X ≥ 1683, et `0 failed`.
  </action>
  <verify>
    <automated>python -m pytest tests/unit -q 2>&1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - La sortie `pytest tests/unit -q` termine avec `X passed` et `0 failed` où X >= 1683
    - `pytest tests/unit/mcp/ -q` : 0 failed
    - `pytest tests/unit/mcp/test_server.py -v 2>&1 | grep -c PASSED` retourne au moins 23 (13 existants + 10 nouveaux)
    - Aucun fichier dans `src/vidscope/` n'a été modifié par cette tâche (`git diff src/` vide pour T03)
  </acceptance_criteria>
  <done>
    Suite unit complète passe (≥1683 tests, 0 failed). Aucune modification source `src/`. MCP tests tous verts.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `vidscope_get_video` (MCP) → agent LLM | Le dict retourné est transmis au modèle LLM appelant le tool |
| `video_stats` table → `_video_to_dict`/`vidscope_get_video` | Données stats lues depuis SQLite locale |
| `frame_texts` table → `ocr_preview` | Texte OCR extrait d'images Instagram/YouTube |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-M012S03-01 | Information Disclosure | `description` exposée dans MCP | accept | La description est une métadonnée publique (caption Instagram/YouTube) — déjà accessible via `vidscope show`. Aucune nouvelle surface privée exposée. VidScope est mono-utilisateur local. |
| T-M012S03-02 | Tampering (Prompt Injection) | `ocr_preview` contient texte OCR arbitraire d'une image Instagram | accept | Le texte OCR est passé tel quel à l'agent LLM. Un attaquant contrôlant l'image peut y injecter des instructions. Niveau de risque identique à toute donnée user-generated passée à un LLM — hors scope VidScope (outil local de veille). Mitigation future : sanitisation ou truncation à N chars. |
| T-M012S03-03 | DoS | `ocr_preview` concaténant de nombreux blocs volumineux (D-06 limite à 5) | mitigate | La limite de 5 blocs est implémentée par `sorted_fts[:5]`. Chaque texte OCR est une ligne d'image — typiquement < 200 chars. Impact négligeable sur le contexte agent. |
| T-M012S03-04 | Integrity | `captured_at` null dans VideoStats | accept | `VideoStats.captured_at` est non-optional dans le dataclass et toujours peuplé à l'insertion (voir `video_stats_repository.py`). `.isoformat()` ne peut pas lever sur une datetime valide. |
| T-M012S03-05 | Injection (SQL) | `frame_texts.list_for_video` via `video_id` | mitigate | `ShowVideoUseCase` utilise les repositories avec bind params SQLAlchemy Core. `video_id` vient d'un paramètre MCP (int) validé par FastMCP avant l'appel. Aucun SQL brut dans le chemin. |

**Aucun nouveau vecteur réseau, authentification, ou écriture DB introduit.**
</threat_model>

<verification>

## Vérification globale de phase

```bash
# 1. Tests MCP ciblés (R064 + R065)
python -m pytest \
    tests/unit/mcp/test_server.py::TestVidscopeGetVideoR064 \
    tests/unit/mcp/test_server.py::TestVidscopeGetVideoR065 \
    tests/unit/mcp/test_server.py::TestVidscopeGetVideo \
    tests/unit/mcp/test_server.py::TestVidscopeListVideos \
    -x -v

# 2. Non-régression pleine suite unit
python -m pytest tests/unit -q

# 3. Vérifications grep (ancres anti-régression)
# R064 anchors
grep -n '"description": video.description' src/vidscope/mcp/server.py
grep -n "latest_engagement" src/vidscope/mcp/server.py
grep -n 's\.captured_at\.isoformat()' src/vidscope/mcp/server.py

# R065 anchors
grep -n 'content_shape == "carousel"' src/vidscope/mcp/server.py
grep -n '"ocr_preview"' src/vidscope/mcp/server.py
grep -n '"ocr_full_tool"' src/vidscope/mcp/server.py
grep -n 'sorted_fts\[:5\]' src/vidscope/mcp/server.py

# D-03 — vérifier que ocr_full_tool est bien ABSENT pour non-carousels
# (ce test existe dans TestVidscopeGetVideoR065::test_non_carousel_has_no_ocr_preview_or_ocr_full_tool)

# 4. Vérification runtime R064 (smoke test en mémoire)
python -c "
from vidscope.mcp.server import _video_to_dict
from vidscope.domain import Platform, PlatformId, Video

v = Video(
    platform=Platform.YOUTUBE,
    platform_id=PlatformId('smoke'),
    url='https://x.y/smoke',
    description='Test description',
)
d = _video_to_dict(v)
assert 'description' in d
assert d['description'] == 'Test description'
print('R064 _video_to_dict OK:', d['description'])
"

# 5. Vérification runtime R065 (carousel logic en mémoire)
python -c "
# Vérifier que la logique carousel produit les bons champs
# (test indirect — le vrai test est dans test_server.py)
import inspect
from vidscope.mcp.server import build_mcp_server
src = inspect.getsource(build_mcp_server)
assert 'ocr_preview' in src
assert 'ocr_full_tool' in src
assert 'latest_engagement' in src
assert 'carousel' in src
print('R065 server.py fields OK')
"
```

## Checklist must_haves (goal-backward)

- [ ] `_video_to_dict` contient `"description": video.description`
- [ ] `vidscope_get_video` retourne `latest_engagement: null` quand aucune VideoStats
- [ ] `vidscope_get_video` retourne `latest_engagement` dict avec les 5 champs + `captured_at` quand VideoStats existe
- [ ] Pour un carousel avec FrameTexts, `vidscope_get_video` retourne `ocr_preview` (str) et `ocr_full_tool: "vidscope_get_frame_texts"`
- [ ] Pour un non-carousel, `ocr_preview` et `ocr_full_tool` sont ABSENTS du dict racine
- [ ] `ocr_preview` est cappé à 5 blocs maximum
- [ ] Les FrameTexts sont triés par `(frame_id ASC, id ASC)` avant truncation
- [ ] 10 nouveaux tests MCP en place (6 R064 + 4 R065)
- [ ] `pytest tests/unit -q` : 0 failed, ≥1683 tests
- [ ] Aucune autre modification dans `src/` en dehors de `server.py`

</verification>

<success_criteria>

**R064 couvert** :
1. `vidscope_get_video` retourne `description` dans le sous-dict `video` (null si absent, string si peuplé). → T01+T02
2. `vidscope_list_videos` retourne `description` dans chaque video (effet de bord D-05). → T01+T02
3. `vidscope_get_video` retourne `latest_engagement: null` quand aucune stats. → T01+T02
4. `vidscope_get_video` retourne `latest_engagement` dict avec les 6 champs quand stats présentes. → T01+T02

**R065 couvert** :
5. Pour un carousel, `vidscope_get_video` retourne `ocr_preview` (str, max 5 blocs, `\n`-séparés) et `ocr_full_tool: "vidscope_get_frame_texts"`. → T01+T02
6. Pour un non-carousel, `ocr_preview` et `ocr_full_tool` sont absents (D-03). → T01+T02
7. Un agent peut déterminer type + richesse en un seul appel MCP sans appel supplémentaire pour les métadonnées de base. → ensemble des champs R064+R065

**Robustesse & non-régression** :
8. Les 1673 tests baseline passent toujours. → T03
9. Aucune modification en dehors de `server.py` et `test_server.py`. → vérifiable via `git diff`

</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M012/M012-S03-SUMMARY.md` couvrant :
- Requirements R064 + R065 réalisés
- Fichiers modifiés (1 source + 1 test)
- Décisions de design :
  - `description` dans `_video_to_dict` (D-05) → exposé aussi dans `vidscope_list_videos` automatiquement
  - `latest_engagement` null vs dict (D-01) — pattern explicite plutôt que champs plats pour garder la structure JSON propre
  - `ocr_preview` absent (pas null) pour non-carousels (D-03) — évite le bruit dans le context agent
  - Tri `(frame_id, id)` pour `ocr_preview` (D-06) — ordre déterministe même si `id` est null
- Résultat `pytest tests/unit -q` (baseline 1673 → attendu ≥1683)
- Toute surprise rencontrée
- Confirmation : M012/S03 dépendances sur M012/S01 (description DB) et M012/S02 (analysis pour carousels) satisfaites
</output>
