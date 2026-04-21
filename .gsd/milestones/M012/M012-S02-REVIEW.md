---
phase: M012/S02
status: advisory
reviewed_at: 2026-04-21
depth: standard
files_reviewed: 2
files_reviewed_list:
  - src/vidscope/pipeline/stages/analyze.py
  - src/vidscope/adapters/heuristic/stopwords.py
findings:
  critical: 0
  warning: 1
  advisory: 3
  info: 1
  total: 5
---

# M012/S02 — Rapport de Code Review

**Revue du :** 2026-04-21
**Profondeur :** standard (analyse par fichier + vérification des contrats inter-couches)
**Fichiers revus :** 2
**Statut :** advisory (1 warning, 3 advisory, 0 critical)

## Résumé

Les deux fichiers sources de M012/S02 sont propres, bien documentés et
conformes aux exigences R062 et R063. L'implémentation de l'OCR fallback
dans `AnalyzeStage` est correcte : la concaténation filtre les lignes
vides/whitespace, le Transcript synthétique n'est jamais persisté, et
`dataclasses.replace` préserve correctement tous les champs M010.
L'extension de `stopwords.py` est structurée avec les deux frozensets
privés `_FRENCH_CONTRACTIONS` (37 entrées) et `_FRENCH_COMMON_VERBS`
(74 entrées) unionés proprement dans `FRENCH_STOPWORDS` (288 entrées).

Un point de vigilance non critique mérite attention : `AnalyzeStage.execute`
accède à `uow.frame_texts` alors que ce champ n'est **pas déclaré** dans le
`UnitOfWork` Protocol (port). Le code fonctionne en production via
`SqliteUnitOfWork`, mais le contrat de port est incomplet et l'accès à un
mock/stub sans `frame_texts` lèverait `AttributeError` à l'exécution plutôt
qu'une erreur mypy au build. C'est le finding principal (warning).

---

## Findings

| ID | Sévérité | Fichier | Ligne | Finding |
|----|----------|---------|-------|---------|
| W-01 | warning | `src/vidscope/pipeline/stages/analyze.py` | 79 | `uow.frame_texts` absent du Protocol `UnitOfWork` — contrat de port incomplet |
| A-01 | advisory | `src/vidscope/adapters/heuristic/stopwords.py` | 54-71 | Entrées `n'a` (3 chars) et `j'y` (3 chars) redondantes dans `_FRENCH_CONTRACTIONS` |
| A-02 | advisory | `src/vidscope/adapters/heuristic/stopwords.py` | 94, 99 | Entrées `dit` (3 chars) et `mis` (3 chars) redondantes dans `_FRENCH_COMMON_VERBS` |
| A-03 | advisory | `src/vidscope/adapters/heuristic/stopwords.py` | 122 | Entrée `là-bas` unreachable — le tokenizer la découpe en `['là', 'bas']` (tiret non capturé) |
| I-01 | info | `src/vidscope/pipeline/stages/analyze.py` | 80-81 | Double évaluation de `ft.text.strip()` dans le filtre OCR — mineure |

---

## Détails

### W-01 — `uow.frame_texts` absent du Protocol `UnitOfWork`

**Fichier :** `src/vidscope/pipeline/stages/analyze.py:79`

**Issue :**
`AnalyzeStage.execute` appelle `uow.frame_texts.list_for_video(ctx.video_id)` (ligne 79),
mais `frame_texts` n'est pas déclaré dans le Protocol `UnitOfWork`
(`src/vidscope/ports/unit_of_work.py`). Le Protocol liste : `videos`,
`transcripts`, `frames`, `analyses`, `pipeline_runs`, `search_index`, ainsi que
les repos ajoutés ultérieurement — mais **pas** `frame_texts`.

`SqliteUnitOfWork` déclare et initialise bien `self.frame_texts` (ligne 111
et 135 de `unit_of_work.py`), donc le code fonctionne en production.
Cependant :

- Un mypy strict sur la signature `execute(self, ctx, uow: UnitOfWork)` détecte
  que `uow.frame_texts` n'existe pas sur le type `UnitOfWork` et lève une erreur.
