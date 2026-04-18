---
plan_id: S02-P01
phase: M006/S02
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/vidscope/ports/pipeline.py
  - src/vidscope/ports/__init__.py
  - tests/unit/ports/__init__.py
  - tests/unit/ports/test_pipeline_creator_info.py
autonomous: true
requirements: [R040]
must_haves:
  truths:
    - "Downloader implementations can return creator metadata via IngestOutcome.creator_info"
    - "IngestStage can read CreatorInfo fields without importing adapters"
    - "CreatorInfo lives in the ports layer so both adapters and pipeline can reference the same contract"
    - "IngestOutcome stays backward-compatible (creator_info default = None)"
  artifacts:
    - path: "src/vidscope/ports/pipeline.py"
      provides: "CreatorInfo TypedDict + IngestOutcome.creator_info optional field"
      contains: "class CreatorInfo"
    - path: "src/vidscope/ports/__init__.py"
      provides: "Re-export of CreatorInfo from public ports API"
      contains: "CreatorInfo"
    - path: "tests/unit/ports/test_pipeline_creator_info.py"
      provides: "Contract tests for CreatorInfo TypedDict shape + IngestOutcome default"
      min_lines: 50
  key_links:
    - from: "src/vidscope/ports/pipeline.py"
      to: "IngestOutcome"
      via: "creator_info: CreatorInfo | None = None field"
      pattern: "creator_info:\\s*CreatorInfo\\s*\\|\\s*None"
    - from: "src/vidscope/ports/__init__.py"
      to: "CreatorInfo"
      via: "imports + __all__"
      pattern: "CreatorInfo"
---

<objective>
Établir le contrat `CreatorInfo` TypedDict dans la couche ports (D-01) pour que les plans en aval (downloader et pipeline) puissent s'y référer sans duplication et sans violer l'architecture hexagonale.

**Ce plan livre uniquement le contrat — zéro extraction réelle, zéro wiring pipeline.** Les plans S02-P02 (downloader) et S02-P03 (pipeline stage) consomment ce contrat en parallèle.

Purpose: `IngestStage` (pipeline) doit pouvoir lire `outcome.creator_info` pour construire un `Creator`, et `YtdlpDownloader` (adapter) doit pouvoir peupler le même type. Les deux couches ne peuvent se rencontrer que via ports (contrat import-linter). Définir `CreatorInfo` ici est la seule façon légale.

Output: `ports/pipeline.py` étendu avec `CreatorInfo` TypedDict + `IngestOutcome.creator_info` optionnel (défaut `None` — rétrocompat totale). Re-export via `ports/__init__.py`. Tests de contrat garantissant la forme du TypedDict.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/STATE.md
@.gsd/REQUIREMENTS.md
@.gsd/milestones/M006/M006-ROADMAP.md
@.gsd/milestones/M006/slices/S02/S02-CONTEXT.md
@.gsd/milestones/M006/slices/S01/S01-CONTEXT.md
@src/vidscope/ports/pipeline.py
@src/vidscope/ports/__init__.py
@src/vidscope/domain/entities.py
@.importlinter

<interfaces>
<!-- Existing contracts the executor must preserve -->

Currently in src/vidscope/ports/pipeline.py (lines 156-174):

```python
@dataclass(frozen=True, slots=True)
class IngestOutcome:
    """Result of a successful ingest operation."""
    platform: Platform
    platform_id: PlatformId
    url: str
    media_path: str
    title: str | None = None
    author: str | None = None
    duration: float | None = None
    upload_date: str | None = None
    view_count: int | None = None
```

Currently in src/vidscope/domain/entities.py (Creator dataclass — what CreatorInfo fields must map to):

```python
@dataclass(frozen=True, slots=True)
class Creator:
    platform: Platform
    platform_user_id: PlatformUserId  # yt-dlp uploader_id
    id: CreatorId | None = None
    handle: str | None = None
    display_name: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None
    follower_count: int | None = None
    is_verified: bool | None = None
    is_orphan: bool = False
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime | None = None
```

Currently in src/vidscope/ports/__init__.py, __all__ exports (preserve these):
`IngestOutcome`, `ProbeResult`, `ProbeStatus` (already present — add `CreatorInfo` alongside).

Architectural constraint from .importlinter (`ports-are-pure`):
Ports MUST NOT import sqlalchemy, typer, rich, yt_dlp, faster_whisper, httpx, mcp.
TypedDict is stdlib (typing module) — OK.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
<name>Task 1: Ajouter CreatorInfo TypedDict et étendre IngestOutcome.creator_info dans ports/pipeline.py</name>

