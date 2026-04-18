---
phase: M010
plan: S01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - src/vidscope/domain/values.py
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/ports/taxonomy_catalog.py
  - src/vidscope/ports/__init__.py
  - src/vidscope/adapters/config/__init__.py
  - src/vidscope/adapters/config/yaml_taxonomy.py
  - config/taxonomy.yaml
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/analysis_repository.py
  - src/vidscope/infrastructure/container.py
  - .importlinter
  - tests/architecture/test_layering.py
  - tests/unit/domain/test_entities.py
  - tests/unit/adapters/config/__init__.py
  - tests/unit/adapters/config/test_yaml_taxonomy.py
  - tests/unit/adapters/sqlite/test_schema.py
  - tests/unit/adapters/sqlite/test_analysis_repository.py
autonomous: true
requirements: [R053, R054, R055]
must_haves:
  truths:
    - "`Analysis` expose 9 nouveaux champs: verticals (tuple[str,...]), information_density, actionability, novelty, production_quality (float|None), sentiment (SentimentLabel|None), is_sponsored (bool|None), content_type (ContentType|None), reasoning (str|None) — tous avec defaults"
    - "Le domain reste pur: `SentimentLabel` et `ContentType` sont des `StrEnum` dans `vidscope.domain.values`; `vidscope.domain` n'importe aucun third-party"
    - "Le port `TaxonomyCatalog` (Protocol @runtime_checkable) expose `verticals() -> list[str]`, `keywords_for_vertical(slug) -> frozenset[str]`, `match(tokens) -> list[str]`"
    - "`YamlTaxonomy` charge `config/taxonomy.yaml` via `yaml.safe_load`, valide le schéma (dict, listes lowercase non vides, pas de doublon de slug) et implémente `TaxonomyCatalog`"
    - "`config/taxonomy.yaml` contient ≥12 verticales et ≥200 keywords au total, tous lowercase ASCII, sans doublon"
    - "`init_db` appelle `_ensure_analysis_v2_columns` (migration 009 additive): les 9 colonnes nullable sont ajoutées à la table `analyses` via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, idempotent"
    - "`AnalysisRepositorySQLite.add` sérialise les 9 nouveaux champs; `_row_to_analysis` lit défensivement (sentiment/content_type `None` si DB=NULL, pas de `ValueError`)"
    - "Le Container expose `taxonomy_catalog: TaxonomyCatalog` instancié via `YamlTaxonomy(Path('config/taxonomy.yaml'))`"
    - "Nouveau contrat import-linter `config-adapter-is-self-contained` présent dans `.importlinter` ET dans `EXPECTED_CONTRACTS` de `tests/architecture/test_layering.py` — `lint-imports` exit 0"
    - "PyYAML (`pyyaml>=6.0,<7`) est déclaré dans `[project.dependencies]` de `pyproject.toml`"
  artifacts:
    - path: "src/vidscope/domain/values.py"
      provides: "ContentType + SentimentLabel StrEnum"
      contains: "class ContentType"
    - path: "src/vidscope/domain/entities.py"
      provides: "Analysis étendu avec 9 nouveaux champs"
      contains: "reasoning: str | None"
    - path: "src/vidscope/ports/taxonomy_catalog.py"
      provides: "TaxonomyCatalog Protocol (stdlib-only)"
      contains: "class TaxonomyCatalog"
    - path: "src/vidscope/adapters/config/yaml_taxonomy.py"
      provides: "YamlTaxonomy adapter implémentant TaxonomyCatalog"
      contains: "class YamlTaxonomy"
    - path: "config/taxonomy.yaml"
      provides: "Catalogue de 12+ verticales avec 200+ keywords"
      contains: "tech:"
    - path: "src/vidscope/adapters/sqlite/schema.py"
      provides: "Migration 009 additive (_ensure_analysis_v2_columns)"
      contains: "_ensure_analysis_v2_columns"
    - path: ".importlinter"
      provides: "Contrat config-adapter-is-self-contained"
      contains: "config-adapter-is-self-contained"
  key_links:
    - from: "src/vidscope/infrastructure/container.py"
      to: "YamlTaxonomy"
      via: "from vidscope.adapters.config import YamlTaxonomy + instanciation dans build_container"
      pattern: "YamlTaxonomy\\("
    - from: "src/vidscope/adapters/sqlite/schema.py"
      to: "_ensure_analysis_v2_columns"
      via: "Appel depuis init_db() (après _ensure_video_stats_indexes)"
      pattern: "_ensure_analysis_v2_columns"
    - from: "src/vidscope/adapters/sqlite/analysis_repository.py"
      to: "Analysis (domain)"
      via: "_analysis_to_row / _row_to_analysis étendus"
      pattern: "reasoning"
    - from: "tests/architecture/test_layering.py"
      to: ".importlinter"
      via: "EXPECTED_CONTRACTS tuple contient 'config adapter does not import other adapters'"
      pattern: "config adapter"
---

<objective>
S01 livre le socle M010 : value objects (`ContentType`, `SentimentLabel`), extension additive de `Analysis` (9 nouveaux champs), port `TaxonomyCatalog`, adapter `YamlTaxonomy` lisant `config/taxonomy.yaml` (12 verticales, 200+ keywords), migration SQLite additive (9 colonnes nullable sur `analyses`), extension du repository, nouveau contrat import-linter `config-adapter-is-self-contained`, wiring du Container.

Purpose: Sans ce socle, S02/S03/S04 ne peuvent rien écrire ni lire — c'est la fondation qui rend la suite possible. La migration est additive (D032): rien n'est détruit, les analyses pré-M010 restent valides.
Output: Domain entities étendues + port/adapter taxonomy + schéma SQLite migré + Container wiré + 10e contrat import-linter vert.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M010/M010-ROADMAP.md
@.gsd/milestones/M010/M010-RESEARCH.md
@.gsd/milestones/M010/M010-VALIDATION.md
@.gsd/KNOWLEDGE.md
@.gsd/DECISIONS.md
@src/vidscope/domain/values.py
@src/vidscope/domain/entities.py
@src/vidscope/domain/__init__.py
@src/vidscope/ports/__init__.py
@src/vidscope/ports/repositories.py
@src/vidscope/adapters/sqlite/schema.py
@src/vidscope/adapters/sqlite/analysis_repository.py
@src/vidscope/adapters/sqlite/unit_of_work.py
@src/vidscope/infrastructure/container.py
@.importlinter
@tests/architecture/test_layering.py
@pyproject.toml

<interfaces>
Patterns et signatures existants DÉJÀ VÉRIFIÉS dans le codebase :

**StrEnum pattern (domain/values.py)** :
```python
from enum import StrEnum

class Platform(StrEnum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
```

**Dataclass pattern (domain/entities.py — Analysis actuel)** :
```python
@dataclass(frozen=True, slots=True)
class Analysis:
    video_id: VideoId
    provider: str
    language: Language
    keywords: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    score: float | None = None
    summary: str | None = None
    id: int | None = None
    created_at: datetime | None = None

    def has_summary(self) -> bool:
        return self.summary is not None and bool(self.summary.strip())
```

**Migration additive pattern (M009 — schema.py)** :
```python
def _ensure_video_stats_table(conn: Connection) -> None:
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }
    if "video_stats" in existing:
        return
    conn.execute(text("""CREATE TABLE video_stats (...)"""))

def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_video_stats_table(conn)
        _ensure_video_stats_indexes(conn)
```

**Repository pattern (analysis_repository.py actuel)** — `_analysis_to_row` et `_row_to_analysis` séparent domain/SQL :
```python
def _analysis_to_row(analysis: Analysis) -> dict[str, Any]:
    return {
        "video_id": int(analysis.video_id),
        "provider": analysis.provider,
        "language": analysis.language.value,
        "keywords": list(analysis.keywords),
        "topics": list(analysis.topics),
        "score": analysis.score,
        "summary": analysis.summary,
        "created_at": analysis.created_at or datetime.now(UTC),
    }
```

**Port Protocol pattern (ports/repositories.py)** :
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class VideoRepository(Protocol):
    def get(self, video_id: VideoId) -> Video | None: ...
```

**Import-linter contract pattern existant (`.importlinter`)** :
```ini
[importlinter:contract:llm-never-imports-other-adapters]
name = llm adapter does not import other adapters
type = forbidden
source_modules =
    vidscope.adapters.llm
forbidden_modules =
    vidscope.adapters.sqlite
    vidscope.adapters.fs
    ...
```

**Container pattern (infrastructure/container.py)** — dataclass frozen+slots, fields ajoutés, `build_container` instancie :
```python
@dataclass(frozen=True, slots=True)
class Container:
    config: Config
    engine: Engine
    media_storage: MediaStorage
    ...
    stats_probe: StatsProbe
    stats_stage: StatsStage
    pipeline_runner: PipelineRunner
    clock: Clock = field(default_factory=SystemClock)
