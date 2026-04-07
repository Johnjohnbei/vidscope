# S01 Replan

**Milestone:** M001
**Slice:** S01
**Blocker Task:** T02
**Created:** 2026-04-07T10:55:11.715Z

## Blocker Description

After T02 completed, the CTO-level architecture decisions D019–D023 were recorded: VidScope adopts a strict hexagonal layered architecture (domain → ports → adapters → pipeline → application → cli + infrastructure as composition root) with import-linter enforcement. The original T03–T07 assumed a flat module layout (db/, cli.py, system_checks.py) that would force a painful refactor in M002 when MCP lands. Replanning S01 to pose the layered structure from day one. T01 and T02 outputs are fully reusable: uv toolchain stays, the package skeleton from T02 stays, and the config module written in T02 will be relocated to infrastructure/config.py with a compatibility shim during the new T05 so no rework is wasted.

## What Changed

T01 and T02 preserved as-is. T03 is replaced with a pure-Python domain layer task (entities, value objects, typed errors, zero I/O, zero third-party imports). T04 is replaced with a ports layer task (Protocols only). T05 is replaced with an infrastructure layer task that relocates config.py under infrastructure/, adds the composition root, the SQLite engine helper, and the startup checks. T06 is new: SQLite adapters (schema with FTS5, five repositories, UnitOfWork, SearchIndex) plus LocalMediaStorage filesystem adapter. T07 is new: pipeline contract (Stage Protocol, StageResult, PipelineRunner with resume-from-failure) and application use cases (IngestVideoUseCase skeleton, GetStatusUseCase, and four other skeletons). T08 replaces the old T04: CLI converted to a package with one file per command, consuming the use cases. T09 replaces the old T06 (quality gates) with the addition of import-linter and an architecture test. T10 replaces the old T07 (end-to-end verification script) on the new layout. The slice now has 10 tasks with stronger layer separation and mechanical enforcement of the architecture.
