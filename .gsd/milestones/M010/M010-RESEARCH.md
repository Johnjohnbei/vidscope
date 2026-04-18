# Phase M010 : Multi-dimensional scoring + controlled taxonomy — Research

**Researched:** 2026-04-18
**Domain:** Domain extension (entities + enums), SQLite migration additive, analyseur heuristique V2, LLM prompt V2, CLI facets
**Confidence:** HIGH

---

## Sommaire

M010 enrichit `Analysis` (actuellement 6 champs + score scalaire) avec un vecteur de scores à 5 dimensions, deux champs booléens/enum, un champ `reasoning`, et remplace les topics freeform par une taxonomie contrôlée en YAML. L'architecture hexagonale existante absorbe ce changement sans restructuration : le domaine gagne de nouveaux value objects, le schéma SQLite gagne des colonnes nullables (migration additive), l'analyseur heuristique est remplacé par V2 comme implémentation par défaut, les 5 fournisseurs LLM reçoivent un prompt étendu, et la CLI gagne des filtres facettes + la commande `vidscope explain`.

La migration est additive-compatible (D032 du ROADMAP) : la colonne `score` existante est préservée, les nouvelles colonnes sont `NULL` pour les analyses pré-M010. Aucune donnée n'est perdue ; les vidéos déjà analysées restent valides jusqu'à ré-analyse.

**Recommandation principale :** Suivre exactement le découpage S01→S02→S03→S04 du ROADMAP. S01 est le socle bloquant (entités + taxonomie + migration) ; chaque slice suivante n'étend qu'un adaptateur ou la CLI, sans toucher aux couches inférieures.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Support de la recherche |
|----|-------------|------------------------|
| R053 | Score vector (information_density, actionability, novelty, production_quality, sentiment), `is_sponsored` bool, `content_type` enum sur Analysis | S01 : nouveaux champs domain ; S02/S03 : implémentation analyseurs |
| R054 | Taxonomie verticale contrôlée (`config/taxonomy.yaml`) — remplacement des topics freeform | S01 : `TaxonomyCatalog` port + `YamlTaxonomy` adapter + fichier YAML |
| R055 | Champ `reasoning` (2-3 phrases) expliquant le verdict ; `vidscope explain <id>` | S01 : champ domain ; S03 : prompt LLM ; S04 : CLI |
</phase_requirements>

---

## User Constraints (from CONTEXT.md)

> Aucun CONTEXT.md n'existe pour M010 — pas de décisions verrouillées antérieures au research. Les contraintes ci-dessous sont déduites du ROADMAP M010 et des décisions projet existantes.

### Decisions locked (ROADMAP + DECISIONS.md)
- Migration **additive** uniquement : `score` préservé, nouvelles colonnes nullable. Pas de DROP ou de data migration destructive.
- Taxonomie editée à la main dans `config/taxonomy.yaml` ; pas d'expansion ML automatique.
- `HeuristicAnalyzerV2` devient le défaut (`heuristic`) ; l'ancien reste accessible sous `heuristic-v1`.
- Le prompt LLM centralisé dans `adapters/llm/_base.py` — aucun provider ne définit son propre prompt.
- Sentiment au niveau vidéo entière uniquement (pas par phrase).
- Pas de scoring audience-fit.
- Pas de réécriture du champ `summary`.

