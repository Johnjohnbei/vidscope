# M010 — Multi-dimensional scoring + controlled taxonomy

## Vision
Current `Analysis.score: float | None` is a single opaque 0–100 number. Users cannot know *why* a video scored 72 nor filter "only tutorials with high actionability". M010 replaces the flat score with a score vector: `information_density`, `actionability`, `novelty`, `production_quality`, `sentiment`, plus booleans `is_sponsored` and a `content_type` enum. A `reasoning` field (2–3 natural-language sentences) explains the verdict. Topic tagging moves from freeform keywords to a **controlled vertical taxonomy** (`config/taxonomy.yaml`: tech, beauty, fitness, finance, food…) so facet search works. Migration is **additive-compatible** (D032): old `score` column preserved, new columns nullable, existing rows remain valid until re-analyzed.

## Slice Overview

| ID | Slice | Risk | Depends | Done when |
|----|-------|------|---------|-----------|
| S01 | Extended Analysis entity + taxonomy config + migration | low | M001 (analysis seam) | `Analysis` extended with 7 new fields + `reasoning`, `taxonomy.yaml` loaded at startup, migration 009 adds nullable columns + `analysis_topics` side table for controlled vocabulary, port `TaxonomyCatalog`. |
| S02 | Heuristic analyzer V2 implements new fields | medium | S01 | `HeuristicAnalyzerV2` produces all new fields from transcript only (zero network): sentiment via lexicon, sponsor detection via keyword list, content_type via structural heuristics, topic mapping via keyword → taxonomy match. |
| S03 | LLM analyzers V2 + reasoning prompt | medium | S02, M004 | All 5 LLM providers upgraded to emit the JSON schema including reasoning. Prompt template centralised in `adapters/llm/_base.py`. JSON schema validation in `parse_llm_json` extended. |
| S04 | CLI facets + `vidscope explain` | low | S02 | `vidscope search --content-type tutorial --min-actionability 70 --sponsored false`, `vidscope explain <id>` prints per-dimension scores + reasoning, `vidscope show <id>` renders new fields. |

## Layer Architecture

| Slice | Layer | New/Changed files |
|-------|-------|-------------------|
| S01 | domain | `entities.py` (Analysis extended), `values.py` (+ContentType enum, +SentimentLabel, +Vertical) |
| S01 | ports | `taxonomy_catalog.py` (Protocol: verticals, keywords_for_vertical, match) |
| S01 | adapters/config | `adapters/config/yaml_taxonomy.py` **new submodule** |
| S01 | config | `config/taxonomy.yaml` **new repo file** (~12 verticals, ~200 keywords total) |
| S01 | adapters/sqlite | `migrations/009_analysis_v2.py` (nullable add), `analysis_repository.py` (extended), new `analysis_topics` table + repo |
| S02 | adapters/analyzer | `adapters/analyzer/heuristic_v2.py` (or bump existing), `adapters/analyzer/sentiment_lexicon.py` **new**, `adapters/analyzer/sponsor_detector.py` **new** |
| S02 | infrastructure | `analyzer_registry.py` (heuristic → V2 as default), backward-compat alias `heuristic-v1` |
| S03 | adapters/llm | `_base.py` (prompt + schema update), 5 providers unchanged in structure |
| S04 | application | `use_cases/explain_analysis.py`, `use_cases/search_videos.py` (facets) |
| S04 | cli | `main.py` (search facets), `explain.py` **new** |

## Test Strategy

| Test kind | Scope | Tooling |
|-----------|-------|---------|
| Domain unit | Analysis with new fields, enum exhaustiveness, Vertical validation against loaded taxonomy | pytest |
| Config unit | yaml_taxonomy loader validates schema (no duplicate verticals, keywords lowercase, no empty vertical) | pytest |
| Adapter unit — heuristic V2 | 20+ transcript fixtures covering each content_type + sponsored + sentiment classes. Every fixture asserts all 7 new fields populated with plausible values | pytest |
| Adapter unit — sentiment | Lexicon over 30 FR+EN fixtures (positive / negative / neutral / mixed / empty) | pytest |
| Adapter unit — sponsor | 15 fixtures: affiliate disclosure, discount code, "partnership with", "not sponsored", ambiguous | pytest |
| Adapter unit — LLM V2 | Each provider via httpx MockTransport returning sample JSON matching new schema, verify `parse_llm_json` accepts; sample truncation / malformed JSON handled gracefully | existing LLM test pattern |
| Migration unit | Apply migration to fixture DB with pre-M010 rows, verify old rows untouched, new columns NULL, re-analyzing populates them | pytest |
| CLI snapshot | `vidscope search --content-type tutorial`, `vidscope explain <id>` | CliRunner |
| Architecture | 9+ contracts green, `config-adapter-is-self-contained` new contract | lint-imports |
| E2E live | `verify-m010.sh`: `vidscope add <instructional Reel>` with `VIDSCOPE_ANALYZER=heuristic` → assert all new fields populated; repeat with `VIDSCOPE_ANALYZER=groq` if key set; `vidscope explain <id>` shows reasoning | bash |
| Regression | Re-run all M001-M005 E2E verify-*.sh scripts post-M010 migration, all must stay green | bash |

### Ground-truth fixture set
S02 ships `tests/fixtures/analysis_golden.jsonl` — 40 hand-labelled transcripts with expected `content_type` + `is_sponsored` + `sentiment`. Heuristic V2 must hit ≥ 70% match rate on this golden set. LLM providers must hit ≥ 85%. Blocks merge if regression.

## Requirements Mapping

- Closes R053 (score vector + is_sponsored + content_type), R054 (controlled taxonomy), R055 (reasoning).
- Preserves all previously validated requirements (R004 still holds with `score` + summary, just augmented).

## Out of Scope (explicit)

- No per-sentence sentiment — whole-video label only.
- No automatic taxonomy expansion — `taxonomy.yaml` is edited by hand; a "suggest new vertical" ML pass is future work.
- No audience-fit scoring — not enough signal without external user context.
- No style transfer / rewrite of summary — summary field remains a factual 200-char blurb.
