# M008 — Visual Intelligence on Frames : Research

**Date de recherche :** 2026-04-18
**Domaine :** OCR local CPU (RapidOCR/ONNX), OpenCV Haarcascade, SQLite FTS5, pipeline stage pattern
**Confiance globale :** HIGH (stack vérifié PyPI + code source existant)

---

## Résumé

M008 transforme les frames extraites par M001 (jusqu'à 30 JPG par vidéo) en signal structuré :
texte OCR, thumbnail canonique, et classification contenu (talking\_head / broll / mixed).
L'extractor OCR est `rapidocr-onnxruntime 1.4.4`, exécuté localement en CPU-only via ONNX Runtime,
sans aucun appel réseau (principe D010). La dépendance critique est que `rapidocr-onnxruntime`
exige `opencv-python` — mais le projet doit préférer `opencv-python-headless` pour un environnement
sans GUI. La résolution est d'utiliser `uv override-dependencies` pour substituer
`opencv-python-headless` à `opencv-python` en tant que fournisseur du namespace `cv2`.

L'architecture suit le pattern pipeline-stage établi : `VisualIntelligenceStage` est une nouvelle
étape insérée **après** `FramesStage` et **avant** `MetadataExtractStage`. Elle est idempotente
(is\_satisfied vérifie si `frame_texts` existent déjà pour la vidéo). Les URLs extraites par OCR
passent dans le `LinkExtractor` existant (M007) avec `source='ocr'`.

**Recommandation principale :** utiliser `rapidocr-onnxruntime==1.4.4` avec chargement lazy du
modèle + dégradation gracieuse si non installé ; haarcascade OpenCV pour la classification
talking\_head ; FTS5 table `frame_texts_fts` distincte de `search_index`.

---

## 1. rapidocr-onnxruntime : API et comportement

### 1.1 Informations package

[VERIFIED: PyPI registry]
- Package : `rapidocr-onnxruntime==1.4.4`
- Python : `>=3.6, <3.13` — compatible Python 3.12 du projet
- Dépendances directes : `opencv-python>=4.5.1.48`, `onnxruntime>=1.7.0`, `numpy`, `Shapely`, `pyclipper`, `PyYAML`, `Pillow`, `six`, `tqdm`
- ONNX Runtime CPU : `onnxruntime` (pas de CUDA requis) — dernière version `1.24.4`

**Problème de dépendance critique :**
`rapidocr-onnxruntime` déclare `opencv-python` comme dépendance, pas `opencv-python-headless`.
`opencv-python` et `opencv-python-headless` fournissent le même namespace `cv2` mais ne peuvent
pas coexister. La solution pour un environnement headless (serveur, CI) est l'override uv :

```toml
# pyproject.toml — section [tool.uv]
[tool.uv]
override-dependencies = [
    "opencv-python-headless>=4.5.1.48",
]
```

Cela remplace `opencv-python` par `opencv-python-headless` pour satisfaire la dépendance de
rapidocr sans installer le variant GUI. `opencv-python-headless 4.13.0.92` est la dernière version.

### 1.2 Import et API — version 1.4.x

[CITED: https://github.com/RapidAI/RapidOCR/blob/0a603b4e8919386f3647eca5cdeba7620b4988e0/python/README.md]

```python
from rapidocr_onnxruntime import RapidOCR

# Instantiation (lazy : les modèles ONNX ne sont PAS chargés ici)
engine = RapidOCR()

# Appel sur un chemin fichier (str | Path | bytes | np.ndarray)
result, elapse = engine("path/to/frame.jpg")

# Quand aucun texte n'est détecté :
# result = None, elapse = float

# Quand du texte est détecté :
# result = list[list]  où chaque élément est :
#   [[pt_haut_gauche, pt_haut_droit, pt_bas_droit, pt_bas_gauche], texte, score_confiance]
# Exemple :
# [[[10, 20], [100, 20], [100, 40], [10, 40]], 'Link in bio: example.com', 0.9921]
```

**ATTENTION : API de la version 1.4.x vs version 2.x/3.x**

La nouvelle API (`rapidocr >= 2.0`) retourne un objet `RapidOCROutput` avec les attributs
`.boxes`, `.txts`, `.scores`, `.elapse`. Cette API n'est PAS disponible dans
`rapidocr-onnxruntime 1.4.4` qui retourne un tuple `(result, elapse)`.

L'adapter doit donc utiliser l'ancienne API de retour pour `rapidocr-onnxruntime 1.4.4` :

```python
result, elapse = engine(image_path)
if result is None:
    texts = []
else:
    texts = [
        {"text": item[1], "confidence": float(item[2]), "bbox": item[0]}
        for item in result
        if float(item[2]) >= confidence_threshold
    ]
```

### 1.3 Chargement lazy du modèle

[CITED: https://github.com/RapidAI/RapidOCR — architecture source]

Le modèle ONNX (~50 MB) est téléchargé depuis ModelScope CDN lors du **premier appel** à `engine()`
(pas lors de `RapidOCR()`). Donc `RapidOcrEngine.__init__()` peut stocker `self._engine = None`
et créer le `RapidOCR()` lors du premier appel. Pattern recommandé :

```python
class RapidOcrEngine:
    def __init__(self) -> None:
        self._engine: RapidOCR | None = None

    def _get_engine(self) -> RapidOCR:
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415
            self._engine = RapidOCR()
        return self._engine

    def extract_text(self, image_path: str, *, min_confidence: float = 0.5) -> list[OcrLine]:
        engine = self._get_engine()
        result, _elapse = engine(image_path)
        ...
```

### 1.4 Dégradation gracieuse si non installé

```python
def extract_text(self, image_path: str, *, min_confidence: float = 0.5) -> list[OcrLine]:
    try:
        engine = self._get_engine()
    except ImportError:
        return []   # Stage émmettra SKIPPED si l'engine retourne []
    ...
```

Le `VisualIntelligenceStage` vérifie si l'engine est disponible dans `is_satisfied` et
retourne `StageResult(status=RunStatus.SKIPPED, message="rapidocr not installed")` si besoin.

### 1.5 Seuil de confiance recommandé

[CITED: RapidOCR docs — config defaults]
- `text_score` par défaut : `0.5`
- `box_thresh` par défaut : `0.5`
- Pour les textes on-screen dans des vidéos (souvent nets) : `min_confidence=0.5` est approprié
- Pour filtrer le bruit (petits textes parasites) : `0.7` est plus conservateur

**Recommandation pour M008** : seuil `0.5` configurable via constante dans l'adapter.

### 1.6 Performance CPU — 30 frames

[ASSUMED] Benchmark indicatif basé sur documentation et profils communautaires :
- RapidOCR ONNX CPU : ~200-500ms par frame 720p sur CPU moderne
- 30 frames : ~6-15s total estimé
- Cible M008 : < 20s sur CPU de référence — réaliste

Le benchmark `pytest-benchmark` devra valider sur un jeu de 30 fixtures JPG réelles.

---

## 2. OpenCV haarcascade : détection de visages

### 2.1 Package

[VERIFIED: PyPI registry]
- `opencv-python-headless==4.13.0.92` — pas de Qt, pas de GUI, adapté serveur
- Le namespace `cv2` est identique à `opencv-python`
- Conflits : `opencv-python` ET `opencv-python-headless` ne peuvent pas coexister → utiliser l'override uv

### 2.2 Emplacement du fichier haarcascade

[VERIFIED: multiple OpenCV docs]
```python
import cv2
cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
# Exemple : /path/to/site-packages/cv2/data/haarcascade_frontalface_default.xml
```

`cv2.data.haarcascades` est le chemin canonique inclus dans le wheel Python — pas besoin de
télécharger le fichier séparément. Fonctionne sur Windows, macOS, Linux.

### 2.3 API detectMultiScale

[CITED: https://docs.opencv.org/4.x/]
```python
import cv2
import numpy as np

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

img = cv2.imread(frame_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
faces = face_cascade.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
)
# faces : np.ndarray shape (N, 4) [x, y, w, h] ou tuple vide si aucun visage
face_count = len(faces) if len(faces) > 0 else 0
```

### 2.4 Logique de classification content_shape

Heuristique définie dans M008-ROADMAP :
- `talking_head` : ≥ 40% des frames ont ≥ 1 visage détecté
- `broll` : 0 visage dans aucune frame
- `mixed` : entre les deux
- `unknown` : si haarcascade non disponible ou erreur

```python
def classify_content_shape(face_counts: list[int]) -> ContentShape:
    if not face_counts:
        return ContentShape.UNKNOWN
    frames_with_face = sum(1 for c in face_counts if c > 0)
    ratio = frames_with_face / len(face_counts)
    if ratio == 0.0:
        return ContentShape.BROLL
    elif ratio >= 0.4:
        return ContentShape.TALKING_HEAD
    else:
        return ContentShape.MIXED
```

### 2.5 Fiabilité et limitations

[ASSUMED]
- Haarcascade est une méthode des années 2000, pas état de l'art en 2024
- Précision raisonnable pour des visages frontaux bien éclairés (cas typique d'un talking head)
- Faux négatifs fréquents : profil, mauvais éclairage, visages petits
- Faux positifs possibles sur des textures répétitives
- Acceptable pour une heuristique de classification (talking\_head vs broll) car on travaille
  sur 30 frames et on calcule un ratio — les erreurs individuelles s'atténuent

**Pas besoin d'alternative** (YOLO, MediaPipe) en M008 — la roadmap l'exclut explicitement.

---

## 3. SQLite FTS5 pour frame_texts

### 3.1 DDL recommandé

[VERIFIED: https://www.sqlite.org/fts5.html — même tokenizer que search_index existant]

```sql
-- Migration 007_fts_frame_texts.py
CREATE VIRTUAL TABLE IF NOT EXISTS frame_texts_fts USING fts5(
    frame_text_id UNINDEXED,
    video_id      UNINDEXED,
    text,
    tokenize = 'unicode61 remove_diacritics 2'
);
```

Même tokenizer `unicode61 remove_diacritics 2` que la `search_index` existante — cohérence
garantie pour FR+EN (suppression des accents, insensible à la casse).

`frame_text_id` et `video_id` sont `UNINDEXED` (filtre, pas tokenisé), `text` est le seul
champ indexé — pattern identique à `search_index`.

### 3.2 Requête de recherche par on-screen text

```python
# SearchLibraryUseCase étendu pour --on-screen-text
query_sql = """
    SELECT DISTINCT ft.video_id
    FROM frame_texts ft
    JOIN frame_texts_fts fts ON fts.frame_text_id = ft.id
    WHERE frame_texts_fts MATCH :query
    ORDER BY fts.rank
    LIMIT :limit
"""
```

Ou via EXISTS subquery pour la cohérence avec le pattern `--hashtag`/`--mention` :
```python
# Facette de recherche --on-screen-text
WHERE EXISTS (
    SELECT 1 FROM frame_texts_fts
    WHERE frame_texts_fts MATCH :text_query
    AND frame_texts_fts.video_id = v.id
)
```

### 3.3 Tokenizer et langues FR+EN

[CITED: https://www.sqlite.org/fts5.html]
- `unicode61` : insensible à la casse selon Unicode 6.1, décomposition des caractères accentués
- `remove_diacritics 2` : supprime les diacritiques de tous les scripts Latin (pas seulement latin de base)
- Résultat : `"éàü"` et `"eau"` matchent — parfait pour du texte OCR en français

---

## 4. Système de migrations — pattern existant

### 4.1 Absence de système de migrations de fichiers

[VERIFIED: ls src/vidscope/adapters/sqlite/]

**Le projet n'a PAS de répertoire `migrations/` avec des fichiers numérotés.** Le pattern
utilisé est différent : toutes les migrations incrémentales sont des fonctions `_ensure_*`
définies directement dans `schema.py`, appelées par `init_db()`.

Exemples dans `schema.py` existant :
- `_ensure_videos_creator_id(conn)` — ajoute la colonne FK M006
- `_ensure_videos_metadata_columns(conn)` — ajoute description/music_track/music_artist M007

### 4.2 Pattern pour M008

M008 devra ajouter dans `schema.py` :

1. **Nouvelles tables** via `Table(...)` dans `metadata` :
   - `frame_texts` (côté SQLAlchemy Core)
   - colonnes `videos.thumbnail_key`, `videos.content_shape` dans la définition inline

2. **Fonctions `_ensure_*`** dans `init_db()` :
   ```python
   def _ensure_frame_texts_table(conn: Connection) -> None:
       """Crée frame_texts si absent — upgrade depuis pre-M008."""
       # SQLite ne supporte pas CREATE TABLE IF NOT EXISTS avec ALTER
       # Vérifier si la table existe :
       tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars().all()
       if "frame_texts" not in tables:
           conn.execute(text("""
               CREATE TABLE frame_texts (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                   frame_id INTEGER NOT NULL REFERENCES frames(id) ON DELETE CASCADE,
                   text TEXT NOT NULL,
                   confidence REAL NOT NULL,
                   created_at DATETIME NOT NULL
               )
           """))

   def _ensure_videos_visual_columns(conn: Connection) -> None:
       """Ajoute thumbnail_key et content_shape sur videos — upgrade."""
       cols = {row[1] for row in conn.execute(text("PRAGMA table_info(videos)"))}
       if "thumbnail_key" not in cols:
           conn.execute(text("ALTER TABLE videos ADD COLUMN thumbnail_key TEXT"))
       if "content_shape" not in cols:
           conn.execute(text("ALTER TABLE videos ADD COLUMN content_shape VARCHAR(32)"))

   def _ensure_frame_texts_fts(conn: Connection) -> None:
       """Crée la FTS5 virtual table frame_texts_fts — upgrade."""
       conn.execute(text("""
           CREATE VIRTUAL TABLE IF NOT EXISTS frame_texts_fts USING fts5(
               frame_text_id UNINDEXED,
               video_id      UNINDEXED,
               text,
               tokenize = 'unicode61 remove_diacritics 2'
           )
       """))
   ```

3. `init_db()` appelle ces fonctions en séquence après `metadata.create_all(engine)`.

**Conclusion :** il n'y a pas de système de fichiers `006_frame_texts.py` / `007_fts_frame_texts.py`.
Le plan doit s'appuyer sur le pattern `_ensure_*` dans `schema.py`. Les références à des fichiers
de migration numérotés dans la roadmap M008 sont des noms conceptuels, pas des fichiers physiques.

---

## 5. Entité FrameText — design

### 5.1 Champs recommandés

[VERIFIED: pattern entités existantes dans entities.py]

```python
@dataclass(frozen=True, slots=True)
class FrameText:
    """Un bloc de texte OCR extrait d'une frame.

    Stored in frame_texts side table keyed by (frame_id, text).
    confidence is a float in [0.0, 1.0].
    bbox is JSON-serialized list of 4 [x,y] corner points — stored
    for potential future visualization but not exposed in CLI/MCP v1.
    """
    video_id: VideoId
    frame_id: int           # FK → frames.id
    text: str
    confidence: float
    bbox: str | None = None  # JSON: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
    id: int | None = None
    created_at: datetime | None = None
```

### 5.2 Relation avec Frame

- `frame_id` est une FK vers `frames.id` avec `ON DELETE CASCADE`
- `video_id` est dénormalisé (aussi présent dans `frames`) pour simplifier les requêtes sans JOIN
  — même pattern que `links` qui a `video_id` ET `source`
- Pas de contrainte UNIQUE sur `(frame_id, text)` — une même frame peut avoir plusieurs lignes

---

## 6. Intégration pipeline

### 6.1 Position de VisualIntelligenceStage

[VERIFIED: container.py, pipeline/stages/__init__.py]

Ordre actuel :
```
ingest → transcribe → frames → analyze → metadata_extract → index
```

Ordre M008 :
```
ingest → transcribe → frames → analyze → visual_intelligence → metadata_extract → index
```

`VisualIntelligenceStage` doit être inséré **avant** `MetadataExtractStage` car M008/S02
alimente la table `links` avec `source='ocr'`, et `MetadataExtractStage.is_satisfied`
vérifie `has_any_for_video`. Si visual_intelligence passe en premier, le check is_satisfied
de metadata_extract pourrait se déclencher prématurément. Résolution :

**Option A (recommandée)** : insérer visual_intelligence AVANT metadata_extract, et
metadata_extract vérifie seulement les sources `description`/`transcript` (les liens OCR
sont un bonus, pas bloquants pour le skip).

**Option B** : insérer après metadata_extract — les liens OCR ne sont produits qu'en
ré-exécution. Cette option est plus simple mais réduit la valeur de M008 sur le premier run.

**Décision recommandée : Option A**. L'`is_satisfied` de MetadataExtractStage devra être
ajusté pour ne pas se satisfaire uniquement des liens OCR (ou VisualIntelligenceStage produit
ses liens dans une transaction séparée avant MetadataExtractStage).

### 6.2 Idempotence de VisualIntelligenceStage

```python
def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
    """True si des frame_texts existent déjà pour cette vidéo."""
    if ctx.video_id is None:
        return False
    return uow.frame_texts.has_any_for_video(ctx.video_id)
```

Pattern identique à `MetadataExtractStage.is_satisfied`.

### 6.3 Nouveau StageName

`StageName` dans `values.py` doit être étendu :
```python
VISUAL_INTELLIGENCE = "visual_intelligence"
```

### 6.4 Wiring dans container.py

```python
ocr_engine = RapidOcrEngine()   # lazy load — pas de download ici
visual_intelligence_stage = VisualIntelligenceStage(
    ocr_engine=ocr_engine,
    link_extractor=link_extractor,  # réutiliser RegexLinkExtractor existant
    media_storage=media_storage,
)
```

Le `PipelineRunner` reçoit la liste de stages mise à jour (visual_intelligence après frames).

---

## 7. Contrat import-linter : vision-adapter-is-self-contained

### 7.1 Pattern existant à répliquer

[VERIFIED: .importlinter]

Le contrat `text-adapter-is-self-contained` est le modèle exact :
```ini
[importlinter:contract:text-adapter-is-self-contained]
name = text adapter does not import other adapters
type = forbidden
source_modules =
    vidscope.adapters.text
forbidden_modules =
    vidscope.adapters.sqlite
    vidscope.adapters.fs
    vidscope.adapters.ytdlp
    vidscope.adapters.whisper
    vidscope.adapters.ffmpeg
    vidscope.adapters.heuristic
    vidscope.adapters.llm
    vidscope.infrastructure
    vidscope.application
    vidscope.pipeline
    vidscope.cli
    vidscope.mcp
```

### 7.2 Nouveau contrat pour l'adapter vision

```ini
[importlinter:contract:vision-adapter-is-self-contained]
name = vision adapter does not import other adapters
type = forbidden
source_modules =
    vidscope.adapters.vision
forbidden_modules =
    vidscope.adapters.sqlite
    vidscope.adapters.fs
    vidscope.adapters.ytdlp
    vidscope.adapters.whisper
    vidscope.adapters.ffmpeg
    vidscope.adapters.heuristic
    vidscope.adapters.llm
    vidscope.adapters.text
    vidscope.infrastructure
    vidscope.application
    vidscope.pipeline
    vidscope.cli
    vidscope.mcp
```

À ajouter dans `.importlinter`. Les autres contrats `forbidden_modules` doivent être mis à
jour pour interdire `vidscope.adapters.vision` (même pattern que l'ajout de `vidscope.adapters.text`).

---

## 8. Chargement lazy — pattern général

### 8.1 Pattern établi dans le projet

[VERIFIED: container.py commentaires sur FasterWhisperTranscriber]

Le projet utilise déjà le chargement lazy dans `FasterWhisperTranscriber` :
> "FasterWhisperTranscriber loads the model lazily on the first transcribe call (S03/D026),
> so this constructor never triggers a model download."

Le même pattern doit s'appliquer à `RapidOcrEngine` :
- `__init__()` : stocker la configuration seulement
- `_get_engine()` : créer l'instance `RapidOCR()` au premier appel (thread-safe avec un
  simple `if self._engine is None`, acceptable car le pipeline est single-thread)
- Premier appel `RapidOCR()` : déclenche le download du modèle ONNX depuis ModelScope CDN

### 8.2 Dégradation gracieuse si non installé

L'`ImportError` sur `rapidocr_onnxruntime` doit être capturée dans l'adapter :
```python
def _get_engine(self) -> "RapidOCR":
    if self._engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415
        except ImportError as exc:
            raise OCRUnavailableError(
                "rapidocr-onnxruntime is not installed. "
                "Install with: uv add 'vidscope[vision]'"
            ) from exc
        self._engine = RapidOCR()
    return self._engine
```

`VisualIntelligenceStage.execute` capture `OCRUnavailableError` et retourne
`StageResult(status="skipped", message="OCR model not available")`.

---

## Standard Stack

| Bibliothèque | Version | Rôle | Justification |
|---|---|---|---|
| `rapidocr-onnxruntime` | `1.4.4` | OCR CPU-only | Seule lib OCR Python mature avec ONNX CPU FR+EN, zéro API cost |
| `opencv-python-headless` | `4.13.0.92` | Haarcascade + imageread | Headless = pas de dépendance Qt, adapté server/CI |
| `onnxruntime` | `1.24.4` (transitive) | Backend ONNX | Inclus via rapidocr-onnxruntime |

**Installation dans pyproject.toml (dépendance optionnelle) :**
```toml
[project.optional-dependencies]
vision = [
    "rapidocr-onnxruntime>=1.4.4,<2",
    "opencv-python-headless>=4.5.1.48",
]

[tool.uv]
# Force opencv-python-headless à satisfaire la dépendance opencv-python de rapidocr
override-dependencies = [
    "opencv-python-headless>=4.5.1.48",
]
```

**Installation dev :**
```bash
uv sync --extra vision
```

---

## Architecture Patterns

### Structure recommandée des nouveaux fichiers

```
src/vidscope/
├── domain/
│   ├── entities.py          # +FrameText dataclass, +Video.thumbnail_key/content_shape
│   └── values.py            # +ContentShape StrEnum, +StageName.VISUAL_INTELLIGENCE
├── ports/
│   ├── ocr_engine.py        # OcrEngine Protocol (extract_text)
│   ├── frame_text_repository.py  # FrameTextRepository Protocol
│   └── repositories.py      # +FrameTextRepository import
├── adapters/
│   └── vision/              # NOUVEAU sous-module
│       ├── __init__.py
│       ├── rapidocr_engine.py       # RapidOcrEngine implements OcrEngine
│       └── haarcascade_face_counter.py  # HaarcascadeFaceCounter
├── adapters/sqlite/
│   ├── schema.py            # +frame_texts table, +_ensure_*, +FTS5 virtual table
│   ├── frame_text_repository.py  # FrameTextRepositorySQLite
│   └── unit_of_work.py      # +frame_texts: FrameTextRepository attribute
├── pipeline/stages/
│   └── visual_intelligence_stage.py  # VisualIntelligenceStage
└── infrastructure/
    ├── container.py         # +RapidOcrEngine, +VisualIntelligenceStage
    └── startup.py           # +check_ocr_model()
```

### Pattern port OcrEngine

```python
# ports/ocr_engine.py
@dataclass(frozen=True, slots=True)
class OcrLine:
    text: str
    confidence: float
    # bbox omis de l'interface publique v1 — impl detail de l'adapter

class OcrEngine(Protocol):
    def extract_text(
        self, image_path: str, *, min_confidence: float = 0.5
    ) -> list[OcrLine]:
        """Retourne les lignes de texte extraites. [] si aucun texte ou lib non installée."""
        ...
```

### Pattern repository FrameTextRepository

```python
class FrameTextRepository(Protocol):
    def add_many_for_frame(
        self, frame_id: int, video_id: VideoId, texts: list[FrameText]
    ) -> list[FrameText]: ...

    def list_for_video(self, video_id: VideoId) -> list[FrameText]: ...

    def has_any_for_video(self, video_id: VideoId) -> bool: ...
    # Utilisé par VisualIntelligenceStage.is_satisfied
```

---

## Anti-Patterns à éviter

- **Ne PAS** utiliser `opencv-python` (variant avec GUI) en dépendance directe — utiliser headless
- **Ne PAS** charger le modèle ONNX dans `__init__()` du container — coût de ~50MB download au démarrage
- **Ne PAS** lever une exception si rapidocr n'est pas installé — dégradation gracieuse requise
- **Ne PAS** créer une FTS5 table séparée par source (une seule table `frame_texts_fts` suffit)
- **Ne PAS** dupliquer `content_shape` dans une side-entity — colonne directe sur `videos` (pattern M007 D-01)
- **Ne PAS** oublier de mettre à jour les contrats `forbidden_modules` existants pour inclure `vidscope.adapters.vision`

---

## Pièges courants

### Piège 1 : Conflit opencv-python / opencv-python-headless
**Ce qui se passe :** rapidocr-onnxruntime installe `opencv-python` qui entre en conflit avec
`opencv-python-headless`. Les deux packages fournissent `cv2` mais ne peuvent pas coexister.
**Prévention :** `tool.uv.override-dependencies` pour forcer headless.
**Signes d'alerte :** `ImportError: cannot import name 'cv2'` ou double installation détectée.

### Piège 2 : API retour rapidocr 1.4.x vs 2.x
**Ce qui se passe :** La documentation actuelle (RapidOCRDocs) décrit la v2/v3 avec
`RapidOCROutput.boxes/.txts/.scores`. La v1.4.x retourne un tuple `(result, elapse)`.
**Prévention :** utiliser `result, elapse = engine(img)` et vérifier `if result is None`.
**Signes d'alerte :** `AttributeError: 'tuple' object has no attribute 'boxes'`.

### Piège 3 : frame_texts_fts non synchronisée après suppression
**Ce qui se passe :** Si une frame est supprimée (CASCADE sur `frame_texts`), la FTS5 virtual
table n'est pas automatiquement mise à jour — il faut supprimer manuellement les entrées FTS5.
**Prévention :** `FrameTextRepositorySQLite.add_many_for_frame` doit aussi insérer dans
`frame_texts_fts` ; un trigger SQLite OU une suppression explicite dans le repository.
**Recommandation :** gérer dans le repository (pas de trigger) — pattern cohérent avec
`SearchIndexSQLite`.

### Piège 4 : Haarcascade manquant si cv2 non installé
**Ce qui se passe :** `cv2.data.haarcascades` lève `AttributeError` si cv2 non disponible.
**Prévention :** `HaarcascadeFaceCounter` doit capturer `ImportError` et retourner
`face_count=0` (ou `content_shape=UNKNOWN`) si OpenCV n'est pas installé.

### Piège 5 : thumbnail_key pointe vers une frame qui n'existe plus
**Ce qui se passe :** Si les frames sont nettoyées, `videos.thumbnail_key` devient un
storage key périmé.
**Prévention :** copier la frame du milieu vers un chemin canonical permanent
(`videos/{id}/thumb.jpg`) distinct des frames temporaires — c'est la sémantique "copy middle frame".

---

## Environnement disponible

| Dépendance | Statut | Action requise |
|---|---|---|
| `rapidocr-onnxruntime` | Non installée | À ajouter en optional-dep `vision` |
| `opencv-python-headless` | Non installée | À ajouter avec override uv |
| `onnxruntime` | Non installée (transitive) | Installée automatiquement avec rapidocr |
| Python 3.12 | Disponible | Compatible (`<3.13,>=3.6`) |
| `ffmpeg` | Disponible (utilisé par FramesStage) | Aucune |
| Frames JPG sur disque | Disponibles (M001) | Aucune — pipeline prérequis |

---

## Validation Architecture

### Framework de tests

| Propriété | Valeur |
|---|---|
| Framework | pytest 9.x (pyproject.toml `[tool.pytest.ini_options]`) |
| Config | `pyproject.toml` — section `[tool.pytest.ini_options]` |
| Commande rapide | `uv run pytest tests/unit/ -x` |
| Suite complète | `uv run pytest tests/ -m "not integration"` |
| Architecture | `uv run lint-imports` |

### Stratégie de test par slice

#### S01 — OCR port + adapter + FrameText + DB

| Req | Comportement | Type | Commande | Fichier |
|---|---|---|---|---|
| R047 | FrameText entity invariants (frozen, slots) | unit | `pytest tests/unit/domain/test_frame_text.py -x` | Wave 0 |
| R047 | ContentShape enum exhaustiveness (4 valeurs) | unit | `pytest tests/unit/domain/test_content_shape.py -x` | Wave 0 |
| R047 | RapidOcrEngine — 5 fixtures JPG avec texte connu | unit | `pytest tests/unit/adapters/vision/test_rapidocr_engine.py -x` | Wave 0 |
| R047 | RapidOcrEngine — dégradation si lib absente | unit | idem | Wave 0 |
| R047 | RapidOcrEngine — chargement lazy (engine None avant 1er appel) | unit | idem | Wave 0 |
| R047 | FrameTextRepositorySQLite CRUD + FK cascade | unit | `pytest tests/unit/adapters/sqlite/test_frame_text_repository.py -x` | Wave 0 |
| R048 | videos.thumbnail_key et videos.content_shape présents dans schema | unit | `pytest tests/unit/adapters/sqlite/test_schema.py -x` | Existant — compléter |
| R049 | _ensure_videos_visual_columns idempotent | unit | idem | Wave 0 |
| arch | vision-adapter-is-self-contained contract | arch | `uv run lint-imports` | .importlinter |

#### S02 — VisualIntelligenceStage

| Req | Comportement | Type | Commande | Fichier |
|---|---|---|---|---|
| R047 | Stage avec OcrEngine stubbed → frame_texts persistés | unit | `pytest tests/unit/pipeline/stages/test_visual_intelligence_stage.py -x` | Wave 0 |
| R047 | Links avec source='ocr' créés dans la table links | unit | idem | Wave 0 |
| R047 | is_satisfied = True si frame_texts existent | unit | idem | Wave 0 |
| R047 | Stage retourne SKIPPED si rapidocr non installé | unit | idem | Wave 0 |
| R047 | Intégration réelle — JPG avec "Link in bio: example.com" → links.source='ocr' | integration | `pytest tests/integration/ -m integration -k ocr` | Wave 0 |

#### S03 — Thumbnail + content_shape

| Req | Comportement | Type | Commande | Fichier |
|---|---|---|---|---|
| R048 | videos.thumbnail_key = 'videos/{id}/thumb.jpg' après stage | unit | `pytest tests/unit/pipeline/stages/test_visual_intelligence_stage.py::test_thumbnail -x` | Wave 0 |
| R049 | HaarcascadeFaceCounter — 5 fixtures JPG (solo/multi/no face) | unit | `pytest tests/unit/adapters/vision/test_haarcascade_face_counter.py -x` | Wave 0 |
| R049 | classify_content_shape heuristique (40% seuil) | unit | `pytest tests/unit/pipeline/stages/test_visual_intelligence_stage.py::test_content_shape -x` | Wave 0 |
| R049 | videos.content_shape ∈ {talking_head, broll, mixed, unknown} | unit | idem | Wave 0 |

#### S04 — CLI + MCP surface

| Req | Comportement | Type | Commande | Fichier |
|---|---|---|---|---|
| R047 | `vidscope show <id>` affiche on-screen text + thumbnail + content_shape | unit | `pytest tests/unit/cli/test_show.py -x` | Existant — compléter |
| R047 | `vidscope search --on-screen-text "promo"` retourne vidéos matchantes | unit | `pytest tests/unit/cli/test_search.py -x` | Existant — compléter |
| R047 | MCP tool `vidscope_get_frame_texts` retourne la liste correcte | unit | `pytest tests/unit/mcp/test_frame_texts_tool.py -x` | Wave 0 |

### Fixtures JPG nécessaires (Wave 0)

```
tests/fixtures/
├── ocr/
│   ├── frame_with_text.jpg       # Texte clair en français : "Lien en bio : example.com"
│   ├── frame_with_en_text.jpg    # Texte en anglais : "Link in bio: promo.com"
│   ├── frame_no_text.jpg         # Image sans texte (B-roll pur)
│   ├── frame_low_confidence.jpg  # Texte flou/partiel (test seuil confidence)
│   └── frame_mixed.jpg           # Texte + visage dans le même frame
├── faces/
│   ├── talking_head_solo.jpg     # Un visage frontal clairement visible
│   ├── talking_head_multi.jpg    # 2+ visages
│   ├── no_face_broll.jpg         # Pas de visage (paysage, texte)
│   └── face_profile.jpg          # Visage de profil (test faux négatif attendu)
```

**Génération des fixtures :** créer des JPGs synthétiques avec PIL (`Pillow`) pour les tests
unitaires — pas besoin de vraies photos. Pour le test d'intégration réelle, utiliser un vrai
frame d'une Reel Instagram avec du texte on-screen.

### Benchmark performance OCR

```python
# tests/unit/adapters/vision/test_rapidocr_performance.py
import pytest
from pathlib import Path

@pytest.mark.slow
def test_ocr_30_frames_under_20s(tmp_path, benchmark):
    """OCR sur 30 frames doit compléter en < 20s sur CPU."""
    # Générer 30 copies de frame_with_text.jpg
    frames = [tmp_path / f"frame_{i:04d}.jpg" for i in range(30)]
    for f in frames:
        f.write_bytes(Path("tests/fixtures/ocr/frame_with_text.jpg").read_bytes())

    engine = RapidOcrEngine()

    def run_30_frames():
        results = []
        for frame_path in frames:
            results.extend(engine.extract_text(str(frame_path)))
        return results

    result = benchmark(run_30_frames)
    assert benchmark.stats.mean < 20.0, f"OCR too slow: {benchmark.stats.mean:.1f}s"
```

### Gaps Wave 0

- [ ] `tests/unit/domain/test_frame_text.py` — invariants FrameText entity
- [ ] `tests/unit/domain/test_content_shape.py` — enum ContentShape
- [ ] `tests/unit/adapters/vision/test_rapidocr_engine.py` — OCR adapter tests
- [ ] `tests/unit/adapters/vision/test_haarcascade_face_counter.py` — face detection tests
- [ ] `tests/unit/adapters/sqlite/test_frame_text_repository.py` — CRUD + FK cascade
- [ ] `tests/unit/pipeline/stages/test_visual_intelligence_stage.py` — stage integration
- [ ] `tests/unit/mcp/test_frame_texts_tool.py` — MCP tool
- [ ] `tests/fixtures/ocr/*.jpg` + `tests/fixtures/faces/*.jpg` — créer avec Pillow
- [ ] Framework install : `uv sync --extra vision` pour rapidocr + opencv

---

## Log des Assumptions

| # | Claim | Section | Risque si faux |
|---|---|---|---|
| A1 | Performance OCR RapidOCR : 200-500ms/frame, 30 frames < 20s | §1.6 | Si plus lent, la cible < 20s serait manquée — benchmark obligatoire |
| A2 | Haarcascade fiable pour talking_head vs broll avec 40% seuil | §2.5 | Trop de faux négatifs → mauvaise classification — acceptable car heuristique |
| A3 | Le modèle ONNX de rapidocr est téléchargé au premier appel `RapidOCR()` | §1.3 | Si téléchargé à l'import, le startup time augmente — vérifier avec test |
| A4 | `cv2.data.haarcascades` disponible dans opencv-python-headless | §2.2 | Si absent, le chemin du fichier XML devra être hardcodé — LOW risk |

---

## Questions ouvertes

1. **rapidocr-onnxruntime 1.4.4 vs optional-dep vision**
   - Ce qu'on sait : le package est en mode "graduated maintenance" (v2.x est le futur)
   - Ce qui est flou : si Python 3.13 est supporté en M009+ (rapidocr-onnxruntime cap à `<3.13`)
   - Recommandation : pin `rapidocr-onnxruntime>=1.4.4,<2` et ajouter une note sur la migration v2 future

2. **Où insérer VisualIntelligenceStage exactement par rapport à MetadataExtractStage**
   - Ce qu'on sait : MetadataExtractStage.is_satisfied vérifie `has_any_for_video` (links)
   - Ce qui est flou : si visual_intelligence produit des OCR-links, le re-run skip metadata_extract
   - Recommandation : insérer AVANT metadata_extract, mais ajuster is_satisfied de metadata_extract
     pour vérifier séparément les sources description/transcript

3. **Taille du modèle ONNX et cache**
   - Ce qu'on sait : ~50 MB annoncé dans la roadmap
   - Ce qui est flou : emplacement exact du cache sur Windows (platformdirs ?)
   - Recommandation : documenter dans doctor.py check_ocr_model()

---

## Sources

### Primaires (HIGH confidence)
- PyPI registry — versions vérifiées de `rapidocr-onnxruntime`, `opencv-python-headless`, `onnxruntime`
- Code source projet — `schema.py`, `container.py`, `startup.py`, `metadata_extract.py`, `.importlinter`
- SQLite FTS5 official docs — tokenizer unicode61 comportement

### Secondaires (MEDIUM confidence)
- https://github.com/RapidAI/RapidOCR/blob/0a603b4e8919386f3647eca5cdeba7620b4988e0/python/README.md — API v1.4.x
- https://deepwiki.com/RapidAI/RapidOCR/5.1-python-api — API v2.x (pour comparaison)
- https://docs.opencv.org/4.x/ — haarcascade API

### Tertiaires (LOW confidence)
- Estimation performance OCR < 20s sur 30 frames — basée sur profils communautaires non vérifiés
