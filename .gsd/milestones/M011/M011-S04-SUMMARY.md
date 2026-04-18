---
phase: M011
plan: S04
subsystem: ports+application+adapters+cli
tags: [export, json, markdown, csv, protocol, import-linter, cli, frozen-schema]
requirements: [R059]

dependency_graph:
  requires: [M011-S01, M011-S02, M011-S03]
  provides: [Exporter_port, ExportRecord_DTO, ExportLibraryUseCase, JsonExporter, MarkdownExporter, CsvExporter, vidscope_export_CLI, export-adapter-is-self-contained_contract, export-schema-v1-doc]
  affects: []

tech_stack:
  added: []
  patterns:
    - Exporter Protocol @runtime_checkable dans ports/exporter.py (list[Any] pour eviter import cycle avec application)
    - ExportRecord DTO frozen+slots 19 champs dans application/export_library.py
    - ExportLibraryUseCase avec AND-intersection logic miroir de SearchVideosUseCase (S03)
    - JsonExporter (stdlib json + dataclasses.asdict), MarkdownExporter (yaml.dump frontmatter), CsvExporter (stdlib csv.DictWriter)
    - Adapters export self-contained: types list[Any] pas d'import depuis vidscope.application
    - 11e contrat import-linter export-adapter-is-self-contained KEPT
    - Path traversal guard _validate_out_path: rejet segment ..  (T-PATH-M011-01)
    - CLI --format json|markdown|csv --out --collection --tag --status --starred --limit

key_files:
  created:
    - src/vidscope/ports/exporter.py (Exporter Protocol @runtime_checkable)
    - src/vidscope/application/export_library.py (ExportRecord DTO + ExportLibraryUseCase)
    - src/vidscope/adapters/export/__init__.py (re-exports 3 exporters)
    - src/vidscope/adapters/export/json_exporter.py (JsonExporter)
    - src/vidscope/adapters/export/markdown_exporter.py (MarkdownExporter)
    - src/vidscope/adapters/export/csv_exporter.py (CsvExporter)
    - src/vidscope/cli/commands/export.py (export_command)
    - docs/export-schema.v1.md (schema frozen v1)
    - tests/unit/adapters/export/__init__.py
    - tests/unit/adapters/export/test_json_exporter.py (4 tests)
    - tests/unit/adapters/export/test_markdown_exporter.py (4 tests)
    - tests/unit/adapters/export/test_csv_exporter.py (3 tests + protocol)
    - tests/unit/application/test_export_library.py (5 tests)
    - tests/unit/cli/test_export_cmd.py (7 tests)
  modified:
    - src/vidscope/ports/__init__.py (re-export Exporter + __all__)
    - src/vidscope/cli/commands/__init__.py (export_command import + __all__)
    - src/vidscope/cli/app.py (app.command("export") registration)
    - .importlinter (nouveau contrat export-adapter-is-self-contained)
    - tests/architecture/test_layering.py (EXPECTED_CONTRACTS 10 noms)

decisions:
  - "Exporter Protocol utilise list[Any] a la place de list[ExportRecord] — import-linter detecte les imports TYPE_CHECKING et violerait ports-are-pure + export-adapter-is-self-contained. list[Any] est le seul moyen de rester stdlib-only dans ports et adapters."
  - "ExportRecord DTO dans vidscope.application (pas domain) — c'est une projection multi-agregate, pas une entite metier. Confirme D6 RESEARCH."
  - "ExportLibraryUseCase reutilise exactement la meme logique AND-intersection que SearchVideosUseCase (S03) pour les filtres — DRY via copie explicite, pas heritage."
  - "_validate_out_path leve typer.Exit(1) directement (pas raise fail_user) car fail_user retourne typer.Exit sans lever d'exception."

metrics:
  duration: ~60min
  tasks_completed: 2
  files_created: 14
  files_modified: 5
  tests_added: 24
---

# Phase M011 Plan S04: Veille Exports (JSON/Markdown/CSV) Summary

