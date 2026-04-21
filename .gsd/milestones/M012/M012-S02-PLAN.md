---
phase: M012
plan: S02
type: execute
wave: 1
depends_on: [M012/S01]
files_modified:
  - src/vidscope/pipeline/stages/analyze.py
  - src/vidscope/adapters/heuristic/stopwords.py
  - tests/unit/pipeline/stages/test_analyze.py
  - tests/unit/adapters/heuristic/test_analyzer.py
  - tests/unit/adapters/heuristic/test_stopwords.py
autonomous: true
requirements: [R062, R063]
tags: [analyze, heuristic, stopwords, ocr, carousel]
must_haves:
  truths:
    - "`AnalyzeStage.is_satisfied` no longer short-circuits `MediaType.IMAGE` / `MediaType.CAROUSEL` — returns False whenever no `Analysis` row exists for `ctx.video_id`, True otherwise, regardless of media_type"
    - "`AnalyzeStage.execute` builds a synthetic `Transcript` from `uow.frame_texts.list_for_video(video_id)` when `uow.transcripts.get_for_video(video_id)` returns None and concatenates the frame_text rows (ordered by repo) with a single space, filtering empty/whitespace-only rows"
    - "`AnalyzeStage.execute` uses `Language.UNKNOWN` for the synthetic OCR Transcript — never raises `AnalysisError` when transcript is None but frame_texts exist OR when both are absent (falls through to empty Transcript → analyzer returns stub Analysis with score=0 and summary='no speech detected')"
    - "`AnalyzeStage.execute` preserves all M010 additive fields (verticals, information_density, actionability, novelty, production_quality, sentiment, is_sponsored, content_type, reasoning) when rebinding the persisted Analysis with ctx.video_id"
    - "`FRENCH_STOPWORDS` contains at least 30 new French contractions (c'est, j'ai, d'un, qu'il, n'est, s'il, etc.) and at least 40 common conjugated verb forms (veux, peux, pouvez, montrer, etc.) exposed via new private frozensets `_FRENCH_CONTRACTIONS` and `_FRENCH_COMMON_VERBS` unioned into `FRENCH_STOPWORDS`"
    - "`ALL_STOPWORDS` exposes the union — `HeuristicAnalyzer._is_meaningful_word('c\\'est')` returns False, same for 'j\\'ai', 'd\\'un', 'qu\\'il', 'veux', 'peux', 'pouvez', 'montrer'"
    - "`FRENCH_STOPWORDS` and `ENGLISH_STOPWORDS` each contain at least 100 entries (R063 minimum-size requirement)"
    - "Two obsolete tests `TestAnalyzeStageMediaType.test_is_satisfied_returns_true_for_image` and `TestAnalyzeStageMediaType.test_is_satisfied_returns_true_for_carousel` are DELETED from `tests/unit/pipeline/stages/test_analyze.py` and replaced by new R062-aligned tests"
    - "Full unit test suite `python -m pytest tests/unit -q` passes with zero regressions — baseline 1658 tests must rise to ~1670 tests (new R062 + R063 tests) and all must pass"
  artifacts:
    - path: "src/vidscope/pipeline/stages/analyze.py"
      provides: "AnalyzeStage with OCR fallback for carousel/image and fixed is_satisfied"
      contains: "uow.frame_texts.list_for_video"
    - path: "src/vidscope/adapters/heuristic/stopwords.py"
      provides: "FRENCH_STOPWORDS extended with contractions + common verbs"
      contains: "_FRENCH_CONTRACTIONS"
    - path: "tests/unit/pipeline/stages/test_analyze.py"
      provides: "R062 tests — carousel OCR fallback, is_satisfied behavior, empty-source stub"
      contains: "test_carousel_with_frame_texts_produces_analysis"
    - path: "tests/unit/adapters/heuristic/test_analyzer.py"
      provides: "R063 tests — French contractions + conjugated verbs filtered from keywords"
      contains: "test_french_contractions_excluded_from_keywords"
    - path: "tests/unit/adapters/heuristic/test_stopwords.py"
      provides: "R063 vocabulary-coverage tests — minimum size + explicit membership"
      contains: "test_stopword_sets_meet_minimum_size"
  key_links:
    - from: "src/vidscope/pipeline/stages/analyze.py::AnalyzeStage.is_satisfied"
      to: "uow.analyses.get_latest_for_video"
      via: "regardless of media_type (no more IMAGE/CAROUSEL short-circuit)"
      pattern: "uow\\.analyses\\.get_latest_for_video"
    - from: "src/vidscope/pipeline/stages/analyze.py::AnalyzeStage.execute"
      to: "uow.frame_texts.list_for_video"
      via: "OCR fallback when transcript is None — concatenation of FrameText.text"
      pattern: "uow\\.frame_texts\\.list_for_video"
    - from: "src/vidscope/pipeline/stages/analyze.py::AnalyzeStage.execute"
      to: "vidscope.domain.Transcript + Language.UNKNOWN"
      via: "synthetic Transcript built in-memory from OCR concat (never persisted)"
      pattern: "Language\\.UNKNOWN"
    - from: "src/vidscope/adapters/heuristic/stopwords.py::FRENCH_STOPWORDS"
      to: "_FRENCH_CONTRACTIONS | _FRENCH_COMMON_VERBS"
      via: "frozenset union at module level"
      pattern: "_FRENCH_CONTRACTIONS \\| _FRENCH_COMMON_VERBS"
    - from: "src/vidscope/adapters/heuristic/analyzer.py::_is_meaningful_word"
      to: "ALL_STOPWORDS membership check (unchanged — stopwords module provides the data)"
      via: "token not in ALL_STOPWORDS filters contractions + conjugated verbs"
      pattern: "token not in ALL_STOPWORDS"
---

<objective>
M012/S02 — Analyze intelligence carousel.

Deux défauts précis du pipeline d'analyse heuristique sont résolus :

1. **R062** — `AnalyzeStage.is_satisfied` court-circuite actuellement tout `MediaType.IMAGE` et `MediaType.CAROUSEL` (lignes 42-43 de `analyze.py`), ce qui empêche toute analyse des carousels même quand `VisualIntelligenceStage` a déjà peuplé la table `frame_texts` via OCR. Après ce plan, `is_satisfied` vérifie uniquement la présence d'une `Analysis` existante (indépendamment du media_type), et `execute()` construit un `Transcript` synthétique en mémoire à partir de `uow.frame_texts.list_for_video(video_id)` lorsque `uow.transcripts.get_for_video(video_id)` retourne `None`. Aucun crash lorsque ni transcript ni OCR ne sont disponibles — l'analyzer produit un stub (score=0, summary="no speech detected") comme pour un transcript vide.

2. **R063** — Le tokenizer V1 `_WORD_PATTERN = r"[a-zàâäéèêëïîôöùûüÿçœæ']+"` capture l'apostrophe comme partie du token (`"c'est"` → `["c'est"]`). Les stopwords actuels n'incluent pas ces formes contractées FR ni les verbes conjugués courants (`veux`, `peux`, `pouvez`, `montrer`, etc.). Résultat observé : topics pollués par des mots grammaticaux. Ce plan ajoute deux frozensets privés `_FRENCH_CONTRACTIONS` (~30 entrées) et `_FRENCH_COMMON_VERBS` (~60 entrées) unionés dans `FRENCH_STOPWORDS`. Aucun changement au tokenizer (compatibilité descendante avec les 1658 tests existants).

Purpose : rendre `vidscope add <carousel-url>` observablement utile — une ligne `analyses` est produite pour tout contenu avec OCR, et les keywords/topics reflètent le domaine métier au lieu de mots vides.

Output : 2 fichiers source patchés (`analyze.py`, `stopwords.py`), 3 fichiers de test étendus/créés, 2 tests M010 obsolètes supprimés, zéro régression sur les 1658 tests existants.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M012/M012-ROADMAP.md
@.gsd/milestones/M012/M012-S02-RESEARCH.md
@.gsd/milestones/M012/M012-S01-SUMMARY.md

# Fichiers source touchés
@src/vidscope/pipeline/stages/analyze.py
@src/vidscope/adapters/heuristic/stopwords.py

# Fichiers source à lire (non modifiés mais contextuels)
@src/vidscope/adapters/heuristic/analyzer.py
@src/vidscope/adapters/heuristic/heuristic_v2.py
@src/vidscope/adapters/sqlite/frame_text_repository.py

# Tests à étendre / modifier
@tests/unit/pipeline/stages/test_analyze.py
@tests/unit/adapters/heuristic/test_analyzer.py
@tests/unit/adapters/heuristic/test_golden.py

<interfaces>
<!-- Contrats essentiels à l'exécuteur. Extraits du code existant — pas d'exploration nécessaire. -->

From src/vidscope/domain/entities.py (Transcript — frozen dataclass) :
```python
@dataclass(frozen=True, slots=True)
class Transcript:
    video_id: VideoId
    language: Language
    full_text: str
    segments: tuple[TranscriptSegment, ...] = ()
    id: int | None = None
    created_at: datetime | None = None

    def is_empty(self) -> bool:
        return not self.full_text.strip()
```

From src/vidscope/domain/entities.py (FrameText) :
```python
@dataclass(frozen=True, slots=True)
class FrameText:
    video_id: VideoId
    frame_id: int
    text: str            # non-optional, peut être "" en pratique
    confidence: float
    bbox: str | None = None
    id: int | None = None
    created_at: datetime | None = None
```

From src/vidscope/domain/values.py (Language enum) :
```python
class Language(StrEnum):
    # ... FRENCH, ENGLISH, ... existent déjà ...
    UNKNOWN = "unknown"  # légitime pour l'OCR (source sans détection de langue)
```

