# M012 — Content Intelligence (v1.12)

**Milestone goal:** Rendre tous les types de contenus ingérés (carousel, reel, vidéo) pleinement exploitables par un agent — métadonnées cohérentes, analyse sur OCR, output MCP enrichi.

**Requirements covered:** R060, R061, R062, R063, R064, R065, R066 (7/7)

---

## Phases

- [x] **M012/S01: Metadata cohérence à l'ingestion** — Caption et engagement initial capturés dès l'ingestion dans InstaLoaderDownloader et YtdlpDownloader (2026-04-20)
- [ ] **M012/S02: Analyze intelligence carousel** — AnalyzeStage avec fallback OCR + stopwords FR/EN dans HeuristicAnalyzer
- [ ] **M012/S03: MCP output enrichi** — vidscope_get_video expose description, engagement et ocr_preview pour les carousels
- [ ] **M012/S04: Audit dead code inter-adapters** — Review cross-adapter InstaLoader/yt-dlp/Fallback, suppression de la dette silencieuse

---

## Phase Details

### M012/S01: Metadata cohérence à l'ingestion
**Goal**: Tout contenu ingéré dispose d'une description et d'un engagement initial en DB dès la fin de l'ingestion, sans étape supplémentaire
**Depends on**: M011 (complete)
**Requirements**: R060, R061
**Success Criteria** (what must be TRUE):
  1. Après `vidscope add <instagram-carousel-url>`, `videos.description` contient la caption du post (non-null si le post a une caption)
  2. Après `vidscope add <url>`, `video_stats` contient une ligne avec `like_count` et/ou `comment_count` si la plateforme les fournit — sans avoir à exécuter `vidscope refresh-stats`
  3. `vidscope show <id>` affiche la description et les compteurs d'engagement pour un contenu fraîchement ingéré
  4. L'ingestion sans caption disponible (vidéo sans description yt-dlp) ne génère pas d'erreur — `description` reste null gracieusement
**Plans**: 1 plan
  - [x] M012-S01-PLAN.md — Schema migration + IngestOutcome extension + downloaders + IngestStage wiring (2026-04-20)

### M012/S02: Analyze intelligence carousel
**Goal**: L'analyse heuristique produit des résultats exploitables pour tout type de contenu — les carousels image/texte sont analysés via OCR et les topics sont des termes métier significatifs
**Depends on**: M012/S01
**Requirements**: R062, R063
**Success Criteria** (what must be TRUE):
  1. Un carousel avec `frame_texts` et `transcript=None` produit une ligne `analyses` non-null après `vidscope add` — `analysis: null` n'apparaît plus pour un contenu ayant du texte OCR
  2. Les keywords et topics heuristiques ne contiennent plus de mots grammaticaux (ex. "c'est", "veux", "les", "the", "and") — seuls des termes sémantiquement significatifs sont retenus
  3. Pour le carousel "Claude skills for Architects!", les topics reflètent le domaine (ex. "terminal", "claude", "agent", "workflow") et non des mots vides
  4. Les carousels sans caption ni OCR ni transcript produisent score=0 et summary approprié — pas de crash ni de comportement indéfini
**Plans**: 1 plan
  - [ ] M012-S02-PLAN.md — R062 AnalyzeStage OCR fallback + is_satisfied fix ; R063 FRENCH_STOPWORDS extended (contractions + conjugated verbs)

### M012/S03: MCP output enrichi
**Goal**: Un agent obtient un portrait complet d'un contenu (description, engagement, aperçu OCR pour carousels) en un seul appel `vidscope_get_video`
**Depends on**: M012/S01, M012/S02
**Requirements**: R064, R065
**Success Criteria** (what must be TRUE):
  1. `vidscope_get_video` retourne `description` (string ou null) et `latest_engagement` (dict avec `like_count`, `comment_count`, ou null si absent)
  2. Pour un carousel, `vidscope_get_video` retourne un champ `ocr_preview` contenant les 5 premiers blocs OCR concaténés, plus une indication que `vidscope_get_frame_texts` expose le contenu complet
  3. Pour un reel ou une vidéo non-carousel, `ocr_preview` est absent ou null — pas de bruit inutile dans la réponse
  4. Un agent peut déterminer le type de contenu et son richesse informative en un seul appel MCP, sans appel supplémentaire pour les métadonnées de base
**Plans**: TBD

### M012/S04: Audit dead code inter-adapters
**Goal**: Les trois adapters downloader (InstaLoaderDownloader, YtdlpDownloader, FallbackDownloader) sont cohérents dans leur contrat, sans chemins morts ni logique dupliquée non justifiée
**Depends on**: M012/S01, M012/S02, M012/S03
**Requirements**: R066
**Success Criteria** (what must be TRUE):
  1. Tous les champs de `IngestOutcome` sont mappés de manière cohérente dans les trois adapters — aucun champ n'est silencieusement ignoré ou toujours null dans un adapter sans documentation explicite
  2. Les méthodes `probe` et `list_channel_videos` ont un statut clair dans chaque adapter : implémentées, intentionnellement non-implémentées (raise NotImplementedError avec message), ou supprimées si hors scope
  3. La suite de tests couvre les chemins identifiés comme manquants lors de l'audit — pas de new code sans test
  4. Les simplifications identifiées (logique dupliquée, dead branches) sont appliquées sans régression sur les 618+ tests existants
**Plans**: TBD

---

## Progress Table

| Slice | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| M012/S01 — Metadata ingestion | 1/1 | Complete | 2026-04-20 |
| M012/S02 — Analyze carousel | 0/1 | Planned | - |
| M012/S03 — MCP enrichi | 0/? | Not started | - |
| M012/S04 — Audit adapters | 0/? | Not started | - |

---

## Coverage Map

| Requirement | Slice | Status |
|-------------|-------|--------|
| R060 — description/caption à l'ingestion | M012/S01 | Complete |
| R061 — engagement initial à l'ingestion | M012/S01 | Complete |
| R062 — AnalyzeStage fallback OCR carousel | M012/S02 | Planned |
| R063 — stopwords FR+EN HeuristicAnalyzer | M012/S02 | Planned |
| R064 — vidscope_get_video enrichi (description + engagement) | M012/S03 | Pending |
| R065 — vidscope_get_video ocr_preview carousel | M012/S03 | Pending |
| R066 — audit dead code inter-adapters | M012/S04 | Pending |

**Coverage: 7/7 requirements mapped. No orphans.**