**One-liner:** Export layer complet avec Exporter Protocol stdlib-only, ExportRecord DTO v1 frozen 19 champs, 3 adapters self-contained (JSON/Markdown/CSV), ExportLibraryUseCase avec filtres AND, CLI `vidscope export`, 11e contrat import-linter KEPT, schema doc v1 frozen.

## What Was Built

S04 ferme le cycle M011. Les annotations (status, tags, collections, analyses) peuvent maintenant sortir vers Notion/Obsidian/Airtable en une commande.

### Port `Exporter` (stdlib only)

```python
# src/vidscope/ports/exporter.py
@runtime_checkable
class Exporter(Protocol):
    def write(self, records: list[Any], out: Path | None = None) -> None: ...
```

`list[Any]` a la place de `list[ExportRecord]` — decision necessaire car import-linter detecte meme les imports sous `TYPE_CHECKING` et violerait `ports-are-pure` + `export-adapter-is-self-contained`.

### DTO `ExportRecord` (frozen+slots, v1 frozen)

19 champs dans `vidscope.application.export_library`:

```python
@dataclass(frozen=True, slots=True)
class ExportRecord:
    video_id: int          platform: str        url: str
    author: str | None     title: str | None    upload_date: str | None
    # Analysis
    score: float | None    summary: str | None  keywords: list[str]
    topics: list[str]      verticals: list[str] actionability: float | None
    content_type: str | None
    # Tracking
    status: str | None     starred: bool        notes: str | None
    # Tags + Collections
    tags: list[str]        collections: list[str]
    # Metadata
    exported_at: str       # ISO 8601 UTC
```

### ExportLibraryUseCase

Meme logique AND-intersection que `SearchVideosUseCase` (S03):
- Sans filtres: `uow.videos.list_recent(limit=limit)` — tous les videos
- Avec filtres: sources positives (status, starred, tag, collection) puis `set.intersection(*sources)` + exclusion starred

### 3 Adapters self-contained

| Adapter | Stdlib | Multi-value | Out=None |
|---------|--------|-------------|----------|
| `JsonExporter` | `json.dumps` | JSON arrays | stdout |
| `MarkdownExporter` | `yaml.dump` (pyyaml) | YAML lists | stdout |
| `CsvExporter` | `csv.DictWriter` | joined par `\|` | stdout |

Tous utilisent `dataclasses.asdict(rec)` — aucun import depuis `vidscope.application`.

### CLI `vidscope export`

```
vidscope export --format {json|markdown|csv}
                [--out PATH]          # chemin fichier (sans ..)
                [--collection NAME]   # collection exacte
                [--tag NAME]          # tag (lowercase)
                [--status STATUS]     # new|reviewed|saved|actioned|ignored|archived
                [--starred | --unstarred]
                [--limit N]           # defaut 10000
```

Path traversal guard `_validate_out_path`: rejette tout segment `..` (T-PATH-M011-01). Accepte chemin absolu et relatif.

### 11e contrat import-linter

```ini
[importlinter:contract:export-adapter-is-self-contained]
name = export adapter does not import other adapters
type = forbidden
source_modules = vidscope.adapters.export
forbidden_modules =
    vidscope.adapters.sqlite  vidscope.adapters.fs  vidscope.adapters.config
    vidscope.adapters.ytdlp   vidscope.adapters.whisper  vidscope.adapters.ffmpeg
    vidscope.adapters.heuristic  vidscope.adapters.llm
    vidscope.infrastructure  vidscope.application  vidscope.pipeline
    vidscope.cli  vidscope.mcp
```

`lint-imports`: **11 contrats KEPT, 0 broken**.

### `docs/export-schema.v1.md` — schema frozen

- 19 champs documentes avec types + descriptions
- Conventions par format (JSON arrays / YAML frontmatter / CSV pipe-separated)
- Contrat de stabilite v1: additions OK, removals/renames = v2

### Comment ajouter un format

