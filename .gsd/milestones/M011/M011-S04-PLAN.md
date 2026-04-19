---
phase: M011
plan: S04
type: execute
wave: 4
depends_on: [S01, S02, S03]
files_modified:
  - src/vidscope/ports/exporter.py
  - src/vidscope/ports/__init__.py
  - src/vidscope/adapters/export/__init__.py
  - src/vidscope/adapters/export/json_exporter.py
  - src/vidscope/adapters/export/markdown_exporter.py
  - src/vidscope/adapters/export/csv_exporter.py
  - src/vidscope/application/export_library.py
  - src/vidscope/infrastructure/container.py
  - src/vidscope/cli/commands/export.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - .importlinter
  - tests/architecture/test_layering.py
  - docs/export-schema.v1.md
  - tests/unit/adapters/export/__init__.py
  - tests/unit/adapters/export/test_json_exporter.py
  - tests/unit/adapters/export/test_markdown_exporter.py
  - tests/unit/adapters/export/test_csv_exporter.py
  - tests/unit/application/test_export_library.py
  - tests/unit/cli/test_export_cmd.py
autonomous: true
requirements: [R059]
must_haves:
  truths:
    - "Port `Exporter` Protocol @runtime_checkable dans `vidscope.ports.exporter` expose: `write(records: list[ExportRecord], out: Path | None = None) -> None` — stdlib only, no project-internal imports beyond domain"
    - "`ExportRecord` dataclass frozen+slots dans `vidscope.application.export_library` (DTO application, PAS domain) avec 18+ champs fidèles à D6 RESEARCH: video_id, platform, url, author, title, upload_date, score, summary, keywords, topics, verticals, actionability, content_type, status, starred, notes, tags, collections, exported_at"
    - "Nouveau sous-paquet `src/vidscope/adapters/export/` avec 3 implementations concrètes: `JsonExporter`, `MarkdownExporter`, `CsvExporter`, chacune dans son fichier"
    - "`JsonExporter.write(records, out)` produit un JSON array avec tous les champs; round-trip `json.loads(output)` restore la structure"
    - "`MarkdownExporter.write(records, out)` produit Markdown avec YAML frontmatter parseable par `yaml.safe_load` — pas de dépendance runtime `python-frontmatter` (RESEARCH D7)"
    - "`CsvExporter.write(records, out)` produit CSV parseable par stdlib `csv.DictReader`, multi-value fields joinés par `|`"
    - "`ExportLibraryUseCase` fabrique les `ExportRecord` via le UoW (videos + analyses + tracking + tags + collections), jamais importe les exporters (D6)"
    - "`ExportLibraryUseCase` accepte filter kwargs (query?, collection?, --tag?, etc) et passe via la même logique que `SearchVideosUseCase` pour déterminer les video_ids à exporter"
    - "CLI `vidscope export --format {json|markdown|csv} [--collection NAME] [--query Q] [--out PATH]` existe et enregistrée dans app.py"
    - "CLI `vidscope export --format markdown --collection MyCol --out ./out` écrit un fichier markdown (ou un répertoire si multi-files)"
    - "`--out PATH` est validé: pas de path traversal (rejeter `..` dans le segment, path absolu accepté, path relatif accepté)"
    - "Nouveau contrat import-linter `export-adapter-is-self-contained` (miroir exact de `config-adapter-is-self-contained`) listé dans `.importlinter` et dans `EXPECTED_CONTRACTS` de test_layering.py — `lint-imports` exit 0 avec KEPT"
    - "`docs/export-schema.v1.md` existe, documente la liste des champs + types pour les 3 formats + invariant v1 frozen (any breaking change = v2 additive)"
  artifacts:
    - path: "src/vidscope/ports/exporter.py"
      provides: "Exporter Protocol (stdlib only, imports Path)"
      contains: "class Exporter"
    - path: "src/vidscope/application/export_library.py"
      provides: "ExportRecord DTO + ExportLibraryUseCase"
      contains: "class ExportRecord"
    - path: "src/vidscope/adapters/export/json_exporter.py"
      provides: "JsonExporter implementation"
      contains: "class JsonExporter"
    - path: "src/vidscope/adapters/export/markdown_exporter.py"
      provides: "MarkdownExporter avec yaml.dump frontmatter"
      contains: "class MarkdownExporter"
    - path: "src/vidscope/adapters/export/csv_exporter.py"
      provides: "CsvExporter avec stdlib csv"
      contains: "class CsvExporter"
    - path: "src/vidscope/cli/commands/export.py"
      provides: "vidscope export CLI command"
      contains: "export_command"
    - path: "docs/export-schema.v1.md"
      provides: "Schema documentation v1 frozen"
      contains: "v1"
    - path: ".importlinter"
      provides: "New contract export-adapter-is-self-contained"
      contains: "export-adapter-is-self-contained"
  key_links:
    - from: "src/vidscope/application/export_library.py"
      to: "uow.videos + uow.analyses + uow.video_tracking + uow.tags + uow.collections"
      via: "Use case fetches via UoW, assembles ExportRecord list, passes to injected Exporter"
      pattern: "ExportRecord\\("
    - from: "src/vidscope/cli/commands/export.py"
      to: "JsonExporter/MarkdownExporter/CsvExporter"
      via: "Format → exporter factory dans le CLI (container or inline map)"
      pattern: "--format"
    - from: ".importlinter"
      to: "export-adapter-is-self-contained contract"
      via: "Nouvelle section [importlinter:contract:export-adapter-is-self-contained]"
      pattern: "export-adapter-is-self-contained"
    - from: "tests/architecture/test_layering.py"
      to: "EXPECTED_CONTRACTS includes new name"
      via: "tuple appended with 'export adapter does not import other adapters'"
      pattern: "export adapter does not import other adapters"
---

<objective>
S04 ferme le cycle M011 avec les exports. Livre :
1. Port `Exporter` Protocol (stdlib only, dans `vidscope.ports.exporter`).
2. DTO `ExportRecord` (application layer, D6 research — frozen schema v1).
3. 3 adapters: `JsonExporter`, `MarkdownExporter`, `CsvExporter` dans le nouveau sous-paquet `vidscope.adapters.export`.
4. Use case `ExportLibraryUseCase` qui assemble les ExportRecord via UoW puis délègue à un Exporter.
5. CLI `vidscope export --format {json|markdown|csv} [--collection] [--query] [--out]`.
6. 11e contrat import-linter `export-adapter-is-self-contained` (miroir de config-adapter).
7. `docs/export-schema.v1.md` — contrat d'export v1 frozen.

Purpose: Sortir les annotations (status, tags, collections, analyses) vers Notion/Obsidian/Airtable — l'objectif final du milestone M011. Les données ingérées depuis M001 deviennent actionnables dans n'importe quel outil externe.
Output: Protocol + 3 adapters + use case + CLI + nouveau contrat architecture + doc schema.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M011/M011-ROADMAP.md
@.gsd/milestones/M011/M011-RESEARCH.md
@.gsd/milestones/M011/M011-VALIDATION.md
@.gsd/milestones/M011/M011-S01-PLAN.md
@.gsd/milestones/M011/M011-S02-PLAN.md
@.gsd/milestones/M011/M011-S03-PLAN.md
@src/vidscope/ports/__init__.py
@src/vidscope/ports/taxonomy_catalog.py
@src/vidscope/adapters/config/__init__.py
@src/vidscope/adapters/config/yaml_taxonomy.py
@src/vidscope/application/search_videos.py
@src/vidscope/cli/app.py
@src/vidscope/cli/commands/__init__.py
@.importlinter
@tests/architecture/test_layering.py