- N'importe quel mock ou stub implémentant le Protocol `UnitOfWork` (et pas
  `SqliteUnitOfWork`) manquera `frame_texts` → `AttributeError` à l'exécution.
- Les tests utilisent directement `SqliteUnitOfWork(engine)`, ce qui masque le
  problème.

**Fix :**
Ajouter `frame_texts: FrameTextRepository` au Protocol `UnitOfWork` dans
`src/vidscope/ports/unit_of_work.py` :

```python
# src/vidscope/ports/unit_of_work.py

from vidscope.ports.repositories import (
    AnalysisRepository,
    CollectionRepository,
    FrameRepository,
    FrameTextRepository,   # ajouter cet import
    PipelineRunRepository,
    ...
)

@runtime_checkable
class UnitOfWork(Protocol):
    videos: VideoRepository
    transcripts: TranscriptRepository
    frames: FrameRepository
    frame_texts: FrameTextRepository   # ajouter cette ligne
    analyses: AnalysisRepository
    pipeline_runs: PipelineRunRepository
    search_index: SearchIndex
    ...
```

---

### A-01 — Entrées `n'a` et `j'y` redondantes dans `_FRENCH_CONTRACTIONS`

**Fichier :** `src/vidscope/adapters/heuristic/stopwords.py:54-71`

**Issue :**
`_FRENCH_CONTRACTIONS` contient `"n'a"` (3 chars) et `"j'y"` (3 chars).
Or `_MIN_KEYWORD_LENGTH = 4` dans `analyzer.py` élimine déjà tout token
de longueur inférieure à 4, **avant** la vérification des stopwords.
Ces deux entrées ne peuvent donc jamais produire d'effet filtrant.

Le `SUMMARY.md` documente ce choix : elles ont été ajoutées pour satisfaire
les assertions de T03. Ce choix est délibéré mais crée une incohérence entre
le commentaire du module (« All >= 4 chars — shorter forms already dropped by
_MIN_KEYWORD_LENGTH ») et la réalité du contenu des frozensets.

**Fix :**
Soit retirer ces deux entrées et supprimer les assertions de T03 qui les
testent explicitement (car elles testent un comportement sans effet réel),
soit mettre à jour le commentaire du module pour refléter la présence
intentionnelle d'entrées < 4 chars :

```python
# R063 (M012/S02) — French contractions.
# NOTE: some entries are < 4 chars (e.g. "j'y", "n'a"). These are already
# filtered by _MIN_KEYWORD_LENGTH=4 in analyzer.py, but are kept here for
# explicit membership tests (test_stopwords.py T03 canonical list).
```

---

### A-02 — Entrées `dit` et `mis` redondantes dans `_FRENCH_COMMON_VERBS`

**Fichier :** `src/vidscope/adapters/heuristic/stopwords.py:94, 99`

**Issue :**
Même problème que A-01 : `"dit"` (3 chars, ligne 94) et `"mis"` (3 chars,
ligne 99) dans `_FRENCH_COMMON_VERBS` sont sous le seuil `_MIN_KEYWORD_LENGTH=4`.
Le commentaire du module est également en contradiction avec leur présence.

**Fix :** Même approche que A-01 — aligner commentaire et contenu, ou
supprimer les entrées et leurs assertions dans les tests.

---

### A-03 — Entrée `là-bas` unreachable dans `FRENCH_STOPWORDS`

**Fichier :** `src/vidscope/adapters/heuristic/stopwords.py:122`

**Issue :**
`FRENCH_STOPWORDS` contient `"là-bas"`. Or le tokenizer
`_WORD_PATTERN = r"[a-zàâäéèêëïîôöùûüÿçœæ']+"` ne capture **pas** le tiret
(`-`), donc `"là-bas"` produit deux tokens : `["là", "bas"]`. Le token
`"là-bas"` en tant que tel ne peut jamais être produit par `_tokenize`, et
cette entrée dans le frozenset ne peut jamais servir à filtrer quoi que ce
soit.