1. Creer `src/vidscope/adapters/export/ndjson_exporter.py` avec `class NdjsonExporter`
2. Ajouter dans `adapters/export/__init__.py`
3. Ajouter `"ndjson": NdjsonExporter` dans `_FORMATS` de `cli/commands/export.py`
4. Ajouter tests dans `tests/unit/adapters/export/test_ndjson_exporter.py`
5. Le contrat `export-adapter-is-self-contained` s'applique automatiquement — pas de modification `.importlinter` necessaire

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] import-linter detecte les imports TYPE_CHECKING**

- **Found during:** Task 1 — apres premier lint-imports (2 contrats BROKEN)
- **Issue:** import-linter analyse les imports statiques incluant ceux sous `if TYPE_CHECKING:`. Le plan prevoyait `from vidscope.application.export_library import ExportRecord` sous `TYPE_CHECKING` dans les adapters et le port, mais cela brise `export-adapter-is-self-contained` et `ports-are-pure`.
- **Fix:** Remplacement de tous les imports `ExportRecord` par `list[Any]` dans les adapters (`json_exporter.py`, `markdown_exporter.py`, `csv_exporter.py`) et dans le port (`exporter.py`). `dataclasses.asdict(rec)` fonctionne avec `Any` a runtime.
- **Files modified:** `src/vidscope/ports/exporter.py`, les 3 adapters
- **Commit:** ab0017f

**2. [Rule 1 - Bug] `fail_user` retourne typer.Exit sans lever d'exception**

- **Found during:** Task 2 — analyse du code `_support.py`
- **Issue:** Le plan ecrivait `raise fail_user(...)` dans `_validate_out_path` mais `fail_user()` retourne `typer.Exit` (pas une exception). Le pattern correct est `raise typer.Exit(1)` apres `console.print(...)`.
- **Fix:** `_validate_out_path` utilise `console.print(...)` + `raise typer.Exit(1)` directement.
- **Files modified:** `src/vidscope/cli/commands/export.py`
- **Commit:** 4586dae

## Known Stubs

Aucun stub. Toutes les fonctionnalites S04 sont wired end-to-end:
- ExportRecord ← ExportLibraryUseCase ← UoW (videos + analyses + tracking + tags + collections)
- ExportLibraryUseCase → Exporter.write(records, out)
- CLI → ExportLibraryUseCase → 3 adapters concrets

## Threat Flags

Aucune nouvelle surface de securite hors plan. Les mitigations du threat model sont toutes couvertes:
- T-PATH-M011-01: `_validate_out_path` rejette `..` — COVERED (test_path_traversal_rejected)
- T-YAML-M011-01: `yaml.dump(default_flow_style=False)` — COVERED
- T-ARCH-M011-04: contrat `export-adapter-is-self-contained` KEPT — COVERED
- T-ARCH-M011-05: contrat `application-has-no-adapters` KEPT — COVERED
- T-SCHEMA-M011-01: `docs/export-schema.v1.md` FROZEN documente — COVERED

## Self-Check: PASSED

Fichiers crees:
- src/vidscope/ports/exporter.py — class Exporter: YES
- src/vidscope/application/export_library.py — class ExportRecord + ExportLibraryUseCase: YES
- src/vidscope/adapters/export/json_exporter.py — class JsonExporter: YES
- src/vidscope/adapters/export/markdown_exporter.py — class MarkdownExporter: YES
- src/vidscope/adapters/export/csv_exporter.py — class CsvExporter: YES
- src/vidscope/cli/commands/export.py — def export_command: YES
- docs/export-schema.v1.md — v1 + exported_at: YES

Commits:
- ab0017f: feat(M011-S04): Task 1 — VERIFIED
- 4586dae: feat(M011-S04): Task 2 — VERIFIED

Tests: 24 passed, 0 failed
lint-imports: 11 contrats KEPT, 0 broken
vidscope export --help: OK (--format, --out, --collection, --tag, --status, --starred, --limit)