```

**EXPECTED_CONTRACTS (tests/architecture/test_layering.py)** — actuellement 8 contrats :
```python
EXPECTED_CONTRACTS = (
    "Hexagonal layering - inward-only",
    "sqlite adapter does not import fs adapter",
    "fs adapter does not import sqlite adapter",
    "Domain is pure Python - no third-party runtime deps",
    "Ports are pure Python - no third-party runtime deps",
    "Pipeline layer depends only on ports and domain",
    "Application layer depends only on ports and domain",
    "MCP interface layer depends only on application and infrastructure",
)
```
NOTE: le contrat `llm-never-imports-other-adapters` existe dans `.importlinter` mais n'apparaît PAS dans EXPECTED_CONTRACTS — documenter si on l'ajoute en même temps, mais ce n'est PAS un objectif de S01.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Value objects domain + extension Analysis + PyYAML en dep directe</name>
  <files>pyproject.toml, src/vidscope/domain/values.py, src/vidscope/domain/entities.py, src/vidscope/domain/__init__.py, tests/unit/domain/test_entities.py</files>
  <read_first>
    - src/vidscope/domain/values.py (pattern StrEnum : `Platform`, `Language`, `StageName`, `RunStatus` — placement, __all__, docstring)
    - src/vidscope/domain/entities.py (pattern frozen+slots dataclass, Analysis actuel en lignes 119-134 à étendre)
    - src/vidscope/domain/__init__.py (re-exports et __all__)
    - pyproject.toml (bloc [project.dependencies] où ajouter pyyaml)
    - tests/unit/adapters/heuristic/test_analyzer.py (pattern test qui instancie Analysis avec ses champs)
    - .gsd/milestones/M010/M010-RESEARCH.md (section "Pattern S01 : Extension additive d'entité domain" + "Pitfall 1 : frozen+slots avec valeurs par défaut")
  </read_first>
  <behavior>
    - Test 1: `ContentType` est un `StrEnum` avec au moins les membres suivants (valeurs lowercase): `TUTORIAL = "tutorial"`, `REVIEW = "review"`, `VLOG = "vlog"`, `NEWS = "news"`, `STORY = "story"`, `OPINION = "opinion"`, `COMEDY = "comedy"`, `EDUCATIONAL = "educational"`, `PROMO = "promo"`, `UNKNOWN = "unknown"`.
    - Test 2: `SentimentLabel` est un `StrEnum` avec exactement: `POSITIVE = "positive"`, `NEGATIVE = "negative"`, `NEUTRAL = "neutral"`, `MIXED = "mixed"`.
    - Test 3: `Analysis(video_id=VideoId(1), provider="heuristic", language=Language.ENGLISH)` construit un objet valide (tous les nouveaux champs ont des defaults).
    - Test 4: `Analysis` étendu expose EXACTEMENT ces nouveaux champs avec ces defaults: `verticals: tuple[str,...] = ()`, `information_density: float|None = None`, `actionability: float|None = None`, `novelty: float|None = None`, `production_quality: float|None = None`, `sentiment: SentimentLabel|None = None`, `is_sponsored: bool|None = None`, `content_type: ContentType|None = None`, `reasoning: str|None = None`.
    - Test 5: `Analysis` reste `frozen=True, slots=True` — assignation post-construction lève `FrozenInstanceError`, pas de `__dict__`.
    - Test 6: `Analysis(...)` accepte et retient correctement des valeurs non-défaut pour chaque nouveau champ.
    - Test 7: `Analysis.has_summary()` (méthode existante) continue de fonctionner — pas de régression.
    - Test 8: Les imports fonctionnent: `from vidscope.domain import Analysis, ContentType, SentimentLabel` sans erreur.
    - Test 9: `yaml` peut être importé (vérifie que `pyyaml` est installé): `import yaml; yaml.__version__` ne lève pas ImportError.
  </behavior>
  <action>
Étape 1 — Lire `src/vidscope/domain/values.py` puis ajouter 2 nouveaux StrEnum JUSTE avant le `class Language` existant (pour regrouper avec les autres enums). Valeurs EXACTES :

```python
class ContentType(StrEnum):
    """Structural content type of a short-form video.

    Assigned by the analyzer layer (M010). UNKNOWN is a legitimate
    default — callers must not treat ``None`` and UNKNOWN as the same:
    ``None`` = pre-M010 analysis, ``UNKNOWN`` = M010 analyzer could not
    decide between the typed options.
    """

    TUTORIAL = "tutorial"
    REVIEW = "review"
    VLOG = "vlog"
    NEWS = "news"
    STORY = "story"
    OPINION = "opinion"
    COMEDY = "comedy"
    EDUCATIONAL = "educational"
    PROMO = "promo"
    UNKNOWN = "unknown"


class SentimentLabel(StrEnum):
    """Whole-video sentiment label (not per-sentence — explicitly out of
    scope per M010 ROADMAP).
    """

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"
```

Mettre à jour le `__all__` du module (AJOUTER `"ContentType"` et `"SentimentLabel"` triés alphabétiquement) :
```python
__all__ = [
    "ContentType",
    "Language",
    "Platform",
    "PlatformId",
    "RunStatus",
    "SentimentLabel",
    "StageName",
    "VideoId",
]
```

Étape 2 — Étendre `src/vidscope/domain/entities.py` :

(a) Importer les nouveaux enums en haut du fichier (ligne ~24-31 dans l'import existant) :
```python
from vidscope.domain.values import (
    ContentType,
    Language,
    Platform,
    PlatformId,
    RunStatus,
    SentimentLabel,
    StageName,
    VideoId,
)
```

(b) Remplacer intégralement la classe `Analysis` (lignes 119-134 actuelles) par :
```python
@dataclass(frozen=True, slots=True)
class Analysis:
    """Qualitative analysis produced by an analyzer provider.

    M010 extension: adds a score vector (5 dimensions), sentiment label,
    sponsor flag, structural content type, controlled-vocabulary verticals,
    and a natural-language reasoning field. All new fields default to
    ``None`` / ``()`` so analyses produced before M010 remain valid (D032
    additive migration).
    """

    video_id: VideoId
    provider: str
    language: Language
    keywords: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()            # freeform, preserved for compat (M001-M009)
    score: float | None = None              # overall score preserved (D032)
    summary: str | None = None
    # --- M010 additive fields (R053, R054, R055) ---
    verticals: tuple[str, ...] = ()                  # R054 controlled taxonomy slugs
    information_density: float | None = None         # R053 score vector — [0, 100]
    actionability: float | None = None               # R053 score vector — [0, 100]
    novelty: float | None = None                     # R053 score vector — [0, 100]
    production_quality: float | None = None          # R053 score vector — [0, 100]
    sentiment: SentimentLabel | None = None          # R053 sentiment label
    is_sponsored: bool | None = None                 # R053 sponsor flag (None = unknown)
    content_type: ContentType | None = None          # R053 structural content type
    reasoning: str | None = None                     # R055 2-3 sentence explanation
    id: int | None = None
    created_at: datetime | None = None

    def has_summary(self) -> bool:
        return self.summary is not None and bool(self.summary.strip())
```

**CRITIQUE (Pitfall 1 de RESEARCH.md)** : l'ordre des champs DOIT être: d'abord les champs hérités (M001→M009) non-défaut (`video_id`, `provider`, `language`) puis les champs avec defaults, puis les nouveaux champs M010 (tous avec defaults), puis `id` et `created_at`. Comme tous les nouveaux champs ont un default et viennent AVANT `id`/`created_at` (qui ont aussi des defaults), Python accepte la construction. Ne JAMAIS placer un nouveau champ sans default ailleurs.

Étape 3 — Étendre `src/vidscope/domain/__init__.py` pour re-exporter les nouveaux enums :

Ajouter `ContentType` et `SentimentLabel` dans l'import depuis `values` et dans `__all__` :
```python
from vidscope.domain.values import (
    ContentType,
    Language,
    Platform,
    PlatformId,
    RunStatus,
    SentimentLabel,
    StageName,
    VideoId,
)
```
Dans `__all__`, ajouter `"ContentType"` et `"SentimentLabel"` dans la section "# values" (tri alphabétique).

Étape 4 — Ajouter `pyyaml` dans `pyproject.toml` > `[project.dependencies]`. Emplacement exact : entre `"platformdirs>=4.9,<5"` et `"rich>=14.0,<15"` pour garder l'ordre alphabétique. Ligne à ajouter :
```toml
    "pyyaml>=6.0,<7",
```
Le bloc final ressemble à :
```toml
dependencies = [
    "faster-whisper>=1.2,<2",
    "httpx>=0.28,<1",
    "mcp>=1.27,<2",
    "platformdirs>=4.9,<5",
    "pyyaml>=6.0,<7",
    "rich>=14.0,<15",
    "sqlalchemy>=2.0,<3",
    "typer>=0.20,<1",
    "yt-dlp>=2026.3",
]
```

Puis exécuter `uv sync` pour matérialiser la dépendance.

Étape 5 — Étendre `tests/unit/domain/test_entities.py` :

Si le fichier existe, AJOUTER les tests ci-dessous en fin de fichier. Si absent, créer le fichier avec le squelette complet. Tests requis :
```python
"""Unit tests for domain entities — M010 extension of Analysis."""

from __future__ import annotations

import dataclasses

import pytest

from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    SentimentLabel,
    VideoId,
)