<interfaces>
**Port Protocol pattern (taxonomy_catalog.py — M010 S01 — modèle pour exporter.py)**:
```python
from __future__ import annotations
from typing import Protocol, runtime_checkable

@runtime_checkable
class TaxonomyCatalog(Protocol):
    def verticals(self) -> list[str]: ...
    def keywords_for_vertical(self, vertical: str) -> frozenset[str]: ...
    def match(self, tokens: list[str]) -> list[str]: ...
```

**Self-contained adapter pattern (config-adapter-is-self-contained)** — à dupliquer pour export :
```ini
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

Pour export:
```ini
[importlinter:contract:export-adapter-is-self-contained]
name = export adapter does not import other adapters
type = forbidden
source_modules =
    vidscope.adapters.export
forbidden_modules =
    vidscope.adapters.sqlite
    vidscope.adapters.fs
    vidscope.adapters.config
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

**EXPECTED_CONTRACTS actuel (tests/architecture/test_layering.py)** — 9 contrats + le nouveau à ajouter:
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
    # NEW M011/S04:
    "export adapter does not import other adapters",
)
```

**ExportRecord cible (D6 RESEARCH)**:
```python
@dataclass(frozen=True, slots=True)
class ExportRecord:
    video_id: int
    platform: str
    url: str
    author: str | None
    title: str | None
    upload_date: str | None
    # Analysis
    score: float | None
    summary: str | None
    keywords: list[str]
    topics: list[str]
    verticals: list[str]
    actionability: float | None
    content_type: str | None
    # Tracking
    status: str | None       # None if no tracking row
    starred: bool
    notes: str | None
    # Tags + Collection
    tags: list[str]
    collections: list[str]
    # Metadata
    exported_at: str          # ISO 8601 UTC
```

**Markdown format (RESEARCH Code Examples)**:
```markdown
---
video_id: 1
platform: youtube
status: saved
tags: ["idea", "hook"]
collections: ["Concurrents"]
...
---
# Title or URL
Summary text here...
---
```

**CSV format**: flat DictWriter, multi-value (keywords, tags, collections, topics, verticals) joinés par `|`.

**Path validation (security)**: `--out` must not contain `..` segments. Accept absolute, accept relative. Use `Path(out).resolve()` + check that the resolved path doesn't escape cwd if relative.

**UoW usage for ExportRecord assembly**:
- `uow.videos.get(video_id)` → Video
- `uow.analyses.get_latest_for_video(video_id)` → Analysis or None
- `uow.video_tracking.get_for_video(video_id)` → VideoTracking or None
- `uow.tags.list_for_video(video_id)` → list[Tag]
- `uow.collections.list_collections_for_video(video_id)` → list[Collection]
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Port Exporter + ExportRecord DTO + 3 adapters (json/markdown/csv) + new import-linter contract + docs/export-schema.v1.md</name>
  <files>src/vidscope/ports/exporter.py, src/vidscope/ports/__init__.py, src/vidscope/application/export_library.py, src/vidscope/adapters/export/__init__.py, src/vidscope/adapters/export/json_exporter.py, src/vidscope/adapters/export/markdown_exporter.py, src/vidscope/adapters/export/csv_exporter.py, .importlinter, tests/architecture/test_layering.py, docs/export-schema.v1.md, tests/unit/adapters/export/__init__.py, tests/unit/adapters/export/test_json_exporter.py, tests/unit/adapters/export/test_markdown_exporter.py, tests/unit/adapters/export/test_csv_exporter.py</files>
  <read_first>
    - src/vidscope/ports/taxonomy_catalog.py (pattern Protocol stdlib only — modèle direct pour Exporter)
    - src/vidscope/adapters/config/yaml_taxonomy.py (pattern self-contained adapter — imports uniquement yaml + ports/taxonomy_catalog)
    - .importlinter (contrat `config-adapter-is-self-contained` — à cloner pour export)
    - tests/architecture/test_layering.py (EXPECTED_CONTRACTS tuple — ajouter le nouveau nom)
    - .gsd/milestones/M011/M011-RESEARCH.md (Pattern 8 Exporter Protocol + D6 ExportRecord + D7 python-frontmatter NOT runtime dep + Pitfall 6 self-containment)
    - .gsd/milestones/M011/M011-ROADMAP.md (ligne 13 S04 — CLI signature + Export schema contract)
  </read_first>
  <behavior>
    - Test 1: `from vidscope.ports import Exporter` fonctionne; `Exporter._is_runtime_protocol` is True.
    - Test 2: `Exporter.write(records, out=None)` est déclaré comme un Protocol method (imprime sur stdout si out is None).
    - Test 3: `ExportRecord(video_id=1, platform="youtube", url="...", author="a", title="t", upload_date="2026-01-01", ...)` construit, frozen+slots.
    - Test 4: `JsonExporter().write(records, out=tmp_path/"out.json")` produit un fichier dont `json.loads(content)` est un array de dicts; chaque dict contient tous les champs de ExportRecord.
    - Test 5: JSON round-trip: écrire 5 records puis re-parse → chaque champ est préservé (types Python natifs).
    - Test 6: `MarkdownExporter().write(records, out=tmp_path/"out.md")` produit un fichier: chaque record commence par `---\n`, suivi d'un bloc YAML parseable par `yaml.safe_load`, puis `---\n# Title\n...\n---\n`.
    - Test 7: Markdown frontmatter round-trip: extraire le YAML block, `yaml.safe_load(block)` → dict avec les champs de ExportRecord.
    - Test 8: `CsvExporter().write(records, out=tmp_path/"out.csv")` produit un CSV dont `csv.DictReader` parse 5 rows; multi-value fields (keywords/tags/collections/topics/verticals) sont joinés par `|`.
    - Test 9: Avec `out=None`, chaque exporter imprime vers stdout (via `print()` ou retourne la string via capsys capture).
    - Test 10: `uv run lint-imports` exit 0 avec `export adapter does not import other adapters KEPT`.
    - Test 11: `tests/architecture/test_layering.py::test_every_expected_contract_is_kept` exit 0 avec le nouveau nom.
    - Test 12: `docs/export-schema.v1.md` existe, contient "v1" et liste les 18+ fields.
  </behavior>
  <action>
Étape 1 — Créer `src/vidscope/ports/exporter.py` (stdlib only) :

```python
"""Port for library export adapters (M011/S04/R059).

Stdlib only. Concrete implementations live in
:mod:`vidscope.adapters.export` — JsonExporter, MarkdownExporter,
CsvExporter. The use case :class:`ExportLibraryUseCase` builds a list
of ``ExportRecord`` via the UoW and hands it off to the selected
exporter.

The port declares no YAML, no SQL, no HTTP — it only knows about
:class:`ExportRecord` (a plain dataclass in the application layer) and
an optional output :class:`Path`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    # Break a potential import cycle with vidscope.application —
    # TYPE_CHECKING defers resolution to the type checker; at runtime
    # the dataclass is forward-referenced by string only.
    from vidscope.application.export_library import ExportRecord

__all__ = ["Exporter"]


@runtime_checkable
class Exporter(Protocol):
    """Write a list of :class:`ExportRecord` to disk or stdout."""

    def write(
        self,
        records: "list[ExportRecord]",
        out: Path | None = None,
    ) -> None:
        """Serialise ``records``.

        When ``out`` is ``None``, write to stdout. When ``out`` is a
        :class:`Path`, write to the file — callers ensure the parent
        directory exists and validate the path against traversal.
        """
        ...
```

Étape 2 — Étendre `src/vidscope/ports/__init__.py` :

(a) Ajouter `from vidscope.ports.exporter import Exporter`.

(b) Ajouter `"Exporter"` dans `__all__` (tri alphabétique, avant `"FrameExtractor"`).

Étape 3 — Créer `src/vidscope/application/export_library.py` (ExportRecord DTO + use case stub pour Task 2) :

