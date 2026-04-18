---
phase: M010
slug: multi-dimensional-scoring-taxonomy
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase M010 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + hypothesis 6.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit/domain/ tests/unit/adapters/heuristic/ tests/unit/adapters/llm/ tests/unit/adapters/sqlite/test_schema.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Architecture command** | `uv run pytest -m architecture -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/domain/ tests/unit/adapters/heuristic/ tests/unit/adapters/llm/ tests/unit/adapters/sqlite/test_schema.py -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green + `uv run pytest -m architecture -q`
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| M010-S01-01 | S01 | 1 | R053, R054, R055 | T-SCHEMA-01 | Migration additive, colonnes nullable, anciens rows inchangés | unit sqlite | `uv run pytest tests/unit/adapters/sqlite/test_schema.py -q` | ✅ (à étendre) | ⬜ pending |
| M010-S01-02 | S01 | 1 | R053, R055 | — | Analysis nouveaux champs defaults correct, frozen+slots OK | unit domain | `uv run pytest tests/unit/domain/test_entities.py -q` | ✅ (à étendre) | ⬜ pending |
| M010-S01-03 | S01 | 1 | R054 | — | YamlTaxonomy charge YAML, valide schéma, match() fonctionne | unit config | `uv run pytest tests/unit/adapters/config/test_yaml_taxonomy.py -q` | ❌ Wave 0 | ⬜ pending |
| M010-S02-01 | S02 | 2 | R053, R054, R055 | — | HeuristicAnalyzerV2 produit 7 nouveaux champs, golden ≥70% | unit heuristic | `uv run pytest tests/unit/adapters/heuristic/test_heuristic_v2.py -q` | ❌ Wave 0 | ⬜ pending |
| M010-S02-02 | S02 | 2 | R053 | — | sentiment_lexicon 30+ fixtures FR+EN | unit heuristic | `uv run pytest tests/unit/adapters/heuristic/test_sentiment_lexicon.py -q` | ❌ Wave 0 | ⬜ pending |
| M010-S02-03 | S02 | 2 | R053 | — | sponsor_detector 15 fixtures | unit heuristic | `uv run pytest tests/unit/adapters/heuristic/test_sponsor_detector.py -q` | ❌ Wave 0 | ⬜ pending |
| M010-S02-04 | S02 | 2 | R053 | — | Golden fixture ≥70% match rate | unit golden | `uv run pytest tests/unit/adapters/heuristic/test_golden.py -q` | ❌ Wave 0 | ⬜ pending |
| M010-S03-01 | S03 | 3 | R053, R055 | — | LLM V2 parse nouveaux champs depuis JSON (défensif si absent) | unit llm | `uv run pytest tests/unit/adapters/llm/ -q` | ✅ (à étendre) | ⬜ pending |
| M010-S04-01 | S04 | 4 | R055 | — | `vidscope explain <id>` affiche reasoning + scores | unit CLI | `uv run pytest tests/unit/cli/test_explain.py -q` | ❌ Wave 0 | ⬜ pending |
| M010-S04-02 | S04 | 4 | R053 | — | CLI search filtre par content_type/min_actionability/sponsored | unit CLI | `uv run pytest tests/unit/cli/test_search.py -q` | ✅ (à étendre) | ⬜ pending |
| M010-ARCH | S01 | 1 | — | — | 10 contrats import-linter verts (9 existants + config-adapter) | architecture | `uv run pytest -m architecture -q` | ✅ (à étendre) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/adapters/heuristic/test_heuristic_v2.py` — stubs/fixtures pour R053 HeuristicV2
- [ ] `tests/unit/adapters/heuristic/test_sentiment_lexicon.py` — 30+ fixtures FR+EN pour sentiment
- [ ] `tests/unit/adapters/heuristic/test_sponsor_detector.py` — 15 fixtures sponsor detection
- [ ] `tests/unit/adapters/heuristic/test_golden.py` — charge `tests/fixtures/analysis_golden.jsonl`, vérifie ≥70% match
- [ ] `tests/fixtures/analysis_golden.jsonl` — 40 transcripts hand-labelled (content_type + is_sponsored + sentiment)
- [ ] `tests/unit/adapters/config/` — nouveau répertoire + `__init__.py`
- [ ] `tests/unit/adapters/config/test_yaml_taxonomy.py` — schema validation + matching
- [ ] `tests/unit/cli/test_explain.py` — CliRunner smoke test pour `vidscope explain`
- [ ] `config/taxonomy.yaml` — fichier données (~12 verticales, ~200 keywords total)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| E2E `vidscope add <url>` avec `VIDSCOPE_ANALYZER=heuristic` → tous les nouveaux champs populés | R053 | Appel réseau yt-dlp | `VIDSCOPE_ANALYZER=heuristic uv run vidscope add <instructional url> && uv run vidscope explain <id>` |
| LLM V2 avec `VIDSCOPE_ANALYZER=groq` → reasoning en JSON | R055 | Clé API nécessaire | `VIDSCOPE_ANALYZER=groq uv run vidscope add <url> && uv run vidscope explain <id>` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