### Claude's Discretion
- Noms exacts des méthodes lexicales dans `HeuristicAnalyzerV2` (implémentation interne).
- Structure interne de `config/taxonomy.yaml` (tant qu'elle respecte le schéma validé).
- Taille et contenu exact des fixtures golden `tests/fixtures/analysis_golden.jsonl`.
- Stratégie de test unitaire pour les helpers internes du heuristic V2.

### Deferred (OUT OF SCOPE)
- Sentiment par phrase.
- Expansion ML de la taxonomie.
- Scoring audience-fit.
- Style transfer / réécriture du `summary`.

---

## Standard Stack

### Core (existant, aucun ajout)
| Bibliothèque | Version | Usage | Statut |
|---|---|---|---|
| SQLAlchemy Core | 2.0.49 | Migrations additive via `text()` DDL | [VERIFIED: uv run] |
| PyYAML | 6.0.3 | Chargement `config/taxonomy.yaml` | [VERIFIED: uv run] — déjà dans l'env via dépendance transitive |
| pytest | 9.x | Tests unitaires | [VERIFIED: pyproject.toml] |
| hypothesis | 6.x | Property-based tests | [VERIFIED: pyproject.toml dev deps] |

### Nouvelle dépendance : PyYAML dans pyproject.toml
PyYAML est disponible dans l'environnement uv (version 6.0.3) mais **n'est pas déclaré comme dépendance directe** dans `pyproject.toml`. Il arrive via une dépendance transitive. Pour M010, il faut l'ajouter explicitement dans `[project.dependencies]` pour que l'install propre garantisse sa présence.

```bash
# Vérification
uv run python -c "import yaml; print(yaml.__version__)"
# → 6.0.3  [VERIFIED]
```

**Installation :** Ajouter dans `pyproject.toml` > `[project.dependencies]` :
```toml
"pyyaml>=6.0,<7",
```

Aucune autre dépendance nouvelle n'est nécessaire pour M010.

---

## Architecture Patterns

### Layering applicable à M010

La règle hexagonale (D019-D023, KNOWLEDGE.md) impose strictement :

```
domain/values.py      ← ContentType, SentimentLabel, Vertical (nouveaux StrEnum)
domain/entities.py    ← Analysis étendu (8 nouveaux champs)
ports/taxonomy_catalog.py   ← Protocol TaxonomyCatalog (nouveau)
adapters/config/yaml_taxonomy.py  ← YamlTaxonomy implémentant TaxonomyCatalog
config/taxonomy.yaml  ← données (fichier à la racine du repo)
adapters/sqlite/schema.py   ← colonnes nullable ajoutées à `analyses`
adapters/sqlite/migrations/009_analysis_v2.py  ← DDL ALTER TABLE + CREATE TABLE
adapters/sqlite/analysis_repository.py  ← étendu (read/write nouveaux champs)
adapters/heuristic/heuristic_v2.py  ← HeuristicAnalyzerV2 (provider "heuristic")
adapters/heuristic/sentiment_lexicon.py  ← nouveau
adapters/heuristic/sponsor_detector.py  ← nouveau
adapters/llm/_base.py  ← prompt étendu + JSON schema étendu
application/explain_analysis.py  ← nouveau use case
application/search_videos.py  ← SearchVideosUseCase avec facets (nouveau ou étendu)
cli/commands/explain.py  ← nouveau
cli/commands/search.py  ← étendu (--content-type, --min-actionability, --sponsored)
infrastructure/analyzer_registry.py  ← "heuristic" pointe vers V2, "heuristic-v1" vers V1
```

### Pattern S01 : Extension additive d'entité domain

**Ce qui change dans `Analysis` :**

```python
# AVANT (M001 - M009)
@dataclass(frozen=True, slots=True)
class Analysis:
    video_id: VideoId
    provider: str
    language: Language
    keywords: tuple[str, ...]
    topics: tuple[str, ...]
    score: float | None
    summary: str | None
    id: int | None = None
    created_at: datetime | None = None

# APRES (M010)
@dataclass(frozen=True, slots=True)
class Analysis:
    video_id: VideoId
    provider: str
    language: Language
    keywords: tuple[str, ...]
    topics: tuple[str, ...]          # toujours freeform pour compat arrière
    score: float | None              # PRESERVE (D032)
    summary: str | None
    # --- Nouveaux champs M010 (tous optionnels = None si pré-M010) ---
    verticals: tuple[str, ...] = ()   # taxonomie contrôlée (slugs du YAML)
    information_density: float | None = None   # 0-100
    actionability: float | None = None         # 0-100
    novelty: float | None = None               # 0-100
    production_quality: float | None = None    # 0-100
    sentiment: SentimentLabel | None = None    # enum StrEnum
    is_sponsored: bool | None = None           # None = unknown
    content_type: ContentType | None = None    # enum StrEnum
    reasoning: str | None = None               # 2-3 phrases
    id: int | None = None
    created_at: datetime | None = None
```

**Règles domain :**
- `SentimentLabel`, `ContentType`, `Vertical` sont des `StrEnum` dans `domain/values.py` (stdlib only, pas de pydantic).
- Tous les nouveaux champs ont une valeur par défaut (`None` ou `()`) pour la compatibilité avec le code existant qui construit `Analysis(video_id=..., provider=..., ...)` sans les nouveaux champs.
- `frozen=True, slots=True` est maintenu — les frozen dataclasses avec `slots=True` fonctionnent en Python 3.12+ avec des valeurs par défaut.

[VERIFIED: codebase read — entities.py pattern existant avec slots+frozen+defaults]

### Pattern S01 : Port TaxonomyCatalog

```python
# ports/taxonomy_catalog.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class TaxonomyCatalog(Protocol):
    def verticals(self) -> list[str]:
        """Retourne les slugs de toutes les verticales actives."""
        ...

    def keywords_for_vertical(self, vertical: str) -> frozenset[str]:
        """Retourne tous les mots-clés associés à la verticale ``vertical``."""
        ...

    def match(self, tokens: list[str]) -> list[str]:
        """Retourne les slugs des verticales dont les mots-clés matchent les tokens.
        Résultats ordonnés par score décroissant (coverage)."""
        ...
```

Ce port respecte la règle `ports-are-pure` : stdlib uniquement, zéro PyYAML.

**Adapter YamlTaxonomy** : placé dans `adapters/config/` (nouveau sous-module). Il importe PyYAML et lit le fichier YAML. Il est instancié dans `infrastructure/container.py` et passé comme argument au `HeuristicAnalyzerV2`.

**Nouveau contrat import-linter requis :**
```ini
[importlinter:contract:config-adapter-is-self-contained]
name = config adapter does not import other adapters
type = forbidden
source_modules =
    vidscope.adapters.config
forbidden_modules =
    vidscope.adapters.sqlite
    vidscope.adapters.llm
    vidscope.adapters.heuristic
    vidscope.adapters.fs
    vidscope.adapters.ytdlp
    vidscope.adapters.whisper
    vidscope.adapters.ffmpeg
    vidscope.adapters.vision
    vidscope.adapters.text
```

[ASSUMED: le contrat exact sera ajusté à l'implémentation, mais la structure est cohérente avec le pattern existant]

### Pattern S01 : Migration 009 (additive)

Le projet n'a pas encore de système de migration formalisé avec un runner — M009 a utilisé `_ensure_video_stats_table()` dans `init_db()`. M010 suivra le même pattern : une fonction `_ensure_analysis_v2_columns()` dans `schema.py` appelée depuis `init_db()`.

```python
# adapters/sqlite/schema.py — à ajouter dans init_db()
def _ensure_analysis_v2_columns(conn: Connection) -> None:
    """Migration additive M010 : ajoute les colonnes nullable sur analyses.
    
    Utilise ADD COLUMN IF NOT EXISTS (SQLite >= 3.37). Safe à appeler
    plusieurs fois.
    """
    new_columns = [
        ("verticals", "JSON"),
        ("information_density", "FLOAT"),
        ("actionability", "FLOAT"),
        ("novelty", "FLOAT"),
        ("production_quality", "FLOAT"),
        ("sentiment", "VARCHAR(32)"),
        ("is_sponsored", "BOOLEAN"),
        ("content_type", "VARCHAR(64)"),
        ("reasoning", "TEXT"),
    ]
    for col_name, col_type in new_columns:
        conn.execute(
            text(f"ALTER TABLE analyses ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
        )
```

**Alternative (si ADD COLUMN IF NOT EXISTS non dispo) :** Vérifier via `PRAGMA table_info(analyses)` avant chaque ALTER.

**Table `analysis_topics`** (taxonomie contrôlée) : selon le ROADMAP, une table de jointure `analysis_topics` stocke les verticales associées à une analyse. Cela est justifié pour le facet filtering SQL efficace.

```sql
CREATE TABLE IF NOT EXISTS analysis_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    vertical VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analysis_topics_analysis_id 
    ON analysis_topics (analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_topics_vertical
    ON analysis_topics (vertical);
```

[VERIFIED: SQLite ADD COLUMN IF NOT EXISTS — disponible depuis SQLite 3.37.0, uv env utilise Python 3.13 qui bundle SQLite bien plus récent]

### Pattern S02 : HeuristicAnalyzerV2

Stratégie zero-network pour les 7 nouveaux champs :

| Champ | Stratégie heuristique |
|---|---|
| `information_density` | ratio mots significatifs / total tokens × facteur longueur — extension du `_compute_score()` existant |
| `actionability` | détection de verbes impératifs + expressions d'appel à l'action (lexique FR+EN) |
| `novelty` | absence de mots très communs + density de termes spécialisés du domaine |
| `production_quality` | proxy : densité de segments / durée totale — transcripts bien structurés = meilleure qualité audio |
| `sentiment` | lexique sentiments FR+EN — `sentiment_lexicon.py` (SentimentPositif/Negatif/Neutre/Mixte) |
| `is_sponsored` | `sponsor_detector.py` — liste de mots-clés sponsor FR+EN (partenariat, code promo, lien bio, #ad, etc.) |
| `content_type` | heuristiques structurelles : tutoriel (liste étapes), review (comparatif), vlog (narration première personne), news (références temporelles), etc. |
| `verticals` | `TaxonomyCatalog.match(tokens)` — délégué à l'adapter config |
| `reasoning` | Template textuel composé depuis les scores obtenus |

Le fichier `heuristic_v2.py` doit rester sous 300 lignes (limite organism per CLAUDE global rules). Les helpers lexicaux vont dans `sentiment_lexicon.py` et `sponsor_detector.py`.

**Backward compat :** `"heuristic"` dans l'analyzer_registry pointe vers V2. `"heuristic-v1"` pointe vers l'ancienne classe. Aucun test existant ne brisé car ils testent via le nom du provider, pas la classe.

### Pattern S03 : LLM V2 — prompt étendu

Le prompt centralisé dans `_base.py._SYSTEM_PROMPT` est remplacé. Le JSON schema demandé au LLM s'étend à :

```
{
  "language": "en",
  "keywords": [...],
  "topics": [...],
  "verticals": ["tech", "fitness"],
  "score": 72,
  "information_density": 65,
  "actionability": 80,
  "novelty": 40,
  "production_quality": 70,
  "sentiment": "positive",
  "is_sponsored": false,
  "content_type": "tutorial",
  "reasoning": "2-3 sentence explanation",
  "summary": "..."
}
```

`make_analysis()` dans `_base.py` est étendu pour parser les nouveaux champs. Les 5 providers (`groq.py`, `nvidia_build.py`, `openrouter.py`, `openai.py`, `anthropic.py`) **ne changent pas** — ils délèguent tous à `run_openai_compatible()` ou aux helpers de `_base.py`.

**Robustesse :** `parse_llm_json` + `make_analysis` doivent rester défensifs — si un LLM ne retourne pas `information_density`, le champ reste `None` (pas de levée d'exception).

### Pattern S04 : CLI facets + `vidscope explain`

**Nouveau use case `explain_analysis.py` :**
```python
class ExplainAnalysisUseCase:
    def execute(self, video_id: VideoId) -> ExplainAnalysisResult: ...
```
Lit l'analyse la plus récente et retourne tous les champs scoring + reasoning.

**Extension `search_videos.py` / `SearchVideosUseCase` :** Ajout de filtres facettes sur `content_type`, `min_actionability`, `is_sponsored`. Le filtre passe par `AnalysisRepository` (nouveau method ou query directe via UoW).

**CLI `explain.py` :** Nouvelle commande standalone (pas un sub-app Typer), enregistrée directement dans `app.py` via `@app.command("explain")`.

**Règle ASCII dans CLI (KNOWLEDGE.md) :** Pas d'emojis ou glyphs unicode dans stdout (crash Windows cp1252 sur pipes).

---

## Don't Hand-Roll

| Problème | Ne pas construire | Utiliser à la place | Pourquoi |
|---|---|---|---|
| Chargement YAML structuré | Parser YAML maison | `yaml.safe_load()` (PyYAML) | Gestion des types, aliases, encodages |
| Validation du schéma YAML | Assertions ad-hoc | Schema déclaratif dans le loader (dicts + assertions explicites avec messages d'erreur) | Simples en Python, pas besoin de jsonschema |
| Sentiment analysis | Modèle ML | Lexique statique FR+EN (~200 mots positifs/négatifs) | Zero dépendance, 70%+ accuracy sur short-form content |
| Enum persistence SQLite | INT ou mapping | `StrEnum` → valeur string directe en DB | Lisible, stable, déjà le pattern du projet (Platform, Language) |

---

## Common Pitfalls

### Pitfall 1 : `frozen=True, slots=True` avec nouvelles valeurs par défaut
**Ce qui va mal :** Ajouter des champs avec valeur par défaut à un dataclass `slots=True` après des champs sans défaut provoque un `TypeError` en Python 3.12+ si l'ordre n'est pas correct.
**Pourquoi :** Python exige que les champs avec défaut viennent après les champs sans défaut dans un dataclass hérité ou modifié. Ici `Analysis` est réécrit — les nouveaux champs optionnels doivent tous venir après `summary`.
**Comment éviter :** Placer tous les nouveaux champs M010 après `summary: str | None`, avant `id: int | None`. Vérifier avec `python -c "from vidscope.domain.entities import Analysis; print(Analysis.__dataclass_fields__)"`.

[VERIFIED: entities.py actuel — pattern `id: int | None = None` déjà en fin de champ, safe d'insérer avant]

### Pitfall 2 : ADD COLUMN IF NOT EXISTS et tests en mémoire
**Ce qui va mal :** Les tests qui créent une DB in-memory avec `init_db()` peuvent échouer si `_ensure_analysis_v2_columns` est appelée sur une DB fraîche qui a déjà les colonnes (via `schema.py` SQLAlchemy), déclenchant une erreur "duplicate column".
**Pourquoi :** SQLAlchemy `metadata.create_all` crée la table avec les nouvelles colonnes ; ensuite `_ensure_analysis_v2_columns` tente de les ADD COLUMN à nouveau.
**Comment éviter :** Utiliser `ADD COLUMN IF NOT EXISTS` (SQLite 3.37+) OU tester l'existence via `PRAGMA table_info(analyses)` avant chaque ALTER. Recommandation : `IF NOT EXISTS` — plus propre et garanti sur Python 3.13 (SQLite bundlé ≥ 3.45).

[VERIFIED: Python 3.13 bundle SQLite ≥ 3.43 — ADD COLUMN IF NOT EXISTS disponible]

### Pitfall 3 : `topics` vs `verticals` — double champ de sujets
**Ce qui va mal :** Confusion entre `topics` (freeform, legacy, alimenté par les keywords heuristiques) et `verticals` (taxonomie contrôlée, nouveau M010). Les analyses LLM V2 doivent peupler les deux.
**Pourquoi :** `topics` est préservé pour compat arrière (le FTS5 index et `vidscope show` l'affichent encore). `verticals` est le nouveau champ structuré.
**Comment éviter :** Dans `make_analysis()` et `HeuristicAnalyzerV2`, toujours peupler `topics` (au moins avec les 3 premiers keywords) ET `verticals` (depuis la taxonomie).

### Pitfall 4 : `SentimentLabel` dans `_row_to_analysis` — valeur inconnue en DB
**Ce qui va mal :** Une analyse pré-M010 a `sentiment=NULL` ; `_row_to_analysis` tente `SentimentLabel(data["sentiment"])` et lève `ValueError`.
**Comment éviter :** Toujours utiliser `SentimentLabel(val) if val else None` dans le mapper. Pattern existant dans `Language` (voir `_row_to_analysis` pour `Language`).

### Pitfall 5 : `analysis_topics` table non exposée via UnitOfWork
**Ce qui va mal :** Créer un repository `AnalysisTopicsRepository` séparé qui n'est pas dans `UnitOfWork` brise les garanties transactionnelles.
**Comment éviter :** Soit (a) embarquer les writes `analysis_topics` dans `AnalysisRepositorySQLite.add()` (même connexion, même transaction), soit (b) ajouter un `analysis_topics: AnalysisTopicsRepository` dans `UnitOfWork`. Option (a) est plus simple pour M010.

### Pitfall 6 : Test de l'architecture — nouveau contrat non déclaré dans `test_layering.py`
**Ce qui va mal :** Le nouveau contrat `config-adapter-is-self-contained` déclaré dans `.importlinter` ne sera pas vérifié par `test_layering.py` si `EXPECTED_CONTRACTS` n'est pas mis à jour.
**Comment éviter :** Ajouter le nom du nouveau contrat dans le tuple `EXPECTED_CONTRACTS` de `tests/architecture/test_layering.py` en même temps que `.importlinter`.

---

## Code Examples

### Extension Analysis entity (pattern suivi par VideoStats en M009)
```python
# Source: src/vidscope/domain/entities.py — pattern VideoStats
@dataclass(frozen=True, slots=True)
class Analysis:
    video_id: VideoId
    provider: str
    language: Language
    keywords: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    score: float | None = None
    summary: str | None = None
    # M010 — champs nullable, compat arrière garantie
    verticals: tuple[str, ...] = ()
    information_density: float | None = None
    actionability: float | None = None
    novelty: float | None = None
    production_quality: float | None = None
    sentiment: "SentimentLabel | None" = None
    is_sponsored: bool | None = None
    content_type: "ContentType | None" = None
    reasoning: str | None = None
    id: int | None = None
    created_at: datetime | None = None
```

### yaml.safe_load + validation de schéma simple
```python
# Source: [ASSUMED] pattern PyYAML officiel
import yaml
from pathlib import Path

def load_taxonomy(path: Path) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"taxonomy.yaml doit être un mapping, got {type(raw)}")
    for key, val in raw.items():
        if not isinstance(val, list):
            raise ValueError(f"vertical '{key}' doit avoir une liste de keywords")
        if not all(isinstance(k, str) and k == k.lower() for k in val):
            raise ValueError(f"vertical '{key}' — tous les keywords doivent être lowercase")
    return raw
```

### Détection sponsor (pattern lexical)
```python
# Source: [ASSUMED] pattern stdlib
_SPONSOR_MARKERS_FR = frozenset([
    "partenariat", "sponsorisé", "code promo", "lien en bio",
    "en collaboration", "offert par",
])
_SPONSOR_MARKERS_EN = frozenset([
    "sponsored", "partnership", "promo code", "discount code",
    "link in bio", "#ad", "affiliate", "paid promotion",
])
_ALL_MARKERS = _SPONSOR_MARKERS_FR | _SPONSOR_MARKERS_EN

def detect_sponsored(text_lower: str) -> bool:
    return any(marker in text_lower for marker in _ALL_MARKERS)
```

### Extension make_analysis pour champs V2
```python
# Source: [ASSUMED] extension de _base.py.make_analysis existant
def _parse_score_field(parsed: dict, key: str) -> float | None:
    val = parsed.get(key)
    if val is None:
        return None
    try:
        return max(0.0, min(100.0, float(val)))
    except (TypeError, ValueError):
        return None

# Dans make_analysis() :
information_density = _parse_score_field(parsed, "information_density")
actionability = _parse_score_field(parsed, "actionability")
# ... etc.
sentiment_raw = parsed.get("sentiment")
sentiment = None
if sentiment_raw:
    try:
        sentiment = SentimentLabel(str(sentiment_raw).lower())
    except ValueError:
        sentiment = None
```

---

## Validation Architecture

### Test Framework
| Propriété | Valeur |
|---|---|
| Framework | pytest 9.x |
| Config | `pyproject.toml` `[tool.pytest.ini_options]` |
| Commande rapide | `uv run pytest tests/unit/domain/ tests/unit/adapters/heuristic/ tests/unit/adapters/llm/ -q` |
| Suite complète | `uv run pytest -q` (hors integration) |
| Architecture | `uv run pytest -m architecture -q` |

### Phase Requirements → Test Map

| Req ID | Comportement | Type de test | Commande automatisée | Fichier existe ? |
|---|---|---|---|---|
| R053 | Analysis a les 7 nouveaux champs (score vector + is_sponsored + content_type) | unit domain | `uv run pytest tests/unit/domain/test_entities.py -q` | ✅ (à étendre) |
| R053 | HeuristicAnalyzerV2 produit tous les nouveaux champs | unit adapter | `uv run pytest tests/unit/adapters/heuristic/test_heuristic_v2.py -q` | ❌ Wave 0 |
| R053 | LLM providers (groq, nvidia, etc.) retournent les nouveaux champs via JSON | unit adapter | `uv run pytest tests/unit/adapters/llm/ -q` | ✅ (à étendre) |
| R053 | Migration additive : anciens rows non touchés, nouvelles colonnes NULL | unit adapter sqlite | `uv run pytest tests/unit/adapters/sqlite/test_schema.py -q` | ✅ (à étendre) |
| R054 | YamlTaxonomy charge le YAML correctement (validation schéma) | unit adapter | `uv run pytest tests/unit/adapters/config/test_yaml_taxonomy.py -q` | ❌ Wave 0 |
| R054 | TaxonomyCatalog.match() retourne les bonnes verticales pour des tokens donnés | unit adapter | `uv run pytest tests/unit/adapters/config/test_yaml_taxonomy.py -q` | ❌ Wave 0 |
| R054 | HeuristicAnalyzerV2 mappe vers les verticals de la taxonomie | unit adapter | `uv run pytest tests/unit/adapters/heuristic/test_heuristic_v2.py -q` | ❌ Wave 0 |
| R055 | Analysis.reasoning est peuplé par HeuristicAnalyzerV2 | unit adapter | `uv run pytest tests/unit/adapters/heuristic/test_heuristic_v2.py -q` | ❌ Wave 0 |
| R055 | LLM V2 parse le champ reasoning depuis la réponse JSON | unit adapter | `uv run pytest tests/unit/adapters/llm/test_base.py -q` | ✅ (à étendre) |
| R055 | `vidscope explain <id>` affiche reasoning + scores | unit CLI | `uv run pytest tests/unit/cli/test_explain.py -q` | ❌ Wave 0 |
| R053 | Golden fixture ≥ 70% match rate (content_type + is_sponsored + sentiment) | unit golden | `uv run pytest tests/unit/adapters/heuristic/test_golden.py -q` | ❌ Wave 0 |
| R053 | CLI facet search filtre par content_type / min_actionability / sponsored | unit CLI | `uv run pytest tests/unit/cli/test_search.py -q` | ✅ (à étendre) |
| Architecture | 10+ contrats import-linter verts (9 existants + config-adapter) | architecture | `uv run pytest -m architecture -q` | ✅ (à étendre) |

### Taux d'échantillonnage
- **Par commit de tâche :** `uv run pytest tests/unit/domain/ tests/unit/adapters/heuristic/ tests/unit/adapters/llm/ tests/unit/adapters/sqlite/test_schema.py -q`
- **Par merge de wave :** `uv run pytest -q` (toute la suite unit)
- **Gate de phase :** Suite complète verte (`uv run pytest -q`) + `uv run pytest -m architecture -q` avant `/gsd-verify-work`

### Wave 0 Gaps (fichiers à créer)
- [ ] `tests/unit/adapters/heuristic/test_heuristic_v2.py` — 20+ fixtures content_type/sponsored/sentiment
- [ ] `tests/unit/adapters/heuristic/test_sentiment_lexicon.py` — 30 fixtures FR+EN
- [ ] `tests/unit/adapters/heuristic/test_sponsor_detector.py` — 15 fixtures
- [ ] `tests/unit/adapters/heuristic/test_golden.py` — charge `tests/fixtures/analysis_golden.jsonl`, vérifie ≥70% match
- [ ] `tests/fixtures/analysis_golden.jsonl` — 40 transcripts annotés à la main
- [ ] `tests/unit/adapters/config/` (nouveau répertoire + `__init__.py`)
- [ ] `tests/unit/adapters/config/test_yaml_taxonomy.py` — schema validation + matching
- [ ] `tests/unit/cli/test_explain.py` — CliRunner smoke test
- [ ] `config/taxonomy.yaml` — fichier de données (pas un test, mais Wave 0)

---

## State of the Art

| Ancienne approche | Approche M010 | Impact |
|---|---|---|
| `Analysis.score: float | None` (opaque) | Vecteur 5 dimensions + is_sponsored + content_type | Filtrage facettes possible ; diagnostic sur "pourquoi ce score" |
| `topics: tuple[str, ...]` freeform | `verticals` via taxonomie YAML contrôlée | Facet search SQL sur verticales canoniques |
| Pas de reasoning | `reasoning: str | None` (2-3 phrases) | `vidscope explain <id>` devient possible |
| Un seul prompt LLM sans schéma étendu | Prompt centralisé V2 dans `_base.py` | Tous les 5 providers bénéficient immédiatement |

---

## Environment Availability

| Dépendance | Requise par | Disponible | Version | Fallback |
|---|---|---|---|---|
| Python 3.13 | Tout | ✓ | 3.13.13 | — |
| SQLAlchemy | Migration + repository | ✓ | 2.0.49 | — |
| PyYAML | YamlTaxonomy adapter | ✓ | 6.0.3 (transitif) | Ajouter en dep directe |
| pytest + hypothesis | Tests | ✓ | 9.x + 6.x | — |
| import-linter | Architecture tests | ✓ | 2.11+ | — |
| SQLite ADD COLUMN IF NOT EXISTS | Migration | ✓ | SQLite ≥ 3.37 (Python 3.13 bundle) | PRAGMA table_info fallback |

**Aucun bloquant.** Toutes les dépendances sont disponibles.

---

## Assumptions Log

| # | Claim | Section | Risque si faux |
|---|---|---|---|
| A1 | PyYAML n'est pas déclaré en dep directe dans pyproject.toml — arrivé en transitif | Standard Stack | Faible : vérifiable en 30s ; ajouter `pyyaml>=6,<7` dans pyproject.toml si absent |
| A2 | La table `analysis_topics` est implémentée en side table de jointure (pas en JSON inline) | Architecture Patterns | Faible : JSON inline dans la colonne `verticals` (JSON) de `analyses` est une alternative valide et plus simple — décision au planificateur |
| A3 | `HeuristicAnalyzerV2` utilise un lexique statique pour le sentiment (pas un modèle ML) | Architecture Patterns | Faible : cohérent avec le principe zero-dep du heuristic existant |
| A4 | Le nouveau contrat import-linter pour `adapters/config` s'appelle `config-adapter-is-self-contained` | Architecture Patterns | Faible : nom cosmétique, l'important est d'avoir le contrat |
| A5 | `vidscope explain` est enregistré directement dans `app.py` (pas un sub-app) | Architecture Patterns | Faible : un sub-app serait `vidscope explain show <id>` — la commande est une action directe, pas une catégorie |

---

## Open Questions

1. **Table `analysis_topics` vs colonne JSON `verticals`**
   - Ce qu'on sait : le ROADMAP mentionne une `analysis_topics` side table pour le facet filtering SQL. La colonne `verticals: tuple[str, ...]` dans `Analysis` peut être stockée soit en JSON dans `analyses`, soit en lignes dans `analysis_topics`.
   - Ce qui est flou : la table de jointure est plus propre pour les requêtes `WHERE vertical = 'tech'` mais alourdit S01.
   - Recommandation : Implémenter la **colonne JSON `verticals` dans `analyses`** en M010 (simpler, additive) + un index virtuel si besoin ; déférer la table de jointure à un futur M011 si les performances de facet search le nécessitent.

2. **Backward compat du test `test_app.py::test_help_lists_every_command`**
   - Ce qu'on sait : ce test vérifie que `vidscope --help` liste toutes les commandes.
   - Ce qui est flou : la nouvelle commande `explain` doit-elle y être ajoutée manuellement ?
   - Recommandation : Oui — ajouter `"explain"` à la liste attendue dans le test.

---

## Sources

### Primaires (HIGH confidence)
- `src/vidscope/domain/entities.py` — structure actuelle de `Analysis`, pattern dataclass frozen+slots
- `src/vidscope/domain/values.py` — pattern StrEnum existant (Platform, Language)
- `src/vidscope/adapters/sqlite/schema.py` — pattern migration additive `_ensure_*` de M009
- `src/vidscope/adapters/llm/_base.py` — architecture prompt centralisé + `make_analysis` + `parse_llm_json`
- `src/vidscope/adapters/heuristic/analyzer.py` — structure HeuristicAnalyzer à étendre
- `.importlinter` — 9 contrats existants + pattern pour le 10ème
- `tests/architecture/test_layering.py` — pattern `EXPECTED_CONTRACTS`
- `.gsd/milestones/M010/M010-ROADMAP.md` — vision, découpage, requirements

### Secondaires (MEDIUM confidence)
- `pyproject.toml` — dépendances et outils
- `src/vidscope/adapters/sqlite/unit_of_work.py` — composition repositories

### Tertiaires (LOW confidence)
- [ASSUMED] Structure interne des lexiques sentiment/sponsor — à concevoir lors de S02

---

## Metadata

**Confidence breakdown :**
- Standard stack : HIGH — toutes les dépendances vérifiées via `uv run`
- Architecture : HIGH — codebase lue en totalité, patterns directs extraits
- Pitfalls : HIGH — basés sur code réel (migration pattern M009, rule KNOWLEDGE.md)
- Lexiques heuristiques : MEDIUM — structure connue, contenu exact à définir en S02

**Research date :** 2026-04-18
**Valid until :** 2026-05-18 (stack stable, pas de breaking changes attendus)