```python
"""ExportLibraryUseCase + ExportRecord DTO (M011/S04/R059).

ExportRecord is an application-layer DTO (not a domain entity — D6
M011 RESEARCH). It aggregates data from multiple aggregates (Video,
Analysis, VideoTracking, Tag, Collection) into a single projection
suited for exporting.

The use case is wired in Task 2 — this file defines the DTO and the
basic use case skeleton. Task 2 extends it with filter logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from vidscope.application.search_videos import SearchFilters
from vidscope.domain import Collection, Tag, TrackingStatus, VideoId
from vidscope.ports import Exporter, UnitOfWorkFactory

__all__ = ["ExportLibraryUseCase", "ExportRecord"]


@dataclass(frozen=True, slots=True)
class ExportRecord:
    """One exported video + all associated data. V1 frozen schema (D6).

    Field types (never breaking without a v2):
    - Scalars: int, str | None, float | None, bool.
    - Lists: list[str] (always concrete list, never None — empty list).
    """

    video_id: int
    platform: str
    url: str
    author: str | None
    title: str | None
    upload_date: str | None
    # Analysis
    score: float | None
    summary: str | None
    keywords: list[str]
    topics: list[str]
    verticals: list[str]
    actionability: float | None
    content_type: str | None
    # Tracking
    status: str | None       # None if no tracking row
    starred: bool
    notes: str | None
    # Tags + Collection
    tags: list[str]
    collections: list[str]
    # Metadata
    exported_at: str          # ISO 8601 UTC


class ExportLibraryUseCase:
    """Assemble ExportRecord list and delegate to the Exporter.

    Selection:
    - ``filters`` (optional SearchFilters) narrows the video set using
      the same intersection logic as SearchVideosUseCase (S03).
    - When filters is None or empty, every video in the library is
      exported (capped at ``limit``).
    """

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        *,
        exporter: Exporter,
        out: Path | None = None,
        filters: SearchFilters | None = None,
        limit: int = 10_000,
    ) -> int:
        """Export records and return the number written."""
        records = self._collect_records(filters=filters, limit=limit)
        exporter.write(records, out=out)
        return len(records)

    def _collect_records(
        self,
        *,
        filters: SearchFilters | None,
        limit: int,
    ) -> list[ExportRecord]:
        filters = filters or SearchFilters()
        now_iso = datetime.now(UTC).isoformat(timespec="seconds")

        with self._uow_factory() as uow:
            # Determine candidate video_ids.
            if filters.is_empty():
                videos = uow.videos.list_recent(limit=limit)
                video_ids = [v.id for v in videos if v.id is not None]
            else:
                video_ids = self._resolve_filtered_ids(uow, filters, limit=limit)

            records: list[ExportRecord] = []
            for vid in video_ids[:limit]:
                video = uow.videos.get(VideoId(int(vid)))
                if video is None:
                    continue
                analysis = uow.analyses.get_latest_for_video(VideoId(int(vid)))
                tracking = uow.video_tracking.get_for_video(VideoId(int(vid)))
                video_tags: list[Tag] = uow.tags.list_for_video(VideoId(int(vid)))
                video_colls: list[Collection] = uow.collections.list_collections_for_video(VideoId(int(vid)))

                record = ExportRecord(
                    video_id=int(video.id) if video.id else 0,
                    platform=video.platform.value,
                    url=video.url,
                    author=video.author,
                    title=video.title,
                    upload_date=video.upload_date,
                    score=analysis.score if analysis else None,
                    summary=analysis.summary if analysis else None,
                    keywords=list(analysis.keywords) if analysis else [],
                    topics=list(analysis.topics) if analysis else [],
                    verticals=list(analysis.verticals) if analysis else [],
                    actionability=analysis.actionability if analysis else None,
                    content_type=(
                        analysis.content_type.value
                        if analysis and analysis.content_type is not None
                        else None
                    ),
                    status=tracking.status.value if tracking else None,
                    starred=bool(tracking.starred) if tracking else False,
                    notes=tracking.notes if tracking else None,
                    tags=[t.name for t in video_tags],
                    collections=[c.name for c in video_colls],
                    exported_at=now_iso,
                )
                records.append(record)
        return records

    def _resolve_filtered_ids(
        self,
        uow,
        filters: SearchFilters,
        *,
        limit: int,
    ) -> list[int]:
        """Same AND intersection logic as SearchVideosUseCase (S03)."""
        sources: list[set[int]] = []

        if (
            filters.content_type is not None
            or filters.min_actionability is not None
            or filters.is_sponsored is not None
        ):
            analysis_ids = {
                int(v)
                for v in uow.analyses.list_by_filters(
                    content_type=filters.content_type,
                    min_actionability=filters.min_actionability,
                    is_sponsored=filters.is_sponsored,
                    limit=limit,
                )
            }
            sources.append(analysis_ids)

        if filters.status is not None:
            sources.append({
                int(t.video_id)
                for t in uow.video_tracking.list_by_status(filters.status, limit=limit)
            })

        excluded_starred: set[int] | None = None
        if filters.starred is True:
            sources.append({
                int(t.video_id)
                for t in uow.video_tracking.list_starred(limit=limit)
            })
        elif filters.starred is False:
            excluded_starred = {
                int(t.video_id)
                for t in uow.video_tracking.list_starred(limit=limit)
            }

        if filters.tag is not None:
            sources.append({
                int(v)
                for v in uow.tags.list_video_ids_for_tag(filters.tag, limit=limit)
            })

        if filters.collection is not None:
            sources.append({
                int(v)
                for v in uow.collections.list_video_ids_for_collection(
                    filters.collection, limit=limit,
                )
            })

        if sources:
            allowed = set.intersection(*sources) if len(sources) > 1 else sources[0]
        else:
            allowed = None

        if allowed is None:
            # Only --unstarred → start from all videos
            all_videos = uow.videos.list_recent(limit=limit)
            all_ids = {int(v.id) for v in all_videos if v.id is not None}
            allowed = all_ids

        if excluded_starred is not None:
            allowed = allowed - excluded_starred

        return sorted(allowed)
```

Étape 4 — Créer `src/vidscope/adapters/export/__init__.py` :

```python
"""Library export adapters (M011/S04/R059).

Self-contained submodule — governed by the
``export-adapter-is-self-contained`` import-linter contract. Each
exporter is a single class implementing the :class:`Exporter` port.
"""

from __future__ import annotations

from vidscope.adapters.export.csv_exporter import CsvExporter
from vidscope.adapters.export.json_exporter import JsonExporter
from vidscope.adapters.export.markdown_exporter import MarkdownExporter

__all__ = ["CsvExporter", "JsonExporter", "MarkdownExporter"]
```

Étape 5 — Créer `src/vidscope/adapters/export/json_exporter.py` :

```python
"""JSON library exporter (M011/S04/R059).

Serialises ``list[ExportRecord]`` to a JSON array of objects.
Stdlib only (json). Self-contained per the
``export-adapter-is-self-contained`` import-linter contract.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vidscope.application.export_library import ExportRecord

__all__ = ["JsonExporter"]


class JsonExporter:
    """Write export records as a pretty JSON array."""

    def write(
        self,
        records: "list[ExportRecord]",
        out: Path | None = None,
    ) -> None:
        data = [dataclasses.asdict(r) for r in records]
        content = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
        if out is None:
            sys.stdout.write(content)
            sys.stdout.write("\n")
        else:
            out.write_text(content, encoding="utf-8")
```

Étape 6 — Créer `src/vidscope/adapters/export/markdown_exporter.py` :