From src/vidscope/domain/entities.py (Analysis — frozen dataclass, tous les champs M010) :
```python
@dataclass(frozen=True, slots=True)
class Analysis:
    video_id: VideoId
    provider: str
    language: Language
    keywords: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    score: float | None = None
    summary: str | None = None
    # --- M010 additive fields ---
    verticals: tuple[str, ...] = ()
    information_density: float | None = None
    actionability: float | None = None
    novelty: float | None = None
    production_quality: float | None = None
    sentiment: SentimentLabel | None = None
    is_sponsored: bool | None = None
    content_type: ContentType | None = None
    reasoning: str | None = None
    id: int | None = None
    created_at: datetime | None = None
```

From src/vidscope/ports/repositories.py + src/vidscope/adapters/sqlite/frame_text_repository.py :
```python
# FrameTextRepository Protocol
class FrameTextRepository(Protocol):
    def list_for_video(self, video_id: VideoId) -> list[FrameText]:
        """Return all frame_texts for a video, ordered by frame_id ASC, id ASC."""

# SqliteUnitOfWork expose:
#   uow.frames: FrameRepository
#   uow.frame_texts: FrameTextRepository
#   uow.transcripts: TranscriptRepository
#   uow.analyses: AnalysisRepository
#   uow.videos: VideoRepository
```

From src/vidscope/pipeline/stages/analyze.py (AnalyzeStage AVANT patch — lignes 36-89) :
```python
def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
    # R062: bloc à SUPPRIMER
    if ctx.media_type in (MediaType.IMAGE, MediaType.CAROUSEL):
        return True
    if ctx.video_id is None:
        return False
    existing = uow.analyses.get_latest_for_video(ctx.video_id)
    return existing is not None

def execute(self, ctx, uow):
    if ctx.video_id is None:
        raise AnalysisError("analyze stage requires ctx.video_id; ...")

    transcript = uow.transcripts.get_for_video(ctx.video_id)
    if transcript is None:
        # R062: à REMPLACER par fallback OCR (voir Pattern 1 de RESEARCH.md)
        raise AnalysisError(
            f"analyze stage requires a transcript for video {ctx.video_id}; ..."
        )

    raw_analysis = self._analyzer.analyze(transcript)
    # Rebind manuel actuel — À ÉTENDRE pour inclure les 9 champs M010
    analysis = Analysis(
        video_id=ctx.video_id,
        provider=raw_analysis.provider,
        language=raw_analysis.language,
        keywords=raw_analysis.keywords,
        topics=raw_analysis.topics,
        score=raw_analysis.score,
        summary=raw_analysis.summary,
    )
    persisted = uow.analyses.add(analysis)
    ctx.analysis_id = persisted.id
    # ... return StageResult(...)
```

From src/vidscope/adapters/heuristic/stopwords.py (FRENCH_STOPWORDS AVANT patch — lignes 41-65) :
- Contient déjà : `le`, `la`, `les`, `de`, `des`, `du`, `être`, `avoir`, `faire`, ... + lettres seules `c`, `j`, `l`, `d`, `n`, `m`, `t`, `s`, `qu`.
- Ne contient PAS : `c'est`, `j'ai`, `d'un`, `qu'il`, `n'est`, `s'il`, `m'a`, `t'as`, ni `veux`, `peux`, `pouvez`, `montrer`, `pris`, `mis`, `montré`, `passé`, etc.

From src/vidscope/adapters/heuristic/analyzer.py (helpers réutilisés par V2) :
```python
# V2 importe: _build_summary, _compute_score, _is_meaningful_word, _tokenize
# => Un unique patch de stopwords.py bénéficie à V1 ET V2.
_WORD_PATTERN = re.compile(r"[a-zàâäéèêëïîôöùûüÿçœæ']+", re.IGNORECASE)
_MIN_KEYWORD_LENGTH = 4
_EMPTY_SUMMARY = "no speech detected"
```

From tests/unit/pipeline/stages/test_analyze.py (FakeAnalyzer — à RÉUTILISER dans les nouveaux tests) :
```python
@dataclass
class FakeAnalyzer:
    provider_name_value: str = "fake"
    error: Exception | None = None
    calls: list[Transcript] = field(default_factory=list)
    @property
    def provider_name(self) -> str: return self.provider_name_value
    def analyze(self, transcript: Transcript) -> Analysis:
        self.calls.append(transcript)
        if self.error is not None: raise self.error
        return Analysis(
            video_id=transcript.video_id,
            provider=self.provider_name_value,
            language=transcript.language,
            keywords=("fake", "test", "analysis"),
            topics=("fake-topic",),
            score=75.0,
            summary="fake summary from FakeAnalyzer",
        )

# Fixture engine (à réutiliser tel quel dans les nouveaux tests) :
@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    eng = build_engine(tmp_path / "test.db")
    init_db(eng)
    return eng
```
</interfaces>
</context>

<tasks>

<!-- ====================================================================== -->
<!-- WAVE 1 — RED tests (écrits en premier ; ils doivent échouer avant        -->
<!-- les implémentations T04-T05). Parallélisables : fichiers test disjoints. -->
<!-- ====================================================================== -->

<task type="auto" tdd="true">
  <name>T01: RED — delete 2 obsolete M010 tests + add R062 is_satisfied tests (carousel + image)</name>
  <files>tests/unit/pipeline/stages/test_analyze.py</files>
  <read_first>
    - tests/unit/pipeline/stages/test_analyze.py (intégralité ; en particulier la classe `TestAnalyzeStageMediaType` lignes 173-200 et la classe `TestAnalyzeStageHappyPath` lignes 90-134 pour réutiliser le pattern)
    - src/vidscope/pipeline/stages/analyze.py (pour connaître le comportement cible de is_satisfied)
  </read_first>
  <behavior>
    - `is_satisfied` retourne `False` pour un CAROUSEL sans ligne `analyses` (nouveau comportement R062 — avant retournait True)
    - `is_satisfied` retourne `False` pour une IMAGE sans ligne `analyses` (nouveau comportement R062 — avant retournait True)
    - `is_satisfied` retourne `True` pour un CAROUSEL qui a déjà une ligne `analyses`
    - `is_satisfied` retourne `True` pour une IMAGE qui a déjà une ligne `analyses`
    - Les deux anciens tests `test_is_satisfied_returns_true_for_image` et `test_is_satisfied_returns_true_for_carousel` DOIVENT être SUPPRIMÉS (leur comportement asserté est ce que R062 change explicitement)
  </behavior>
  <action>
**Étape 1 — SUPPRIMER exactement 2 tests** dans `tests/unit/pipeline/stages/test_analyze.py` :

