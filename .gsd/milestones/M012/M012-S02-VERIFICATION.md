---
phase: M012-S02
verified: 2026-04-21T10:30:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase M012/S02 : Analyze intelligence carousel — Rapport de vérification

**Objectif de la phase :** AnalyzeStage OCR fallback pour IMAGE/CAROUSEL (R062) + Extension stopwords français éliminant le bruit grammatical des keywords (R063).
**Vérifié le :** 2026-04-21T10:30:00Z
**Statut :** PASSED
**Re-vérification :** Non — vérification initiale

---

## Résultat par rapport à l'objectif

### Vérités observables

| # | Vérité | Statut | Preuve |
|---|--------|--------|--------|
| 1 | `AnalyzeStage.is_satisfied` ne court-circuite plus IMAGE/CAROUSEL — retourne False si aucune ligne `analyses` existe, True sinon, quel que soit le media_type | VERIFIE | `analyze.py:46-49` — bloc IMAGE/CAROUSEL supprimé, logique réduite à `video_id is None → False` puis `get_latest_for_video → not None → True`. Grep confirme 0 occurrence de `if ctx.media_type in (MediaType.IMAGE, MediaType.CAROUSEL)` |
| 2 | `AnalyzeStage.execute` construit un Transcript synthétique depuis `uow.frame_texts.list_for_video(video_id)` quand `transcript is None`, filtre les lignes vides/whitespace, concatène avec espace simple | VERIFIE | `analyze.py:74-88` — branche `if transcript is None:` appelle `uow.frame_texts.list_for_video(ctx.video_id)`, filtre `ft.text and ft.text.strip()`, construit `Transcript(video_id, Language.UNKNOWN, ocr_concat, segments=())` |
| 3 | `Language.UNKNOWN` utilisé pour le Transcript OCR synthétique — AnalysisError jamais levée à cause d'un transcript None (carousel vide → stub Analysis score=0, summary="no speech detected") | VERIFIE | `analyze.py:85` — `Language.UNKNOWN` présent exactement 1 fois. Smoke test R062 confirme `a.score == 0.0` et `a.summary == 'no speech detected'` pour un carousel sans frame_texts ni transcript |
| 4 | Champs M010 additifs (verticals, information_density, actionability, novelty, production_quality, sentiment, is_sponsored, content_type, reasoning) préservés via `dataclasses.replace` | VERIFIE | `analyze.py:99` — `analysis = replace(raw_analysis, video_id=ctx.video_id)` copie tous les champs M010 automatiquement. Import `from dataclasses import replace` à ligne 13. Résout aussi la dette latente du rebind manuel pré-R062. |
| 5 | `FRENCH_STOPWORDS` contient >= 30 contractions (c'est, j'ai, d'un, qu'il, n'est, s'il, etc.) et >= 40 formes verbales conjuguées (veux, peux, pouvez, montrer, etc.) dans deux frozensets privés `_FRENCH_CONTRACTIONS` et `_FRENCH_COMMON_VERBS` | VERIFIE | `stopwords.py:54-102` — `_FRENCH_CONTRACTIONS` = 37 entrées, `_FRENCH_COMMON_VERBS` = 74 entrées. Smoke test confirme les tailles. Toutes les formes canoniques des tests sont présentes. |
| 6 | `ALL_STOPWORDS` filtre `c'est`, `j'ai`, `d'un`, `qu'il`, `veux`, `peux`, `pouvez`, `montrer` | VERIFIE | `stopwords.py:131` — `ALL_STOPWORDS = ENGLISH_STOPWORDS | FRENCH_STOPWORDS`. Smoke test R063 confirme chacun des 10 mots requis dans ALL_STOPWORDS. `HeuristicAnalyzer._is_meaningful_word` délègue au check `token not in ALL_STOPWORDS`. |
| 7 | `FRENCH_STOPWORDS` et `ENGLISH_STOPWORDS` contiennent chacun >= 100 entrées | VERIFIE | FRENCH_STOPWORDS = 288 entrées, ENGLISH_STOPWORDS = 196 entrées. Smoke test confirme. Largement au-dessus des 100 requis par R063. |
| 8 | Les 2 tests M010 obsolètes (`test_is_satisfied_returns_true_for_image` et `test_is_satisfied_returns_true_for_carousel`) sont SUPPRIMÉS et remplacés par `TestAnalyzeStageMediaTypeR062` (4 tests) + `TestAnalyzeStageOcrFallback` (4 tests) | VERIFIE | Grep sur `test_analyze.py` : 0 occurrence des anciens noms. `class TestAnalyzeStageMediaTypeR062` présente à ligne 206, `class TestAnalyzeStageOcrFallback` à ligne 330, `test_carousel_with_frame_texts_produces_analysis` à ligne 333. `test_missing_transcript_raises` supprimé et remplacé par `test_missing_transcript_no_ocr_produces_empty_analysis` (ligne 146). |
| 9 | Suite unit complète `pytest tests/unit -q` : >= 1673 tests, 0 failed | VERIFIE | Résultat : **1673 passed, 0 failed**, 180 warnings (uniquement SQLite DeprecationWarning Python 3.12 — hors scope), 49.46s. Baseline M012/S01 : 1658. Gain net : +15 tests (17 ajoutés - 2 supprimés). |