```python
"""Markdown library exporter (M011/S04/R059).

Each record becomes a Markdown block:

    ---
    <YAML frontmatter>
    ---
    # Title
    Summary body...
    ---

Uses ``yaml.dump`` from pyyaml (already a project dep) for the
frontmatter — D7 M011 RESEARCH: python-frontmatter is NOT a runtime
requirement. Self-contained per import-linter contract.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from vidscope.application.export_library import ExportRecord

__all__ = ["MarkdownExporter"]


class MarkdownExporter:
    """Write export records as one concatenated Markdown stream."""

    def write(
        self,
        records: "list[ExportRecord]",
        out: Path | None = None,
    ) -> None:
        lines: list[str] = []
        for rec in records:
            frontmatter = dataclasses.asdict(rec)
            lines.append("---")
            lines.append(
                yaml.dump(
                    frontmatter,
                    allow_unicode=True,
                    sort_keys=True,
                    default_flow_style=False,
                ).rstrip()
            )
            lines.append("---")
            lines.append(f"# {rec.title or rec.url}")
            if rec.summary:
                lines.append("")
                lines.append(rec.summary)
            lines.append("")
            lines.append("---")
            lines.append("")
        content = "\n".join(lines)
        if out is None:
            sys.stdout.write(content)
            sys.stdout.write("\n")
        else:
            out.write_text(content, encoding="utf-8")
```

Étape 7 — Créer `src/vidscope/adapters/export/csv_exporter.py` :

```python
"""CSV library exporter (M011/S04/R059).

Flat CSV via stdlib ``csv.DictWriter``. Multi-value fields (keywords,
topics, verticals, tags, collections) are joined by ``|``. Self-contained.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vidscope.application.export_library import ExportRecord

__all__ = ["CsvExporter"]


_MULTI_VALUE_FIELDS = ("keywords", "topics", "verticals", "tags", "collections")


class CsvExporter:
    """Write export records as a flat CSV with ``|`` multi-value separator."""

    def write(
        self,
        records: "list[ExportRecord]",
        out: Path | None = None,
    ) -> None:
        if not records:
            # Even empty export writes header (caller may expect it)
            fieldnames: list[str] = []
            if out is None:
                return
            out.write_text("", encoding="utf-8")
            return

        sample = dataclasses.asdict(records[0])
        fieldnames = list(sample.keys())

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for rec in records:
            row: dict[str, Any] = dataclasses.asdict(rec)
            for mv in _MULTI_VALUE_FIELDS:
                if isinstance(row.get(mv), list):
                    row[mv] = "|".join(str(x) for x in row[mv])
            writer.writerow(row)
        content = buf.getvalue()

        if out is None:
            sys.stdout.write(content)
        else:
            out.write_text(content, encoding="utf-8")
```

Étape 8 — Ajouter le contrat dans `.importlinter`. Ajouter EN FIN DE FICHIER :

```ini

# ---------------------------------------------------------------------------
# The export adapter is self-contained: it serializes ExportRecord lists
# to JSON / Markdown / CSV. It must not reach for other adapters or
# the application/infrastructure layers. Mirror of
# config-adapter-is-self-contained (M010/S01).
# ---------------------------------------------------------------------------
[importlinter:contract:export-adapter-is-self-contained]
name = export adapter does not import other adapters
type = forbidden
source_modules =
    vidscope.adapters.export
forbidden_modules =
    vidscope.adapters.sqlite
    vidscope.adapters.fs
    vidscope.adapters.config
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

Étape 9 — Mettre à jour `tests/architecture/test_layering.py` pour ajouter le nouveau nom dans `EXPECTED_CONTRACTS` :

Remplacer le tuple existant par :
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
    "export adapter does not import other adapters",
)
```

Étape 10 — Créer `docs/export-schema.v1.md` :

```markdown
# VidScope Export Schema v1

**Status:** FROZEN (M011/S04 R059)
**Invariant:** Any breaking change to this schema requires a v2 exporter.
v1 must remain valid indefinitely.

## Rationale

Downstream Notion / Obsidian / Airtable imports rely on stable field
names and types. Field additions may happen in v2 (additive, backward
compatible). Removals / renames / type changes break the contract.

## Field List

The v1 export schema emits one `ExportRecord` per video with these
fields:

| Field | Type | Description |
|-------|------|-------------|
| `video_id` | `int` | Stable primary key from the SQLite DB. |
| `platform` | `str` | `"instagram"`, `"tiktok"`, or `"youtube"`. |
| `url` | `str` | Original video URL. |
| `author` | `str \| null` | Channel / account handle or `null`. |
| `title` | `str \| null` | Platform title or `null`. |
| `upload_date` | `str \| null` | ISO-style `YYYYMMDD` or `null`. |
| `score` | `float \| null` | Overall analysis score `[0, 100]` or `null`. |
| `summary` | `str \| null` | Short analyzer summary or `null`. |
| `keywords` | `list[str]` | Heuristic keywords. Always a list (may be empty). |
| `topics` | `list[str]` | Freeform topics. |
| `verticals` | `list[str]` | M010 controlled-vocabulary vertical slugs. |
| `actionability` | `float \| null` | M010 actionability score `[0, 100]` or `null`. |
| `content_type` | `str \| null` | M010 `ContentType` value (e.g. `"tutorial"`) or `null`. |
| `status` | `str \| null` | M011 `TrackingStatus` value or `null` if no tracking row. |
| `starred` | `bool` | M011 starred flag. `false` when no tracking row. |
| `notes` | `str \| null` | M011 user note or `null`. |
| `tags` | `list[str]` | M011 tag names (lowercase). |
| `collections` | `list[str]` | M011 collection names (case-preserved). |
| `exported_at` | `str` | ISO 8601 UTC timestamp of the export run. |

## Per-Format Conventions

### JSON
- `list[dict]` — one object per video.
- Multi-value fields are JSON arrays.
- `null` values are preserved explicitly.

### Markdown
- YAML frontmatter (`---` delimited) per record using the same field
  names and types as JSON.
- `# Title` header after the frontmatter uses `title` or falls back to `url`.
- Record separator: blank line + `---` between entries.

### CSV
- One row per record + header row.
- Multi-value fields (`keywords`, `topics`, `verticals`, `tags`, `collections`)
  are joined with `|` (pipe).
- `null` is serialised as empty cell.
- Compatible with stdlib `csv.DictReader`.

## Stability Contract

1. Field order may change across formats and releases. Consumers must
   use field names, not positional indexes.
2. Adding a new field in the future is allowed (v1-compatible).
3. Removing, renaming, or changing the semantic of an existing field
   ships as a v2 exporter alongside v1 — never in-place.
4. CSV column names are stable; readers relying on column order are
   explicitly out of scope for this contract.