class TestAnalysisM010Extension:
    def test_construct_with_all_defaults(self) -> None:
        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
        )
        assert a.verticals == ()
        assert a.information_density is None
        assert a.actionability is None
        assert a.novelty is None
        assert a.production_quality is None
        assert a.sentiment is None
        assert a.is_sponsored is None
        assert a.content_type is None
        assert a.reasoning is None

    def test_construct_with_all_m010_fields(self) -> None:
        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
            verticals=("tech", "ai"),
            information_density=72.5,
            actionability=80.0,
            novelty=40.0,
            production_quality=65.0,
            sentiment=SentimentLabel.POSITIVE,
            is_sponsored=False,
            content_type=ContentType.TUTORIAL,
            reasoning="Clear step-by-step tutorial with concrete examples.",
        )
        assert a.verticals == ("tech", "ai")
        assert a.information_density == 72.5
        assert a.sentiment is SentimentLabel.POSITIVE
        assert a.content_type is ContentType.TUTORIAL
        assert a.is_sponsored is False  # explicitly False != None
        assert "step-by-step" in (a.reasoning or "")

    def test_frozen_prevents_mutation(self) -> None:
        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.reasoning = "nope"  # type: ignore[misc]

    def test_slots_prevents_new_attributes(self) -> None:
        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
        )
        # slots=True means no __dict__; attempting to set a
        # non-declared attribute raises AttributeError.
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            a.bogus_field = "x"  # type: ignore[attr-defined]

    def test_has_summary_still_works(self) -> None:
        a = Analysis(
            video_id=VideoId(1),
            provider="heuristic",
            language=Language.ENGLISH,
            summary="something",
        )
        assert a.has_summary() is True

    def test_is_sponsored_none_vs_false_distinct(self) -> None:
        unknown = Analysis(
            video_id=VideoId(1), provider="heuristic", language=Language.ENGLISH,
        )
        explicit_false = Analysis(
            video_id=VideoId(1), provider="heuristic",
            language=Language.ENGLISH, is_sponsored=False,
        )
        assert unknown.is_sponsored is None
        assert explicit_false.is_sponsored is False
        assert unknown.is_sponsored != explicit_false.is_sponsored


class TestContentTypeEnum:
    def test_contains_expected_members(self) -> None:
        expected_values = {
            "tutorial", "review", "vlog", "news", "story",
            "opinion", "comedy", "educational", "promo", "unknown",
        }
        assert expected_values.issubset({c.value for c in ContentType})

    def test_is_strenum_serialises_to_str(self) -> None:
        # StrEnum: value equals its string form
        assert str(ContentType.TUTORIAL) == "tutorial"
        assert ContentType.TUTORIAL == "tutorial"  # StrEnum equality

    def test_construction_from_string(self) -> None:
        assert ContentType("tutorial") is ContentType.TUTORIAL


class TestSentimentLabelEnum:
    def test_contains_exactly_four_labels(self) -> None:
        assert {s.value for s in SentimentLabel} == {
            "positive", "negative", "neutral", "mixed",
        }

    def test_invalid_label_raises(self) -> None:
        with pytest.raises(ValueError):
            SentimentLabel("joyful")


class TestPyyamlAvailable:
    """Ensure pyyaml is a direct dependency (not just transitive)."""

    def test_yaml_importable(self) -> None:
        import yaml  # noqa: PLC0415
        assert hasattr(yaml, "safe_load")