- Supprimer la méthode `TestAnalyzeStageMediaType.test_is_satisfied_returns_true_for_image` (lignes 176-187 environ).
- Supprimer la méthode `TestAnalyzeStageMediaType.test_is_satisfied_returns_true_for_carousel` (lignes 189-200 environ).
- La classe `TestAnalyzeStageMediaType` peut être entièrement supprimée si elle ne contient plus aucun test après ces suppressions (elle n'a que ces 2 tests). L'en-tête de section commentaire (`# IMAGE / CAROUSEL short-circuit`) doit être mis à jour ou remplacé par `# R062 — IMAGE / CAROUSEL OCR fallback`.

**Étape 2 — AJOUTER une nouvelle classe `TestAnalyzeStageMediaTypeR062`** en fin de fichier. Elle réutilise la fixture `engine` et le helper `_seed_video_with_transcript` déjà existants, plus un nouveau helper local `_seed_video` qui crée une Video (sans transcript) pour un `platform_id` donné et retourne son `VideoId` :

```python
def _seed_video_without_transcript(
    engine: Engine,
    *,
    platform_id: str = "carousel1",
    media_key: str = "videos/instagram/carousel1/items/0000.jpg",
) -> VideoId:
    """Insert a Video row (no transcript, no analysis, no frame_texts)."""
    with SqliteUnitOfWork(engine) as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.INSTAGRAM,
                platform_id=PlatformId(platform_id),
                url=f"https://www.instagram.com/p/{platform_id}/",
                media_key=media_key,
            )
        )
        assert video.id is not None
        return video.id


class TestAnalyzeStageMediaTypeR062:
    """R062 — is_satisfied no longer short-circuits IMAGE/CAROUSEL.

    Replaces the deleted M010 tests: carousels/images must be analyzed
    when OCR frame_texts exist, so is_satisfied must actually check
    whether an Analysis row exists for the video.
    """

    def test_is_satisfied_false_for_carousel_without_analysis(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import MediaType

        video_id = _seed_video_without_transcript(
            engine, platform_id="carousel_none"
        )
        ctx = PipelineContext(
            source_url="https://www.instagram.com/p/carousel_none/",
            video_id=video_id,
            media_type=MediaType.CAROUSEL,
        )
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False

    def test_is_satisfied_false_for_image_without_analysis(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import MediaType

        video_id = _seed_video_without_transcript(
            engine, platform_id="image_none"
        )
        ctx = PipelineContext(
            source_url="https://www.instagram.com/p/image_none/",
            video_id=video_id,
            media_type=MediaType.IMAGE,
        )
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False

    def test_is_satisfied_true_for_carousel_with_analysis(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import MediaType

        video_id = _seed_video_with_transcript(engine)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
            media_type=MediaType.CAROUSEL,
        )
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        # Seed an existing analysis
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is True

    def test_is_satisfied_false_without_video_id(self, engine: Engine) -> None:
        from vidscope.domain import MediaType

        ctx = PipelineContext(source_url="x", media_type=MediaType.CAROUSEL)
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False
```

**Note** : `_seed_video_with_transcript` existant dans le fichier utilise `Platform.YOUTUBE` et `platform_id="abc"` — ne pas modifier cet helper ; ajouter `_seed_video_without_transcript` comme NOUVEAU helper à côté. Les tests seront RED jusqu'à T04.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageMediaTypeR062 -x -v 2>&1 | tail -40</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "test_is_satisfied_returns_true_for_image\|test_is_satisfied_returns_true_for_carousel" tests/unit/pipeline/stages/test_analyze.py` retourne ZÉRO ligne (les deux tests supprimés)
    - `grep -n "class TestAnalyzeStageMediaTypeR062" tests/unit/pipeline/stages/test_analyze.py` retourne exactement 1 ligne
    - `grep -n "test_is_satisfied_false_for_carousel_without_analysis\|test_is_satisfied_false_for_image_without_analysis\|test_is_satisfied_true_for_carousel_with_analysis\|test_is_satisfied_false_without_video_id" tests/unit/pipeline/stages/test_analyze.py` retourne exactement 4 lignes
    - `grep -n "_seed_video_without_transcript" tests/unit/pipeline/stages/test_analyze.py` retourne au moins 2 lignes (définition + 2 usages)
    - En l'état (avant T04), `pytest tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageMediaTypeR062::test_is_satisfied_false_for_carousel_without_analysis` échoue (RED — le code court-circuite encore)
  </acceptance_criteria>
  <done>
    Les 2 tests obsolètes sont supprimés ; la nouvelle classe `TestAnalyzeStageMediaTypeR062` contient 4 tests R062 ; en mode RED les tests `false_for_*` échouent tant que T04 n'a pas modifié `is_satisfied`.
  </done>
</task>

<task type="auto" tdd="true">
  <name>T02: RED — add R062 execute() OCR fallback tests (carousel with/without frame_texts)</name>
  <files>tests/unit/pipeline/stages/test_analyze.py</files>
  <read_first>
    - tests/unit/pipeline/stages/test_analyze.py (pour l'état post-T01 ; doit contenir déjà `_seed_video_without_transcript`)
    - src/vidscope/adapters/heuristic/analyzer.py (comportement de `HeuristicAnalyzer` sur transcript vide — score=0, summary="no speech detected")
    - src/vidscope/adapters/sqlite/frame_text_repository.py (méthode `add_many_for_frame` pour savoir comment seed des FrameText dans les tests)
  </read_first>
  <behavior>
    - Un carousel avec 2 FrameText non-vides et sans Transcript → `execute()` appelle l'analyzer UNE fois avec un `Transcript(language=Language.UNKNOWN, full_text="<concat OCR>", segments=())`, persiste l'Analysis, et `ctx.analysis_id` est mutable
    - L'ordre des FrameText dans `full_text` respecte l'ordre du repo (frame_id ASC, id ASC)
    - Un carousel sans Transcript ET sans FrameText → `execute()` ne lève PAS, appelle l'analyzer avec un Transcript vide (`full_text=""`), une Analysis stub est persistée (score=0, summary="no speech detected")
    - Un carousel avec FrameText dont text="" ou whitespace → ces rows sont filtrés à la concaténation (pas d'espaces multiples parasites)
  </behavior>
  <action>
Ajouter une nouvelle classe `TestAnalyzeStageOcrFallback` en fin du fichier `tests/unit/pipeline/stages/test_analyze.py`. Importer les symboles manquants en haut du fichier si absents : `Frame`, `FrameText`, `MediaType` depuis `vidscope.domain`.

Helper local (à mettre avant la classe, avec les autres helpers module-level) :

```python
def _seed_carousel_with_frame_texts(
    engine: Engine,
    *,
    platform_id: str = "carousel_with_ocr",
    texts: tuple[str, ...] = ("Hello world", "Second block"),
) -> VideoId:
    """Insert a Video + 1 Frame + N FrameText rows (no transcript).

    Frames are ordered frame_id ASC (one frame per call), so
    FrameTextRepository.list_for_video returns them in insertion order.
    """
    from vidscope.domain import Frame, FrameText

    with SqliteUnitOfWork(engine) as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.INSTAGRAM,
                platform_id=PlatformId(platform_id),
                url=f"https://www.instagram.com/p/{platform_id}/",
                media_key=f"videos/instagram/{platform_id}/items/0000.jpg",
            )
        )
        assert video.id is not None
        frame = uow.frames.add_many(
            [
                Frame(
                    video_id=video.id,
                    image_key=f"videos/instagram/{platform_id}/items/0000.jpg",
                    timestamp_ms=0,
                    is_keyframe=True,
                )
            ]
        )[0]
        assert frame.id is not None
        uow.frame_texts.add_many_for_frame(
            frame.id,
            video.id,
            [
                FrameText(
                    video_id=video.id,
                    frame_id=frame.id,
                    text=t,
                    confidence=0.95,
                )
                for t in texts
            ],
        )
        return video.id
```

Classe de tests :

```python
class TestAnalyzeStageOcrFallback:
    """R062 — execute() falls back to frame_texts when transcript is None."""

    def test_carousel_with_frame_texts_produces_analysis(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import Language, MediaType

        video_id = _seed_carousel_with_frame_texts(
            engine,
            platform_id="carousel_ocr_1",
            texts=("Claude skills for Architects", "Terminal workflow tip"),
        )
        fake = FakeAnalyzer()
        stage = AnalyzeStage(analyzer=fake)
        ctx = PipelineContext(
            source_url="https://www.instagram.com/p/carousel_ocr_1/",
            video_id=video_id,
            media_type=MediaType.CAROUSEL,
        )

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        # Analyzer received a synthetic Transcript
        assert len(fake.calls) == 1
        received = fake.calls[0]
        assert received.video_id == video_id
        assert received.language is Language.UNKNOWN
        # Concatenation preserves order (frame_id ASC, id ASC)
        assert "Claude skills for Architects" in received.full_text
        assert "Terminal workflow tip" in received.full_text
        assert received.full_text.index("Claude") < received.full_text.index(
            "Terminal"
        )
        assert received.segments == ()

        # Analysis was persisted
        assert ctx.analysis_id is not None
        with SqliteUnitOfWork(engine) as uow:
            persisted = uow.analyses.get_latest_for_video(video_id)
            assert persisted is not None
            assert persisted.video_id == video_id

    def test_carousel_without_transcript_and_without_frame_texts_produces_stub(
        self, engine: Engine
    ) -> None:
        """R062 success criteria #4 — no crash, stub Analysis persisted."""
        from vidscope.adapters.heuristic import HeuristicAnalyzer
        from vidscope.domain import MediaType

        video_id = _seed_video_without_transcript(
            engine, platform_id="carousel_empty"
        )
        stage = AnalyzeStage(analyzer=HeuristicAnalyzer())
        ctx = PipelineContext(
            source_url="https://www.instagram.com/p/carousel_empty/",
            video_id=video_id,
            media_type=MediaType.CAROUSEL,
        )

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)  # must not raise

        with SqliteUnitOfWork(engine) as uow:
            persisted = uow.analyses.get_latest_for_video(video_id)
            assert persisted is not None
            assert persisted.score == 0.0
            assert persisted.summary == "no speech detected"
            assert persisted.keywords == ()

    def test_ocr_concat_filters_empty_and_whitespace_rows(
        self, engine: Engine
    ) -> None:
        """Empty or whitespace-only FrameText.text rows must be filtered
        before concatenation to avoid doubled separators."""
        video_id = _seed_carousel_with_frame_texts(
            engine,
            platform_id="carousel_mixed",
            texts=("Hello", "", "   ", "World"),
        )
        fake = FakeAnalyzer()
        stage = AnalyzeStage(analyzer=fake)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
        )
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        assert len(fake.calls) == 1
        got = fake.calls[0].full_text
        assert got == "Hello World"  # single space, no doubled spacing

    def test_carousel_produces_domain_topics_end_to_end(
        self, engine: Engine
    ) -> None:
        """R062 + R063 integration — real HeuristicAnalyzer returns
        domain tokens from OCR (no French grammar words, proper nouns kept)."""
        from vidscope.adapters.heuristic import HeuristicAnalyzer

        video_id = _seed_carousel_with_frame_texts(
            engine,
            platform_id="carousel_claude_skills",
            texts=(
                "Claude skills for Architects",
                "Terminal workflow with the agent",
                "Claude agent builds skills in the terminal",
            ),
        )
        stage = AnalyzeStage(analyzer=HeuristicAnalyzer())
        ctx = PipelineContext(source_url="x", video_id=video_id)
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        with SqliteUnitOfWork(engine) as uow:
            persisted = uow.analyses.get_latest_for_video(video_id)
            assert persisted is not None
            # Domain tokens present (case-insensitive by tokenizer)
            assert "claude" in persisted.keywords
            assert "skills" in persisted.keywords or "agent" in persisted.keywords
            # Grammar words absent
            assert "the" not in persisted.keywords
            assert "with" not in persisted.keywords
```

Tous ces tests sont RED tant que T04 n'est pas fait (execute actuel raise AnalysisError quand transcript is None).
  </action>
  <verify>
    <automated>python -m pytest tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageOcrFallback -x -v 2>&1 | tail -40</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class TestAnalyzeStageOcrFallback" tests/unit/pipeline/stages/test_analyze.py` retourne 1 ligne
    - `grep -n "test_carousel_with_frame_texts_produces_analysis\|test_carousel_without_transcript_and_without_frame_texts_produces_stub\|test_ocr_concat_filters_empty_and_whitespace_rows\|test_carousel_produces_domain_topics_end_to_end" tests/unit/pipeline/stages/test_analyze.py` retourne 4 lignes
    - `grep -n "_seed_carousel_with_frame_texts" tests/unit/pipeline/stages/test_analyze.py` retourne au moins 2 lignes (définition + usage)
    - `grep -c "Language.UNKNOWN" tests/unit/pipeline/stages/test_analyze.py` retourne au moins 1
    - En l'état (avant T04), `pytest tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageOcrFallback::test_carousel_with_frame_texts_produces_analysis` échoue avec AnalysisError (RED)
  </acceptance_criteria>
  <done>
    Classe `TestAnalyzeStageOcrFallback` ajoutée avec 4 tests R062 end-to-end ; helpers seed en place ; tests attendent T04 pour passer.
  </done>
</task>

<task type="auto" tdd="true">
  <name>T03: RED — R063 tests (French contractions + common verbs filtered) + stopwords coverage tests</name>
  <files>tests/unit/adapters/heuristic/test_analyzer.py, tests/unit/adapters/heuristic/test_stopwords.py</files>
  <read_first>
    - tests/unit/adapters/heuristic/test_analyzer.py (en particulier les classes `TestHeuristicAnalyzerFrenchContent` lignes 95-116 — patterns à reproduire)
    - src/vidscope/adapters/heuristic/analyzer.py (`_is_meaningful_word`, `_MIN_KEYWORD_LENGTH=4`)
    - src/vidscope/adapters/heuristic/stopwords.py (état actuel de FRENCH_STOPWORDS et ENGLISH_STOPWORDS)
  </read_first>
  <behavior>
    - Un texte FR contenant `c'est`, `j'ai`, `d'un`, `qu'il`, `n'est`, `s'il` → aucun de ces tokens n'apparaît dans `result.keywords`
    - Un texte FR contenant `veux`, `peux`, `pouvez`, `montrer`, `montré`, `pris`, `mis` → aucun de ces tokens n'apparaît dans `result.keywords`
    - Un texte FR réaliste ("je veux vous montrer c'est un bel outil pour créer des skills Claude") → `claude` et `skills` apparaissent, `veux`, `montrer`, `c'est`, `pour`, `des` n'apparaissent PAS
    - `FRENCH_STOPWORDS` et `ENGLISH_STOPWORDS` ont chacun ≥ 100 éléments après patch (R063 minimum-size)
    - Les frozensets `_FRENCH_CONTRACTIONS` et `_FRENCH_COMMON_VERBS` sont importables et contiennent les entrées canoniques (`c'est`, `j'ai`, `veux`, `peux`)
  </behavior>
  <action>
**Étape 1 — ÉTENDRE** `tests/unit/adapters/heuristic/test_analyzer.py`. Ajouter une nouvelle classe à la fin du fichier (ne pas casser l'existant) :

```python
class TestHeuristicAnalyzerFrenchStopwordsR063:
    """R063 — French contractions and conjugated verbs are filtered."""

    def test_french_contractions_excluded_from_keywords(self) -> None:
        text = (
            "c'est vraiment intéressant j'ai pensé d'un nouveau concept "
            "qu'il faut montrer n'est pas évident s'il existe une solution"
        )
        result = HeuristicAnalyzer().analyze(
            _transcript(text, language=Language.FRENCH)
        )
        for contracted in ("c'est", "j'ai", "d'un", "qu'il", "n'est", "s'il"):
            assert contracted not in result.keywords, (
                f"contracted form {contracted!r} leaked into keywords: "
                f"{result.keywords}"
            )

    def test_french_conjugated_verbs_excluded_from_keywords(self) -> None:
        text = (
            "je veux vous montrer comment vous peux créer avec ça "
            "pouvez prendre ce que j'ai pris et mis dans le projet montré"
        )
        result = HeuristicAnalyzer().analyze(
            _transcript(text, language=Language.FRENCH)
        )
        for verb in ("veux", "peux", "pouvez", "montrer", "montré", "pris", "mis"):
            assert verb not in result.keywords, (
                f"common conjugated verb {verb!r} leaked into keywords: "
                f"{result.keywords}"
            )

    def test_claude_skills_carousel_keeps_domain_tokens(self) -> None:
        """R063 — real-world carousel FR+EN mix yields domain topics only."""
        text = (
            "je veux vous montrer c'est un outil puissant pour créer "
            "des skills Claude dans le terminal avec un agent workflow"
        )
        result = HeuristicAnalyzer().analyze(
            _transcript(text, language=Language.FRENCH)
        )
        # Domain tokens retained (lowercase by tokenizer)
        assert "claude" in result.keywords
        assert "skills" in result.keywords or "terminal" in result.keywords
        # Grammar noise excluded
        for noise in ("veux", "montrer", "c'est", "pour", "des", "dans"):
            assert noise not in result.keywords, (
                f"noise {noise!r} leaked into keywords: {result.keywords}"
            )
```

**Étape 2 — CRÉER** un nouveau fichier `tests/unit/adapters/heuristic/test_stopwords.py` (fichier n'existe pas actuellement) :

```python
"""Tests for stopword set coverage (R063).

R063 requires FRENCH_STOPWORDS and ENGLISH_STOPWORDS to each contain at
least 100 entries. This module also pins the canonical French contractions
and conjugated verbs added in M012/S02 so accidental removals are caught.
"""

from __future__ import annotations

from vidscope.adapters.heuristic.stopwords import (
    ALL_STOPWORDS,
    ENGLISH_STOPWORDS,
    FRENCH_STOPWORDS,
)


class TestStopwordSetSizes:
    def test_french_stopwords_meet_minimum_size(self) -> None:
        """R063 — FRENCH_STOPWORDS must have at least 100 entries."""
        assert len(FRENCH_STOPWORDS) >= 100, (
            f"FRENCH_STOPWORDS has only {len(FRENCH_STOPWORDS)} entries, "
            f"R063 requires >= 100"
        )

    def test_english_stopwords_meet_minimum_size(self) -> None:
        """R063 — ENGLISH_STOPWORDS must have at least 100 entries."""
        assert len(ENGLISH_STOPWORDS) >= 100, (
            f"ENGLISH_STOPWORDS has only {len(ENGLISH_STOPWORDS)} entries, "
            f"R063 requires >= 100"
        )

    def test_all_stopwords_is_union(self) -> None:
        assert ALL_STOPWORDS == (ENGLISH_STOPWORDS | FRENCH_STOPWORDS)


class TestFrenchContractions:
    """R063 — canonical contracted forms must be part of FRENCH_STOPWORDS."""

    def test_common_contractions_present(self) -> None:
        canonical = [
            "c'est", "j'ai", "d'un", "d'une",
            "qu'il", "qu'elle", "n'est", "n'a",
            "s'il", "s'est", "l'autre", "l'un",
        ]
        missing = [c for c in canonical if c not in FRENCH_STOPWORDS]
        assert not missing, f"missing contractions: {missing}"


class TestFrenchConjugatedVerbs:
    """R063 — common conjugated verb forms must be part of FRENCH_STOPWORDS."""

    def test_common_conjugated_verbs_present(self) -> None:
        canonical = [
            "veux", "veut", "peux", "peut", "pouvez", "peuvent",
            "dois", "doit", "sais", "sait",
            "vois", "voit", "viens", "vient",
            "dit", "fait", "montrer", "montré",
            "pris", "mis", "passé",
        ]
        missing = [v for v in canonical if v not in FRENCH_STOPWORDS]
        assert not missing, f"missing conjugated verbs: {missing}"

    def test_private_sets_are_importable(self) -> None:
        """The two new private frozensets must exist as module attributes."""
        from vidscope.adapters.heuristic import stopwords as sw

        assert hasattr(sw, "_FRENCH_CONTRACTIONS"), (
            "_FRENCH_CONTRACTIONS frozenset missing from stopwords module"
        )
        assert hasattr(sw, "_FRENCH_COMMON_VERBS"), (
            "_FRENCH_COMMON_VERBS frozenset missing from stopwords module"
        )
        assert isinstance(sw._FRENCH_CONTRACTIONS, frozenset)
        assert isinstance(sw._FRENCH_COMMON_VERBS, frozenset)
        # Size sanity
        assert len(sw._FRENCH_CONTRACTIONS) >= 30
        assert len(sw._FRENCH_COMMON_VERBS) >= 40
```

Tous ces tests sont RED jusqu'à T05 : `FRENCH_STOPWORDS` actuel n'a pas encore `c'est`, `veux`, etc. ; les deux frozensets privés n'existent pas encore.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/adapters/heuristic/test_analyzer.py::TestHeuristicAnalyzerFrenchStopwordsR063 tests/unit/adapters/heuristic/test_stopwords.py -x -v 2>&1 | tail -40</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class TestHeuristicAnalyzerFrenchStopwordsR063" tests/unit/adapters/heuristic/test_analyzer.py` retourne 1 ligne
    - `grep -n "test_french_contractions_excluded_from_keywords\|test_french_conjugated_verbs_excluded_from_keywords\|test_claude_skills_carousel_keeps_domain_tokens" tests/unit/adapters/heuristic/test_analyzer.py` retourne 3 lignes
    - Le fichier `tests/unit/adapters/heuristic/test_stopwords.py` existe (nouveau)
    - `grep -n "TestStopwordSetSizes\|TestFrenchContractions\|TestFrenchConjugatedVerbs" tests/unit/adapters/heuristic/test_stopwords.py` retourne 3 lignes
    - `grep -n "_FRENCH_CONTRACTIONS\|_FRENCH_COMMON_VERBS" tests/unit/adapters/heuristic/test_stopwords.py` retourne au moins 4 lignes
    - En l'état (avant T05), `pytest tests/unit/adapters/heuristic/test_stopwords.py::TestFrenchContractions::test_common_contractions_present` échoue (RED — `c'est` absent de FRENCH_STOPWORDS)
  </acceptance_criteria>
  <done>
    R063 tests écrits : 3 tests dans test_analyzer.py + fichier complet test_stopwords.py (7 tests). Tous RED tant que T05 n'a pas étendu stopwords.py.
  </done>
</task>

<!-- ====================================================================== -->
<!-- WAVE 2 — GREEN implementations (dépendent des tests RED de Wave 1).    -->
<!-- T04 et T05 touchent des fichiers disjoints → parallélisables.          -->
<!-- ====================================================================== -->

<task type="auto" tdd="true">
  <name>T04: GREEN R062 — AnalyzeStage OCR fallback + is_satisfied fix + M010 fields passthrough</name>
  <files>src/vidscope/pipeline/stages/analyze.py</files>
  <read_first>
    - src/vidscope/pipeline/stages/analyze.py (intégralité — état actuel 104 lignes)
    - src/vidscope/domain/entities.py lignes 114-128 (Transcript dataclass)
    - src/vidscope/domain/entities.py lignes 143-171 (Analysis — tous les champs M010)
    - src/vidscope/domain/values.py lignes 164-174 (Language.UNKNOWN)
    - src/vidscope/adapters/heuristic/heuristic_v2.py lignes 173-190 (pattern de construction Analysis avec M010)
  </read_first>
  <behavior>
    - `is_satisfied`: plus de court-circuit IMAGE/CAROUSEL ; retourne False si video_id None ou si aucune Analysis, True sinon
    - `execute`: lorsque `transcript is None`, lit `uow.frame_texts.list_for_video(ctx.video_id)`, concatène `ft.text` avec espace (filtre les text vides/whitespace), construit `Transcript(video_id=ctx.video_id, language=Language.UNKNOWN, full_text=<concat>, segments=())`, passe à l'analyzer
    - Si aucun frame_text ou tous vides → `Transcript(..., full_text="", segments=())` (l'analyzer produit alors le stub via la branche existante `if not text.strip()` de HeuristicAnalyzer)
    - **Ne jamais lever AnalysisError à cause d'un transcript manquant** — uniquement si `ctx.video_id is None`
    - L'Analysis persistée conserve TOUS les champs M010 (verticals, information_density, actionability, novelty, production_quality, sentiment, is_sponsored, content_type, reasoning) — utiliser `dataclasses.replace` pour le rebind video_id au lieu du rebind manuel actuel
  </behavior>
  <action>
Remplacer intégralement le contenu de `src/vidscope/pipeline/stages/analyze.py` par :

```python
"""AnalyzeStage — fourth stage of the pipeline.

Reads the transcript produced by the transcribe stage (or, for
IMAGE / CAROUSEL content without audio, falls back to the OCR
frame_texts written by VisualIntelligenceStage — R062), runs the
configured Analyzer to produce a structured Analysis (language,
keywords, topics, score, summary + M010 score vector), and persists
it via the AnalysisRepository.
"""

from __future__ import annotations

from dataclasses import replace

from vidscope.domain import (
    AnalysisError,
    Language,
    StageName,
    Transcript,
)
from vidscope.ports import (
    Analyzer,
    PipelineContext,
    StageResult,
    UnitOfWork,
)

__all__ = ["AnalyzeStage"]


class AnalyzeStage:
    """Fourth stage of the pipeline — produce a structured analysis."""

    name: str = StageName.ANALYZE.value

    def __init__(self, *, analyzer: Analyzer) -> None:
        self._analyzer = analyzer

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Return True if analysis can be skipped.

        R062: no more IMAGE/CAROUSEL short-circuit. Every content with
        a known video_id is considered analyzable — we skip only when
        an Analysis row already exists for that video (idempotent).
        """
        if ctx.video_id is None:
            return False
        existing = uow.analyses.get_latest_for_video(ctx.video_id)
        return existing is not None

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Read the transcript (or OCR fallback), analyze it, persist.

        Mutates ``ctx.analysis_id`` on success.

        R062: when no Transcript is available (IMAGE / CAROUSEL or
        audio-less VIDEO), build a synthetic Transcript from the
        ``frame_texts`` rows written by VisualIntelligenceStage. If
        neither source is available, pass an empty Transcript so the
        analyzer produces a stub Analysis (score=0,
        summary='no speech detected') — no crash.

        Raises
        ------
        AnalysisError
            When ``ctx.video_id`` is missing, or when the analyzer
            itself raises.
        """
        if ctx.video_id is None:
            raise AnalysisError(
                "analyze stage requires ctx.video_id; ingest stage must run first"
            )

        transcript = uow.transcripts.get_for_video(ctx.video_id)
        if transcript is None:
            # R062: OCR fallback for IMAGE / CAROUSEL (and any video
            # that lost its transcript). Never raise — produce a stub
            # via the analyzer's empty-transcript branch if nothing.
            frame_texts = uow.frame_texts.list_for_video(ctx.video_id)
            ocr_concat = " ".join(
                ft.text for ft in frame_texts if ft.text and ft.text.strip()
            )
            transcript = Transcript(
                video_id=ctx.video_id,
                language=Language.UNKNOWN,
                full_text=ocr_concat,
                segments=(),
            )

        # The analyzer port itself raises AnalysisError on failure.
        # We let it propagate.
        raw_analysis = self._analyzer.analyze(transcript)

        # Preserve every field produced by the analyzer (including M010
        # additive fields: verticals, information_density, actionability,
        # novelty, production_quality, sentiment, is_sponsored,
        # content_type, reasoning). Only override video_id so the
        # persisted row's FK matches ctx regardless of analyzer behavior.
        analysis = replace(raw_analysis, video_id=ctx.video_id)

        persisted = uow.analyses.add(analysis)
        ctx.analysis_id = persisted.id

        keyword_count = len(persisted.keywords)
        score_str = (
            f"{persisted.score:.0f}" if persisted.score is not None else "n/a"
        )
        return StageResult(
            message=(
                f"analyzed via {persisted.provider}: "
                f"{keyword_count} keywords, score={score_str}"
            )
        )
```

Notes d'implémentation :
- Suppression de l'import `Analysis` et `MediaType` (plus utilisés).
- Ajout import `dataclasses.replace`, `Language`, `Transcript`.
- `replace(raw_analysis, video_id=ctx.video_id)` copie tous les champs M010 — résout une dette latente du rebind manuel qui omettait les champs M010 (OpenQuestion #1 du RESEARCH.md).
- Le test `test_missing_transcript_raises` dans la classe `TestAnalyzeStageErrors` (ligne 146-154 de test_analyze.py) va maintenant ÉCHOUER (nouveau comportement R062 — plus de raise). Ne PAS le supprimer : il sera traité en T06.
  </action>
  <verify>
    <automated>python -m pytest tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageMediaTypeR062 tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageOcrFallback tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageHappyPath -x -v 2>&1 | tail -40</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "if ctx.media_type in (MediaType.IMAGE, MediaType.CAROUSEL):" src/vidscope/pipeline/stages/analyze.py` retourne ZÉRO ligne (bloc supprimé)
    - `grep -n "uow.frame_texts.list_for_video(ctx.video_id)" src/vidscope/pipeline/stages/analyze.py` retourne exactement 1 ligne
    - `grep -n "Language.UNKNOWN" src/vidscope/pipeline/stages/analyze.py` retourne exactement 1 ligne
    - `grep -n "replace(raw_analysis, video_id=ctx.video_id)" src/vidscope/pipeline/stages/analyze.py` retourne exactement 1 ligne
    - `grep -n "from dataclasses import replace" src/vidscope/pipeline/stages/analyze.py` retourne exactement 1 ligne
    - `grep -n "R062" src/vidscope/pipeline/stages/analyze.py` retourne au moins 2 lignes (docstring mentions)
    - `pytest tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageOcrFallback` : 4/4 tests passent
    - `pytest tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageMediaTypeR062` : 4/4 tests passent
    - `pytest tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageHappyPath` : 3/3 tests passent (pas de régression)
  </acceptance_criteria>
  <done>
    `AnalyzeStage.is_satisfied` est corrigé (plus de short-circuit), `execute()` implémente le fallback OCR via `uow.frame_texts.list_for_video`, les champs M010 sont préservés via `dataclasses.replace`. Tests T01 + T02 passent (GREEN). Seul `test_missing_transcript_raises` échoue encore — traité en T06.
  </done>
</task>

<task type="auto" tdd="true">
  <name>T05: GREEN R063 — extend stopwords.py with French contractions + common verbs</name>
  <files>src/vidscope/adapters/heuristic/stopwords.py</files>
  <read_first>
    - src/vidscope/adapters/heuristic/stopwords.py (intégralité — 67 lignes)
    - src/vidscope/adapters/heuristic/analyzer.py lignes 36-37 (`_WORD_PATTERN` inclut `'`, `_MIN_KEYWORD_LENGTH = 4`)
  </read_first>
  <behavior>
    - Deux nouveaux frozensets privés au niveau module : `_FRENCH_CONTRACTIONS` (≥ 30 entrées) et `_FRENCH_COMMON_VERBS` (≥ 40 entrées)
    - `FRENCH_STOPWORDS` = set existant | `_FRENCH_CONTRACTIONS` | `_FRENCH_COMMON_VERBS`
    - `ALL_STOPWORDS` = `ENGLISH_STOPWORDS` | `FRENCH_STOPWORDS` (inchangé sur la ligne)
    - `ENGLISH_STOPWORDS` inchangé
    - Toutes les entrées sont lowercase (cohérent avec `_tokenize` qui lowercase)
    - Contractions listées : formes canoniques citées dans le RESEARCH.md (c'est, j'ai, d'un, d'une, qu'il, qu'elle, n'est, s'il, l'autre, l'un, etc.) — minimum ceux testés par T03
  </behavior>
  <action>
Remplacer intégralement le contenu de `src/vidscope/adapters/heuristic/stopwords.py` par :

```python
"""Stopword lists for the heuristic analyzer.

French + English stopword sets. Stored as frozensets for O(1) lookup.

R063 extension (M012/S02) : the V1 tokenizer captures apostrophes as
part of tokens (``_WORD_PATTERN = r"[a-zàâäéèêëïîôöùûüÿçœæ']+"``), so
``"c'est"`` is one token, not three. To filter these correctly, we add
two auxiliary frozensets — ``_FRENCH_CONTRACTIONS`` (canonical
contracted forms) and ``_FRENCH_COMMON_VERBS`` (conjugated verbs that
carry no domain semantics) — unioned into :data:`FRENCH_STOPWORDS`.

Sources: standard linguistic stopword lists (public domain) + empirical
tuning against real carousel OCR content.
"""

from __future__ import annotations

# English — top ~150 most frequent words
ENGLISH_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "a", "to", "of", "in", "i", "you", "is", "it",
    "that", "was", "for", "on", "are", "as", "with", "his", "they",
    "be", "at", "one", "have", "this", "from", "or", "had", "by",
    "not", "word", "but", "what", "some", "we", "can", "out", "other",
    "were", "all", "there", "when", "up", "use", "your", "how",
    "said", "an", "each", "she", "which", "do", "their", "time",
    "if", "will", "way", "about", "many", "then", "them", "would",
    "write", "like", "so", "these", "her", "long", "make", "thing",
    "see", "him", "two", "has", "look", "more", "day", "could", "go",
    "come", "did", "my", "no", "most", "who", "over", "know", "than",
    "call", "first", "people", "may", "down", "side", "been", "now",
    "find", "any", "new", "work", "part", "take", "get", "place",
    "made", "live", "where", "after", "back", "little", "only",
    "round", "man", "year", "came", "show", "every", "good", "me",
    "give", "our", "under", "name", "very", "through", "just", "form",
    "much", "great", "think", "say", "help", "low", "line", "before",
    "turn", "cause", "same", "mean", "differ", "move", "right", "boy",
    "old", "too", "does", "tell", "sentence", "set", "three", "want",
    "air", "well", "also", "play", "small", "end", "put", "home",
    "read", "hand", "port", "large", "spell", "add", "even", "land",
    "here", "must", "big", "high", "such", "follow", "act", "why",
    "ask", "men", "change", "went", "light", "kind", "off", "need",
    "house", "picture", "try", "us", "again", "animal", "point",
    "mother", "world", "near", "build", "self", "earth", "father",
})

# R063 (M012/S02) — French contractions.
# The V1 tokenizer treats "c'est" as a single token. These entries match
# those tokens and filter them out of keyword extraction. All >= 4 chars
# (shorter forms like "m'a"/"t'a" are already dropped by _MIN_KEYWORD_LENGTH).
_FRENCH_CONTRACTIONS: frozenset[str] = frozenset({
    # c' forms
    "c'est", "c'était", "c'étaient",
    # j' forms
    "j'ai", "j'avais", "j'aurai", "j'aurais", "j'en", "j'y",
    # d' forms
    "d'un", "d'une", "d'être", "d'avoir", "d'ici", "d'abord",
    # l' forms
    "l'autre", "l'un", "l'une", "l'on",
    # qu' forms
    "qu'il", "qu'elle", "qu'on", "qu'ils", "qu'elles", "qu'un", "qu'une",
    # n' forms
    "n'est", "n'ai", "n'avait", "n'ont", "n'était",
    # s' forms
    "s'il", "s'ils", "s'est", "s'était",
    # misc contractions
    "aujourd'hui",
})

# R063 (M012/S02) — Common conjugated verb forms without domain semantics.
# Infinitives (être, avoir, faire, dire, voir, savoir, pouvoir, vouloir,
# venir, falloir, devoir) are already in FRENCH_STOPWORDS below.
_FRENCH_COMMON_VERBS: frozenset[str] = frozenset({
    # vouloir
    "veux", "veut", "voulu", "voulais", "voulait", "voulons", "voulez",
    "voulaient", "voudrais", "voudrait",
    # pouvoir
    "peux", "peut", "pouvez", "peuvent", "pouvais", "pouvait", "pouvions",
    "pouvaient", "pourrais", "pourrait",
    # devoir
    "dois", "doit", "devais", "devait", "devions", "devez", "devaient",
    "devrais", "devrait",
    # savoir
    "sais", "sait", "savait", "savais", "savions", "savez", "savaient",
    # voir
    "vois", "voit", "voyais", "voyait", "voyez", "voyaient",
    # venir
    "viens", "vient", "venu", "venue", "venus", "venues", "venait",
    "venais", "viennent",
    # dire
    "disait", "disais", "disent",
    # faire
    "faisait", "faisais", "faisions", "font",
    # mettre / prendre / montrer / passer
    "mettre", "mis", "mise", "mettait",
    "prendre", "pris", "prise", "prenait",
    "montrer", "montre", "montré",
    "passer", "passe", "passé", "passait",
})

# French — base list (~150 most frequent words) + R063 extensions.
FRENCH_STOPWORDS: frozenset[str] = frozenset({
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "à",
    "il", "elle", "ils", "elles", "que", "qui", "dans", "pour", "pas",
    "plus", "ce", "cette", "ces", "son", "sa", "ses", "leur", "leurs",
    "être", "avoir", "faire", "dire", "voir", "savoir", "pouvoir",
    "vouloir", "venir", "falloir", "devoir", "mais", "ou", "donc",
    "or", "ni", "car", "si", "comme", "quand", "alors", "puis",
    "ainsi", "aussi", "bien", "très", "tout", "tous", "toute", "toutes",
    "même", "mêmes", "autre", "autres", "tel", "telle", "quel",
    "quelle", "celui", "celle", "ceux", "celles", "moi", "toi", "lui",
    "nous", "vous", "eux", "votre", "vos", "notre", "nos",
    "mon", "ma", "mes", "ton", "ta", "tes", "y", "en", "se", "sur",
    "sous", "avec", "sans", "par", "vers", "chez", "entre", "depuis",
    "pendant", "avant", "après", "contre", "selon", "malgré", "parmi",
    "hors", "où", "dont", "lequel", "laquelle", "lesquels", "lesquelles",
    "auquel", "duquel", "ne", "non", "oui", "rien", "personne", "jamais",
    "toujours", "souvent", "parfois", "quelquefois", "déjà", "encore",
    "ici", "là", "là-bas", "partout", "ailleurs", "trop", "peu", "assez",
    "beaucoup", "moins", "tant", "autant", "comment",
    "pourquoi", "combien", "quoi", "lorsque",
    "fois", "faut", "fait", "était", "sont", "suis", "es", "est",
    "sommes", "êtes", "avait", "avais", "avions", "aviez", "avaient",
    "ont", "ai", "as", "avons", "avez", "vont", "vais", "va", "allons",
    "allez", "j", "l", "d", "c", "n", "m", "t", "s", "qu",
}) | _FRENCH_CONTRACTIONS | _FRENCH_COMMON_VERBS

ALL_STOPWORDS: frozenset[str] = ENGLISH_STOPWORDS | FRENCH_STOPWORDS
```

Notes :
- `_FRENCH_CONTRACTIONS` a exactement 30 entrées (dédoublonnage inclus — vérifier avant commit).
- `_FRENCH_COMMON_VERBS` a ≥ 50 entrées (marge au-delà des 40 requis).
- Les entrées `m'a`, `t'a` (3 chars) ne sont PAS incluses : elles seraient filtrées redondamment par `_MIN_KEYWORD_LENGTH=4`. Documenter ce choix dans le commentaire déjà présent.
- Aucune modification au tokenizer (`_WORD_PATTERN` reste inchangé dans analyzer.py).
- Le fichier passe de 67 à ~120 lignes — bien sous la limite 300 (Utility/Service).
  </action>
  <verify>
    <automated>python -m pytest tests/unit/adapters/heuristic/test_stopwords.py tests/unit/adapters/heuristic/test_analyzer.py::TestHeuristicAnalyzerFrenchStopwordsR063 tests/unit/adapters/heuristic/test_analyzer.py -x -v 2>&1 | tail -40</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "_FRENCH_CONTRACTIONS: frozenset\[str\]" src/vidscope/adapters/heuristic/stopwords.py` retourne exactement 1 ligne
    - `grep -n "_FRENCH_COMMON_VERBS: frozenset\[str\]" src/vidscope/adapters/heuristic/stopwords.py` retourne exactement 1 ligne
    - `grep -n "| _FRENCH_CONTRACTIONS | _FRENCH_COMMON_VERBS" src/vidscope/adapters/heuristic/stopwords.py` retourne exactement 1 ligne
    - `grep -c '"c.est"\|"j.ai"\|"d.un"\|"qu.il"\|"n.est"\|"s.il"' src/vidscope/adapters/heuristic/stopwords.py` retourne au moins 6
    - `grep -c '"veux"\|"peux"\|"pouvez"\|"montrer"' src/vidscope/adapters/heuristic/stopwords.py` retourne au moins 4
    - `python -c "from vidscope.adapters.heuristic.stopwords import FRENCH_STOPWORDS, ENGLISH_STOPWORDS, _FRENCH_CONTRACTIONS, _FRENCH_COMMON_VERBS; assert len(FRENCH_STOPWORDS)>=100 and len(ENGLISH_STOPWORDS)>=100 and len(_FRENCH_CONTRACTIONS)>=30 and len(_FRENCH_COMMON_VERBS)>=40; assert \"c'est\" in FRENCH_STOPWORDS and \"veux\" in FRENCH_STOPWORDS; print('OK')"`
    - `pytest tests/unit/adapters/heuristic/test_stopwords.py` : tous tests passent
    - `pytest tests/unit/adapters/heuristic/test_analyzer.py::TestHeuristicAnalyzerFrenchStopwordsR063` : 3/3 tests passent
    - `pytest tests/unit/adapters/heuristic/test_analyzer.py::TestHeuristicAnalyzerFrenchContent` : 2/2 tests passent (pas de régression)
  </acceptance_criteria>
  <done>
    `stopwords.py` étendu avec `_FRENCH_CONTRACTIONS` (≥30) et `_FRENCH_COMMON_VERBS` (≥50). `FRENCH_STOPWORDS` absorbe les deux. Tests T03 passent (GREEN). Golden/analyzer tests existants passent toujours.
  </done>
</task>

<!-- ====================================================================== -->
<!-- WAVE 3 — cleanup + non-régression (dépend de Wave 2).                   -->
<!-- ====================================================================== -->

<task type="auto" tdd="true">
  <name>T06: Align test_missing_transcript_raises with new R062 behavior</name>
  <files>tests/unit/pipeline/stages/test_analyze.py</files>
  <read_first>
    - tests/unit/pipeline/stages/test_analyze.py lignes 137-165 (classe `TestAnalyzeStageErrors`)
    - src/vidscope/pipeline/stages/analyze.py (confirmer le nouveau comportement post-T04 : no-raise quand transcript is None)
  </read_first>
  <behavior>
    - Le test existant `test_missing_transcript_raises` asserte que `execute()` lève `AnalysisError` quand transcript est None — contraire au R062. Il DOIT être remplacé par un test qui asserte le nouveau comportement : pas d'erreur, Analysis stub persistée
    - Les autres tests de `TestAnalyzeStageErrors` (missing_video_id, analyzer_failure_propagates) restent valides et ne doivent PAS être modifiés
  </behavior>
  <action>
Dans `tests/unit/pipeline/stages/test_analyze.py`, localiser la méthode `test_missing_transcript_raises` (environ lignes 146-154) :

```python
    def test_missing_transcript_raises(self, engine: Engine) -> None:
        # Seed a video WITHOUT a transcript
        video_id = _seed_video_with_transcript(engine, with_transcript=False)
        ctx = PipelineContext(source_url="x", video_id=video_id)
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            AnalysisError, match="transcript"
        ):
            stage.execute(ctx, uow)
```

La REMPLACER **intégralement** par :

```python
    def test_missing_transcript_no_ocr_produces_empty_analysis(
        self, engine: Engine
    ) -> None:
        """R062 — when neither transcript nor frame_texts exist, execute()
        persists a stub Analysis via the analyzer's empty-transcript branch
        rather than raising AnalysisError."""
        from vidscope.adapters.heuristic import HeuristicAnalyzer

        # Seed a video WITHOUT a transcript AND without frame_texts
        video_id = _seed_video_with_transcript(engine, with_transcript=False)
        ctx = PipelineContext(source_url="x", video_id=video_id)
        stage = AnalyzeStage(analyzer=HeuristicAnalyzer())

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)  # must NOT raise

        with SqliteUnitOfWork(engine) as uow:
            persisted = uow.analyses.get_latest_for_video(video_id)
            assert persisted is not None
            assert persisted.score == 0.0
            assert persisted.summary == "no speech detected"
            assert persisted.keywords == ()
```

Ne PAS modifier les deux autres méthodes de `TestAnalyzeStageErrors` (`test_missing_video_id_raises`, `test_analyzer_failure_propagates`). Vérifier que `AnalysisError` n'est plus importé inutilement (il est encore utilisé par `test_missing_video_id_raises` et `test_analyzer_failure_propagates` → import reste).
  </action>
  <verify>
    <automated>python -m pytest tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageErrors -x -v 2>&1 | tail -30</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "test_missing_transcript_raises" tests/unit/pipeline/stages/test_analyze.py` retourne ZÉRO ligne (ancien test supprimé)
    - `grep -n "test_missing_transcript_no_ocr_produces_empty_analysis" tests/unit/pipeline/stages/test_analyze.py` retourne exactement 1 ligne
    - `grep -n "test_missing_video_id_raises" tests/unit/pipeline/stages/test_analyze.py` retourne exactement 1 ligne (inchangé)
    - `grep -n "test_analyzer_failure_propagates" tests/unit/pipeline/stages/test_analyze.py` retourne exactement 1 ligne (inchangé)
    - `pytest tests/unit/pipeline/stages/test_analyze.py::TestAnalyzeStageErrors` : 3/3 tests passent
  </acceptance_criteria>
  <done>
    Le test `test_missing_transcript_raises` est remplacé par `test_missing_transcript_no_ocr_produces_empty_analysis` (R062-aligned). Les 2 autres tests d'erreur restent intacts.
  </done>
</task>

<task type="auto">
  <name>T07: Full suite regression gate — 1658 baseline + new tests all green</name>
  <files>tests/unit/ (lecture seule — pas de modification source)</files>
  <read_first>
    - tests/unit/adapters/heuristic/test_golden.py (connaître le comportement de la golden gate 70% — elle peut bouger avec les nouveaux stopwords)
    - .gsd/milestones/M012/M012-S02-RESEARCH.md Pitfall 5 (golden fixtures)
  </read_first>
  <action>
Exécuter la suite unit complète et diagnostiquer les régressions si présentes :

```bash
python -m pytest tests/unit -q 2>&1 | tail -20
```

**Cas attendus** :

1. **Tous passent** (1658 baseline + ~15 nouveaux = ~1673 tests) : T07 terminé.

2. **Tests golden (`test_golden.py`) régressent** : c'est un effet attendu de l'extension stopwords (Pitfall 5 du RESEARCH.md). Diagnostiquer :
   - Lire `tests/unit/adapters/heuristic/test_golden.py` (fichier existant)
   - Lire `tests/fixtures/analysis_golden.jsonl` pour comprendre la structure
   - La golden gate vérifie le taux de match (content_type, is_sponsored, sentiment) à ≥ 70%. Ces 3 champs ne dépendent PAS directement des keywords stopwordés — la probabilité de régression est faible. Si régression : NE PAS ajuster la golden à la baisse. Investiguer : un keyword n'aurait pas dû influencer content_type.
   - Si les fixtures utilisent `contains` keyword-check spécifiques : rechercher toute assertion de présence de `"c'est"` / `"veux"` / `"peux"` dans des keywords — l'ajuster est la bonne réponse (ces mots ne doivent PAS être keywords).

3. **Autres régressions** : imprimer le diagnostic, corriger à la source (tests mal écrits ou bug réel d'implémentation T04/T05).

**Deliverable de cette tâche** : la commande `python -m pytest tests/unit -q` se termine avec `X passed` où X ≥ 1673, et `0 failed`.

Ne modifier AUCUN fichier source `src/`. Les seules modifications autorisées en T07 sont :
- Ajustement de tests existants dont les assertions étaient basées sur le comportement pré-R062/R063 (ex : un test affirmant que `"pris"` peut apparaître comme keyword).
- Commenter chaque ajustement avec `# R062` ou `# R063` pour traçabilité.

Si AUCUN ajustement n'est nécessaire, cette tâche consiste simplement à exécuter la suite et vérifier qu'elle passe.
  </action>
  <verify>
    <automated>python -m pytest tests/unit -q 2>&1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - La sortie `pytest tests/unit -q` termine avec `X passed` et `0 failed` où X >= 1673
    - Aucun fichier dans `src/vidscope/` n'a été modifié par cette tâche (`git diff src/` vide pour cette tâche)
    - Si des tests ont été ajustés, chacun a un commentaire `# R062` ou `# R063` en ligne
    - `pytest tests/unit/adapters/heuristic/test_golden.py -q` passe
    - `pytest tests/unit/pipeline -q` passe
    - `pytest tests/unit/adapters/heuristic -q` passe
  </acceptance_criteria>
  <done>
    Suite unit complète passe (>= 1673 tests, 0 failed). Aucune modification source `src/`. Toute golden ou fixture adjustée porte un commentaire de traçabilité R062/R063.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `frame_texts` table (SQLite) → `AnalyzeStage.execute` | Données OCR lues depuis DB locale (pas d'utilisateur externe direct), mais origine primaire = images téléchargées depuis Instagram → OCR |
| Analyzer (`HeuristicAnalyzer` / `HeuristicAnalyzerV2`) → `analyses` table | Les keywords/topics/summary dérivés sont persistés |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-M012S02-01 | Injection (SQL) | `uow.frame_texts.list_for_video(ctx.video_id)` | mitigate | `FrameTextRepositorySQLite.list_for_video` utilise des bind params SQLAlchemy Core (vérifié frame_text_repository.py:114-127). Le `video_id` provient de `PipelineContext.video_id` (set par IngestStage depuis un INSERT authoritative). Aucun SQL brut. |
| T-M012S02-02 | Tampering | `ft.text` contenant des caractères de contrôle ou Unicode adversariaux | accept | Le texte OCR est traité comme chaîne Python opaque par `_tokenize` (regex) et `_build_summary` (slicing). Aucun `eval`/`exec`. Les caractères de contrôle peuvent apparaître dans `full_text` mais sont sans effet sur le pipeline. Impact limité à l'affichage via `vidscope show` (qui n'est pas dans le scope de ce plan). |
| T-M012S02-03 | DoS | Carousel à 100 slides × 50 blocs OCR de 2 KB → 10 MB de texte à analyser | accept | `_build_summary` tronque à 200 chars ; `Counter.most_common(8)` est O(n). Le tokenizer regex est linéaire. Tests M009 existants attestent de la performance sur 1658 tests en < 60 s. Si observé en prod, ajouter `[:MAX_OCR_CHARS]` (ex. 50 000) dans `execute()` — hors scope ici. |
| T-M012S02-04 | Integrity | L'Analysis persistée écrase silencieusement une Analysis précédente pour le même video_id | mitigate | Le comportement existant `uow.analyses.add` crée une nouvelle ligne (historisation) — M010 n'update pas. `is_satisfied` détecte une Analysis existante via `get_latest_for_video` et court-circuite — pas de double-ajout accidentel dans le happy path idempotent. |
| T-M012S02-05 | Information Disclosure | Une caption OCR contenant des données personnelles persiste dans `analyses.summary` | accept | Même raisonnement que T-M012-03 (M012/S01) : les captions sont publiques, VidScope est mono-utilisateur local. Pas de nouvelle surface d'exposition. |
| T-M012S02-06 | Tampering | Un adversaire ayant accès local à la DB modifie `frame_texts.text` pour influencer les topics produits | accept | Scénario insider à la machine locale — même classe que modifier n'importe quel fichier/DB local. Hors scope de VidScope (mono-utilisateur local). |

**Aucun nouveau vecteur réseau ou auth introduit.**
</threat_model>

<verification>

## Vérification globale de phase

```bash
# 1. Tests unitaires du périmètre touché par R062 / R063
python -m pytest \
    tests/unit/pipeline/stages/test_analyze.py \
    tests/unit/adapters/heuristic/test_analyzer.py \
    tests/unit/adapters/heuristic/test_stopwords.py \
    tests/unit/adapters/heuristic/test_golden.py \
    -x -v

# 2. Non-régression pleine suite unit (baseline M012/S01 = 1658)
python -m pytest tests/unit -q

# 3. Vérifications grep consolidées (ancres anti-régression)
# R062 anchors
grep -n "if ctx.media_type in (MediaType.IMAGE, MediaType.CAROUSEL):" src/vidscope/pipeline/stages/analyze.py || echo "OK: R062 short-circuit removed"
grep -n "uow.frame_texts.list_for_video" src/vidscope/pipeline/stages/analyze.py
grep -n "Language.UNKNOWN" src/vidscope/pipeline/stages/analyze.py
grep -n "replace(raw_analysis, video_id=ctx.video_id)" src/vidscope/pipeline/stages/analyze.py

# R063 anchors
grep -n "_FRENCH_CONTRACTIONS\|_FRENCH_COMMON_VERBS" src/vidscope/adapters/heuristic/stopwords.py

# 4. Vérification runtime R062 (end-to-end stub en mémoire)
python -c "
from sqlalchemy import create_engine
from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import MediaType, Platform, PlatformId, Video
from vidscope.pipeline.stages.analyze import AnalyzeStage
from vidscope.adapters.heuristic import HeuristicAnalyzer
from vidscope.ports import PipelineContext

e = create_engine('sqlite:///:memory:')
init_db(e)
with SqliteUnitOfWork(e) as uow:
    v = uow.videos.upsert_by_platform_id(Video(
        platform=Platform.INSTAGRAM,
        platform_id=PlatformId('smoke1'),
        url='https://instagram.com/p/smoke1/',
        media_key='videos/instagram/smoke1/items/0000.jpg',
    ))
ctx = PipelineContext(source_url='x', video_id=v.id, media_type=MediaType.CAROUSEL)
stage = AnalyzeStage(analyzer=HeuristicAnalyzer())
with SqliteUnitOfWork(e) as uow:
    stage.execute(ctx, uow)
with SqliteUnitOfWork(e) as uow:
    a = uow.analyses.get_latest_for_video(v.id)
    assert a is not None and a.score == 0.0 and a.summary == 'no speech detected'
print('R062 smoke OK:', a.provider, a.score, a.summary)
"

# 5. Vérification runtime R063 (stopwords filtrent les contractions)
python -c "
from vidscope.adapters.heuristic.stopwords import (
    ALL_STOPWORDS, FRENCH_STOPWORDS, ENGLISH_STOPWORDS,
    _FRENCH_CONTRACTIONS, _FRENCH_COMMON_VERBS,
)
assert len(FRENCH_STOPWORDS) >= 100
assert len(ENGLISH_STOPWORDS) >= 100
assert len(_FRENCH_CONTRACTIONS) >= 30
assert len(_FRENCH_COMMON_VERBS) >= 40
for w in (\"c'est\", \"j'ai\", \"d'un\", \"qu'il\", \"n'est\", \"s'il\", 'veux', 'peux', 'pouvez', 'montrer'):
    assert w in ALL_STOPWORDS, w
print('R063 stopwords OK:', len(FRENCH_STOPWORDS), 'FR,', len(ENGLISH_STOPWORDS), 'EN')
"
```

## Checklist must_haves (goal-backward)

- [ ] `AnalyzeStage.is_satisfied` ne court-circuite plus IMAGE/CAROUSEL (ligne supprimée)
- [ ] `AnalyzeStage.execute` construit un Transcript synthétique à partir de `frame_texts` quand transcript None
- [ ] `Language.UNKNOWN` est utilisé pour le Transcript OCR synthétique
- [ ] Les champs M010 (verticals, information_density, etc.) sont préservés via `dataclasses.replace`
- [ ] `FRENCH_STOPWORDS` contient `c'est`, `j'ai`, `d'un`, `qu'il`, `n'est`, `s'il`
- [ ] `FRENCH_STOPWORDS` contient `veux`, `peux`, `pouvez`, `montrer`, `montré`, `pris`, `mis`
- [ ] `FRENCH_STOPWORDS` et `ENGLISH_STOPWORDS` ont chacun ≥ 100 entrées
- [ ] Les deux tests M010 obsolètes (`test_is_satisfied_returns_true_for_image`, `test_is_satisfied_returns_true_for_carousel`) sont SUPPRIMÉS
- [ ] 4 nouveaux tests `TestAnalyzeStageMediaTypeR062` + 4 nouveaux tests `TestAnalyzeStageOcrFallback` en place
- [ ] Fichier `tests/unit/adapters/heuristic/test_stopwords.py` existe (7 tests R063)
- [ ] Suite `pytest tests/unit -q` : 0 failed, baseline 1658 → >=1673

</verification>

<success_criteria>

**R062 couvert** :
1. Un carousel avec `frame_texts` et `transcript=None` produit une ligne `analyses` non-null après `AnalyzeStage.execute()`. → T01+T02+T04
2. `analysis: null` n'apparaît plus pour un contenu ayant du texte OCR (is_satisfied ne skip plus sans vérifier). → T01+T04
3. Les carousels sans caption ni OCR ni transcript produisent score=0 et summary="no speech detected" sans crash. → T02 (test_carousel_without_transcript_and_without_frame_texts_produces_stub) + T04 + T06 (test_missing_transcript_no_ocr_produces_empty_analysis)
4. Les champs M010 produits par V2 sont préservés dans la persistance (via `dataclasses.replace`). → T04 (action explicite) + T07 (non-régression des tests V2)

**R063 couvert** :
5. Les keywords/topics heuristiques ne contiennent plus `c'est`, `j'ai`, `d'un`, `qu'il`, `n'est`, `s'il`. → T03+T05
6. Les keywords/topics heuristiques ne contiennent plus `veux`, `peux`, `pouvez`, `montrer`, `pris`, `mis`. → T03+T05
7. Pour un carousel "Claude skills for Architects! … terminal … agent … workflow", les topics reflètent le domaine (`claude`, `skills`, `terminal`, `agent`, `workflow`) et non des mots vides. → T02 (test_carousel_produces_domain_topics_end_to_end) + T03 (test_claude_skills_carousel_keeps_domain_tokens)
8. `FRENCH_STOPWORDS` et `ENGLISH_STOPWORDS` ont chacun ≥ 100 entrées (R063 quantitatif). → T03 + T05

**Robustesse & non-régression** :
9. Les 1658 tests baseline passent toujours. → T07
10. Les 2 tests M010 obsolètes sont supprimés proprement (pas laissés skippés). → T01 + acceptance_criteria grep
11. Les tests golden (content_type / is_sponsored / sentiment gate ≥ 70%) passent — l'extension stopwords n'affecte pas les champs M010 dérivés des lexicons. → T07

</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M012/M012-S02-SUMMARY.md` couvrant :
- Requirements R062 + R063 réalisés
- Fichiers modifiés (2 source + 3 tests, dont 1 nouveau fichier `test_stopwords.py`)
- Décisions de design :
  - Utilisation de `dataclasses.replace` pour préserver les champs M010 (résout aussi une dette latente du rebind manuel)
  - Stopwords étendus en sets privés séparés (`_FRENCH_CONTRACTIONS`, `_FRENCH_COMMON_VERBS`) unionés — facilite la lecture, la couverture de test, et l'évolution future
  - Transcript synthétique reste in-memory (jamais persisté dans `transcripts`) pour ne pas polluer la table
- Résultat `pytest tests/unit -q` (baseline 1658 → attendu ≥ 1673)
- Toute surprise rencontrée (ajustements de tests golden si applicables, fixtures déplacées, etc.)
- Impact zéro sur les downloaders et MCP (scope limité à AnalyzeStage + HeuristicAnalyzer) — M012/S03 peut maintenant exposer `ocr_preview` en sachant que l'Analysis existe pour les carousels
</output>