```

Étape 11 — Créer les tests dans `tests/unit/adapters/export/`.

(a) `tests/unit/adapters/export/__init__.py` : `"""Export adapter tests."""`

(b) `tests/unit/adapters/export/test_json_exporter.py` :

```python
"""JsonExporter unit tests (M011/S04/R059)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vidscope.adapters.export.json_exporter import JsonExporter
from vidscope.application.export_library import ExportRecord
from vidscope.ports import Exporter


def _fixture_records() -> list[ExportRecord]:
    return [
        ExportRecord(
            video_id=1, platform="youtube", url="https://y.be/a",
            author="creator", title="Title A", upload_date="20260101",
            score=72.0, summary="summary A",
            keywords=["code", "python"], topics=["tech"], verticals=["tech"],
            actionability=80.0, content_type="tutorial",
            status="saved", starred=True, notes="great hook",
            tags=["idea"], collections=["Concurrents"],
            exported_at="2026-04-18T10:00:00+00:00",
        ),
        ExportRecord(
            video_id=2, platform="tiktok", url="https://t.co/b",
            author=None, title=None, upload_date=None,
            score=None, summary=None,
            keywords=[], topics=[], verticals=[],
            actionability=None, content_type=None,
            status=None, starred=False, notes=None,
            tags=[], collections=[],
            exported_at="2026-04-18T10:00:00+00:00",
        ),
    ]


class TestProtocolConformance:
    def test_is_exporter(self) -> None:
        assert isinstance(JsonExporter(), Exporter)


class TestJsonExporter:
    def test_write_to_path(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        JsonExporter().write(_fixture_records(), out=out)
        content = out.read_text(encoding="utf-8")
        data = json.loads(content)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["video_id"] == 1
        assert data[0]["tags"] == ["idea"]
        assert data[0]["status"] == "saved"
        assert data[1]["status"] is None
        assert data[1]["starred"] is False

    def test_roundtrip_preserves_fields(self, tmp_path: Path) -> None:
        records = _fixture_records()
        out = tmp_path / "rt.json"
        JsonExporter().write(records, out=out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data[0]["platform"] == "youtube"
        assert data[0]["score"] == 72.0
        assert data[0]["keywords"] == ["code", "python"]
        assert data[0]["verticals"] == ["tech"]
        assert data[0]["collections"] == ["Concurrents"]

    def test_write_to_stdout(self, capsys) -> None:
        JsonExporter().write(_fixture_records(), out=None)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 2

    def test_empty_records_writes_empty_array(self, tmp_path: Path) -> None:
        out = tmp_path / "empty.json"
        JsonExporter().write([], out=out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == []
```

(c) `tests/unit/adapters/export/test_markdown_exporter.py` :

```python
"""MarkdownExporter unit tests (M011/S04/R059)."""
from __future__ import annotations

from pathlib import Path

import yaml

from vidscope.adapters.export.markdown_exporter import MarkdownExporter
from vidscope.application.export_library import ExportRecord


def _fixture() -> list[ExportRecord]:
    return [
        ExportRecord(
            video_id=1, platform="youtube", url="https://y.be/a",
            author="a", title="Title A", upload_date="20260101",
            score=72.0, summary="Summary body text.",
            keywords=["code"], topics=["tech"], verticals=["tech"],
            actionability=80.0, content_type="tutorial",
            status="saved", starred=True, notes="nope",
            tags=["idea"], collections=["MyCol"],
            exported_at="2026-04-18T10:00:00+00:00",
        ),
    ]


class TestMarkdownExporter:
    def test_writes_frontmatter_and_body(self, tmp_path: Path) -> None:
        out = tmp_path / "out.md"
        MarkdownExporter().write(_fixture(), out=out)
        content = out.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "# Title A" in content
        assert "Summary body text." in content

    def test_frontmatter_parseable_by_yaml_safe_load(self, tmp_path: Path) -> None:
        out = tmp_path / "ya.md"
        MarkdownExporter().write(_fixture(), out=out)
        content = out.read_text(encoding="utf-8")
        # Extract the first frontmatter block between --- lines
        parts = content.split("---", 2)
        # parts[0] is empty (before first ---), parts[1] is the YAML
        yaml_block = parts[1].strip()
        data = yaml.safe_load(yaml_block)
        assert data["video_id"] == 1
        assert data["status"] == "saved"
        assert data["tags"] == ["idea"]
        assert data["collections"] == ["MyCol"]

    def test_empty_records_writes_empty(self, tmp_path: Path) -> None:
        out = tmp_path / "empty.md"
        MarkdownExporter().write([], out=out)
        content = out.read_text(encoding="utf-8").strip()
        assert content == ""

    def test_writes_to_stdout(self, capsys) -> None:
        MarkdownExporter().write(_fixture(), out=None)
        captured = capsys.readouterr()
        assert "# Title A" in captured.out
```

(d) `tests/unit/adapters/export/test_csv_exporter.py` :

```python
"""CsvExporter unit tests (M011/S04/R059)."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from vidscope.adapters.export.csv_exporter import CsvExporter
from vidscope.application.export_library import ExportRecord


def _fixture() -> list[ExportRecord]:
    return [
        ExportRecord(
            video_id=1, platform="youtube", url="https://y.be/a",
            author="a", title="T", upload_date="20260101",
            score=72.0, summary="s1",
            keywords=["code", "python"], topics=["tech"], verticals=["tech", "ai"],
            actionability=80.0, content_type="tutorial",
            status="saved", starred=True, notes="n",
            tags=["idea", "reuse"], collections=["MyCol"],
            exported_at="2026-04-18T10:00:00+00:00",
        ),
        ExportRecord(
            video_id=2, platform="tiktok", url="https://t.co/b",
            author=None, title=None, upload_date=None,
            score=None, summary=None,
            keywords=[], topics=[], verticals=[],
            actionability=None, content_type=None,
            status=None, starred=False, notes=None,
            tags=[], collections=[],
            exported_at="2026-04-18T10:00:00+00:00",
        ),
    ]


class TestCsvExporter:
    def test_write_and_parse(self, tmp_path: Path) -> None:
        out = tmp_path / "out.csv"
        CsvExporter().write(_fixture(), out=out)
        content = out.read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["video_id"] == "1"
        assert rows[0]["tags"] == "idea|reuse"
        assert rows[0]["verticals"] == "tech|ai"
        assert rows[0]["status"] == "saved"
        assert rows[1]["status"] == ""  # None -> empty
        assert rows[1]["starred"] == "False"

    def test_multi_value_joined_by_pipe(self, tmp_path: Path) -> None:
        out = tmp_path / "mv.csv"
        CsvExporter().write(_fixture(), out=out)
        content = out.read_text(encoding="utf-8")
        assert "idea|reuse" in content

    def test_empty_records(self, tmp_path: Path) -> None:
        out = tmp_path / "empty.csv"
        CsvExporter().write([], out=out)
        assert out.read_text(encoding="utf-8") == ""