**Score : 9/9 vérités confirmées**

---

### Artefacts requis

| Artefact | Attendu | Statut | Détails |
|----------|---------|--------|---------|
| `src/vidscope/pipeline/stages/analyze.py` | AnalyzeStage avec OCR fallback carousel/image + is_satisfied corrigé | VERIFIE | 114 lignes, contient `uow.frame_texts.list_for_video`, `Language.UNKNOWN`, `replace(raw_analysis, video_id=ctx.video_id)` |
| `src/vidscope/adapters/heuristic/stopwords.py` | FRENCH_STOPWORDS étendu avec contractions + verbes courants | VERIFIE | 132 lignes, contient `_FRENCH_CONTRACTIONS` (37 entrées) et `_FRENCH_COMMON_VERBS` (74 entrées) unionés dans FRENCH_STOPWORDS (288 entrées) |
| `tests/unit/pipeline/stages/test_analyze.py` | Tests R062 — OCR fallback carousel, comportement is_satisfied, stub empty-source | VERIFIE | Contient `TestAnalyzeStageMediaTypeR062` (4 tests) et `TestAnalyzeStageOcrFallback` (4 tests) avec `test_carousel_with_frame_texts_produces_analysis` |
| `tests/unit/adapters/heuristic/test_analyzer.py` | Tests R063 — contractions françaises + verbes conjugués filtrés des keywords | VERIFIE | Contient `TestHeuristicAnalyzerFrenchStopwordsR063` (ligne 183) avec `test_french_contractions_excluded_from_keywords` |
| `tests/unit/adapters/heuristic/test_stopwords.py` | Tests de couverture du vocabulaire R063 — taille minimale + appartenance explicite | VERIFIE | Fichier nouveau, 6 tests dans 3 classes (`TestStopwordSetSizes`, `TestFrenchContractions`, `TestFrenchConjugatedVerbs`) |

---

### Vérification des liens clés (wiring)

| De | Vers | Via | Statut | Détails |
|----|------|-----|--------|---------|
| `analyze.py::AnalyzeStage.is_satisfied` | `uow.analyses.get_latest_for_video` | Indépendamment du media_type (plus de court-circuit IMAGE/CAROUSEL) | VERIFIE | `analyze.py:48` — unique chemin de retour, pas de branche media_type |
| `analyze.py::AnalyzeStage.execute` | `uow.frame_texts.list_for_video` | OCR fallback quand transcript is None — concaténation de FrameText.text | VERIFIE | `analyze.py:79` — appelé dans la branche `if transcript is None:` |
| `analyze.py::AnalyzeStage.execute` | `vidscope.domain.Transcript + Language.UNKNOWN` | Transcript synthétique construit en mémoire depuis OCR concat (jamais persisté) | VERIFIE | `analyze.py:83-88` — construction explicite avec `language=Language.UNKNOWN` |
| `stopwords.py::FRENCH_STOPWORDS` | `_FRENCH_CONTRACTIONS | _FRENCH_COMMON_VERBS` | Union frozenset au niveau module | VERIFIE | `stopwords.py:129` — `}) | _FRENCH_CONTRACTIONS | _FRENCH_COMMON_VERBS` |
| `analyzer.py::_is_meaningful_word` | `ALL_STOPWORDS` membership check | `token not in ALL_STOPWORDS` filtre contractions + verbes conjugués | VERIFIE | Inchangé — stopwords.py fournit les données, analyzer.py consomme via `ALL_STOPWORDS`. Testé indirectement par `TestHeuristicAnalyzerFrenchStopwordsR063`. |
| `ports/unit_of_work.py::UnitOfWork` | `FrameTextRepository` | Déclaration `frame_texts: FrameTextRepository` dans le Protocol | VERIFIE | `unit_of_work.py:68` — `frame_texts: FrameTextRepository` présent. Le warning W-01 de la code review (contrat de port incomplet) est déjà résolu. |

---

### Trace du flux de données (Niveau 4)

| Artefact | Variable de données | Source | Produit des données réelles | Statut |
|----------|---------------------|--------|----------------------------|--------|
| `analyze.py::AnalyzeStage.execute` | `transcript.full_text` | `uow.frame_texts.list_for_video(ctx.video_id)` → concaténation OCR OU `uow.transcripts.get_for_video(ctx.video_id)` | Oui — requête DB via bind params SQLAlchemy, concaténation des FrameText.text non-vides | FLOWING |
| `analyze.py::AnalyzeStage.execute` | `analysis` | `self._analyzer.analyze(transcript)` → `replace(raw_analysis, video_id=ctx.video_id)` → `uow.analyses.add(analysis)` | Oui — toute la chaîne est câblée, smoke test confirme la persistance | FLOWING |

