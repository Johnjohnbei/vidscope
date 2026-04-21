# GSD State

**Last Completed Milestone:** M011 (complete — S01/S02/S03/S04 all done, 36/36 verified)
**Active Slice:** M012/S03 — MCP output enrichi
**Phase:** M012 v1.12 Content Intelligence — S02 complete (2026-04-21)
**Requirements Status:** R060 ✅, R061 ✅ (M012/S01) | R062 ✅, R063 ✅ (M012/S02 complete 2026-04-21) | R064, R065 (M012/S03 pending) | R066 (M012/S04 pending)

## Milestone Registry
- ✅ **M001:** Pipeline ponctuel end-to-end
- ✅ **M002:** MCP server and related-video suggestions
- ✅ **M003:** Account monitoring and scheduled refresh
- ✅ **M004:** Pluggable LLM analyzers
- ✅ **M005:** Cookies UX improvements
- ✅ **M006:** Creator-as-first-class-entity
- ✅ **M007:** Rich content metadata — descriptions, links, hashtags, mentions, music
- ✅ **M008:** Visual intelligence on frames — OCR, thumbnail, content-shape
- ✅ **M009:** Engagement signals + velocity tracking (S01 ✅, S02 ✅, S03 ✅, S04 ✅)
- ✅ **M010:** Multi-dimensional scoring + controlled taxonomy (S01 ✅, S02 ✅, S03 ✅, S04 ✅)
- ✅ **M011:** Veille workflow layer — tracking, tags, collections, exports (S01 ✅, S02 ✅, S03 ✅, S04 ✅)

## Recent Decisions
- **M012/S02:** dataclasses.replace(raw_analysis, video_id) used instead of manual rebind — preserves all M010 additive fields automatically
- **M012/S02:** Synthetic OCR Transcript stays in-memory (never persisted to transcripts table) to avoid polluting non-audio content
- **M012/S02:** _FRENCH_CONTRACTIONS (37) + _FRENCH_COMMON_VERBS (74) as separate named frozensets unioned into FRENCH_STOPWORDS
- **M009/S04:** views_velocity_24h unit is views/HOUR (D-04) — the function name is misleading; min_velocity comparisons are in views/hour not views/day
- **M009/S04:** rank_candidates_by_delta fetches limit*5 candidates at SQL level so min_velocity Python filter still returns limit results
- **M009/S04:** MCP tool vidscope_trending uses inline window parser (not CLI import) to avoid violating mcp-has-no-adapters contract
- **M009/S04:** test_show_cmd.py and test_show_video.py not modified — pre-existing import errors (Creator, FrameText) are out of scope S04
- **M009/S04:** test_server.py updated from 6 to 7 tools (regression fix — vidscope_trending added)
- **M009/S03:** `list_by_author(platform, handle)` sur le champ `author` existant plutôt que `list_for_creator` sur un `creator_id` FK inexistant — le schéma `videos` utilise `author` comme lien au créateur
- **M009/S03:** `UnitOfWork` n'a pas de `creators` repo — approche sans lookup Creator, filtrage par `author=handle` directement
- **M009/S03:** Stats step isolé en try/except au niveau CLI (T-ISO-03) — failure globale n'empêche pas l'affichage du watch summary
- **M009/S02:** StatsStage lève DomainError (pas StageResult.ok) — pattern de VisualIntelligenceStage
- **M009/S01:** VideoStats.view_count <= 0 → engagement_rate None (Hypothesis gate)

## Blockers
- None

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| M009  | S01  | ~45min   | 1     | 21    |
| M009  | S02  | ~45min   | 3     | 11    |
| M009  | S03  | ~60min   | 2     | 8     |
| M009  | S04  | ~90min   | 3     | 16    |

## Next Action
M011 complete. All 11 milestones done. Next milestone TBD.
