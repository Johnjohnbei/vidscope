---
phase: 9
slug: engagement-signals-velocity
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase M009 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit/ -x -q` |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~30 seconds (unit), ~60 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** Run `uv run pytest -x -q` (inclut architecture)
- **Before `/gsd-verify-work`:** Suite complète verte + `test_metrics_property.py` Hypothesis vert
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| S01-01 | S01 | 0 | R050 | — | N/A | setup | `uv pip install hypothesis && uv sync` | ❌ W0 | ⬜ pending |
| S01-02 | S01 | 1 | R050 | — | None != 0 pour champs absents | unit domain | `uv run pytest tests/unit/domain/test_entities.py -x` | ❌ W0 | ⬜ pending |
| S01-03 | S01 | 1 | R050 | — | velocity monotonicity, zero-bug | unit domain property | `uv run pytest tests/unit/domain/test_metrics_property.py -x` | ❌ W0 | ⬜ pending |
| S01-04 | S01 | 1 | R050 | — | download=False forcé | unit adapter | `uv run pytest tests/unit/adapters/ytdlp/test_stats_probe.py -x` | ❌ W0 | ⬜ pending |
| S01-05 | S01 | 1 | R050 | T-SQL-01 | pas d'UPDATE, INSERT seulement | unit adapter | `uv run pytest tests/unit/adapters/sqlite/test_video_stats_repository.py -x` | ❌ W0 | ⬜ pending |
| S01-06 | S01 | 1 | R050 | — | (video_id, captured_at) UNIQUE à la seconde | unit adapter | `uv run pytest tests/unit/adapters/sqlite/test_video_stats_repository.py -x` | ❌ W0 | ⬜ pending |
| S01-07 | S01 | 1 | R050 | — | migration 008 sur DB existante | unit adapter | `uv run pytest tests/unit/adapters/sqlite/test_schema.py -x` | ✅ (test à ajouter) | ⬜ pending |
| S02-01 | S02 | 2 | R051 | — | StatsStage.is_satisfied toujours False | unit pipeline | `uv run pytest tests/unit/pipeline/ -x` | ❌ W0 | ⬜ pending |
| S02-02 | S02 | 2 | R051 | — | RefreshStatsUseCase avec InMemory probe+repo | unit application | `uv run pytest tests/unit/application/test_refresh_stats.py -x` | ❌ W0 | ⬜ pending |
| S02-03 | S02 | 2 | R051 | T-INPUT-01 | `--limit 0` refusé | unit CLI | `uv run pytest tests/unit/cli/test_stats.py -x` | ❌ W0 | ⬜ pending |
| S03-01 | S03 | 3 | R051 | — | résumé "N nouvelles vidéos + M stats rafraîchies" | unit CLI | `uv run pytest tests/unit/cli/test_watch.py -x` | ✅ (test à ajouter) | ⬜ pending |
| S04-01 | S04 | 4 | R052 | — | ranking correctness ListTrendingUseCase | unit application | `uv run pytest tests/unit/application/test_list_trending.py -x` | ❌ W0 | ⬜ pending |
| S04-02 | S04 | 4 | R052 | T-INPUT-01 | `--since` validation stricte | unit CLI | `uv run pytest tests/unit/cli/test_trending.py -x` | ❌ W0 | ⬜ pending |
| S04-03 | S04 | 4 | R052 | — | vidscope_trending MCP tool | unit MCP | `uv run pytest tests/unit/mcp/ -x` | ✅ (test à ajouter) | ⬜ pending |
| ARCH | all | final | — | — | 9 contrats import-linter verts + metrics.py pure | architecture | `uv run pytest tests/architecture/ -x` | ✅ | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — ajouter `"hypothesis>=6.0,<7"` dans `[dependency-groups] dev` + `uv sync`
- [ ] `tests/unit/domain/test_entities.py` — stubs tests VideoStats (immuabilité, None != 0)
- [ ] `tests/unit/domain/test_metrics_property.py` — créer avec Hypothesis (monotonicity, additivity, zero-bug)
- [ ] `tests/unit/adapters/ytdlp/test_stats_probe.py` — créer (download=False forcé, shape de retour)
- [ ] `tests/unit/adapters/sqlite/test_video_stats_repository.py` — créer (append-only, idempotence)
- [ ] `tests/unit/pipeline/test_stats_stage.py` — créer (is_satisfied=False toujours)
- [ ] `tests/unit/application/test_refresh_stats.py` — créer
- [ ] `tests/unit/application/test_list_trending.py` — créer
- [ ] `tests/unit/cli/test_stats.py` — créer
- [ ] `tests/unit/cli/test_trending.py` — créer

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| E2E live `verify-m009.sh` | R050/R051 | Réseau réel requis | `vidscope add <YT Short>` → wait 60s → `vidscope refresh-stats <id>` → assert ≥2 rows video_stats, velocity calculée |

---

## Threat Model

| ID | Threat | STRIDE | Mitigation |
|----|--------|--------|------------|
| T-SQL-01 | SQL injection via `--since`/`--platform` | Tampering | SQLAlchemy Core parameterized queries — pas de `.raw()` ou `text()` avec f-string |
| T-INPUT-01 | `--limit 0` ou valeur négative | DoS | Validation Typer `min=1` sur `--limit` |
| T-DATA-01 | Données yt-dlp non validées | Tampering | `_int_or_none()` helper sur chaque champ stats |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