---

### Vérifications comportementales (Spot-checks)

| Comportement | Commande | Résultat | Statut |
|-------------|---------|---------|--------|
| R062 : carousel sans frame_texts → stub Analysis score=0 | smoke test Python in-memory | `R062 smoke OK: heuristic 0.0 no speech detected` | PASS |
| R063 : stopwords >= 100 chacun + formes canoniques présentes | smoke test Python imports | `R063 OK: FR 288 EN 196` — 10/10 formes canoniques dans ALL_STOPWORDS | PASS |
| Suite unit complète — zéro régression | `pytest tests/unit -q` | `1673 passed, 0 failed` | PASS |

---

### Couverture des exigences

| Exigence | Plan | Description | Statut | Preuve |
|----------|------|-------------|--------|--------|
| R062 | M012/S02 | Pour les contenus image/carousel (sans audio), l'AnalyzeStage produit une analyse en utilisant le texte OCR (frame_texts) comme substitut du transcript | SATISFAIT | `is_satisfied` ne court-circuite plus ; `execute()` OCR fallback câblé ; smoke test confirme Analysis non-null pour carousel vide et carousel avec frame_texts |
| R063 | M012/S02 | L'analyse heuristique filtre les stopwords français et anglais des keywords et topics (listes d'au moins 100 mots chacune) | SATISFAIT | FRENCH_STOPWORDS=288, ENGLISH_STOPWORDS=196 ; 37 contractions + 74 formes verbales ; ALL_STOPWORDS filtre les 10 formes canoniques testées |

---

### Anti-patterns détectés

| Fichier | Ligne | Pattern | Sévérité | Impact |
|---------|-------|---------|----------|--------|
| `stopwords.py` | 52-53 | Commentaire "All >= 4 chars" incohérent avec la présence de `j'y` (3 chars) et `n'a` (3 chars) dans `_FRENCH_CONTRACTIONS` | Info | Nul — fonctionnellement inoffensif (`_MIN_KEYWORD_LENGTH=4` élimine ces tokens avant vérification des stopwords). Signalé A-01 dans REVIEW.md. |
| `stopwords.py` | 94,99 | `dit` (3 chars) et `mis` (3 chars) dans `_FRENCH_COMMON_VERBS` sous le seuil `_MIN_KEYWORD_LENGTH=4` | Info | Nul — mêmes raisons que A-01. Signalé A-02 dans REVIEW.md. |
| `stopwords.py` | 122 | Entrée `là-bas` unreachable (le tokenizer ne capture pas le tiret) | Info | Nul — héritage pré-M012, aucun impact fonctionnel. Signalé A-03 dans REVIEW.md. |
| `analyze.py` | 81 | `ft.text and ft.text.strip()` — `ft.text and` est redondant puisque `"".strip()` est déjà falsy | Info | Nul — `FrameText.text: str` est non-nullable. Signalé I-01 dans REVIEW.md. |

Aucun anti-pattern bloquant (stub, placeholder, import non utilisé, handler vide). Tous les findings sont de niveau Advisory/Info et documentés dans REVIEW.md.

---

### Vérification humaine requise

Aucun élément ne nécessite de vérification humaine pour cette phase. Les comportements clés (is_satisfied, OCR fallback, stopwords) sont entièrement vérifiables par tests automatisés et smoke tests.

---

## Résumé des écarts vs PLAN

### Mineurs (non-bloquants)

1. **test_stopwords.py : 6 tests au lieu de 7** — Le PLAN mentionnait `test_stopword_sets_meet_minimum_size` comme nom de test dans le champ `contains` de l'artefact. L'implémentation a créé deux tests distincts plus fins : `test_french_stopwords_meet_minimum_size` et `test_english_stopwords_meet_minimum_size`. La couverture est équivalente ou supérieure.

2. **Comment incohérent dans stopwords.py** — Le commentaire "All >= 4 chars" est en contradiction avec la présence de `j'y` et `n'a` (3 chars). Le SUMMARY.md documente ce choix délibéré (exigé par les assertions de T03). Advisory A-01/A-02 dans REVIEW.md, sans impact fonctionnel.

3. **Warning W-01 de la code review déjà résolu** — `frame_texts: FrameTextRepository` est bien déclaré dans le Protocol `UnitOfWork` (`unit_of_work.py:68`). Le finding W-01 de REVIEW.md est déjà corrigé dans la base de code actuelle.

---

_Vérifié le : 2026-04-21T10:30:00Z_
_Vérificateur : Claude (gsd-verifier)_