<read_first>
- `src/vidscope/ports/pipeline.py` lignes 1-66 (imports + __all__ actuel) — on ajoute `CreatorInfo` à `__all__` et on importe `TypedDict` depuis `typing`
- `src/vidscope/ports/pipeline.py` lignes 156-174 (classe `IngestOutcome` actuelle) — on ajoute un champ optionnel à la fin avec défaut `None`
- `src/vidscope/ports/pipeline.py` lignes 190-245 (`ProbeResult` pour mémoire — mêmes champs yt-dlp déjà nommés : `uploader`, `uploader_id`, `uploader_url`, `channel_follower_count`, `uploader_thumbnail`, `uploader_verified`)
- `src/vidscope/domain/entities.py` lignes 214-247 (`Creator` dataclass) — les 7 champs de `CreatorInfo` doivent se mapper 1-pour-1 vers `Creator.__init__`
- `.gsd/milestones/M006/slices/S02/S02-CONTEXT.md` §D-01 — spécifie les 7 champs exacts
- `.importlinter` §`ports-are-pure` — contrainte : pas de dépendance tierce dans ports
</read_first>

<behavior>
- Test 1: `CreatorInfo` est un `TypedDict` importable depuis `vidscope.ports` (via `from vidscope.ports import CreatorInfo`)
- Test 2: `CreatorInfo` a exactement ces 7 clés avec ces types : `platform_user_id: str`, `handle: str | None`, `display_name: str | None`, `profile_url: str | None`, `avatar_url: str | None`, `follower_count: int | None`, `is_verified: bool | None`
- Test 3: `IngestOutcome` accepte `creator_info=None` par défaut (instanciation sans fournir le champ ne casse pas — rétrocompat)
- Test 4: `IngestOutcome` accepte `creator_info={"platform_user_id": "UC_abc", "handle": "@alice", "display_name": "Alice", "profile_url": None, "avatar_url": None, "follower_count": None, "is_verified": None}` et le relit via `outcome.creator_info["platform_user_id"] == "UC_abc"`
- Test 5: `IngestOutcome.creator_info` est `None` par défaut (assert: `IngestOutcome(platform=Platform.YOUTUBE, platform_id=PlatformId("x"), url="u", media_path="/p").creator_info is None`)
</behavior>

<action>
**Fichier 1 : `src/vidscope/ports/pipeline.py`**

1. **Ligne ~39** (imports existants `from typing import Protocol, runtime_checkable`) — ajouter `TypedDict` :
   Remplacer `from typing import Protocol, runtime_checkable` par :
   ```python
   from typing import Protocol, TypedDict, runtime_checkable
   ```

