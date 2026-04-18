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
2. Adding a new field in the future is allowed (v1-compatible additive change).
3. Removing, renaming, or changing the semantic of an existing field
   ships as a v2 exporter alongside v1 — never in-place.
4. CSV column names are stable; readers relying on column order are
   explicitly out of scope for this contract.

## Adding a New Export Format

To add a fourth format (e.g. `ndjson`):

1. Create `src/vidscope/adapters/export/ndjson_exporter.py` with a class
   `NdjsonExporter` implementing `write(records, out)`.
2. Add the import to `src/vidscope/adapters/export/__init__.py`.
3. Add `"ndjson": NdjsonExporter` to the `_FORMATS` dict in
   `src/vidscope/cli/commands/export.py`.
4. Add unit tests in `tests/unit/adapters/export/test_ndjson_exporter.py`.
5. The `export-adapter-is-self-contained` contract enforces no cross-adapter
   imports automatically — no `.importlinter` change needed.
