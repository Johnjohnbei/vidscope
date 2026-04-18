---
phase: M010
plan: S03
type: execute
wave: 3
depends_on: [S01, S02]
files_modified:
  - src/vidscope/adapters/llm/_base.py
  - tests/unit/adapters/llm/test_base.py
  - tests/unit/adapters/llm/test_groq.py
  - tests/unit/adapters/llm/test_nvidia_build.py
  - tests/unit/adapters/llm/test_openrouter.py
  - tests/unit/adapters/llm/test_openai.py
  - tests/unit/adapters/llm/test_anthropic.py
autonomous: true
requirements: [R053, R055]
must_haves:
  truths:
    - "`_SYSTEM_PROMPT` dans `adapters/llm/_base.py` demande au LLM un JSON object avec TOUTES les clés M010 : language, keywords, topics, verticals, score, information_density, actionability, novelty, production_quality, sentiment, is_sponsored, content_type, reasoning, summary"
    - "`make_analysis` parse correctement les 9 nouveaux champs M010 — valeurs valides → populées, valeurs manquantes/invalides → None ou default (pas d'exception)"
    - "`make_analysis` clampe les 4 nouveaux scores (`information_density`, `actionability`, `novelty`, `production_quality`) à [0.0, 100.0]"
    - "`make_analysis` convertit `sentiment` (string) vers `SentimentLabel` avec fallback None si invalide (jamais ValueError)"
    - "`make_analysis` convertit `content_type` (string) vers `ContentType` avec fallback None si invalide"
    - "`make_analysis` convertit `is_sponsored` (bool, int 0/1, 'true'/'false') en bool, avec fallback None si non-convertible"
    - "`make_analysis` convertit `verticals` (array) en `tuple[str, ...]` lowercase, max 5 éléments"
    - "`make_analysis` retient `reasoning` string (max 500 chars, jamais vide si non-None)"
    - "Les 5 providers LLM (groq, nvidia_build, openrouter, openai, anthropic) restent structurellement inchangés — ils délèguent toujours via `run_openai_compatible` ou `parse_llm_json` + `make_analysis`"
    - "Les tests LLM existants continuent de passer + nouveaux tests pour les 9 champs M010"
  artifacts:
    - path: "src/vidscope/adapters/llm/_base.py"
      provides: "Prompt V2 + make_analysis V2 (parse 9 nouveaux champs)"
      contains: "information_density"
    - path: "tests/unit/adapters/llm/test_base.py"
      provides: "Tests V2 extension du prompt et du parser"
      contains: "content_type"
  key_links:
    - from: "src/vidscope/adapters/llm/_base.py"
      to: "vidscope.domain.ContentType, SentimentLabel"
      via: "Import + fallback-None parsing"
      pattern: "SentimentLabel|ContentType"
    - from: "src/vidscope/adapters/llm/_base.py::make_analysis"
      to: "Analysis"
      via: "Construction avec tous les champs M010"
      pattern: "reasoning="
---

<objective>
S03 met à jour le socle LLM partagé (`adapters/llm/_base.py`) pour que les 5 providers (groq, nvidia_build, openrouter, openai, anthropic) retournent les 9 nouveaux champs M010. Le prompt centralisé demande au LLM un JSON étendu; `make_analysis` le parse défensivement. Les providers ne changent pas de forme — c'est l'un des bénéfices du design M004 (un helper central, 5 files minces).

