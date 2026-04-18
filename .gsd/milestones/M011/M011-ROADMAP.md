# M011 — Veille workflow layer (tracking, tags, collections, exports)

## Vision
VidScope is currently read-only: ingest → search. There's no way for the user to mark a video "already reviewed", "save for action", or "ignored"; no way to group videos into named collections ("Concurrents Shopify", "Hooks à réutiliser"); no way to export to Notion / Obsidian / Airtable. M011 adds the **personal workflow overlay** that sits on top of immutable content data: `video_tracking` (status enum + starred + notes), `tags`, `collections`, and `vidscope export --format markdown|csv|json`. D033 keeps the `videos` table immutable — workflow lives in separate tables so re-ingesting a video never wipes user annotations. Combined with facets from M007/M010, search becomes: *"all new + starred videos from @creator with a link and actionability > 70, tagged `idea`, in collection `Concurrents`"*.

## Slice Overview

| ID | Slice | Risk | Depends | Done when |
|----|-------|------|---------|-----------|
| S01 | Tracking table + status transitions + notes | low | M006 | `VideoTracking` entity with `status ENUM {new, reviewed, saved, actioned, ignored, archived}`, `starred bool`, `notes TEXT`, ports, SQLite adapter, migration 010. `vidscope review <id> --status saved --star --note "..."` CLI. |
| S02 | Tags + collections | low | S01 | `Tag`, `Collection`, `CollectionItem` entities + many-to-many tables, CLI `vidscope tag add/remove/list`, `vidscope collection create/add/remove/list/show`. |
| S03 | Facetted search across everything | medium | S01, S02, M007/S04, M010/S04 | `vidscope search "<query>"` accepts `--creator`, `--platform`, `--status`, `--starred`, `--tag`, `--collection`, `--has-link`, `--content-type`, `--min-score`, `--min-actionability`, `--since`, `--until`. Composable AND semantics. MCP tool exposes the same facets. |
| S04 | Exports (JSON, Markdown, CSV) | low | S03 | `vidscope export --format json|markdown|csv [--collection NAME] [--query ...] [--out PATH]`, stable documented JSON schema, Markdown = one-file-per-video with YAML frontmatter (Obsidian-ready), CSV = flat tabular (Airtable-ready). |

## Layer Architecture

| Slice | Layer | New/Changed files |
|-------|-------|-------------------|
| S01 | domain | `entities.py` (+VideoTracking), `values.py` (+TrackingStatus enum) |
| S01 | ports | `video_tracking_repository.py` |
| S01 | adapters/sqlite | `video_tracking_repository.py`, `migrations/010_tracking.py` |
| S01 | application | `use_cases/set_video_tracking.py` |
| S01 | cli | `review.py` **new** |
| S02 | domain | `entities.py` (+Tag, Collection), `values.py` (+TagName, CollectionName) |
| S02 | ports | `tag_repository.py`, `collection_repository.py` |
| S02 | adapters/sqlite | `tag_repository.py`, `collection_repository.py`, `migrations/011_tags_collections.py` |
| S02 | application | 6 use cases: `tag_video`, `untag_video`, `list_tags`, `create_collection`, `add_to_collection`, `remove_from_collection` |
| S02 | cli | `tags.py` **new**, `collections.py` **new** |
| S03 | application | `use_cases/search_videos.py` (SIGNIFICANT extension — all facets) |
| S03 | adapters/sqlite | `search_repository.py` (dynamic query builder with SQL-injection-safe parameterisation — exhaustively tested) |
| S03 | cli | `main.py` (search facets) |
| S03 | mcp | `tools/search.py` (facets) |
| S04 | ports | `exporter.py` (Protocol: write(videos, out)) |
| S04 | adapters/export | **new submodule** `adapters/export/json_exporter.py`, `markdown_exporter.py`, `csv_exporter.py` |
| S04 | application | `use_cases/export_library.py` |
| S04 | cli | `export.py` **new** |

## Test Strategy

| Test kind | Scope | Tooling |
|-----------|-------|---------|
| Domain unit | TrackingStatus enum, transitions (no illegal direct archived→new, document allowed state machine), Tag/Collection validation | pytest |
| Adapter unit | Each new repo CRUD, UNIQUE constraints (tag name global, collection name global, tracking.video_id UNIQUE), FK cascade | pytest |
| Pipeline neutrality | Re-ingesting a video with existing tracking/tags/collection membership must NOT wipe them. Critical regression guard. | pytest integration |
| Application unit | Each use case with InMemory repos | pytest |
| Search query builder | Matrix test: every combination of 3 facets chosen among 11 (≈ 165 combos, sampled to ≥ 50) against fixture DB, assert SQL is valid + results are correct | pytest |
| SQL-injection guard | Fuzz facet values with shell/SQL metacharacters, assert no query error and no leaked rows | pytest |
| Export unit | JSON schema validation (ship `schemas/export.v1.json`), Markdown frontmatter parseable by `python-frontmatter`, CSV parseable by stdlib csv + round-trip | pytest |
| Export correctness | Fixture DB with 5 videos → export JSON → re-parse → every field round-trips | pytest |
| CLI snapshot | `vidscope review`, `vidscope tag add/list`, `vidscope collection create/add/list`, `vidscope search` with 5+ facets, `vidscope export` | CliRunner |
| MCP subprocess | Facet search via MCP matches CLI output shape | existing subprocess harness |
| Architecture | 9+ contracts green, new contract `export-adapter-is-self-contained` | lint-imports |
| E2E live | `verify-m011.sh`: ingest 3 videos → tag one `idea` → add two to `Concurrents` collection → star one → search `--tag idea --min-score 50 --starred` → export collection to Markdown → parse exported files → assert content | bash |
| Regression | All verify-m001..m010.sh must stay green post-M011 | bash |

### Export schema contract
S04 ships `docs/export-schema.v1.md` — frozen field list and types. Any breaking change to export fields requires a `v2` exporter (additive) alongside, never overwriting v1. Protects downstream Notion/Obsidian imports.

## Requirements Mapping

- Closes R056 (tracking + notes), R057 (tags + collections), R058 (facetted search), R059 (export).
- This is the milestone that makes **every previous qualitative improvement (M006-M010) actually useful in daily veille work**.

## Out of Scope (explicit)

- No import-from-external (reverse sync Notion → VidScope) — export-only for now.
- No shared collections (multi-user) — R032 forbids multi-tenancy.
- No UI beyond the CLI — R032 still applies; export feeds the user's preferred external UI.
- No reminder / notification system — "revisit at" could be a future additive field on `video_tracking`.