2. **Lignes 52-66** (`__all__` actuel) — ajouter `"CreatorInfo"` en ordre alphabétique entre `"ChannelEntry"` et `"Downloader"`. Le `__all__` final doit contenir (dans l'ordre) :
   ```python
   __all__ = [
       "Analyzer",
       "ChannelEntry",
       "CreatorInfo",
       "Downloader",
       "FrameExtractor",
       "IngestOutcome",
       "PipelineContext",
       "ProbeResult",
       "ProbeStatus",
       "SearchIndex",
       "SearchResult",
       "Stage",
       "StageResult",
       "Transcriber",
   ]
   ```

3. **Juste AVANT la classe `IngestOutcome`** (actuellement ligne ~156) — insérer la définition `CreatorInfo` :
   ```python
   # ---------------------------------------------------------------------------
   # Creator metadata extracted at ingest time (D-01)
   # ---------------------------------------------------------------------------


   class CreatorInfo(TypedDict):
       """Creator metadata carried alongside a successful ingest.

       Populated by :class:`Downloader` implementations from the yt-dlp
       ``info_dict`` without any extra network call. Consumed by
       :class:`IngestStage` to construct a :class:`~vidscope.domain.Creator`
       and upsert it via :attr:`UnitOfWork.creators` before the video row
       write (per D-04: single UoW transaction).

       Fields mirror the subset of ``ProbeResult`` that populates a
       :class:`Creator`:

       - ``platform_user_id`` comes from yt-dlp's ``uploader_id`` — the
         platform-stable id that survives renames (D-01 canonical UNIQUE key).
       - ``handle`` and ``display_name`` both come from yt-dlp's ``uploader``
         today (MAY diverge later if yt-dlp exposes a separate handle field).
       - ``profile_url`` ← ``uploader_url``
       - ``avatar_url`` ← ``uploader_thumbnail`` (first URL when yt-dlp returns a list)
       - ``follower_count`` ← ``channel_follower_count``
       - ``is_verified`` ← ``channel_verified`` / ``uploader_verified`` (rare)

       When ``Downloader`` cannot extract ``uploader_id`` (empty or absent),
       the whole :class:`CreatorInfo` is set to ``None`` on
       :attr:`IngestOutcome.creator_info` (D-02: ingest succeeds with
       ``creator_id=NULL``).
       """

       platform_user_id: str
       handle: str | None
       display_name: str | None
       profile_url: str | None
       avatar_url: str | None
       follower_count: int | None
       is_verified: bool | None
   ```

4. **Modifier `IngestOutcome`** (actuellement lignes 156-174) — ajouter le champ optionnel `creator_info` à la fin, après `view_count: int | None = None`. Nouveau bloc complet :
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
       uploader, and extractors that don't expose an uploader (D-02:
       ingest succeeds with ``creator_id=NULL``).
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
   ```

**Fichier 2 : `src/vidscope/ports/__init__.py`**

1. **Ligne ~19-33** (import depuis `vidscope.ports.pipeline`) — ajouter `CreatorInfo` en ordre alphabétique entre `ChannelEntry` et `Downloader` :
   ```python
   from vidscope.ports.pipeline import (
       Analyzer,
       ChannelEntry,
       CreatorInfo,
       Downloader,
       FrameExtractor,
       IngestOutcome,
       PipelineContext,
       ProbeResult,
       ProbeStatus,
       SearchIndex,
       SearchResult,
       Stage,
       StageResult,
       Transcriber,
   )
   ```

2. **Ligne ~47-73** (`__all__`) — ajouter `"CreatorInfo"` en ordre alphabétique entre `"CreatorRepository"` et `"Downloader"`. Le `__all__` final doit contenir (ordre alphabétique existant préservé) :
   ```python
   __all__ = [
       "AnalysisRepository",
       "Analyzer",
       "ChannelEntry",
       "Clock",
       "CreatorInfo",
       "CreatorRepository",
       "Downloader",
       "FrameExtractor",
       "FrameRepository",
       "IngestOutcome",
       "MediaStorage",
       "PipelineContext",
       "PipelineRunRepository",
       "ProbeResult",
       "ProbeStatus",
       "SearchIndex",
       "SearchResult",
       "Stage",
       "StageResult",
       "Transcriber",
       "TranscriptRepository",
       "UnitOfWork",
       "UnitOfWorkFactory",
       "VideoRepository",
       "WatchAccountRepository",
       "WatchRefreshRepository",
   ]
   ```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/ports/test_pipeline_creator_info.py -x -q</automated>
</verify>

<acceptance_criteria>
- `grep -q "^from typing import Protocol, TypedDict, runtime_checkable" src/vidscope/ports/pipeline.py` exit 0
- `grep -q "^class CreatorInfo(TypedDict):" src/vidscope/ports/pipeline.py` exit 0
- `grep -q "^    platform_user_id: str$" src/vidscope/ports/pipeline.py` exit 0
- `grep -q "^    handle: str | None$" src/vidscope/ports/pipeline.py` exit 0
- `grep -q "^    display_name: str | None$" src/vidscope/ports/pipeline.py` exit 0
- `grep -q "^    profile_url: str | None$" src/vidscope/ports/pipeline.py` exit 0
- `grep -q "^    avatar_url: str | None$" src/vidscope/ports/pipeline.py` exit 0
- `grep -q "^    follower_count: int | None$" src/vidscope/ports/pipeline.py` exit 0
- `grep -q "^    is_verified: bool | None$" src/vidscope/ports/pipeline.py` exit 0
- `grep -q "creator_info: CreatorInfo | None = None" src/vidscope/ports/pipeline.py` exit 0
- `grep -q '"CreatorInfo"' src/vidscope/ports/pipeline.py` exit 0
- `grep -q '"CreatorInfo"' src/vidscope/ports/__init__.py` exit 0
- `python -m uv run python -c "from vidscope.ports import CreatorInfo, IngestOutcome; print('ok')"` sort `ok`
- `python -m uv run mypy src` exit 0 (ports restent pur Python, pas de dépendance tierce ajoutée)
- `python -m uv run lint-imports` exit 0 (9 contrats verts — `ports-are-pure` doit rester vert car `TypedDict` vient de `typing` stdlib)
</acceptance_criteria>

<done>
`CreatorInfo` TypedDict importable depuis `vidscope.ports`, `IngestOutcome.creator_info` optionnel avec défaut `None`, 9 contrats import-linter verts, mypy strict vert, test contract Plan 01 vert.
</done>
</task>

<task type="auto" tdd="true">
<name>Task 2: Tests contract CreatorInfo + IngestOutcome.creator_info</name>

<read_first>
- `src/vidscope/ports/pipeline.py` (après Task 1) — le nouveau `CreatorInfo` et `IngestOutcome.creator_info`
- `tests/unit/adapters/sqlite/test_video_repository.py` lignes 1-50 — pattern d'imports + fixtures pytest à réutiliser
- `src/vidscope/domain/values.py` — `Platform`, `PlatformId` pour construire des outcomes factices
</read_first>

<action>
**Fichier 1 : `tests/unit/ports/__init__.py`** (nouveau fichier, contenu exact) :
```python
"""Unit tests for the ports layer — Protocols and TypedDicts only."""
```

**Fichier 2 : `tests/unit/ports/test_pipeline_creator_info.py`** (nouveau fichier) :

```python
"""Contract tests for CreatorInfo TypedDict and IngestOutcome.creator_info (M006/S02-P01, D-01)."""