```

Étape 12 — Exécuter :
```
uv run pytest tests/unit/adapters/export/ -x -q
uv run lint-imports
uv run pytest -m architecture -x -q
```

Vérifier que `lint-imports` affiche bien `export adapter does not import other adapters KEPT`.

NE PAS importer depuis `vidscope.application.*`, `vidscope.adapters.sqlite.*`, ou autre adapter dans `vidscope.adapters.export.*` (sauf via `TYPE_CHECKING` pour forward-ref). NE PAS mettre `ExportRecord` dans domain (c'est un DTO application).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/adapters/export/ -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class Exporter" src/vidscope/ports/exporter.py` matches
    - `grep -n "@runtime_checkable" src/vidscope/ports/exporter.py` matches
    - `grep -n '"Exporter"' src/vidscope/ports/__init__.py` matches
    - `grep -n "class ExportRecord" src/vidscope/application/export_library.py` matches
    - `grep -n "exported_at: str" src/vidscope/application/export_library.py` matches
    - `grep -n "class JsonExporter" src/vidscope/adapters/export/json_exporter.py` matches
    - `grep -n "class MarkdownExporter" src/vidscope/adapters/export/markdown_exporter.py` matches
    - `grep -n "class CsvExporter" src/vidscope/adapters/export/csv_exporter.py` matches
    - `grep -n "import yaml" src/vidscope/adapters/export/markdown_exporter.py` matches
    - `grep -nE "from vidscope\.(application|adapters\.(sqlite|fs|config|ytdlp|whisper|ffmpeg|heuristic|llm)|infrastructure|pipeline|cli|mcp)" src/vidscope/adapters/export/json_exporter.py src/vidscope/adapters/export/markdown_exporter.py src/vidscope/adapters/export/csv_exporter.py` returns exit 1 (no match — self-contained)
    - `grep -n "export-adapter-is-self-contained" .importlinter` matches
    - `grep -n "export adapter does not import other adapters" tests/architecture/test_layering.py` matches
    - `test -f docs/export-schema.v1.md` exits 0
    - `grep -n "v1" docs/export-schema.v1.md` matches
    - `grep -n "exported_at" docs/export-schema.v1.md` matches
    - `uv run pytest tests/unit/adapters/export/ -x -q` exits 0
    - `uv run lint-imports` exits 0 AND output contains `export adapter does not import other adapters KEPT`
    - `uv run pytest -m architecture -x -q` exits 0
  </acceptance_criteria>
  <done>
    - Port Exporter Protocol livré (stdlib only)
    - ExportRecord DTO + ExportLibraryUseCase livrés (application layer)
    - 3 adapters livrés (json, markdown, csv) dans vidscope.adapters.export
    - 11e contrat import-linter ajouté + KEPT
    - EXPECTED_CONTRACTS mis à jour (10 contrats)
    - docs/export-schema.v1.md livré
    - 13+ tests exporters verts
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: CLI `vidscope export` + registration + Container factory + tests E2E use case + path traversal guard</name>
  <files>src/vidscope/cli/commands/export.py, src/vidscope/cli/commands/__init__.py, src/vidscope/cli/app.py, src/vidscope/infrastructure/container.py, tests/unit/application/test_export_library.py, tests/unit/cli/test_export_cmd.py</files>
  <read_first>
    - src/vidscope/cli/commands/search.py (pattern CLI avec Annotated options + handle_domain_errors)
    - src/vidscope/cli/commands/__init__.py (registration pattern)
    - src/vidscope/cli/app.py (registration pattern app.command)
    - src/vidscope/application/export_library.py (livré en Task 1 — use case + ExportRecord)
    - src/vidscope/adapters/export/__init__.py (livré en Task 1)
    - src/vidscope/infrastructure/container.py (si on ajoute un exporter factory au container ou on inline dans le CLI — décision: inline dans CLI pour garder le Container stable)
    - .gsd/milestones/M011/M011-ROADMAP.md (ligne 13 S04 — signature CLI `vidscope export --format json|markdown|csv [--collection NAME] [--query ...] [--out PATH]`)
    - .gsd/milestones/M011/M011-RESEARCH.md (Pitfall 6 use case fetches via UoW, pas l'exporter)
  </read_first>
  <behavior>
    - Test 1: `ExportLibraryUseCase.execute(exporter, filters=SearchFilters(), limit=100)` retourne le nombre de records écrits.
    - Test 2: Use case avec `SearchFilters(collection="MyCol")` limite l'export aux videos de cette collection.
    - Test 3: Use case avec `SearchFilters(starred=True)` limite aux videos starred.
    - Test 4: Use case récupère correctement Tag.name + Collection.name + analyse pour chaque video.
    - Test 5: Use case avec DB vide renvoie 0 records, exporter.write([], ...) appelé.
    - Test 6: CLI `vidscope export --format json --out /tmp/out.json` appelle JsonExporter avec le bon path.
    - Test 7: CLI `vidscope export --format markdown` sans `--out` écrit sur stdout.
    - Test 8: CLI `vidscope export --format csv --collection MyCol` passe un SearchFilters(collection="MyCol") au use case.
    - Test 9: CLI `vidscope export --format unknown` lève BadParameter (exit != 0).
    - Test 10: CLI `vidscope export --format json --out "../../../etc/passwd"` rejeté: path contient `..` → fail_user avec message explicite (T-PATH-M011-01).
    - Test 11: CLI avec `--out /tmp/valid/out.json` (chemin absolu sans ..) accepté même si le répertoire n'existe pas (exporter crée via write_text si parent existe, sinon FileNotFoundError — gérée par handle_domain_errors).
    - Test 12: CLI affiche un récapitulatif après export: "exported N records to <path>".
  </behavior>
  <action>
Étape 1 — Créer `src/vidscope/cli/commands/export.py` :

```python
"""`vidscope export --format {json|markdown|csv} [--collection] [--query] [--out]`

M011/S04/R059: export the library (or a filtered subset) to JSON /
Markdown / CSV. Path traversal is validated before writing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from vidscope.adapters.export import CsvExporter, JsonExporter, MarkdownExporter
from vidscope.application.export_library import ExportLibraryUseCase
from vidscope.application.search_videos import SearchFilters
from vidscope.cli._support import (
    acquire_container,
    console,
    fail_user,
    handle_domain_errors,
)
from vidscope.domain import TrackingStatus
from vidscope.ports import Exporter

__all__ = ["export_command"]


_FORMATS: dict[str, type[Exporter]] = {
    "json": JsonExporter,
    "markdown": MarkdownExporter,
    "csv": CsvExporter,
}


def _validate_out_path(raw: str | None) -> Path | None:
    """Reject path traversal (``..`` segment). Accept absolute or relative."""
    if raw is None:
        return None
    candidate = Path(raw)
    # Reject any path with a literal ".." segment (T-PATH-M011-01).
    if any(part == ".." for part in candidate.parts):
        raise fail_user(
            f"--out path {raw!r} contains a '..' segment; path traversal is refused."
        )
    return candidate


def _parse_tracking_status(raw: str | None) -> TrackingStatus | None:
    if raw is None:
        return None
    try:
        return TrackingStatus(raw.strip().lower())
    except ValueError as exc:
        valid = ", ".join(s.value for s in TrackingStatus)
        raise typer.BadParameter(
            f"--status must be one of: {valid}. Got {raw!r}."
        ) from exc


def export_command(
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="json, markdown, or csv."),
    ],
    out: Annotated[
        str | None,
        typer.Option(
            "--out", "-o",
            help="Output file path (absolute or relative). Omit for stdout.",
        ),
    ] = None,
    collection: Annotated[
        str | None,
        typer.Option("--collection", help="Export only videos in this collection."),
    ] = None,
    tag: Annotated[
        str | None,
        typer.Option("--tag", help="Export only videos with this tag."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help="Export only videos with this workflow status."),
    ] = None,
    starred: Annotated[
        bool | None,
        typer.Option(
            "--starred/--unstarred",
            help="Filter by starred flag.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=100_000,
                     help="Maximum number of records to export."),
    ] = 10_000,
) -> None:
    """Export the library (or a filtered subset) to JSON / Markdown / CSV."""
    with handle_domain_errors():
        fmt_norm = format.strip().lower()
        exporter_cls = _FORMATS.get(fmt_norm)
        if exporter_cls is None:
            valid = ", ".join(sorted(_FORMATS.keys()))
            raise typer.BadParameter(
                f"--format must be one of: {valid}. Got {format!r}."
            )

        out_path = _validate_out_path(out)

        filters = SearchFilters(
            status=_parse_tracking_status(status),
            starred=starred,
            tag=tag.lower().strip() if tag else None,
            collection=collection.strip() if collection else None,
        )

        container = acquire_container()
        use_case = ExportLibraryUseCase(
            unit_of_work_factory=container.unit_of_work,
        )
        exporter = exporter_cls()

        n = use_case.execute(
            exporter=exporter,
            out=out_path,
            filters=filters,
            limit=limit,
        )

        target = str(out_path) if out_path is not None else "<stdout>"
        console.print(
            f"[bold green]exported[/bold green] {n} record(s) "
            f"to [bold]{target}[/bold] (format={fmt_norm})"
        )
```

Étape 2 — Enregistrer `export_command` :

(a) Dans `src/vidscope/cli/commands/__init__.py`, ajouter :
```python
from vidscope.cli.commands.export import export_command
```
Et `"export_command"` dans `__all__` (tri alphabétique).

(b) Dans `src/vidscope/cli/app.py`, ajouter dans l'import :
```python
from vidscope.cli.commands import (
    ...,
    export_command,
    ...,
)
```
Et la registration (au niveau des autres `app.command(...)`):
```python
app.command(
    "export",
    help="Export the library to JSON / Markdown / CSV.",
)(export_command)
```

Étape 3 — Container : PAS de modification nécessaire — le CLI instancie `ExportLibraryUseCase` et les exporters directement (mêmes que d'autres use cases utilisent le container pour `unit_of_work`). Les 3 exporters sont des concrete class sans dépendances supplémentaires.

**MAIS attention**: le CLI (`vidscope.cli.commands.export`) importe `from vidscope.adapters.export import ...`. Ce n'est PAS interdit par le contrat `mcp-has-no-adapters` (car c'est CLI), et le contrat de layering autorise `cli -> adapters` (CLI est couche externe). Pour être sûr, vérifier dans `.importlinter` la section `layers`:
```
layers =
    vidscope.cli
    vidscope.mcp
    vidscope.application
    vidscope.pipeline
    vidscope.adapters
    vidscope.ports
    vidscope.domain
```
→ `vidscope.cli` est au-dessus de `vidscope.adapters` → import permis.

Étape 4 — Créer `tests/unit/application/test_export_library.py` :

```python
"""ExportLibraryUseCase unit tests (M011/S04/R059)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from vidscope.application.export_library import (
    ExportLibraryUseCase,
    ExportRecord,
)
from vidscope.application.search_videos import SearchFilters
from vidscope.domain import TrackingStatus


class _CaptureExporter:
    def __init__(self) -> None:
        self.records: list[ExportRecord] = []
        self.out: Path | None = None
        self.call_count = 0

    def write(self, records, out=None):
        self.records = list(records)
        self.out = out
        self.call_count += 1


@pytest.fixture
def _seeded_db(engine):
    """Seed the DB with 3 videos + analyses + tracking + tags + collections."""
    from sqlalchemy import text
    from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
    from vidscope.domain import (
        Analysis, Language, Platform, PlatformId, Video,
        VideoId, VideoTracking,
    )

    ids: list[int] = []
    with SqliteUnitOfWork(engine) as uow:
        for i in range(1, 4):
            v = uow.videos.upsert_by_platform_id(Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId(f"exp{i}"),
                url=f"https://y.be/exp{i}",
                author=f"creator{i}",
                title=f"Title {i}",
                upload_date="20260101",
            ))
            ids.append(int(v.id))
            uow.analyses.add(Analysis(
                video_id=VideoId(int(v.id)),
                provider="heuristic",
                language=Language.ENGLISH,
                keywords=(f"k{i}", "python"),
                summary=f"summary {i}",
                score=50.0 + i,
            ))
            if i % 2 == 1:
                uow.video_tracking.upsert(VideoTracking(
                    video_id=VideoId(int(v.id)),
                    status=TrackingStatus.SAVED,
                    starred=True,
                    notes=f"note {i}",
                ))
    with SqliteUnitOfWork(engine) as uow:
        t = uow.tags.get_or_create("idea")
        assert t.id is not None
        uow.tags.assign(VideoId(ids[0]), t.id)
        c = uow.collections.create("MyCol")
        assert c.id is not None
        uow.collections.add_video(c.id, VideoId(ids[1]))
    return ids, engine


def _factory_from(engine):
    from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork

    def _make():
        return SqliteUnitOfWork(engine)
    return _make


class TestExportLibraryUseCase:
    def test_export_all_no_filters(self, _seeded_db) -> None:
        ids, engine = _seeded_db
        exp = _CaptureExporter()
        uc = ExportLibraryUseCase(unit_of_work_factory=_factory_from(engine))
        n = uc.execute(exporter=exp)
        assert n == 3
        assert len(exp.records) == 3
        by_id = {r.video_id: r for r in exp.records}
        assert by_id[ids[0]].tags == ["idea"]
        assert by_id[ids[1]].collections == ["MyCol"]
        assert by_id[ids[0]].status == "saved"
        assert by_id[ids[0]].starred is True

    def test_export_with_collection_filter(self, _seeded_db) -> None:
        ids, engine = _seeded_db
        exp = _CaptureExporter()
        uc = ExportLibraryUseCase(unit_of_work_factory=_factory_from(engine))
        n = uc.execute(
            exporter=exp, filters=SearchFilters(collection="MyCol"),
        )
        assert n == 1
        assert exp.records[0].video_id == ids[1]

    def test_export_with_starred_filter(self, _seeded_db) -> None:
        ids, engine = _seeded_db
        exp = _CaptureExporter()
        uc = ExportLibraryUseCase(unit_of_work_factory=_factory_from(engine))
        n = uc.execute(exporter=exp, filters=SearchFilters(starred=True))
        # Videos 1 and 3 are starred (odd i)
        assert n == 2
        assert {r.video_id for r in exp.records} == {ids[0], ids[2]}

    def test_export_empty_db(self, engine) -> None:
        exp = _CaptureExporter()
        uc = ExportLibraryUseCase(unit_of_work_factory=_factory_from(engine))
        n = uc.execute(exporter=exp)
        assert n == 0
        assert exp.records == []
        assert exp.call_count == 1  # write called with empty list

    def test_export_record_has_all_fields(self, _seeded_db) -> None:
        ids, engine = _seeded_db
        exp = _CaptureExporter()
        uc = ExportLibraryUseCase(unit_of_work_factory=_factory_from(engine))
        uc.execute(exporter=exp)
        r = next(r for r in exp.records if r.video_id == ids[0])
        assert r.platform == "youtube"
        assert r.url == "https://y.be/exp1"
        assert r.title == "Title 1"
        assert "k1" in r.keywords
        assert r.score == 51.0
        assert r.status == "saved"
        assert r.tags == ["idea"]
        assert r.exported_at  # ISO string
```

Étape 5 — Créer `tests/unit/cli/test_export_cmd.py` :

```python
"""CliRunner tests for `vidscope export` (M011/S04/R059)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

from vidscope.cli.app import app


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    import pathlib
    here = pathlib.Path(__file__).resolve()
    for _ in range(6):
        if (here / "config" / "taxonomy.yaml").is_file():
            monkeypatch.chdir(here)
            break
        here = here.parent
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))


def _insert_video(pid: str) -> int:
    from vidscope.infrastructure.container import build_container
    container = build_container()
    try:
        with container.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO videos (platform, platform_id, url, created_at) "
                     "VALUES ('youtube', :p, :u, :c)"),
                {"p": pid, "u": f"https://y.be/{pid}", "c": datetime.now(UTC)},
            )
            return int(conn.execute(
                text("SELECT id FROM videos WHERE platform_id=:p"),
                {"p": pid},
            ).scalar())
    finally:
        container.engine.dispose()


class TestExportCmd:
    def test_help(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["export", "--help"])
        assert r.exit_code == 0
        for opt in ("--format", "--out", "--collection", "--tag", "--status"):
            assert opt in r.output

    def test_invalid_format_fails(self) -> None:
        runner = CliRunner()
        r = runner.invoke(app, ["export", "--format", "xml"])
        assert r.exit_code != 0
        assert "xml" in r.output or "--format" in r.output

    def test_json_export_to_file(self, tmp_path: Path) -> None:
        _insert_video("exp_json_1")
        out = tmp_path / "out.json"
        runner = CliRunner()
        r = runner.invoke(
            app, ["export", "--format", "json", "--out", str(out)],
        )
        assert r.exit_code == 0, r.output
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "exported" in r.output

    def test_markdown_to_stdout(self) -> None:
        _insert_video("exp_md_1")
        runner = CliRunner()
        r = runner.invoke(app, ["export", "--format", "markdown"])
        assert r.exit_code == 0
        # stdout contient le markdown + le récap
        assert "---" in r.output or "exported" in r.output

    def test_csv_export(self, tmp_path: Path) -> None:
        _insert_video("exp_csv_1")
        out = tmp_path / "out.csv"
        runner = CliRunner()
        r = runner.invoke(
            app, ["export", "--format", "csv", "--out", str(out)],
        )
        assert r.exit_code == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "video_id" in content

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        runner = CliRunner()
        r = runner.invoke(
            app,
            [
                "export", "--format", "json",
                "--out", "../../../etc/passwd",
            ],
        )
        assert r.exit_code != 0
        assert ".." in r.output or "traversal" in r.output

    def test_collection_filter(self, tmp_path: Path) -> None:
        vid = _insert_video("exp_col_1")
        # Add to collection
        runner = CliRunner()
        runner.invoke(app, ["collection", "create", "ExpCol"])
        runner.invoke(app, ["collection", "add", "ExpCol", str(vid)])
        out = tmp_path / "coll.json"
        r = runner.invoke(
            app,
            [
                "export", "--format", "json",
                "--out", str(out), "--collection", "ExpCol",
            ],
        )
        assert r.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert any(r_["video_id"] == vid for r_ in data)
```

Étape 6 — Exécuter :
```
uv run pytest tests/unit/application/test_export_library.py tests/unit/cli/test_export_cmd.py -x -q
uv run lint-imports
uv run pytest -m architecture -x -q
```

NE PAS importer `vidscope.adapters.*` depuis `vidscope.application.export_library` (seulement les ports). Le CLI peut importer les adapters car `cli -> adapters` est permis par la couche `layers`.
  </action>
  <verify>
    <automated>uv run pytest tests/unit/application/test_export_library.py tests/unit/cli/test_export_cmd.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "def export_command" src/vidscope/cli/commands/export.py` matches
    - `grep -n '"--format"' src/vidscope/cli/commands/export.py` matches
    - `grep -n '"--out"' src/vidscope/cli/commands/export.py` matches
    - `grep -n "_validate_out_path" src/vidscope/cli/commands/export.py` matches
    - `grep -nE "\\.\\." src/vidscope/cli/commands/export.py` matches (path traversal guard)
    - `grep -n "export_command" src/vidscope/cli/commands/__init__.py` matches
    - `grep -n 'app.command(\s*"export"' src/vidscope/cli/app.py` matches
    - `grep -nE "from vidscope.adapters" src/vidscope/application/export_library.py` returns exit 1 (application-pure)
    - `uv run pytest tests/unit/application/test_export_library.py -x -q` exits 0
    - `uv run pytest tests/unit/cli/test_export_cmd.py -x -q` exits 0
    - `uv run lint-imports` exits 0 (11 contrats KEPT)
    - `uv run pytest -m architecture -x -q` exits 0
  </acceptance_criteria>
  <done>
    - CLI `vidscope export` livrée et enregistrée
    - Path traversal guard sur --out (rejet de `..`)
    - ExportLibraryUseCase connecté aux 3 exporters via DI (use case reçoit un Exporter)
    - Filtres (collection/tag/status/starred) respectés
    - Tests E2E sur DB réelle + tests CLI avec CliRunner verts
    - 11 contrats import-linter KEPT dont le nouveau
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Disk FS ← `MarkdownExporter.write(out=PATH)` | L'exporter écrit à l'emplacement fourni. Path traversal possible si `..` non-validé. |
| Disk FS ← `JsonExporter.write` et `CsvExporter.write` | Idem. |
| CLI (user) → `--out PATH` | String user, validé avant appel de Path.write_text. |
| UoW → ExportRecord | Data fetchée depuis la DB, contient notes (texte libre user). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PATH-M011-01 | Tampering / Info Disclosure | `--out` path traversal vers `/etc/passwd` ou équivalent | mitigate | `_validate_out_path` rejette tout chemin contenant un segment `..`. Test `test_path_traversal_rejected`. Accepte absolute et relative. NOTE: rejet strict `..`; un utilisateur peut toujours fournir `/etc/passwd` absolu — c'est un outil local single-user R032, l'utilisateur a les droits natifs de son propre système. |
| T-YAML-M011-01 | Tampering | YAML frontmatter Markdown injection via `notes` ou `title` | mitigate | `yaml.dump(..., default_flow_style=False)` échappe proprement les strings. Aucun use de `yaml.load` dans le writer. `yaml.safe_load` uniquement dans les tests. |
| T-CSV-M011-01 | Tampering | CSV injection via `=`, `+`, `-`, `@` en début de cell (Excel formula) | accept | Export CSV est destiné à Airtable/pandas, pas Excel. R032 single-user → l'utilisateur contrôle son propre flux d'import. Si Excel devient un use case, ajouter escape en v2. |
| T-INFO-M011-01 | Info Disclosure | Export contient `notes` (texte libre) + URLs | accept | C'est exactement le but de l'export. Utilisateur single-user R032, outil local, pas de partage réseau. |
| T-ARCH-M011-04 | Spoofing | adapters.export importing another adapter | mitigate | Nouveau contrat `export-adapter-is-self-contained` KEPT. Test architecture. |
| T-ARCH-M011-05 | Spoofing | application.export_library importing adapter | mitigate | Contrat existant `application-has-no-adapters` KEPT. Use case importe uniquement depuis `vidscope.domain` et `vidscope.ports`. |
| T-SCHEMA-M011-01 | Tampering | Breaking change schema v1 | mitigate | `docs/export-schema.v1.md` FROZEN. Toute modification = v2 additive alongside v1. |
</threat_model>

<verification>
Après les 2 tâches, exécuter :
- `uv run pytest tests/unit/adapters/export/ tests/unit/application/test_export_library.py tests/unit/cli/test_export_cmd.py -x -q` vert
- `uv run lint-imports` vert — 11 contrats KEPT incluant `export adapter does not import other adapters KEPT`
- `uv run pytest -m architecture -x -q` vert (EXPECTED_CONTRACTS = 10 noms comptés)
- `uv run vidscope export --help` OK et liste --format/--out/--collection/--tag/--status/--starred/--limit
- Vérifier manuellement un export JSON minimal: `vidscope export --format json --out /tmp/test.json` suivi de `python -c "import json; print(json.load(open('/tmp/test.json')))"` fonctionne
</verification>

<success_criteria>
S04 est complet quand :
- [ ] Port `Exporter` Protocol livré dans `vidscope.ports.exporter` + re-exporté
- [ ] DTO `ExportRecord` livré dans `vidscope.application.export_library` (frozen+slots)
- [ ] `ExportLibraryUseCase` assemble les records via UoW (videos + analyses + tracking + tags + collections)
- [ ] 3 adapters concrets livrés dans `vidscope.adapters.export/` (json, markdown, csv) — self-contained
- [ ] CLI `vidscope export --format {json|markdown|csv} [--out] [--collection] [--tag] [--status] [--starred] [--limit]` enregistrée
- [ ] Path traversal guard: `--out` avec `..` rejeté
- [ ] `docs/export-schema.v1.md` livré, FROZEN contract documenté
- [ ] 11e contrat import-linter `export-adapter-is-self-contained` KEPT
- [ ] `EXPECTED_CONTRACTS` dans `tests/architecture/test_layering.py` inclut le nouveau nom (10 total)
- [ ] Suite tests verte (exporters + use case + CLI)
- [ ] `lint-imports` vert (11 contrats KEPT)
- [ ] R059 couvert end-to-end
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M011/M011-S04-SUMMARY.md` documentant :
- Signature finale de `Exporter` Protocol (stdlib only)
- Schéma final `ExportRecord` (18+ champs, v1 frozen)
- Les 3 adapters: pattern commun (stdlib / yaml.dump / csv.DictWriter)
- CLI signature finale `vidscope export`
- Path traversal guard implémenté
- 11e contrat import-linter en place
- `docs/export-schema.v1.md` link + résumé du contrat de stabilité v1
- Comment étendre avec un format additionnel (ajouter un fichier dans `adapters/export/` + entrée dans `_FORMATS` du CLI)
- Liste exhaustive des fichiers créés/modifiés
</output>