Purpose: Sans ce plan, les analyses LLM (utilisées quand l'utilisateur export `VIDSCOPE_ANALYZER=groq` etc.) resteraient bloquées sur le schéma M001 (score scalaire), incapables de peupler les nouveaux champs de `Analysis`. La cohérence cross-provider (même JSON schema partout) est la garantie promise par M004.
Output: Un prompt V2 + un parser V2 dans `_base.py`, plus une batterie de tests qui prouvent la robustesse (JSON manquant, invalides, bornes).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.gsd/milestones/M010/M010-S01-PLAN.md
@.gsd/milestones/M010/M010-S02-PLAN.md
@.gsd/milestones/M010/M010-ROADMAP.md
@.gsd/milestones/M010/M010-RESEARCH.md
@.gsd/milestones/M010/M010-VALIDATION.md
@.gsd/KNOWLEDGE.md
@src/vidscope/adapters/llm/_base.py
@src/vidscope/adapters/llm/groq.py
@src/vidscope/adapters/llm/openai.py
@src/vidscope/adapters/llm/anthropic.py
@src/vidscope/domain/entities.py
@src/vidscope/domain/values.py
@tests/unit/adapters/llm/test_base.py

<interfaces>
**Prompt V1 actuel (`_base.py._SYSTEM_PROMPT`)** :
```
You are a video-analysis assistant. Given the transcript of a short-form vertical video,
return a strict JSON object with these keys and nothing else:
  "language": ISO 639-1 lowercase 2-letter code (e.g. "en")
  "keywords": array of 5-10 lowercase keywords from the transcript
  "topics": array of 1-3 short topic phrases (2-4 words each)
  "score": integer 0-100 measuring content quality and richness
  "summary": one-sentence summary, max 200 characters
Do not wrap the JSON in markdown fences. Do not add explanations.
```

**Prompt V2 cible** : conserver les 5 champs M001, AJOUTER 8 nouveaux (`verticals`, 4 scores, `sentiment`, `is_sponsored`, `content_type`, `reasoning`).

**make_analysis V1 actuel** — 9 lignes de parsing par champ, défensif. Pattern à étendre.

**Analysis M010 (livré S01)** :
```python
@dataclass(frozen=True, slots=True)
class Analysis:
    ...
    verticals: tuple[str, ...] = ()
    information_density: float | None = None
    actionability: float | None = None
    novelty: float | None = None
    production_quality: float | None = None
    sentiment: SentimentLabel | None = None
    is_sponsored: bool | None = None
    content_type: ContentType | None = None
    reasoning: str | None = None
    ...
```

**Providers structurellement inchangés** : `groq.py`, `openai.py`, `openrouter.py`, `nvidia_build.py` délèguent à `run_openai_compatible` qui retourne `make_analysis(parsed, ...)`. `anthropic.py` appelle `parse_llm_json` + `make_analysis` directement. Aucune modification des 5 fichiers providers.

**Robustesse (Pitfall RESEARCH.md)** : si le LLM oublie un champ ou renvoie une valeur invalide, `make_analysis` retourne `None` pour ce champ (pas d'exception). Les tests provider existants (`test_groq.py` etc.) s'appuient sur cette garantie — ajouter des tests V2 pour chaque provider sans casser les tests V1.

**Règle défensive sur les champs numériques** : un score numérique hors [0, 100] est clampé; un string "65" est converti via `float()`; un None reste None.

**Règle défensive sur les enums** : une valeur string inconnue ("joyful" pour sentiment, "podcast" pour content_type) → None, jamais ValueError. Exactement le même pattern que `_row_to_analysis` de S01.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Prompt V2 + make_analysis V2 (parse des 9 nouveaux champs, défensif)</name>
  <files>src/vidscope/adapters/llm/_base.py, tests/unit/adapters/llm/test_base.py</files>
  <read_first>
    - src/vidscope/adapters/llm/_base.py (fichier entier — _SYSTEM_PROMPT ligne 67-77, make_analysis ligne 412-482)
    - src/vidscope/domain/entities.py (Analysis M010 étendu livré S01)
    - src/vidscope/domain/values.py (ContentType, SentimentLabel livrés S01)
    - src/vidscope/adapters/sqlite/analysis_repository.py (pattern `_row_to_analysis` défensif livré S01 — reproduire pour `make_analysis`)
    - tests/unit/adapters/llm/test_base.py (tests V1 existants — ne pas casser, étendre)
    - .gsd/milestones/M010/M010-RESEARCH.md (Pattern S03 : prompt + JSON schema étendu + Pitfall 3 topics vs verticals)
    - .gsd/KNOWLEDGE.md (M004 : one-file-per-provider, _base.py is the shared toolkit)
  </read_first>
  <behavior>
    - Test 1 (prompt contient toutes les clés M010): `_SYSTEM_PROMPT` mentionne "verticals", "information_density", "actionability", "novelty", "production_quality", "sentiment", "is_sponsored", "content_type", "reasoning".
    - Test 2 (prompt liste les valeurs d'enum): le prompt liste explicitement les content_type valides (tutorial, review, vlog, news, story, opinion, comedy, educational, promo, unknown) et les sentiment valides (positive, negative, neutral, mixed).
    - Test 3 (parse V2 happy path): `make_analysis({"language": "en", "keywords": ["code"], "verticals": ["tech"], "information_density": 70, "actionability": 80, "novelty": 40, "production_quality": 60, "sentiment": "positive", "is_sponsored": false, "content_type": "tutorial", "reasoning": "Clear tutorial.", "summary": "ok", "topics": ["code"], "score": 75}, t, provider="test")` → Analysis avec tous les champs populés correctement.
    - Test 4 (score numérique manquant): si `information_density` absent du dict → `Analysis.information_density is None`.
    - Test 5 (score numérique hors bornes): `information_density=150` → clampé à 100.0; `-5` → 0.0.
    - Test 6 (score numérique string numérique): `"75"` → 75.0.
    - Test 7 (score numérique non-numérique): `"bogus"` → None.
    - Test 8 (sentiment invalide): `sentiment="joyful"` → `Analysis.sentiment is None` (pas de ValueError).
    - Test 9 (sentiment valide): `sentiment="NEGATIVE"` (uppercase) → `Analysis.sentiment is SentimentLabel.NEGATIVE` (case-insensitive).
    - Test 10 (content_type invalide): `content_type="podcast"` → `Analysis.content_type is None`.
    - Test 11 (content_type valide): `content_type="Tutorial"` → `ContentType.TUTORIAL`.
    - Test 12 (is_sponsored bool): `True` → True, `False` → False, `0` → False, `1` → True, `"true"` → True, `"false"` → False, `None` → None, `"bogus"` → None.
    - Test 13 (verticals array): `["tech", "ai", "fitness"]` → tuple lowercase, max 5, déduplique.
    - Test 14 (verticals non-array): `"tech"` (string au lieu de list) → `()`.
    - Test 15 (reasoning string): `"A clear tutorial."` → retenu tel quel si ≤500 chars, tronqué au-delà.
    - Test 16 (reasoning None): absent du dict → None.
    - Test 17 (reasoning empty): `""` → None.
    - Test 18 (V1 compat): `make_analysis({"language": "en", "keywords": [], "topics": [], "score": 50, "summary": "ok"}, t, provider="test")` retourne un Analysis valide avec tous les nouveaux champs à None/() — comportement préservé.
  </behavior>
  <action>
Étape 1 — Remplacer `_SYSTEM_PROMPT` dans `src/vidscope/adapters/llm/_base.py` par le nouveau prompt V2. Localisation: ligne ~67-77. Nouveau contenu exact :

```python
_SYSTEM_PROMPT = (
    "You are a video-analysis assistant. Given the transcript of a "
    "short-form vertical video, return a strict JSON object with "
    "EXACTLY these keys and nothing else (no markdown, no prose):\n"
    '  "language": ISO 639-1 lowercase 2-letter code (e.g. "en" or "fr")\n'
    '  "keywords": array of 5-10 lowercase keywords from the transcript\n'
    '  "topics": array of 1-3 short topic phrases (2-4 words each)\n'
    '  "verticals": array of 0-5 lowercase vertical slugs that best '
    "describe the content (e.g. tech, beauty, fitness, finance, food, "
    "travel, gaming, education, fashion, music, productivity, ai)\n"
    '  "score": integer 0-100 measuring overall content quality and richness\n'
    '  "information_density": integer 0-100 measuring meaningful-content ratio\n'
    '  "actionability": integer 0-100 measuring how actionable the advice is '
    "(0 = pure entertainment, 100 = step-by-step tutorial)\n"
    '  "novelty": integer 0-100 measuring how novel/original the ideas are\n'
    '  "production_quality": integer 0-100 measuring pacing/clarity/structure '
    "(not video-quality — transcript-inferable signals only)\n"
    '  "sentiment": one of "positive", "negative", "neutral", "mixed"\n'
    '  "is_sponsored": boolean — true if the transcript signals a paid '
    'partnership (phrases like "sponsored by", "in partnership with", '
    '"#ad", "use code", "affiliate"), else false\n'
    '  "content_type": one of "tutorial", "review", "vlog", "news", '
    '"story", "opinion", "comedy", "educational", "promo", "unknown"\n'
    '  "reasoning": 2-3 short sentences explaining the verdict '
    "(why this content_type, what drove the sentiment, any sponsorship cue). "
    "Max 500 characters.\n"
    '  "summary": one-sentence factual summary, max 200 characters\n'
    "Numeric fields must be integers in [0, 100]. All strings must be "
    "lowercase except where noted. Return bare JSON — no code fences, "
    "no explanations, no preamble."
)
```

Étape 2 — Étendre les imports en tête de `_base.py` :
```python
from vidscope.domain import (
    Analysis,
    AnalysisError,
    ContentType,
    Language,
    SentimentLabel,
    Transcript,
)
```

Étape 3 — Ajouter des helpers privés (juste avant `make_analysis`) :

```python
def _parse_score_100(value: Any) -> float | None:
    """Parse a 0-100 numeric score. Returns None for non-numeric inputs.

    Accepts int, float, or numeric string. Clamps to [0.0, 100.0].
    """
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:  # NaN
        return None
    return max(0.0, min(100.0, num))


def _parse_sentiment(value: Any) -> SentimentLabel | None:
    """Parse a sentiment string case-insensitively. None on invalid."""
    if value is None:
        return None
    if isinstance(value, SentimentLabel):
        return value
    if not isinstance(value, str):
        return None
    try:
        return SentimentLabel(value.strip().lower())
    except ValueError:
        return None


def _parse_content_type(value: Any) -> ContentType | None:
    """Parse a content_type string case-insensitively. None on invalid."""
    if value is None:
        return None
    if isinstance(value, ContentType):
        return value
    if not isinstance(value, str):
        return None
    try:
        return ContentType(value.strip().lower())
    except ValueError:
        return None


_TRUTHY_STRINGS: frozenset[str] = frozenset({"true", "yes", "1", "t"})
_FALSY_STRINGS: frozenset[str] = frozenset({"false", "no", "0", "f"})


def _parse_bool_flag(value: Any) -> bool | None:
    """Parse a boolean flag tolerantly. None on unrecognised inputs.

    Recognises: True/False, 0/1, 'true'/'false' (case-insensitive),
    'yes'/'no', 't'/'f'. Any other value → None.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        norm = value.strip().lower()
        if norm in _TRUTHY_STRINGS:
            return True
        if norm in _FALSY_STRINGS:
            return False
        return None
    return None


def _parse_verticals(value: Any, *, max_count: int = 5) -> tuple[str, ...]:
    """Parse a verticals array. Returns () for invalid input.

    Normalises to lowercase stripped strings. Deduplicates while
    preserving order. Caps at ``max_count``.
    """
    if not isinstance(value, list):
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for v in value:
        if not isinstance(v, str):
            continue
        norm = v.strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(norm)
        if len(result) >= max_count:
            break
    return tuple(result)


_REASONING_MAX_CHARS: int = 500


def _parse_reasoning(value: Any) -> str | None:
    """Parse reasoning text. None for empty/non-string. Truncated at 500."""
    if value is None or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > _REASONING_MAX_CHARS:
        text = text[:_REASONING_MAX_CHARS].rstrip() + "..."
    return text
```

Étape 4 — Remplacer `make_analysis` par la version V2 qui construit un `Analysis` avec les 9 nouveaux champs. Conserver STRICTEMENT le comportement V1 sur les 5 champs existants (keywords, topics, score, summary, language).

```python
def make_analysis(
    parsed: dict[str, Any], transcript: Transcript, *, provider: str
) -> Analysis:
    """Convert parsed LLM JSON output into an :class:`Analysis`.

    Defensive about missing/malformed keys — falls back to safe defaults
    rather than raising. Extended in M010 to parse the 9 new fields
    (verticals, 4 score dimensions, sentiment, is_sponsored, content_type,
    reasoning). The score is clamped to [0, 100].

    Raises
    ------
    AnalysisError
        Only if the parsed object isn't a dict (caller bug).
    """
    if not isinstance(parsed, dict):
        raise AnalysisError(
            f"expected dict from parse_llm_json, got {type(parsed).__name__}",
            retryable=False,
        )

    # --- V1 fields (preserved) ---
    keywords_raw = parsed.get("keywords") or []
    if not isinstance(keywords_raw, list):
        keywords_raw = []
    keywords = tuple(
        str(k).strip().lower() for k in keywords_raw if k and str(k).strip()
    )[:10]

    topics_raw = parsed.get("topics") or []
    if not isinstance(topics_raw, list):
        topics_raw = []
    topics = tuple(
        str(t).strip() for t in topics_raw if t and str(t).strip()
    )[:3]

    score = _parse_score_100(parsed.get("score"))

    summary_raw = parsed.get("summary")
    summary: str | None
    if summary_raw is None:
        summary = None
    else:
        summary_text = str(summary_raw).strip()
        summary = summary_text[:200] if summary_text else None

    # Resolve language: prefer transcript's detected language, fall
    # back to LLM's value if transcript was unknown.
    language = transcript.language
    if language == Language.UNKNOWN:
        lang_raw = parsed.get("language")
        if lang_raw:
            try:
                language = Language(str(lang_raw).lower())
            except ValueError:
                language = Language.UNKNOWN

    # --- M010 fields (all defensive, never raise) ---
    verticals = _parse_verticals(parsed.get("verticals"))
    information_density = _parse_score_100(parsed.get("information_density"))
    actionability = _parse_score_100(parsed.get("actionability"))
    novelty = _parse_score_100(parsed.get("novelty"))
    production_quality = _parse_score_100(parsed.get("production_quality"))
    sentiment = _parse_sentiment(parsed.get("sentiment"))
    is_sponsored = _parse_bool_flag(parsed.get("is_sponsored"))
    content_type = _parse_content_type(parsed.get("content_type"))
    reasoning = _parse_reasoning(parsed.get("reasoning"))

    return Analysis(
        video_id=transcript.video_id,
        provider=provider,
        language=language,
        keywords=keywords,
        topics=topics,
        score=score,
        summary=summary,
        verticals=verticals,
        information_density=information_density,
        actionability=actionability,
        novelty=novelty,
        production_quality=production_quality,
        sentiment=sentiment,
        is_sponsored=is_sponsored,
        content_type=content_type,
        reasoning=reasoning,
    )
```

Étape 5 — Mettre à jour `__all__` de `_base.py` pour exposer les helpers (utile aux tests) :
```python
__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_REQUEST_TIMEOUT_SECONDS",
    "LlmCallContext",
    "build_messages",
    "call_with_retry",
    "make_analysis",
    "parse_llm_json",
    "run_openai_compatible",
]
```
**Ne PAS exporter les helpers privés** (`_parse_*`) — ils restent internes. Les tests peuvent les importer via `from vidscope.adapters.llm._base import _parse_score_100` (pattern accepté dans les tests unitaires).

Étape 6 — Étendre `tests/unit/adapters/llm/test_base.py` en AJOUTANT (ne pas casser les tests V1 existants) une classe complète couvrant les 18 behaviors listés :

```python
"""M010 — tests for the extended _SYSTEM_PROMPT + make_analysis."""

from __future__ import annotations

import pytest

from vidscope.adapters.llm._base import (
    _SYSTEM_PROMPT,
    _parse_bool_flag,
    _parse_content_type,
    _parse_reasoning,
    _parse_score_100,
    _parse_sentiment,
    _parse_verticals,
    make_analysis,
)
from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    SentimentLabel,
    Transcript,
    VideoId,
)


def _t(*, language: Language = Language.ENGLISH) -> Transcript:
    return Transcript(
        video_id=VideoId(1),
        language=language,
        full_text="hello world",
        segments=(),
    )


class TestSystemPromptM010:
    @pytest.mark.parametrize("key", [
        "verticals",
        "information_density",
        "actionability",
        "novelty",
        "production_quality",
        "sentiment",
        "is_sponsored",
        "content_type",
        "reasoning",
    ])
    def test_prompt_mentions_every_m010_key(self, key: str) -> None:
        assert key in _SYSTEM_PROMPT

    def test_prompt_lists_content_type_enum_values(self) -> None:
        for ct in ("tutorial", "review", "vlog", "news", "story",
                   "opinion", "comedy", "educational", "promo", "unknown"):
            assert ct in _SYSTEM_PROMPT

    def test_prompt_lists_sentiment_enum_values(self) -> None:
        for s in ("positive", "negative", "neutral", "mixed"):
            assert s in _SYSTEM_PROMPT


class TestParseScore100:
    def test_none_returns_none(self) -> None:
        assert _parse_score_100(None) is None

    def test_int_in_range_returns_float(self) -> None:
        assert _parse_score_100(50) == 50.0

    def test_float_preserved(self) -> None:
        assert _parse_score_100(72.5) == 72.5

    def test_out_of_range_clamped(self) -> None:
        assert _parse_score_100(150) == 100.0
        assert _parse_score_100(-5) == 0.0

    def test_numeric_string_parsed(self) -> None:
        assert _parse_score_100("75") == 75.0

    def test_non_numeric_string_returns_none(self) -> None:
        assert _parse_score_100("bogus") is None

    def test_nan_returns_none(self) -> None:
        assert _parse_score_100(float("nan")) is None


class TestParseSentiment:
    @pytest.mark.parametrize("raw,expected", [
        ("positive", SentimentLabel.POSITIVE),
        ("NEGATIVE", SentimentLabel.NEGATIVE),
        ("  neutral  ", SentimentLabel.NEUTRAL),
        ("Mixed", SentimentLabel.MIXED),
    ])
    def test_valid_strings(self, raw: str, expected: SentimentLabel) -> None:
        assert _parse_sentiment(raw) is expected

    @pytest.mark.parametrize("raw", [None, "joyful", "", 123, ["positive"]])
    def test_invalid_returns_none(self, raw: object) -> None:
        assert _parse_sentiment(raw) is None

    def test_enum_passthrough(self) -> None:
        assert _parse_sentiment(SentimentLabel.POSITIVE) is SentimentLabel.POSITIVE


class TestParseContentType:
    @pytest.mark.parametrize("raw,expected", [
        ("tutorial", ContentType.TUTORIAL),
        ("REVIEW", ContentType.REVIEW),
        ("  vlog  ", ContentType.VLOG),
        ("Promo", ContentType.PROMO),
    ])
    def test_valid_strings(self, raw: str, expected: ContentType) -> None:
        assert _parse_content_type(raw) is expected

    @pytest.mark.parametrize("raw", [None, "podcast", "", 42, ["tutorial"]])
    def test_invalid_returns_none(self, raw: object) -> None:
        assert _parse_content_type(raw) is None


class TestParseBoolFlag:
    @pytest.mark.parametrize("raw,expected", [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        ("False", False),
        ("TRUE", True),
        ("yes", True),
        ("no", False),
        ("1", True),
        ("0", False),
    ])
    def test_valid(self, raw: object, expected: bool) -> None:
        assert _parse_bool_flag(raw) is expected

    @pytest.mark.parametrize("raw", [None, "maybe", "bogus", 2, 3.14, ["true"]])
    def test_invalid_returns_none(self, raw: object) -> None:
        assert _parse_bool_flag(raw) is None


class TestParseVerticals:
    def test_valid_list(self) -> None:
        assert _parse_verticals(["tech", "AI", "Fitness"]) == ("tech", "ai", "fitness")

    def test_deduplicates(self) -> None:
        result = _parse_verticals(["tech", "tech", "ai", "TECH"])
        assert result == ("tech", "ai")

    def test_caps_at_max_count(self) -> None:
        result = _parse_verticals(["a", "b", "c", "d", "e", "f", "g"], max_count=5)
        assert len(result) == 5

    def test_non_list_returns_empty(self) -> None:
        assert _parse_verticals("tech") == ()
        assert _parse_verticals(None) == ()
        assert _parse_verticals(42) == ()

    def test_non_string_elements_skipped(self) -> None:
        assert _parse_verticals(["tech", 42, None, "ai"]) == ("tech", "ai")


class TestParseReasoning:
    def test_valid_string(self) -> None:
        text = "This is a short tutorial."
        assert _parse_reasoning(text) == text

    def test_none_or_empty_returns_none(self) -> None:
        assert _parse_reasoning(None) is None
        assert _parse_reasoning("") is None
        assert _parse_reasoning("   ") is None

    def test_truncated_at_500_chars(self) -> None:
        long = "x" * 800
        result = _parse_reasoning(long)
        assert result is not None
        assert len(result) <= 504  # 500 + "..."
        assert result.endswith("...")

    def test_non_string_returns_none(self) -> None:
        assert _parse_reasoning(42) is None
        assert _parse_reasoning(["a"]) is None


class TestMakeAnalysisV2:
    def test_happy_path_all_m010_fields(self) -> None:
        parsed = {
            "language": "en",
            "keywords": ["code", "python"],
            "topics": ["code"],
            "verticals": ["tech", "ai"],
            "score": 75,
            "information_density": 70,
            "actionability": 80,
            "novelty": 40,
            "production_quality": 60,
            "sentiment": "positive",
            "is_sponsored": False,
            "content_type": "tutorial",
            "reasoning": "Clear structured tutorial.",
            "summary": "A tutorial about Python",
        }
        a = make_analysis(parsed, _t(language=Language.ENGLISH), provider="test")
        assert isinstance(a, Analysis)
        assert a.verticals == ("tech", "ai")
        assert a.information_density == 70.0
        assert a.actionability == 80.0
        assert a.novelty == 40.0
        assert a.production_quality == 60.0
        assert a.sentiment is SentimentLabel.POSITIVE
        assert a.is_sponsored is False
        assert a.content_type is ContentType.TUTORIAL
        assert a.reasoning == "Clear structured tutorial."

    def test_missing_m010_fields_all_none(self) -> None:
        """V1-shape parsed dict → V2 fields all None (backward compat)."""
        parsed = {
            "language": "en",
            "keywords": ["a"],
            "topics": ["a"],
            "score": 50,
            "summary": "x",
        }
        a = make_analysis(parsed, _t(), provider="test")
        assert a.verticals == ()
        assert a.information_density is None
        assert a.actionability is None
        assert a.novelty is None
        assert a.production_quality is None
        assert a.sentiment is None
        assert a.is_sponsored is None
        assert a.content_type is None
        assert a.reasoning is None

    def test_invalid_sentiment_becomes_none(self) -> None:
        parsed = {"sentiment": "joyful"}
        a = make_analysis(parsed, _t(), provider="test")
        assert a.sentiment is None

    def test_invalid_content_type_becomes_none(self) -> None:
        parsed = {"content_type": "podcast"}
        a = make_analysis(parsed, _t(), provider="test")
        assert a.content_type is None

    def test_out_of_range_scores_clamped(self) -> None:
        parsed = {
            "information_density": 200,
            "actionability": -50,
            "novelty": 99.9,
            "production_quality": "75",
        }
        a = make_analysis(parsed, _t(), provider="test")
        assert a.information_density == 100.0
        assert a.actionability == 0.0
        assert a.novelty == 99.9
        assert a.production_quality == 75.0

    def test_is_sponsored_int_coercion(self) -> None:
        assert make_analysis({"is_sponsored": 1}, _t(), provider="x").is_sponsored is True
        assert make_analysis({"is_sponsored": 0}, _t(), provider="x").is_sponsored is False
        assert make_analysis({"is_sponsored": "true"}, _t(), provider="x").is_sponsored is True

    def test_non_list_verticals_is_empty_tuple(self) -> None:
        parsed = {"verticals": "tech"}  # wrong shape
        assert make_analysis(parsed, _t(), provider="x").verticals == ()

    def test_reasoning_empty_is_none(self) -> None:
        assert make_analysis({"reasoning": ""}, _t(), provider="x").reasoning is None
        assert make_analysis({"reasoning": "   "}, _t(), provider="x").reasoning is None

    def test_non_dict_parsed_raises(self) -> None:
        from vidscope.domain import AnalysisError
        with pytest.raises(AnalysisError):
            make_analysis([], _t(), provider="x")  # type: ignore[arg-type]
```

Étape 7 — Exécuter :
```
uv run pytest tests/unit/adapters/llm/test_base.py -x -q
uv run lint-imports
```

NE PAS modifier groq.py / openai.py / openrouter.py / nvidia_build.py / anthropic.py structurellement (ils délèguent déjà à `run_openai_compatible` / `make_analysis`, c'est par design). S'assurer que les tests provider existants (`test_groq.py` etc.) passent toujours car ils injectent des réponses JSON mock — le nouveau parser doit accepter les anciennes réponses V1 (Test 18 garantit ce comportement).
  </action>
  <verify>
    <automated>uv run pytest tests/unit/adapters/llm/test_base.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "information_density" src/vidscope/adapters/llm/_base.py` matches (prompt + parsing)
    - `grep -n "actionability" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "production_quality" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "is_sponsored" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "content_type" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "reasoning" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "def _parse_score_100" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "def _parse_sentiment" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "def _parse_content_type" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "def _parse_bool_flag" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "def _parse_verticals" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "def _parse_reasoning" src/vidscope/adapters/llm/_base.py` matches
    - `grep -n "SentimentLabel" src/vidscope/adapters/llm/_base.py` matches (import + usage)
    - `grep -n "ContentType" src/vidscope/adapters/llm/_base.py` matches
    - `uv run pytest tests/unit/adapters/llm/test_base.py -x -q` exits 0 (V1 tests existants + V2 tests nouveaux)
    - `uv run lint-imports` exits 0
  </acceptance_criteria>
  <done>
    - `_SYSTEM_PROMPT` V2 demande les 13 clés (5 V1 + 8 M010)
    - `make_analysis` peuple les 9 nouveaux champs, défensif sur toutes les entrées invalides
    - 6 helpers `_parse_*` testés unitairement (score, sentiment, content_type, bool, verticals, reasoning)
    - 20+ tests verts dans test_base.py (V1 compat + V2 nouveauté)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Tests d'intégration des 5 providers LLM avec réponses M010 (MockTransport)</name>
  <files>tests/unit/adapters/llm/test_groq.py, tests/unit/adapters/llm/test_nvidia_build.py, tests/unit/adapters/llm/test_openrouter.py, tests/unit/adapters/llm/test_openai.py, tests/unit/adapters/llm/test_anthropic.py</files>
  <read_first>
    - tests/unit/adapters/llm/test_groq.py (pattern MockTransport + test happy path existant — copier pour étendre)
    - tests/unit/adapters/llm/test_openai.py (même pattern OpenAI-compatible)
    - tests/unit/adapters/llm/test_anthropic.py (pattern Anthropic native content blocks — structure différente)
    - tests/unit/adapters/llm/test_nvidia_build.py
    - tests/unit/adapters/llm/test_openrouter.py
    - src/vidscope/adapters/llm/_base.py (version V2 livrée Task 1)
    - .gsd/KNOWLEDGE.md (pattern httpx.MockTransport dans tests LLM)
  </read_first>
  <behavior>
    - Test 1 (groq V2 happy): MockTransport retourne JSON M010 complet → analyzer.analyze(t) retourne Analysis avec les 9 nouveaux champs correctement parsés.
    - Test 2 (groq partial M010): MockTransport retourne JSON avec seulement 3 des 9 nouveaux champs → les 3 sont populés, les 6 autres à None.
    - Test 3 (groq invalid M010 values): MockTransport retourne `sentiment="bogus"`, `content_type="podcast"` → sentiment/content_type à None, pas d'exception.
    - Test 4 (nvidia V2 happy): même pattern que groq.
    - Test 5 (openrouter V2 happy): même pattern.
    - Test 6 (openai V2 happy): même pattern.
    - Test 7 (anthropic V2 happy): MockTransport retourne la forme Anthropic (`content: [{type: text, text: JSON}]`) avec les 9 champs M010 → correctement parsés.
    - Test 8 (anthropic V2 partial): même robustesse sur partial.
    - Pas de test `make_analysis` direct — les providers sont testés en bout-en-bout via leur `analyze(transcript)` method.
  </behavior>
  <action>
Pour chacun des 5 providers, AJOUTER une classe de tests `TestM010ExtendedJson` à la fin du fichier existant. Pattern à dupliquer (exemple pour groq — adapter pour chaque provider) :

**Étape 1** — Lire `tests/unit/adapters/llm/test_groq.py` pour identifier le pattern exact de MockTransport utilisé. Le fichier existe depuis M004/S01. Le pattern typique est :

```python
import httpx
from httpx import MockTransport

def _mock_response(json_payload: dict) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": json.dumps(json_payload)}}]
    })

def test_xxx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _mock_response(...)
    transport = MockTransport(handler)
    client = httpx.Client(transport=transport)
    analyzer = GroqAnalyzer(api_key="x", client=client)
    result = analyzer.analyze(_transcript(...))
    ...
```

**Étape 2** — Dans `tests/unit/adapters/llm/test_groq.py`, AJOUTER à la fin :

```python
class TestM010ExtendedGroqJson:
    """M010: groq must surface new fields via make_analysis."""

    def _transcript(self) -> Transcript:
        return Transcript(
            video_id=VideoId(1),
            language=Language.ENGLISH,
            full_text="hello",
            segments=(),
        )

    def _mock_openai_response(self, payload: dict) -> httpx.Response:
        import json as _json
        return httpx.Response(200, json={
            "choices": [{"message": {"content": _json.dumps(payload)}}]
        })

    def test_happy_path_all_m010_fields(self) -> None:
        payload = {
            "language": "en",
            "keywords": ["code", "python"],
            "topics": ["code"],
            "verticals": ["tech", "ai"],
            "score": 75,
            "information_density": 70,
            "actionability": 80,
            "novelty": 40,
            "production_quality": 60,
            "sentiment": "positive",
            "is_sponsored": False,
            "content_type": "tutorial",
            "reasoning": "Clear Python tutorial with step-by-step instructions.",
            "summary": "A tutorial about Python",
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_openai_response(payload)
        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        try:
            analyzer = GroqAnalyzer(api_key="test-key", client=client)
            result = analyzer.analyze(self._transcript())
        finally:
            client.close()
        assert result.verticals == ("tech", "ai")
        assert result.information_density == 70.0
        assert result.actionability == 80.0
        assert result.novelty == 40.0
        assert result.production_quality == 60.0
        from vidscope.domain import ContentType, SentimentLabel
        assert result.sentiment is SentimentLabel.POSITIVE
        assert result.is_sponsored is False
        assert result.content_type is ContentType.TUTORIAL
        assert result.reasoning is not None and "Python" in result.reasoning

    def test_partial_m010_fields(self) -> None:
        """Missing fields → None, not exception (defensive)."""
        payload = {
            "language": "en",
            "keywords": ["a"],
            "topics": ["a"],
            "score": 50,
            "summary": "ok",
            # Only 3 of 9 M010 fields provided
            "sentiment": "neutral",
            "content_type": "vlog",
            "is_sponsored": True,
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_openai_response(payload)
        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        try:
            analyzer = GroqAnalyzer(api_key="test-key", client=client)
            result = analyzer.analyze(self._transcript())
        finally:
            client.close()
        from vidscope.domain import ContentType, SentimentLabel
        assert result.sentiment is SentimentLabel.NEUTRAL
        assert result.content_type is ContentType.VLOG
        assert result.is_sponsored is True
        assert result.information_density is None
        assert result.verticals == ()
        assert result.reasoning is None

    def test_invalid_m010_values_safe(self) -> None:
        """Unknown enum values → None, not exception."""
        payload = {
            "language": "en",
            "keywords": [],
            "topics": [],
            "score": 50,
            "summary": "x",
            "sentiment": "joyful",     # invalid
            "content_type": "podcast", # invalid
            "is_sponsored": "maybe",   # invalid
            "information_density": "very high",  # invalid numeric
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_openai_response(payload)
        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        try:
            analyzer = GroqAnalyzer(api_key="test-key", client=client)
            result = analyzer.analyze(self._transcript())
        finally:
            client.close()
        assert result.sentiment is None
        assert result.content_type is None
        assert result.is_sponsored is None
        assert result.information_density is None
```

**Étape 3** — Répliquer EXACTEMENT le même pattern dans :

- `tests/unit/adapters/llm/test_nvidia_build.py` (remplacer `GroqAnalyzer` par `NvidiaBuildAnalyzer` — la réponse JSON reste la forme OpenAI-compatible).
- `tests/unit/adapters/llm/test_openrouter.py` (remplacer par `OpenRouterAnalyzer`).
- `tests/unit/adapters/llm/test_openai.py` (remplacer par `OpenAIAnalyzer`).

**Étape 4** — Pour `tests/unit/adapters/llm/test_anthropic.py`, la forme de réponse est DIFFÉRENTE (Anthropic native). La structure est :
```json
{"content": [{"type": "text", "text": "<JSON string>"}]}
```

Ajouter à la fin :

```python
class TestM010ExtendedAnthropicJson:
    """M010: anthropic must surface new fields via make_analysis."""

    def _transcript(self) -> Transcript:
        return Transcript(
            video_id=VideoId(1),
            language=Language.ENGLISH,
            full_text="hello",
            segments=(),
        )

    def _mock_anthropic_response(self, payload: dict) -> httpx.Response:
        import json as _json
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": _json.dumps(payload)}]
        })

    def test_happy_path_all_m010_fields(self) -> None:
        payload = {
            "language": "en",
            "keywords": ["code"],
            "topics": ["code"],
            "verticals": ["tech"],
            "score": 80,
            "information_density": 65,
            "actionability": 85,
            "novelty": 50,
            "production_quality": 70,
            "sentiment": "positive",
            "is_sponsored": False,
            "content_type": "tutorial",
            "reasoning": "Structured technical tutorial.",
            "summary": "A tutorial",
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_anthropic_response(payload)
        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        try:
            analyzer = AnthropicAnalyzer(api_key="test-key", client=client)
            result = analyzer.analyze(self._transcript())
        finally:
            client.close()
        from vidscope.domain import ContentType, SentimentLabel
        assert result.verticals == ("tech",)
        assert result.information_density == 65.0
        assert result.sentiment is SentimentLabel.POSITIVE
        assert result.content_type is ContentType.TUTORIAL
        assert result.reasoning is not None

    def test_partial_m010_fields(self) -> None:
        payload = {
            "language": "en",
            "keywords": ["a"],
            "topics": [],
            "score": 50,
            "summary": "x",
            "sentiment": "negative",
        }
        def handler(req: httpx.Request) -> httpx.Response:
            return self._mock_anthropic_response(payload)
        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport)
        try:
            analyzer = AnthropicAnalyzer(api_key="test-key", client=client)
            result = analyzer.analyze(self._transcript())
        finally:
            client.close()
        from vidscope.domain import SentimentLabel
        assert result.sentiment is SentimentLabel.NEGATIVE
        assert result.content_type is None
        assert result.reasoning is None
```

**Étape 5** — Exécuter :
```
uv run pytest tests/unit/adapters/llm/ -x -q
uv run lint-imports
```

**Critique** : certains tests V1 existants dans `test_groq.py` etc. peuvent ASSERT spécifiquement sur `Analysis` fields (ex: `result.score == X`). Ces tests DOIVENT continuer de passer car :
- `make_analysis` V2 retourne un `Analysis` avec les anciens champs préservés.
- Les tests V1 ne checkent PAS les nouveaux champs M010 (`information_density` etc.) donc ils s'en moquent.
- Si certains tests assertent `result.reasoning is None` par défaut c'est OK parce que les payloads V1 n'ont pas ce champ donc `_parse_reasoning(None)` retourne None.

Si un test existant échoue de façon inattendue, lire son message et déterminer si (a) le test checkait un comportement V1 cassé par V2 (à investiguer avant modif), ou (b) le test a besoin d'un tweak pour accommoder M010 (ex: Analysis() constructor maintenant avec plus de fields requis — mais vu que tous les nouveaux ont des defaults, ce n'est pas le cas). **Ne pas casser les tests existants pour faire passer les nouveaux.**
  </action>
  <verify>
    <automated>uv run pytest tests/unit/adapters/llm/ -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "TestM010ExtendedGroqJson" tests/unit/adapters/llm/test_groq.py` matches
    - `grep -n "TestM010ExtendedNvidiaJson\\|TestM010Extended" tests/unit/adapters/llm/test_nvidia_build.py` matches
    - `grep -n "TestM010Extended" tests/unit/adapters/llm/test_openrouter.py` matches
    - `grep -n "TestM010Extended" tests/unit/adapters/llm/test_openai.py` matches
    - `grep -n "TestM010ExtendedAnthropicJson" tests/unit/adapters/llm/test_anthropic.py` matches
    - `grep -nE "^import yaml" src/vidscope/adapters/llm/_base.py` returns exit 1 (no match — LLM layer doesn't read YAML directly)
    - `uv run pytest tests/unit/adapters/llm/test_groq.py -x -q` exits 0 (V1 + V2)
    - `uv run pytest tests/unit/adapters/llm/test_anthropic.py -x -q` exits 0 (V1 + V2)
    - `uv run pytest tests/unit/adapters/llm/ -x -q` exits 0 (global LLM suite)
    - `uv run lint-imports` exits 0 (contrat `llm-never-imports-other-adapters` toujours KEPT)
  </acceptance_criteria>
  <done>
    - Les 5 providers LLM testés avec payloads M010 complets, partiels, invalides
    - Total ≥15 nouveaux tests M010 (3 par provider × 5)
    - Aucun test V1 cassé (comportement préservé)
    - Contrat `llm-never-imports-other-adapters` KEPT
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM HTTP response → `parse_llm_json` | Données externes non contrôlées. LLM peut retourner JSON mal formé, vide, arbitraire. |
| `parse_llm_json` output (dict) → `make_analysis` | Dict validé comme dict mais les VALEURS sont user-controlled (le LLM ne sait pas ce qu'on attend). |
| `Analysis` → DB / CLI | Sortie ensuite persistée (S01 repository) puis affichée (S04 CLI). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-INPUT-01 | Tampering | LLM retourne `sentiment="ignore_all_previous; rm -rf /"` | mitigate | `_parse_sentiment` vérifie que la valeur est UN membre valide de `SentimentLabel` via try/except ValueError. Strings arbitraires → None. L'injection de commande serait inefficace de toute façon (valeur stockée en DB, jamais exécutée). |
| T-INPUT-02 | Tampering | LLM retourne `information_density=99999999999999999` | mitigate | `_parse_score_100` clampe via `min(100.0, max(0.0, float(x)))`. Overflow impossible: Python float. |
| T-INPUT-03 | Injection | LLM retourne `reasoning="<script>alert(1)</script>"` | accept | `reasoning` est une string stockée en DB (TEXT column). Affichée par `rich.console` en S04 — `rich` échappe automatiquement le HTML. R032 single-user local tool (pas de cible XSS). |
| T-INPUT-04 | DoS | LLM retourne `reasoning="x"*1_000_000` | mitigate | `_parse_reasoning` tronque à 500 chars + "...". Pas de risque d'explosion mémoire. |
| T-INPUT-05 | Tampering | LLM retourne `verticals=["../../../../etc/passwd"]` | accept | Les verticals sont utilisés en DB (JSON column) et dans les filtres SQL (en S04, parameterized queries). Pas de I/O basé sur les verticals. R032. |
| T-INPUT-06 | Spoofing | LLM retourne `content_type=None, sentiment=None, is_sponsored=None` (n'a pas classifié) | accept | Comportement attendu: `make_analysis` retourne `Analysis` avec ces champs None. L'utilisateur voit "—" dans `vidscope explain` (S04). |
| T-DATA-01 | Availability | Provider LLM retourne réponse sans aucun champ M010 | mitigate | Test `test_missing_m010_fields_all_none` garantit que le parsing ne lève pas. L'`Analysis` reste valide (V1-compat). |
| T-DATA-02 | Repudiation | Provider change de modèle et retourne un JSON différent | mitigate | Le prompt V2 est explicite sur les 13 clés attendues ET sur les valeurs d'enum autorisées. Si le modèle dévie, les champs invalides deviennent None (defensive parsing) — le pipeline ne crash pas, l'utilisateur voit des champs manquants. |
</threat_model>

<verification>
Après les 2 tâches :
- `uv run pytest tests/unit/adapters/llm/ -x -q` vert (V1 + V2)
- `uv run lint-imports` vert (tous contrats KEPT)
- `uv run pytest -m architecture -x -q` vert
- `grep -c "information_density\\|actionability\\|novelty\\|production_quality\\|reasoning\\|sentiment\\|is_sponsored\\|content_type\\|verticals" src/vidscope/adapters/llm/_base.py` returns >= 20 (présence substantielle dans prompt + parser)
- Les 5 providers continuent de fonctionner sans modification de leur code
</verification>

<success_criteria>
S03 est complet quand :
- [ ] `_SYSTEM_PROMPT` V2 demande les 13 clés (5 V1 + 8 M010) avec les valeurs d'enum listées
- [ ] `make_analysis` parse les 9 nouveaux champs défensivement (pas d'exception sur input invalide)
- [ ] 6 helpers `_parse_*` livrés (score, sentiment, content_type, bool_flag, verticals, reasoning)
- [ ] Scores numériques clampés à [0, 100] (information_density, actionability, novelty, production_quality)
- [ ] Enums invalides → None (sentiment, content_type)
- [ ] `is_sponsored` accepte bool/int/string tolérant
- [ ] `verticals` tuple lowercase, dédupliqué, cap à 5
- [ ] `reasoning` tronqué à 500 chars
- [ ] Les 5 providers LLM inchangés structurellement + nouveaux tests M010 (3 par provider)
- [ ] V1 tests existants continuent de passer (backward compat)
- [ ] Suite LLM verte (`tests/unit/adapters/llm/`)
- [ ] `lint-imports` vert (`llm-never-imports-other-adapters` KEPT)
- [ ] R053 (scores LLM) + R055 (reasoning LLM) couverts
</success_criteria>

<output>
Après complétion, créer `.gsd/milestones/M010/M010-S03-SUMMARY.md` documentant :
- Le contenu exact du nouveau `_SYSTEM_PROMPT` (prompt V2)
- La signature de chaque helper `_parse_*`
- La signature mise à jour de `make_analysis`
- Les règles défensives (clamp, fallback None, truncation 500)
- Les 5 providers non modifiés — confirmation que M004 design tient
- Nombre de tests ajoutés par provider
- Liste des fichiers modifiés
</output>
</content>
</invoke>