from __future__ import annotations

from typing import get_type_hints

from vidscope.domain import Platform, PlatformId
from vidscope.ports import CreatorInfo, IngestOutcome


class TestCreatorInfoShape:
    """CreatorInfo is the contract both adapters/ytdlp and pipeline/stages
    agree on. Its shape is not negotiable — it maps 1-for-1 to the 7
    mutable fields of domain.Creator.
    """

    def test_creator_info_has_exactly_seven_keys(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert set(hints.keys()) == {
            "platform_user_id",
            "handle",
            "display_name",
            "profile_url",
            "avatar_url",
            "follower_count",
            "is_verified",
        }, f"unexpected CreatorInfo keys: {hints.keys()}"

    def test_platform_user_id_is_required_str(self) -> None:
        hints = get_type_hints(CreatorInfo)
        # platform_user_id is the D-01 canonical UNIQUE key — must be str,
        # not optional. A creator with no stable id has creator_info=None
        # at the IngestOutcome level (D-02), not an empty CreatorInfo.
        assert hints["platform_user_id"] is str

    def test_handle_is_optional(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["handle"] == (str | None)

    def test_display_name_is_optional(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["display_name"] == (str | None)

    def test_profile_url_is_optional(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["profile_url"] == (str | None)

    def test_avatar_url_is_optional(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["avatar_url"] == (str | None)

    def test_follower_count_is_optional_int(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["follower_count"] == (int | None)

    def test_is_verified_is_optional_bool(self) -> None:
        hints = get_type_hints(CreatorInfo)
        assert hints["is_verified"] == (bool | None)

    def test_construction_with_all_fields(self) -> None:
        info: CreatorInfo = {
            "platform_user_id": "UC_abc",
            "handle": "@alice",
            "display_name": "Alice",
            "profile_url": "https://y/c/alice",
            "avatar_url": "https://y/img.jpg",
            "follower_count": 12345,
            "is_verified": True,
        }
        assert info["platform_user_id"] == "UC_abc"
        assert info["follower_count"] == 12345
        assert info["is_verified"] is True

    def test_construction_with_nullable_fields_as_none(self) -> None:
        info: CreatorInfo = {
            "platform_user_id": "UC_xyz",
            "handle": None,
            "display_name": None,
            "profile_url": None,
            "avatar_url": None,
            "follower_count": None,
            "is_verified": None,
        }
        assert info["platform_user_id"] == "UC_xyz"
        assert info["handle"] is None


class TestIngestOutcomeBackwardCompat:
    """IngestOutcome.creator_info defaults to None so existing callers
    that don't know about creators keep compiling (D-01 rétrocompat)."""

    def test_default_creator_info_is_none(self) -> None:
        outcome = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc"),
            url="https://y/watch?v=abc",
            media_path="/tmp/abc.mp4",
        )
        assert outcome.creator_info is None

    def test_creator_info_can_be_populated(self) -> None:
        outcome = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc"),
            url="https://y/watch?v=abc",
            media_path="/tmp/abc.mp4",
            creator_info={
                "platform_user_id": "UC_abc",
                "handle": "@alice",
                "display_name": "Alice",
                "profile_url": None,
                "avatar_url": None,
                "follower_count": None,
                "is_verified": None,
            },
        )
        assert outcome.creator_info is not None
        assert outcome.creator_info["platform_user_id"] == "UC_abc"
        assert outcome.creator_info["display_name"] == "Alice"

    def test_creator_info_none_keeps_other_fields_intact(self) -> None:
        """D-02 scenario: ingest succeeds without creator_info — every
        other field still populates normally."""
        outcome = IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc"),
            url="https://y/watch?v=abc",
            media_path="/tmp/abc.mp4",
            title="Hello",
            author="Unknown",
            duration=42.0,
            creator_info=None,
        )
        assert outcome.title == "Hello"
        assert outcome.author == "Unknown"
        assert outcome.creator_info is None


class TestCreatorInfoExposedInPortsPublicApi:
    """CreatorInfo must be importable from the ports public surface so
    the pipeline stage (P03) can consume it without reaching into
    vidscope.ports.pipeline."""

    def test_creator_info_importable_from_vidscope_ports(self) -> None:
        from vidscope import ports as ports_pkg

        assert hasattr(ports_pkg, "CreatorInfo")
        assert ports_pkg.CreatorInfo is CreatorInfo

    def test_creator_info_listed_in_all(self) -> None:
        from vidscope import ports as ports_pkg

        assert "CreatorInfo" in ports_pkg.__all__
```
</action>

<verify>
  <automated>python -m uv run pytest tests/unit/ports/test_pipeline_creator_info.py -x -q</automated>
</verify>

<acceptance_criteria>
- `test -f tests/unit/ports/__init__.py`
- `test -f tests/unit/ports/test_pipeline_creator_info.py`
- `python -m uv run pytest tests/unit/ports/test_pipeline_creator_info.py -x -q` exit 0
- `python -m uv run pytest tests/unit/ports/test_pipeline_creator_info.py::TestCreatorInfoShape -x -q` exit 0
- `python -m uv run pytest tests/unit/ports/test_pipeline_creator_info.py::TestIngestOutcomeBackwardCompat -x -q` exit 0
- `python -m uv run pytest tests/unit/ports/test_pipeline_creator_info.py::TestCreatorInfoExposedInPortsPublicApi -x -q` exit 0
- `python -m uv run pytest -q` exit 0 (suite complète — aucune régression)
- `python -m uv run ruff check src tests` exit 0
- `python -m uv run mypy src` exit 0
</acceptance_criteria>

<done>
14+ tests de contrat couvrent la forme de `CreatorInfo` (7 clés, types exacts), la rétrocompat de `IngestOutcome` (défaut `None`), et l'export public. Tous verts. Suite complète verte.
</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| ports → adapters/pipeline | Un TypedDict est un contrat partagé ; un adapter malveillant ou buggé pourrait produire un dict qui ne matche pas la forme déclarée |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-S02P01-01 | **Tampering (T)** — adapter renvoie un dict avec des clés manquantes ou des types erronés | `IngestOutcome.creator_info` consommé par IngestStage | LOW | accept | `TypedDict` de Python est structurel, pas runtime-checked. mypy strict attrape les mismatches à la compile-time (les plans P02 et P03 sont mypy-gated). Les tests de contrat P01-Task2 garantissent la forme. Un adapter buggé qui renverrait un dict non conforme à runtime échouerait dans `_creator_from_info` (P03) avec `KeyError` — fail-loud est la bonne sémantique pour un bug adapter. |
| T-S02P01-02 | **Information Disclosure (I)** — fuite de données d'uploader dans les logs via creator_info | N/A (ce plan ne log rien) | LOW | accept | Ce plan ne touche aucun logger. La question est reposée en P03 (WARNING log quand `uploader_id` absent inclut l'URL publique — acceptable). |
</threat_model>

<verification>
```bash
# Plan 01 spécifique
python -m uv run pytest tests/unit/ports/test_pipeline_creator_info.py -x -q

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
- `CreatorInfo` TypedDict défini dans `src/vidscope/ports/pipeline.py` avec exactement 7 clés typées
- `IngestOutcome.creator_info: CreatorInfo | None = None` (rétrocompat préservée)
- `CreatorInfo` exporté dans `vidscope.ports.__init__.__all__`
- Tests de contrat : 14+ tests verts couvrant forme, rétrocompat, export public
- 9 contrats import-linter verts (`ports-are-pure` ne régresse pas)
- mypy strict vert, ruff vert
- Suite complète pytest verte (aucune régression sur les tests existants)
</success_criteria>

<output>
À la fin du plan, créer `.gsd/milestones/M006/slices/S02/S02-P01-SUMMARY.md` résumant :
- Fichiers modifiés (`ports/pipeline.py`, `ports/__init__.py`) + nouveaux tests (`tests/unit/ports/`)
- Shape finale de `CreatorInfo` (7 champs, TypedDict)
- Confirmation rétrocompat : les 25+ usages existants de `IngestOutcome` continuent de compiler sans changement
- Handoff pour P02 (downloader peut maintenant importer `CreatorInfo` depuis `vidscope.ports`) et P03 (pipeline stage peut lire `outcome.creator_info`)
</output>
</content>
</invoke>