De plus, `"bas"` (3 chars) serait de toute façon éliminé par
`_MIN_KEYWORD_LENGTH=4`, donc il n'y a pas de bug fonctionnel. Mais
`"là-bas"` est une entrée morte dans FRENCH_STOPWORDS (héritée avant M012).

**Fix :**
Retirer `"là-bas"` de `FRENCH_STOPWORDS` (entrée inefficace) ou la remplacer
par une mention dans un commentaire explicatif. Ce n'est pas une régression
M012/S02 mais un nettoyage à prévoir.

---

### I-01 — Double évaluation implicite de `ft.text.strip()` dans le filtre OCR

**Fichier :** `src/vidscope/pipeline/stages/analyze.py:80-81`

**Issue :**
```python
ocr_concat = " ".join(
    ft.text for ft in frame_texts if ft.text and ft.text.strip()
)
```

La condition `ft.text and ft.text.strip()` évalue `ft.text.strip()` deux fois
implicitement (une fois dans `and`, une fois on ignore le résultat). Python
court-circuite correctement quand `ft.text` est falsy, donc pas de bug, mais
le code est légèrement redondant : si `ft.text` est truthy mais blanc,
`ft.text.strip()` est évalué une seule fois. La formulation est donc correcte
et sans coût notable pour les volumes OCR attendus.

Alternative plus idiomatique si la lisibilité est souhaitée :

```python
ocr_concat = " ".join(
    ft.text for ft in frame_texts if ft.text.strip()
)
```

`ft.text.strip()` sur une chaîne vide (`""`) retourne `""` (falsy) — le
`ft.text and` préfixe est donc superflu puisque `"".strip()` est déjà falsy.
La version simplifiée est strictement équivalente et légèrement plus lisible.

Note : si `ft.text` pouvait être `None` (ce que le dataclass `FrameText`
n'autorise pas — `text: str` sans `None`), la garde `ft.text and` serait
nécessaire. Mais comme `FrameText.text: str` est non-nullable, elle est
redondante.

---

## Points validés (conformes)

- **R062 `is_satisfied`** : le court-circuit IMAGE/CAROUSEL est correctement supprimé. La logique `video_id is None → False`, `get_latest_for_video → not None → True` est correcte et idempotente.
- **R062 `execute` OCR fallback** : `uow.frame_texts.list_for_video` appelé uniquement quand `transcript is None`. Filtrage des lignes vides/whitespace correct. Transcript synthétique non persisté.
- **R062 `Language.UNKNOWN`** : utilisé exactement une fois, pour le Transcript synthétique OCR.
- **R062 M010 passthrough** : `dataclasses.replace(raw_analysis, video_id=ctx.video_id)` préserve tous les champs M010 (verticals, information_density, actionability, novelty, production_quality, sentiment, is_sponsored, content_type, reasoning). Résout aussi la dette latente du rebind manuel pré-R062.
- **R063 `_FRENCH_CONTRACTIONS`** : 37 entrées, intersection avec `_FRENCH_COMMON_VERBS` = vide (pas de doublon entre sets privés).
- **R063 `_FRENCH_COMMON_VERBS`** : 74 entrées, bien au-dessus du minimum de 40 requis.
- **R063 `FRENCH_STOPWORDS`** : 288 entrées (>= 100 requis). `ALL_STOPWORDS == ENGLISH_STOPWORDS | FRENCH_STOPWORDS` vérifié.
- **Sécurité** : aucune injection SQL (paramètres bind SQLAlchemy), aucun `eval`, aucun secret hardcodé. Conforme au threat model T-M012S02-01.
- **Immutabilité** : `Transcript` et `Analysis` sont des `@dataclass(frozen=True)` ; `replace()` retourne un nouvel objet. Aucune mutation.
- **Taille des fichiers** : `analyze.py` 114 lignes (< 300), `stopwords.py` 132 lignes (< 200). Dans les limites du CLAUDE.md.
- **DoS** : accepté par le threat model (T-M012S02-03). `_build_summary` tronque à 200 chars, `Counter.most_common(8)` est O(n). Conforme.

---

_Révisé le : 2026-04-21_
_Réviseur : Claude (gsd-code-reviewer)_
_Profondeur : standard_
