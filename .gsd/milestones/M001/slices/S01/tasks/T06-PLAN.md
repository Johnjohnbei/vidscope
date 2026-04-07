---
estimated_steps: 1
estimated_files: 22
skills_used: []
---

# T06: SQLite adapters: schema + FTS5 + repositories + UnitOfWork + LocalMediaStorage

Create src/vidscope/adapters/sqlite/ with schema.py (SQLAlchemy Core Table definitions for videos, transcripts, frames, analyses, pipeline_runs + FTS5 virtual table via raw DDL + init_db(engine) idempotent) and five repository files — video_repository.py, transcript_repository.py, frame_repository.py, analysis_repository.py, pipeline_run_repository.py — each implementing the matching port Protocol from T04. Also unit_of_work.py implementing the UnitOfWork port: opens a Connection inside a `with engine.begin() as conn:` and exposes repository properties bound to that connection. search_index.py implements SearchIndex on top of the FTS5 virtual table. Use SQLAlchemy Core only (no ORM). Timestamps are UTC-aware. JSON columns for segments/keywords/topics. FK ON DELETE CASCADE for video children. videos.platform_id is UNIQUE — provide an `upsert_by_platform_id()` using `INSERT ... ON CONFLICT(platform_id) DO UPDATE SET ...` for idempotence. Create src/vidscope/adapters/fs/local_media_storage.py implementing MediaStorage on the filesystem — store(key, source_path) copies the file under data_dir/key, resolve(key) -> Path, exists(key) -> bool, open(key) -> readable binary file handle, delete(key) -> None. Keys are slash-separated strings; the adapter converts them to the OS's path separator internally. Add tests/unit/adapters/sqlite/ with test_schema.py, test_video_repository.py (insert + get + upsert idempotence), test_pipeline_run_repository.py (insert + latest_by_video + list_recent), test_search_index.py (insert + query returns match with rank), test_unit_of_work.py (rollback on exception preserves pre-state). Add tests/unit/adapters/fs/test_local_media_storage.py (round-trip against tmp_path). Update infrastructure/container.py from T05 to wire the concrete adapters into the Container (container was a skeleton before; this task makes it real).

## Inputs

- ``src/vidscope/domain/__init__.py``
- ``src/vidscope/ports/repositories.py``
- ``src/vidscope/ports/storage.py``
- ``src/vidscope/ports/unit_of_work.py``
- ``src/vidscope/infrastructure/sqlite_engine.py``

## Expected Output

- ``src/vidscope/adapters/sqlite/schema.py` — Table defs + FTS5 DDL + init_db`
- ``src/vidscope/adapters/sqlite/video_repository.py` — VideoRepositorySQLite with upsert_by_platform_id`
- ``src/vidscope/adapters/sqlite/transcript_repository.py``
- ``src/vidscope/adapters/sqlite/frame_repository.py``
- ``src/vidscope/adapters/sqlite/analysis_repository.py``
- ``src/vidscope/adapters/sqlite/pipeline_run_repository.py` — with latest_by_video / list_recent`
- ``src/vidscope/adapters/sqlite/search_index.py` — SearchIndexSQLite over FTS5`
- ``src/vidscope/adapters/sqlite/unit_of_work.py` — SqliteUnitOfWork with transactional connection`
- ``src/vidscope/adapters/fs/local_media_storage.py` — LocalMediaStorage implementing MediaStorage`
- ``src/vidscope/infrastructure/container.py` — updated to wire concrete adapters`
- ``tests/unit/adapters/sqlite/*` — schema + repository + FTS5 + UoW tests`
- ``tests/unit/adapters/fs/test_local_media_storage.py` — filesystem round-trip tests`

## Verification

python -m uv run pytest tests/unit/adapters -q && python -m uv run python -c "from vidscope.infrastructure.container import build_container; c = build_container(); from sqlalchemy import inspect; names = inspect(c.engine).get_table_names(); assert {'videos','transcripts','frames','analyses','pipeline_runs'}.issubset(set(names)), names; print('sqlite adapters ok')"