```

Étape 6 — Exécuter :
```
uv sync
uv run pytest tests/unit/domain/ -x -q
uv run lint-imports
```

NE PAS importer `yaml` dans `vidscope.domain.*` ou `vidscope.ports.*` (contrats `domain-is-pure`, `ports-are-pure`). `yaml` est réservé à `vidscope.adapters.config.*`.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/domain/ -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class ContentType" src/vidscope/domain/values.py` matches
    - `grep -n "class SentimentLabel" src/vidscope/domain/values.py` matches
    - `grep -n "TUTORIAL = \"tutorial\"" src/vidscope/domain/values.py` matches
    - `grep -n "POSITIVE = \"positive\"" src/vidscope/domain/values.py` matches
    - `grep -n "reasoning: str | None" src/vidscope/domain/entities.py` matches
    - `grep -n "information_density: float | None" src/vidscope/domain/entities.py` matches
    - `grep -n "is_sponsored: bool | None" src/vidscope/domain/entities.py` matches
    - `grep -n "content_type: ContentType | None" src/vidscope/domain/entities.py` matches
    - `grep -n "sentiment: SentimentLabel | None" src/vidscope/domain/entities.py` matches
    - `grep -n "verticals: tuple\\[str, \\.\\.\\.\\]" src/vidscope/domain/entities.py` matches
    - `grep -n '"ContentType"' src/vidscope/domain/__init__.py` matches
    - `grep -n '"SentimentLabel"' src/vidscope/domain/__init__.py` matches
    - `grep -n "pyyaml>=6.0,<7" pyproject.toml` matches
    - `uv run pytest tests/unit/domain/ -x -q` exits 0
    - `uv run lint-imports` exits 0 (domain-is-pure ET ports-are-pure toujours verts — personne n'importe yaml)
  </acceptance_criteria>
  <done>
    - ContentType + SentimentLabel StrEnum dans domain/values.py
    - Analysis étendue avec 9 nouveaux champs nullable (defaults corrects)
    - pyyaml déclaré en dep directe
    - 10+ tests domain verts
    - domain-is-pure et ports-are-pure toujours KEPT
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Port TaxonomyCatalog + adapter YamlTaxonomy + config/taxonomy.yaml + nouveau contrat import-linter</name>
  <files>src/vidscope/ports/taxonomy_catalog.py, src/vidscope/ports/__init__.py, src/vidscope/adapters/config/__init__.py, src/vidscope/adapters/config/yaml_taxonomy.py, config/taxonomy.yaml, .importlinter, tests/architecture/test_layering.py, tests/unit/adapters/config/__init__.py, tests/unit/adapters/config/test_yaml_taxonomy.py</files>
  <read_first>
    - src/vidscope/ports/repositories.py (pattern Protocol @runtime_checkable, imports stdlib only)
    - src/vidscope/ports/__init__.py (pattern re-export + __all__)
    - src/vidscope/ports/stats_probe.py (exemple de port standalone simple livré en M009)
    - .importlinter (pattern `llm-never-imports-other-adapters` pour dupliquer la structure — le nouveau contrat doit lister les MÊMES modules interdits sauf `vidscope.adapters.config`)
    - tests/architecture/test_layering.py (EXPECTED_CONTRACTS tuple — où ajouter le nouveau nom de contrat)
    - .gsd/milestones/M010/M010-RESEARCH.md (Pattern S01 : Port TaxonomyCatalog + contrat config-adapter-is-self-contained + Pitfall 6)
    - .gsd/milestones/M010/M010-VALIDATION.md (M010-ARCH : 10 contrats verts attendus)
  </read_first>
  <behavior>
    - Test 1: `from vidscope.ports import TaxonomyCatalog` fonctionne (re-export depuis `ports/__init__.py`).
    - Test 2: `TaxonomyCatalog` est un `Protocol` décoré `@runtime_checkable` — `isinstance(yaml_instance, TaxonomyCatalog)` retourne True.
    - Test 3: `YamlTaxonomy(path)` avec un YAML valide charge les verticales et expose `.verticals()`, `.keywords_for_vertical(slug)`, `.match(tokens)`.
    - Test 4: `YamlTaxonomy.verticals()` retourne la liste des slugs triée alphabétiquement (déterministe).
    - Test 5: `YamlTaxonomy.keywords_for_vertical("tech")` retourne un `frozenset[str]` non vide pour un slug connu, `frozenset()` pour un slug inconnu (pas de KeyError).
    - Test 6: `YamlTaxonomy.match(tokens)` retourne une liste de slugs triée par nombre de matches décroissant, puis alphabétiquement pour les ties (déterministe, pas dépendant de l'ordre des tokens).
    - Test 7: YAML malformé (non-dict, liste vide pour une vertical, keyword non-string, slug dupliqué en YAML malformé) → `ValueError` au chargement (fail-fast, pas à l'usage).
    - Test 8: Le fichier `config/taxonomy.yaml` réel contient ≥12 verticales et ≥200 keywords au total, tous lowercase, sans doublon de slug.
    - Test 9: `uv run lint-imports` exit 0 avec le contrat `config-adapter-is-self-contained` présent ET KEPT.
    - Test 10: `tests/architecture/test_layering.py::EXPECTED_CONTRACTS` contient `"config adapter does not import other adapters"` ET le test passe.
  </behavior>
  <action>
Étape 1 — Créer `src/vidscope/ports/taxonomy_catalog.py` :
```python
"""Port for controlled vertical taxonomy lookup.

Stdlib only. The port stays portable: no yaml, no SQL, no HTTP. The
concrete loader lives in :mod:`vidscope.adapters.config.yaml_taxonomy`.

Usage in the analyzer layer (S02):

    verticals = taxonomy.match(tokens)

The analyzer calls :meth:`match` with tokenised transcript words and
gets back an ordered list of vertical slugs.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["TaxonomyCatalog"]


@runtime_checkable
class TaxonomyCatalog(Protocol):
    """Read-only controlled vocabulary of verticals.

    Implementations must be effectively immutable after construction —
    a running pipeline must see the same verticals between calls.
    """

    def verticals(self) -> list[str]:
        """Return all vertical slugs, sorted alphabetically.

        The returned list is safe to mutate — implementations return a
        fresh list each call.
        """
        ...

    def keywords_for_vertical(self, vertical: str) -> frozenset[str]:
        """Return every keyword registered under ``vertical``.

        Returns an empty ``frozenset`` when ``vertical`` is not a known
        slug — callers must not rely on exceptions to detect absence.
        """
        ...

    def match(self, tokens: list[str]) -> list[str]:
        """Return vertical slugs whose keywords intersect ``tokens``.

        Ordered by (match_count DESC, slug ASC) for deterministic
        output. Empty ``tokens`` returns ``[]``. Tokens are compared
        lowercase — callers do not need to pre-lower.
        """
        ...
```

Étape 2 — Étendre `src/vidscope/ports/__init__.py` :
Ajouter l'import :
```python
from vidscope.ports.taxonomy_catalog import TaxonomyCatalog
```
Ajouter `"TaxonomyCatalog"` dans `__all__` (tri alphabétique, après `"StatsProbe"` et avant `"Transcriber"`).

Étape 3 — Créer le répertoire `src/vidscope/adapters/config/` et le fichier `__init__.py` :

```python
"""Configuration-file adapters.

Isolates the "I read a YAML config file and expose it as a port" work
from every other adapter category. Governed by the
``config-adapter-is-self-contained`` import-linter contract.
"""

from __future__ import annotations

from vidscope.adapters.config.yaml_taxonomy import YamlTaxonomy

__all__ = ["YamlTaxonomy"]
```

Étape 4 — Créer `src/vidscope/adapters/config/yaml_taxonomy.py` :

```python
"""YAML-backed :class:`TaxonomyCatalog` implementation.

Loads ``config/taxonomy.yaml`` once at construction time, validates the
schema (dict of slug → list[lowercase str]), and exposes the
:class:`TaxonomyCatalog` port. Zero I/O after construction.

The loader is strict on the YAML shape so a typo in taxonomy.yaml fails
the container build — no silent "your vertical is broken" at runtime.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from vidscope.ports.taxonomy_catalog import TaxonomyCatalog

__all__ = ["YamlTaxonomy"]


class YamlTaxonomy:
    """Concrete :class:`TaxonomyCatalog` reading a YAML file.

    The file must be a mapping of ``slug: list[keyword]``. Every slug
    must be a non-empty lowercase string. Every keyword must be a
    non-empty lowercase string. Empty keyword lists are rejected (a
    vertical with no keywords is useless).
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, frozenset[str]] = self._load_and_validate(path)

    # ------------------------------------------------------------------
    # TaxonomyCatalog Protocol
    # ------------------------------------------------------------------

    def verticals(self) -> list[str]:
        return sorted(self._data.keys())

    def keywords_for_vertical(self, vertical: str) -> frozenset[str]:
        return self._data.get(vertical, frozenset())

    def match(self, tokens: list[str]) -> list[str]:
        if not tokens:
            return []
        lowered = {t.lower() for t in tokens if t}
        if not lowered:
            return []
        scores: list[tuple[int, str]] = []
        for slug, keywords in self._data.items():
            hits = len(lowered & keywords)
            if hits > 0:
                scores.append((hits, slug))
        # Sort by (count DESC, slug ASC) for determinism
        scores.sort(key=lambda pair: (-pair[0], pair[1]))
        return [slug for _, slug in scores]

    # ------------------------------------------------------------------
    # Internal — validation
    # ------------------------------------------------------------------

    @staticmethod
    def _load_and_validate(path: Path) -> dict[str, frozenset[str]]:
        if not path.is_file():
            raise ValueError(f"taxonomy file not found: {path}")
        with path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        if not isinstance(raw, dict):
            raise ValueError(
                f"taxonomy.yaml must be a top-level mapping, got {type(raw).__name__}"
            )
        if not raw:
            raise ValueError("taxonomy.yaml is empty — at least one vertical required")

        result: dict[str, frozenset[str]] = {}
        for slug, keywords in raw.items():
            if not isinstance(slug, str) or not slug:
                raise ValueError(f"vertical slug must be a non-empty string, got {slug!r}")
            if slug != slug.lower() or slug != slug.strip():
                raise ValueError(f"vertical slug must be lowercase stripped, got {slug!r}")
            if not isinstance(keywords, list):
                raise ValueError(
                    f"vertical {slug!r} must map to a list of keywords, "
                    f"got {type(keywords).__name__}"
                )
            if not keywords:
                raise ValueError(f"vertical {slug!r} has an empty keyword list")
            kw_set: set[str] = set()
            for kw in keywords:
                if not isinstance(kw, str) or not kw:
                    raise ValueError(
                        f"vertical {slug!r} contains an invalid keyword: {kw!r}"
                    )
                if kw != kw.lower() or kw != kw.strip():
                    raise ValueError(
                        f"vertical {slug!r} keyword must be lowercase stripped: {kw!r}"
                    )
                kw_set.add(kw)
            result[slug] = frozenset(kw_set)
        return result
```

Étape 5 — Créer `config/taxonomy.yaml` avec **au moins 12 verticales** et **au moins 200 keywords** répartis. Toutes les valeurs lowercase ASCII. Placer le fichier à la racine du repo (pas dans src/). Contenu exact requis :

```yaml
# Controlled vertical taxonomy for M010 analyzer output.
# Each top-level key is a vertical slug; the value is the lowercase
# keyword list used by YamlTaxonomy.match(tokens).
# Edited by hand (M010 ROADMAP: no ML auto-expansion).

tech:
  - code
  - coding
  - software
  - python
  - javascript
  - typescript
  - react
  - nodejs
  - api
  - framework
  - backend
  - frontend
  - devops
  - linux
  - docker
  - kubernetes
  - git
  - github
  - programming
  - developer

ai:
  - ai
  - llm
  - gpt
  - chatgpt
  - claude
  - gemini
  - prompt
  - neural
  - machine
  - learning
  - model
  - training
  - inference
  - agent
  - embedding
  - dataset
  - openai
  - anthropic

beauty:
  - makeup
  - skincare
  - foundation
  - mascara
  - lipstick
  - serum
  - moisturizer
  - concealer
  - beauty
  - cosmetic
  - highlighter
  - blush
  - eyeliner
  - routine
  - sephora

fitness:
  - workout
  - gym
  - fitness
  - cardio
  - strength
  - muscle
  - bodybuilding
  - squat
  - deadlift
  - reps
  - sets
  - training
  - protein
  - hypertrophy
  - calisthenics
  - running
  - yoga
  - pilates

food:
  - recipe
  - cooking
  - kitchen
  - chef
  - bake
  - baking
  - pasta
  - pizza
  - dessert
  - vegan
  - vegetarian
  - breakfast
  - lunch
  - dinner
  - meal
  - ingredient
  - flavor
  - restaurant
  - snack

finance:
  - money
  - investing
  - stocks
  - crypto
  - bitcoin
  - ethereum
  - trading
  - portfolio
  - dividend
  - retirement
  - savings
  - budget
  - mortgage
  - loan
  - debt
  - etf
  - index
  - finance
  - wealth

travel:
  - travel
  - trip
  - vacation
  - flight
  - airline
  - hotel
  - airbnb
  - passport
  - visa
  - backpack
  - tourist
  - destination
  - itinerary
  - jetlag
  - beach
  - mountain
  - adventure

gaming:
  - gaming
  - gamer
  - playstation
  - xbox
  - nintendo
  - switch
  - steam
  - minecraft
  - fortnite
  - valorant
  - overwatch
  - esports
  - streamer
  - twitch
  - speedrun
  - boss
  - level

education:
  - tutorial
  - lesson
  - learn
  - learning
  - study
  - course
  - teacher
  - student
  - school
  - university
  - science
  - math
  - physics
  - chemistry
  - biology
  - history
  - knowledge

fashion:
  - fashion
  - outfit
  - style
  - wardrobe
  - dress
  - jacket
  - shoes
  - sneakers
  - accessory
  - trend
  - runway
  - brand
  - designer
  - thrift
  - aesthetic

music:
  - music
  - song
  - artist
  - album
  - track
  - guitar
  - piano
  - beat
  - producer
  - concert
  - festival
  - rapper
  - melody
  - chord
  - lyrics
  - spotify

productivity:
  - productivity
  - habit
  - routine
  - focus
  - deepwork
  - calendar
  - planning
  - notion
  - todoist
  - goal
  - discipline
  - morning
  - time
  - pomodoro
  - journaling
```

Compter les keywords : tech=20, ai=18, beauty=15, fitness=18, food=19, finance=19, travel=17, gaming=17, education=17, fashion=15, music=16, productivity=15. Total = 206 > 200. Nombre de verticales = 12 ≥ 12. Conforme aux gates R054.

Étape 6 — Ajouter le contrat dans `.importlinter`. Ajouter EN FIN DE FICHIER (après `[importlinter:contract:mcp-has-no-adapters]`) :

```ini
# ---------------------------------------------------------------------------
# The config adapter layer is self-contained: it reads config files
# and exposes ports. It must never cross-depend on other adapters
# (that would turn it into a god-adapter). Like every other adapter
# category, it only knows domain + ports.
# ---------------------------------------------------------------------------
[importlinter:contract:config-adapter-is-self-contained]
name = config adapter does not import other adapters
type = forbidden
source_modules =
    vidscope.adapters.config
forbidden_modules =
    vidscope.adapters.sqlite
    vidscope.adapters.fs
    vidscope.adapters.ytdlp
    vidscope.adapters.whisper
    vidscope.adapters.ffmpeg
    vidscope.adapters.heuristic
    vidscope.adapters.llm
    vidscope.infrastructure
    vidscope.application
    vidscope.pipeline
    vidscope.cli
    vidscope.mcp
```

Étape 7 — Étendre `EXPECTED_CONTRACTS` dans `tests/architecture/test_layering.py` pour y ajouter le nouveau nom de contrat. Modifier le tuple pour qu'il devienne :

```python
EXPECTED_CONTRACTS = (
    "Hexagonal layering - inward-only",
    "sqlite adapter does not import fs adapter",
    "fs adapter does not import sqlite adapter",
    "Domain is pure Python - no third-party runtime deps",
    "Ports are pure Python - no third-party runtime deps",
    "Pipeline layer depends only on ports and domain",
    "Application layer depends only on ports and domain",
    "MCP interface layer depends only on application and infrastructure",
    "config adapter does not import other adapters",
)
```

**Note** : le `name` du contrat tel que rendu par `lint-imports` correspond EXACTEMENT à la valeur du champ `name` de la section `[importlinter:contract:...]` — ici `config adapter does not import other adapters`.

Étape 8 — Créer `tests/unit/adapters/config/__init__.py` (fichier vide ou juste `"""Config adapter tests."""`) puis `tests/unit/adapters/config/test_yaml_taxonomy.py` :

```python
"""Unit tests for YamlTaxonomy — loader + validation + match()."""

from __future__ import annotations

from pathlib import Path

import pytest

from vidscope.adapters.config.yaml_taxonomy import YamlTaxonomy
from vidscope.ports import TaxonomyCatalog


REPO_ROOT = Path(__file__).resolve().parents[4]
REAL_TAXONOMY = REPO_ROOT / "config" / "taxonomy.yaml"


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class TestYamlTaxonomyProtocolConformance:
    def test_instance_is_taxonomy_catalog(self, tmp_path: Path) -> None:
        yaml_path = _write(tmp_path / "t.yaml", "tech:\n  - code\n  - python\n")
        t = YamlTaxonomy(yaml_path)
        assert isinstance(t, TaxonomyCatalog)


class TestYamlTaxonomyLoader:
    def test_loads_minimal_valid_file(self, tmp_path: Path) -> None:
        yaml_path = _write(
            tmp_path / "t.yaml",
            "tech:\n  - code\n  - python\nai:\n  - llm\n  - gpt\n",
        )
        t = YamlTaxonomy(yaml_path)
        assert t.verticals() == ["ai", "tech"]  # sorted alpha
        assert t.keywords_for_vertical("tech") == frozenset({"code", "python"})
        assert t.keywords_for_vertical("ai") == frozenset({"llm", "gpt"})
        assert t.keywords_for_vertical("unknown-slug") == frozenset()

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            YamlTaxonomy(tmp_path / "does-not-exist.yaml")

    def test_non_mapping_root_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "- just a list\n- of items\n")
        with pytest.raises(ValueError, match="top-level mapping"):
            YamlTaxonomy(p)

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "")
        with pytest.raises(ValueError):
            YamlTaxonomy(p)

    def test_non_list_value_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "tech: just-a-string\n")
        with pytest.raises(ValueError, match="list of keywords"):
            YamlTaxonomy(p)

    def test_empty_keyword_list_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "tech: []\n")
        with pytest.raises(ValueError, match="empty keyword list"):
            YamlTaxonomy(p)

    def test_uppercase_slug_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "Tech:\n  - code\n")
        with pytest.raises(ValueError, match="lowercase"):
            YamlTaxonomy(p)

    def test_uppercase_keyword_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "tech:\n  - Python\n")
        with pytest.raises(ValueError, match="lowercase"):
            YamlTaxonomy(p)

    def test_non_string_keyword_raises(self, tmp_path: Path) -> None:
        p = _write(tmp_path / "t.yaml", "tech:\n  - 123\n")
        with pytest.raises(ValueError, match="invalid keyword"):
            YamlTaxonomy(p)


class TestYamlTaxonomyMatch:
    def _fixture(self, tmp_path: Path) -> YamlTaxonomy:
        p = _write(
            tmp_path / "t.yaml",
            "tech:\n  - code\n  - python\n  - api\n"
            "ai:\n  - llm\n  - gpt\n  - neural\n"
            "food:\n  - recipe\n  - cooking\n",
        )
        return YamlTaxonomy(p)

    def test_match_returns_empty_on_no_tokens(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        assert t.match([]) == []
        assert t.match(["", ""]) == []

    def test_match_single_vertical(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        assert t.match(["python", "code", "hello"]) == ["tech"]

    def test_match_multiple_verticals_ordered_by_count(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        # tech gets 2 matches (python, code), ai gets 1 (gpt)
        assert t.match(["python", "code", "gpt"]) == ["tech", "ai"]

    def test_match_ties_sorted_alphabetically(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        # tech gets 1 (python), ai gets 1 (gpt) — alphabetical tie-break → ai first
        assert t.match(["python", "gpt"]) == ["ai", "tech"]

    def test_match_is_case_insensitive(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        assert t.match(["PYTHON", "Code"]) == ["tech"]

    def test_match_ignores_unknown_tokens(self, tmp_path: Path) -> None:
        t = self._fixture(tmp_path)
        assert t.match(["banana", "xyz"]) == []


class TestRealTaxonomyFile:
    """Sanity checks on the committed config/taxonomy.yaml."""

    def test_real_file_loads(self) -> None:
        assert REAL_TAXONOMY.is_file(), f"expected {REAL_TAXONOMY} to exist"
        t = YamlTaxonomy(REAL_TAXONOMY)
        verticals = t.verticals()
        assert len(verticals) >= 12, (
            f"taxonomy.yaml must have >= 12 verticals, got {len(verticals)}"
        )

    def test_real_file_has_200_plus_keywords(self) -> None:
        t = YamlTaxonomy(REAL_TAXONOMY)
        total = sum(len(t.keywords_for_vertical(v)) for v in t.verticals())
        assert total >= 200, f"taxonomy.yaml must have >= 200 keywords, got {total}"

    def test_real_file_has_no_duplicate_slug(self) -> None:
        t = YamlTaxonomy(REAL_TAXONOMY)
        assert len(t.verticals()) == len(set(t.verticals()))

    def test_match_on_real_file_is_deterministic(self) -> None:
        t = YamlTaxonomy(REAL_TAXONOMY)
        first = t.match(["python", "code", "llm"])
        second = t.match(["python", "code", "llm"])
        assert first == second
```

Étape 9 — Exécuter :
```
uv run pytest tests/unit/adapters/config/ tests/unit/domain/ -x -q
uv run lint-imports
uv run pytest -m architecture -x -q
```

NE PAS importer `yaml` depuis `vidscope.ports.taxonomy_catalog` (contrat `ports-are-pure`). NE PAS importer un autre adapter depuis `vidscope.adapters.config` (nouveau contrat `config-adapter-is-self-contained`).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/adapters/config/ tests/unit/domain/ -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class TaxonomyCatalog" src/vidscope/ports/taxonomy_catalog.py` matches
    - `grep -n "@runtime_checkable" src/vidscope/ports/taxonomy_catalog.py` matches
    - `grep -nE "^import yaml|^from yaml" src/vidscope/ports/taxonomy_catalog.py` returns exit 1 (no match — port is pure)
    - `grep -n "TaxonomyCatalog" src/vidscope/ports/__init__.py` matches (re-export)
    - `grep -n "class YamlTaxonomy" src/vidscope/adapters/config/yaml_taxonomy.py` matches
    - `grep -n "import yaml" src/vidscope/adapters/config/yaml_taxonomy.py` matches
    - `test -f config/taxonomy.yaml` exits 0 (Bash uses `[ -f ... ]` equivalent — the file exists)
    - `grep -n "^tech:" config/taxonomy.yaml` matches
    - `grep -cE "^  - " config/taxonomy.yaml` returns >= 200 (counts keyword lines)
    - `grep -c "^[a-z]*:$" config/taxonomy.yaml` returns >= 12 (counts vertical slugs — slug lines end with colon)
    - `grep -n "config-adapter-is-self-contained" .importlinter` matches
    - `grep -n "config adapter does not import other adapters" tests/architecture/test_layering.py` matches
    - `uv run pytest tests/unit/adapters/config/ -x -q` exits 0
    - `uv run lint-imports` exits 0 AND output contains `config adapter does not import other adapters KEPT`
    - `uv run pytest -m architecture -x -q` exits 0
  </acceptance_criteria>
  <done>
    - Port TaxonomyCatalog + adapter YamlTaxonomy + config/taxonomy.yaml (12 verticales, 200+ keywords)
    - Nouveau contrat import-linter `config-adapter-is-self-contained` KEPT
    - EXPECTED_CONTRACTS mis à jour — 9 contrats listés
    - 18+ tests verts (loader + match + real-file)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Migration SQLite 009 additive + AnalysisRepository étendu + Container wiré</name>
  <files>src/vidscope/adapters/sqlite/schema.py, src/vidscope/adapters/sqlite/analysis_repository.py, src/vidscope/infrastructure/container.py, tests/unit/adapters/sqlite/test_schema.py, tests/unit/adapters/sqlite/test_analysis_repository.py</files>
  <read_first>
    - src/vidscope/adapters/sqlite/schema.py (pattern `_ensure_video_stats_table` M009 et appel depuis `init_db` — lignes 241-256, 264-316)
    - src/vidscope/adapters/sqlite/analysis_repository.py (pattern `_analysis_to_row` + `_row_to_analysis` actuels — toutes les 100 lignes à étendre)
    - src/vidscope/domain/entities.py (Analysis étendu livré en Task 1)
    - src/vidscope/infrastructure/container.py (dataclass Container + build_container — où ajouter taxonomy_catalog)
    - src/vidscope/adapters/config/yaml_taxonomy.py (YamlTaxonomy livré en Task 2)
    - tests/unit/adapters/sqlite/test_schema.py (pattern existant pour test migration video_stats)
    - tests/unit/adapters/sqlite/conftest.py (fixture `engine`)
    - .gsd/milestones/M010/M010-RESEARCH.md (Pattern S01 : Migration 009 additive + Pitfall 2 : ADD COLUMN IF NOT EXISTS + Pitfall 4 : SentimentLabel NULL en DB + Pitfall 5 : analysis_topics vs JSON inline — décision retenue: JSON inline)
    - .gsd/DECISIONS.md (D020 composition root infrastructure — seul endroit qui peut importer adapters)
  </read_first>
  <behavior>
    - Test 1: `_ensure_analysis_v2_columns(conn)` est idempotent: appeler deux fois n'émet aucune erreur.
    - Test 2: Après `init_db(engine)` sur une DB fraîche, les 9 nouvelles colonnes existent sur la table `analyses` (verticals, information_density, actionability, novelty, production_quality, sentiment, is_sponsored, content_type, reasoning).
    - Test 3: Pour une DB pré-M010 (table `analyses` SANS les 9 nouvelles colonnes), `_ensure_analysis_v2_columns` les ajoute sans détruire les rows existantes.
    - Test 4: Les rows `analyses` pré-M010 (insérées avant migration) restent lisibles après migration: leurs nouveaux champs sont NULL.
    - Test 5: `AnalysisRepositorySQLite.add(analysis)` persiste les 9 nouveaux champs (verticals JSON, information_density/actionability/novelty/production_quality FLOAT, sentiment/content_type VARCHAR, is_sponsored BOOLEAN, reasoning TEXT).
    - Test 6: `AnalysisRepositorySQLite.get_latest_for_video(...)` reconstitue un `Analysis` avec les 9 nouveaux champs correctement typés (SentimentLabel/ContentType enums reconstitués depuis string).
    - Test 7: Row avec `sentiment=NULL` en DB → `Analysis.sentiment is None` (PAS de `ValueError` — Pitfall 4).
    - Test 8: Row avec `content_type=NULL` → `Analysis.content_type is None`.
    - Test 9: Row avec `sentiment='bogus'` en DB (corruption) → `Analysis.sentiment is None` (défensif, pas de crash).
    - Test 10: Row avec `verticals=NULL` en DB (pré-M010) → `Analysis.verticals == ()`.
    - Test 11: `build_container(cfg).taxonomy_catalog` retourne une instance `YamlTaxonomy` — `.verticals()` retourne ≥12 slugs.
    - Test 12: `container.taxonomy_catalog` satisfait `isinstance(container.taxonomy_catalog, TaxonomyCatalog)`.
  </behavior>
  <action>
Étape 1 — Étendre `src/vidscope/adapters/sqlite/schema.py`:

(a) Ajouter 9 nouvelles colonnes à la définition `analyses` (lignes 130-147 actuelles). La table SQLAlchemy Core gère `metadata.create_all()` pour les nouvelles DB. Les anciennes DB passent par `_ensure_analysis_v2_columns`. Modifier la Table `analyses` comme ci-dessous — conserver les colonnes existantes EXACTEMENT, AJOUTER les 9 nouvelles APRÈS `summary` et AVANT `created_at` :

```python
analyses = Table(
    "analyses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("provider", String(64), nullable=False),
    Column("language", String(16), nullable=False),
    Column("keywords", JSON, nullable=False, default=list),
    Column("topics", JSON, nullable=False, default=list),
    Column("score", Float, nullable=True),
    Column("summary", Text, nullable=True),
    # M010 additive columns (all nullable — D032 additive migration)
    Column("verticals", JSON, nullable=True),
    Column("information_density", Float, nullable=True),
    Column("actionability", Float, nullable=True),
    Column("novelty", Float, nullable=True),
    Column("production_quality", Float, nullable=True),
    Column("sentiment", String(32), nullable=True),
    Column("is_sponsored", Boolean, nullable=True),
    Column("content_type", String(64), nullable=True),
    Column("reasoning", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
)
```

(b) Ajouter la fonction de migration APRÈS `_ensure_video_stats_indexes`. Placer juste avant la ligne finale `Row = dict[str, Any]` :

```python
def _ensure_analysis_v2_columns(conn: Connection) -> None:
    """M010 additive migration: ensure ``analyses`` carries the 9 new columns.

    Inspects ``PRAGMA table_info(analyses)`` to decide which ALTERs are
    needed — SQLite's ``ADD COLUMN`` has no IF NOT EXISTS before 3.35 on
    some platforms, so we branch on the existing column set for maximum
    portability. Each ALTER adds a nullable column. Pre-M010 rows keep
    their existing values; new columns are NULL until reanalysis.

    Idempotent — safe to call on every startup.
    """
    existing_cols = {
        row[1]
        for row in conn.execute(text("PRAGMA table_info(analyses)"))
    }
    new_columns = [
        ("verticals", "JSON"),
        ("information_density", "FLOAT"),
        ("actionability", "FLOAT"),
        ("novelty", "FLOAT"),
        ("production_quality", "FLOAT"),
        ("sentiment", "VARCHAR(32)"),
        ("is_sponsored", "BOOLEAN"),
        ("content_type", "VARCHAR(64)"),
        ("reasoning", "TEXT"),
    ]
    for col_name, col_type in new_columns:
        if col_name in existing_cols:
            continue
        conn.execute(text(f"ALTER TABLE analyses ADD COLUMN {col_name} {col_type}"))
```

(c) Modifier `init_db` pour appeler la nouvelle migration. Remplacer le bloc existant :
```python
def init_db(engine: Engine) -> None:
    ...
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_video_stats_table(conn)
        _ensure_video_stats_indexes(conn)
        _ensure_analysis_v2_columns(conn)   # <-- NOUVEAU (M010)
```

(d) Ajouter `_ensure_analysis_v2_columns` à `__all__` en haut du fichier :
Modifier le tuple `__all__` existant (lignes 56-67) pour inclure `"_ensure_analysis_v2_columns"` trié — ce n'est pas obligatoire (underscore prefix) mais le test pourra le valider. Alternative simpler : laisser `__all__` tel quel et importer directement dans les tests (`from vidscope.adapters.sqlite.schema import _ensure_analysis_v2_columns`).

Étape 2 — Étendre `src/vidscope/adapters/sqlite/analysis_repository.py` — imports + `_analysis_to_row` + `_row_to_analysis` :

Remplacer l'import `from vidscope.domain import Analysis, Language, VideoId` par :
```python
from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    SentimentLabel,
    VideoId,
)
```

Remplacer `_analysis_to_row` :
```python
def _analysis_to_row(analysis: Analysis) -> dict[str, Any]:
    return {
        "video_id": int(analysis.video_id),
        "provider": analysis.provider,
        "language": analysis.language.value,
        "keywords": list(analysis.keywords),
        "topics": list(analysis.topics),
        "score": analysis.score,
        "summary": analysis.summary,
        # M010 additive
        "verticals": list(analysis.verticals) if analysis.verticals else None,
        "information_density": analysis.information_density,
        "actionability": analysis.actionability,
        "novelty": analysis.novelty,
        "production_quality": analysis.production_quality,
        "sentiment": analysis.sentiment.value if analysis.sentiment is not None else None,
        "is_sponsored": analysis.is_sponsored,
        "content_type": (
            analysis.content_type.value if analysis.content_type is not None else None
        ),
        "reasoning": analysis.reasoning,
        "created_at": analysis.created_at or datetime.now(UTC),
    }
```

Remplacer `_row_to_analysis` avec lecture défensive (Pitfall 4) :
```python
def _row_to_analysis(row: Any) -> Analysis:
    data = cast("dict[str, Any]", dict(row))

    # Defensive enum parsing — Pitfall 4: NULL or unknown value must
    # produce None, not raise.
    sentiment_raw = data.get("sentiment")
    sentiment: SentimentLabel | None = None
    if sentiment_raw:
        try:
            sentiment = SentimentLabel(str(sentiment_raw))
        except ValueError:
            sentiment = None

    content_type_raw = data.get("content_type")
    content_type: ContentType | None = None
    if content_type_raw:
        try:
            content_type = ContentType(str(content_type_raw))
        except ValueError:
            content_type = None

    verticals_raw = data.get("verticals") or ()
    if isinstance(verticals_raw, str):
        # Legacy/corrupted — treat as empty
        verticals: tuple[str, ...] = ()
    else:
        verticals = tuple(str(v) for v in verticals_raw)

    return Analysis(
        id=int(data["id"]),
        video_id=VideoId(int(data["video_id"])),
        provider=str(data["provider"]),
        language=Language(data["language"]),
        keywords=tuple(data.get("keywords") or ()),
        topics=tuple(data.get("topics") or ()),
        score=data.get("score"),
        summary=data.get("summary"),
        verticals=verticals,
        information_density=data.get("information_density"),
        actionability=data.get("actionability"),
        novelty=data.get("novelty"),
        production_quality=data.get("production_quality"),
        sentiment=sentiment,
        is_sponsored=data.get("is_sponsored"),
        content_type=content_type,
        reasoning=data.get("reasoning"),
        created_at=_ensure_utc(data.get("created_at")),
    )
```

Étape 3 — Étendre `src/vidscope/infrastructure/container.py` pour exposer `taxonomy_catalog` :

(a) Ajouter l'import en haut avec les autres adapters :
```python
from vidscope.adapters.config import YamlTaxonomy
```

(b) Ajouter l'import du port depuis `vidscope.ports` :
Modifier l'import existant pour inclure `TaxonomyCatalog`, par ex. en ajoutant :
```python
from vidscope.ports.taxonomy_catalog import TaxonomyCatalog
```
(ou via le re-export `from vidscope.ports import TaxonomyCatalog`).

(c) Ajouter `from pathlib import Path` si pas déjà importé.

(d) Ajouter le champ `taxonomy_catalog: TaxonomyCatalog` dans le dataclass `Container` — juste après `stats_probe: StatsProbe` :

```python
@dataclass(frozen=True, slots=True)
class Container:
    ...
    stats_probe: StatsProbe
    taxonomy_catalog: TaxonomyCatalog
    stats_stage: StatsStage
    pipeline_runner: PipelineRunner
    clock: Clock = field(default_factory=SystemClock)
```

(e) Dans `build_container()`, APRÈS l'instanciation du `stats_probe` et AVANT celle du `stats_stage`, instancier `YamlTaxonomy` :

```python
# M010: load the controlled vertical taxonomy from config/taxonomy.yaml
# at the repo root. The file is required — fail-fast on missing/invalid.
_taxonomy_path = Path("config") / "taxonomy.yaml"
if not _taxonomy_path.is_absolute():
    _taxonomy_path = Path.cwd() / _taxonomy_path
taxonomy_catalog: TaxonomyCatalog = YamlTaxonomy(_taxonomy_path)
```

**Alternative** : si `Config` a un champ `repo_root` ou `data_dir`, adapter. Sinon laisser en chemin relatif au cwd courant (l'installation `uv tool install` conserve le cwd). Si cela pose problème en tests, documenter que `taxonomy_catalog` peut être injecté via un futur `config.taxonomy_file` — mais pour S01, chemin relatif au cwd est acceptable.

(f) Ajouter `taxonomy_catalog=taxonomy_catalog,` dans le `return Container(...)` final (après `stats_probe=stats_probe,` et avant `stats_stage=stats_stage,`).

Étape 4 — Étendre `tests/unit/adapters/sqlite/test_schema.py` (ajouter une classe de tests à la fin) :

```python
class TestAnalysisV2Migration:
    """M010 additive migration on analyses table."""

    def test_new_columns_exist_after_init_db(self, engine: Engine) -> None:
        with engine.connect() as conn:
            cols = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(analyses)"))
            }
        expected_new = {
            "verticals",
            "information_density",
            "actionability",
            "novelty",
            "production_quality",
            "sentiment",
            "is_sponsored",
            "content_type",
            "reasoning",
        }
        missing = expected_new - cols
        assert not missing, f"missing M010 columns on analyses: {missing}"

    def test_ensure_analysis_v2_columns_is_idempotent(self, engine: Engine) -> None:
        with engine.begin() as conn:
            _ensure_analysis_v2_columns(conn)
            _ensure_analysis_v2_columns(conn)
        # no exception means idempotent

    def test_pre_m010_rows_survive_migration(self, engine: Engine) -> None:
        """Rows inserted before the M010 columns existed must stay intact."""
        from datetime import UTC, datetime

        # Insert a row using only pre-M010 columns (values for M010 columns NULL by default)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO videos (platform, platform_id, url, created_at) "
                     "VALUES (:p, :pid, :u, :c)"),
                {"p": "youtube", "pid": "legacy1", "u": "https://y.be/legacy1",
                 "c": datetime(2026, 1, 1, tzinfo=UTC)},
            )
            vid = conn.execute(text("SELECT id FROM videos WHERE platform_id='legacy1'")).scalar()
            conn.execute(
                text("INSERT INTO analyses (video_id, provider, language, keywords, topics, "
                     "score, summary, created_at) "
                     "VALUES (:v, 'heuristic', 'en', '[]', '[]', 42, 'legacy summary', :c)"),
                {"v": vid, "c": datetime(2026, 1, 1, tzinfo=UTC)},
            )
        # Re-apply migration
        with engine.begin() as conn:
            _ensure_analysis_v2_columns(conn)
        # Legacy data still there
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT score, summary, reasoning FROM analyses WHERE provider='heuristic'")
            ).mappings().first()
        assert row is not None
        assert row["score"] == 42
        assert row["summary"] == "legacy summary"
        assert row["reasoning"] is None
```

Étape 5 — Créer `tests/unit/adapters/sqlite/test_analysis_repository.py` (si absent) ou étendre :

```python
"""Unit tests for AnalysisRepositorySQLite — M010 extended fields."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.analysis_repository import AnalysisRepositorySQLite
from vidscope.adapters.sqlite.schema import analyses as analyses_table
from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    SentimentLabel,
    VideoId,
)


def _insert_video(conn, platform_id: str) -> int:
    conn.execute(
        text("INSERT INTO videos (platform, platform_id, url, created_at) "
             "VALUES (:p, :pid, :u, :c)"),
        {"p": "youtube", "pid": platform_id, "u": f"https://y.be/{platform_id}",
         "c": datetime(2026, 1, 1, tzinfo=UTC)},
    )
    return int(conn.execute(
        text("SELECT id FROM videos WHERE platform_id=:pid"),
        {"pid": platform_id},
    ).scalar())


class TestM010Persistence:
    def test_add_persists_all_m010_fields(self, engine: Engine) -> None:
        with engine.begin() as conn:
            vid = _insert_video(conn, "persist1")
            repo = AnalysisRepositorySQLite(conn)
            entity = Analysis(
                video_id=VideoId(vid),
                provider="heuristic",
                language=Language.ENGLISH,
                keywords=("code", "python"),
                topics=("code",),
                score=70.0,
                summary="Tutorial about Python",
                verticals=("tech", "ai"),
                information_density=65.0,
                actionability=80.0,
                novelty=40.0,
                production_quality=55.0,
                sentiment=SentimentLabel.POSITIVE,
                is_sponsored=False,
                content_type=ContentType.TUTORIAL,
                reasoning="Clear structured tutorial covering Python basics.",
            )
            repo.add(entity)

        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            read = repo.get_latest_for_video(VideoId(vid))
        assert read is not None
        assert read.verticals == ("tech", "ai") or set(read.verticals) == {"tech", "ai"}
        assert read.information_density == 65.0
        assert read.actionability == 80.0
        assert read.novelty == 40.0
        assert read.production_quality == 55.0
        assert read.sentiment is SentimentLabel.POSITIVE
        assert read.is_sponsored is False
        assert read.content_type is ContentType.TUTORIAL
        assert read.reasoning is not None
        assert "Python" in read.reasoning

    def test_none_values_round_trip(self, engine: Engine) -> None:
        with engine.begin() as conn:
            vid = _insert_video(conn, "none1")
            repo = AnalysisRepositorySQLite(conn)
            entity = Analysis(
                video_id=VideoId(vid),
                provider="heuristic",
                language=Language.ENGLISH,
            )
            repo.add(entity)

        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            read = repo.get_latest_for_video(VideoId(vid))
        assert read is not None
        assert read.verticals == ()
        assert read.sentiment is None
        assert read.content_type is None
        assert read.is_sponsored is None
        assert read.reasoning is None

    def test_corrupt_sentiment_value_becomes_none(self, engine: Engine) -> None:
        """Pitfall 4: unknown string in DB must not crash the reader."""
        with engine.begin() as conn:
            vid = _insert_video(conn, "corrupt1")
            conn.execute(
                text("INSERT INTO analyses (video_id, provider, language, keywords, topics, "
                     "sentiment, content_type, created_at) "
                     "VALUES (:v, 'heuristic', 'en', '[]', '[]', :s, :ct, :c)"),
                {"v": vid, "s": "joyful", "ct": "podcast",
                 "c": datetime(2026, 1, 1, tzinfo=UTC)},
            )
        with engine.connect() as conn:
            repo = AnalysisRepositorySQLite(conn)
            read = repo.get_latest_for_video(VideoId(vid))
        assert read is not None
        assert read.sentiment is None
        assert read.content_type is None


class TestContainerTaxonomyWiring:
    def test_container_exposes_taxonomy_catalog(self, tmp_path) -> None:
        """Build a container and verify taxonomy_catalog is a TaxonomyCatalog.

        Skip gracefully if the config/taxonomy.yaml is not found (should
        always exist after Task 2 — this guards against test-env oddities).
        """
        import os

        from vidscope.infrastructure.container import build_container
        from vidscope.ports import TaxonomyCatalog

        # build_container resolves the path relative to cwd
        old_cwd = os.getcwd()
        # Walk up from this test file until we find config/taxonomy.yaml
        # to anchor cwd at the repo root.
        from pathlib import Path
        repo_root = Path(__file__).resolve()
        for _ in range(6):
            if (repo_root / "config" / "taxonomy.yaml").is_file():
                break
            repo_root = repo_root.parent
        try:
            os.chdir(repo_root)
            # Use a tmp DB to avoid touching the real one
            os.environ["VIDSCOPE_DATA_DIR"] = str(tmp_path)
            container = build_container()
            try:
                assert isinstance(container.taxonomy_catalog, TaxonomyCatalog)
                verticals = container.taxonomy_catalog.verticals()
                assert len(verticals) >= 12
            finally:
                container.engine.dispose()
        finally:
            os.chdir(old_cwd)
            os.environ.pop("VIDSCOPE_DATA_DIR", None)
```

**Adaptation** : si le fixture `engine` n'a pas la signature attendue (voir `tests/unit/adapters/sqlite/conftest.py`), ajuster. Si `VIDSCOPE_DATA_DIR` n'est pas lu par `get_config()`, utiliser la stratégie de `tests/unit/application/test_refresh_stats.py` — une factory locale qui construit un `Config` à la main et appelle `build_container(cfg)` (voir test_stats_stage.py Task 1 dans M009-S02).

Étape 6 — Exécuter :
```
uv run pytest tests/unit/adapters/sqlite/test_schema.py tests/unit/adapters/sqlite/test_analysis_repository.py tests/unit/adapters/config/ -x -q
uv run lint-imports
uv run pytest -m architecture -x -q
```

NE PAS importer `yaml` depuis le module `container.py` (ce serait un détour ; `YamlTaxonomy` est l'adapter dédié). NE JAMAIS DROP une colonne dans la migration (D032 additive-only).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/adapters/sqlite/test_schema.py tests/unit/adapters/sqlite/test_analysis_repository.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "def _ensure_analysis_v2_columns" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "_ensure_analysis_v2_columns(conn)" src/vidscope/adapters/sqlite/schema.py` matches (appelé depuis init_db)
    - `grep -n "verticals" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "Column(\"reasoning\", Text, nullable=True)" src/vidscope/adapters/sqlite/schema.py` matches
    - `grep -n "SentimentLabel(str(sentiment_raw))" src/vidscope/adapters/sqlite/analysis_repository.py` matches
    - `grep -n "ContentType(str(content_type_raw))" src/vidscope/adapters/sqlite/analysis_repository.py` matches
    - `grep -n "except ValueError:" src/vidscope/adapters/sqlite/analysis_repository.py` matches (2 occurrences — sentiment + content_type defensive)
    - `grep -n "taxonomy_catalog: TaxonomyCatalog" src/vidscope/infrastructure/container.py` matches
    - `grep -n "YamlTaxonomy(" src/vidscope/infrastructure/container.py` matches
    - `grep -n "taxonomy_catalog=taxonomy_catalog" src/vidscope/infrastructure/container.py` matches
    - `uv run pytest tests/unit/adapters/sqlite/test_schema.py::TestAnalysisV2Migration -x -q` exits 0
    - `uv run pytest tests/unit/adapters/sqlite/test_analysis_repository.py -x -q` exits 0
    - `uv run lint-imports` exits 0
    - `uv run pytest -m architecture -x -q` exits 0
  </acceptance_criteria>
  <done>
    - Migration 009 additive ajoutée à `init_db` (9 colonnes nullable, idempotent)
    - AnalysisRepository persiste + relit les 9 nouveaux champs
    - Reader défensif: sentiment/content_type NULL ou invalide → None, pas de crash
    - Container expose `taxonomy_catalog` wiré sur YamlTaxonomy
    - 10+ tests schema/repo verts
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Disk → YamlTaxonomy | `config/taxonomy.yaml` lu au démarrage. Fichier sous contrôle développeur (commit git), pas d'entrée utilisateur. |
| LLM response (futur S03) → AnalysisRepository | Déjà couvert en S03 — mentionné ici pour contexte. S01 ne parse pas de LLM. |
| SQLite DB pré-M010 → `_row_to_analysis` | Données historiques, potentiellement NULL ou valeurs inattendues (ex: sentiment='bogus' après corruption). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-CONFIG-01 | Tampering | `config/taxonomy.yaml` parsing | mitigate | `yaml.safe_load` (pas `yaml.load`) — empêche l'instanciation d'objets Python arbitraires via YAML tags. Schéma strict (dict/list/str only), rejet de tout autre type au chargement. |
| T-CONFIG-02 | DoS | YAML file size | accept | Fichier sous git, ~200 lignes. Pas de risque pratique sur un fichier commit. |
| T-DATA-01 | Tampering | `_row_to_analysis` sur SentimentLabel corrompu | mitigate | Try/except `ValueError` — valeur inconnue → None (Pitfall 4). Pas de propagation d'exception vers use cases. Test `test_corrupt_sentiment_value_becomes_none`. |
| T-DATA-02 | Info Disclosure | reasoning field contient transcript snippets | accept | `reasoning` est affiché à l'utilisateur propriétaire de la vidéo via `vidscope explain` (R032 single-user local tool). Pas de fuite inter-utilisateur. |
| T-SCHEMA-01 | Availability | Migration ALTER TABLE sur DB pré-M010 | mitigate | PRAGMA table_info check avant chaque ALTER (idempotent). Test `test_ensure_analysis_v2_columns_is_idempotent` garantit l'absence de crash. Backward compat: rows pré-M010 restent valides (test `test_pre_m010_rows_survive_migration`). |
| T-ARCH-01 | Spoofing | Adapter config important un autre adapter (ex: sqlite) via transitif | mitigate | Nouveau contrat import-linter `config-adapter-is-self-contained` interdit tous les autres adapters. Test architecture check l'exécution du contrat. |
</threat_model>

<verification>
Après les 3 tâches, exécuter :
- `uv sync` (matérialise pyyaml)
- `uv run pytest tests/unit/domain/ tests/unit/adapters/config/ tests/unit/adapters/sqlite/test_schema.py tests/unit/adapters/sqlite/test_analysis_repository.py -x -q` vert
- `uv run lint-imports` vert AVEC la ligne `config adapter does not import other adapters KEPT`
- `uv run pytest -m architecture -x -q` vert (9 contrats KEPT attendus y compris le nouveau)
- `grep -n "reasoning" src/vidscope/domain/entities.py` matches
- `grep -n "config-adapter-is-self-contained" .importlinter` matches
- `config/taxonomy.yaml` existe, ≥12 verticales, ≥200 keywords
- `uv run python -c "from vidscope.infrastructure.container import build_container; c = build_container(); print(type(c.taxonomy_catalog).__name__, len(c.taxonomy_catalog.verticals()))"` imprime `YamlTaxonomy 12` (ou plus) — tournant depuis le repo root
</verification>

<success_criteria>
S01 est complet quand :
- [ ] `ContentType`, `SentimentLabel` StrEnum livrés dans `vidscope.domain.values`, re-exportés depuis `vidscope.domain`
- [ ] `Analysis` étend 9 nouveaux champs nullable, `frozen=True, slots=True` préservé, `has_summary()` intact
- [ ] `pyyaml>=6.0,<7` en dep directe dans `pyproject.toml`, `uv sync` l'installe
- [ ] `TaxonomyCatalog` Protocol (stdlib only, @runtime_checkable) livré + re-exporté depuis `vidscope.ports`
- [ ] `YamlTaxonomy` adapter livré dans `vidscope.adapters.config` avec validation stricte du schéma
- [ ] `config/taxonomy.yaml` committé : ≥12 verticales, ≥200 keywords, lowercase ASCII
- [ ] Migration SQLite `_ensure_analysis_v2_columns` idempotente, appelée depuis `init_db`
- [ ] `AnalysisRepositorySQLite` persiste + relit les 9 nouveaux champs, défensif sur enums invalides
- [ ] `Container.taxonomy_catalog: TaxonomyCatalog` wiré sur `YamlTaxonomy`
- [ ] Nouveau contrat import-linter `config-adapter-is-self-contained` KEPT
- [ ] `EXPECTED_CONTRACTS` dans `tests/architecture/test_layering.py` inclut le nouveau nom
- [ ] Suite tests unit verte (domain + adapters/config + adapters/sqlite)
- [ ] `lint-imports` vert (9 contrats KEPT)
- [ ] R053 (domain fields), R054 (taxonomy), R055 (reasoning field) tous couverts au niveau socle
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M010/M010-S01-SUMMARY.md` documentant :
- Signature finale de `Analysis` (ordre des champs, defaults)
- Contenu et format de `config/taxonomy.yaml` (12 verticales, 206 keywords)
- Migration 009 idempotente (9 colonnes nullable ajoutées à `analyses`)
- Le champ `taxonomy_catalog` du Container + pattern de résolution du chemin
- Le 9e contrat import-linter `config-adapter-is-self-contained`
- Les mécanismes défensifs de `_row_to_analysis` (Pitfall 4 résolu)
- Liste exhaustive des fichiers créés/modifiés
</output>
</content>
</invoke>