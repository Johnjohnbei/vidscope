---
plan_id: S02-P02
phase: M007/S02
wave: 4
depends_on: [S02-P01]
requirements: [R044]
files_modified:
  - src/vidscope/adapters/text/__init__.py
  - src/vidscope/adapters/text/url_normalizer.py
  - src/vidscope/adapters/text/regex_link_extractor.py
  - tests/fixtures/link_corpus.json
  - tests/unit/adapters/text/__init__.py
  - tests/unit/adapters/text/test_url_normalizer.py
  - tests/unit/adapters/text/test_regex_link_extractor.py
  - .importlinter
  - tests/architecture/test_architecture.py
autonomous: true
---

## Objective

Livrer le nouveau sous-module `adapters/text/` — **self-contained** selon le nouveau contrat import-linter `text-adapter-is-self-contained` — avec : (1) `URLNormalizer` pure-Python (stdlib `urllib.parse` uniquement) qui lowercase scheme+host, strip fragment, strip `utm_*` query params, trie query params alphabétiquement, strip trailing slash (2) `RegexLinkExtractor` qui implémente le Protocol `LinkExtractor` avec stratégie deux-niveaux (scheme explicite + bare-domain avec TLD restreint pour éviter les faux positifs `hello.world`/`file.txt`) (3) **le corpus `tests/fixtures/link_corpus.json` de ≥100 strings (50 positifs, 30 négatifs, 20 edge)** — c'est la gate qualité NON-NÉGOCIABLE de la roadmap M007 : un test parametrisé itère sur TOUTES les entrées du corpus et échoue si l'extracteur manque un positif ou produit un faux positif (4) nouveau contrat import-linter `text-adapter-is-self-contained` structurellement enforçant l'isolation. Les 9 contrats existants + le 10e nouveau restent verts.

## Tasks

<task id="T01-url-normalizer" tdd="true">
  <name>URLNormalizer pure-Python avec ≥ 8 tests d'idempotence et de cas limites</name>

  <read_first>
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"URL normalizer" (algo complet : lowercase scheme+host, strip fragment, filter utm_*, sort query params, strip trailing slash)
    - `.gsd/milestones/M007/M007-CONTEXT.md` §Claude's Discretion "Implémentation interne de `normalized_url` (lowercase scheme+host, strip utm_*)"
    - `.importlinter` — nouveau contrat `text-adapter-is-self-contained` à ajouter en T03 ; ce module ne doit importer que stdlib
    - `src/vidscope/ports/link_extractor.py` — voir `RawLink.normalized_url` pour comprendre le contrat avec l'extractor
  </read_first>

  <behavior>
    - Test 1: `normalize_url("https://example.com/")` → `"https://example.com"` (strip trailing slash).
    - Test 2: `normalize_url("HTTPS://Example.COM/PATH")` → `"https://example.com/PATH"` (lowercase scheme+host, path case preserved).
    - Test 3: `normalize_url("https://example.com/?b=2&a=1")` → `"https://example.com/?a=1&b=2"` (sorted query params).
    - Test 4: `normalize_url("https://example.com/?utm_source=tiktok&id=42")` → `"https://example.com/?id=42"` (utm_* stripped).
    - Test 5: `normalize_url("https://example.com/#fragment")` → `"https://example.com"` (fragment stripped).
    - Test 6: `normalize_url("https://example.com/?utm_source=x&utm_medium=y&utm_campaign=z&id=1")` → `"https://example.com/?id=1"` (tous les utm_* virés).
    - Test 7: idempotence — `normalize_url(normalize_url(url)) == normalize_url(url)` pour 10+ URLs variées.
    - Test 8: `normalize_url("https://www.example.com/path")` → `"https://www.example.com/path"` (www. préservé — pas de hack www-strip en M007).
    - Test 9: `normalize_url("http://example.com")` vs `normalize_url("https://example.com")` → distincts (scheme préservé).
    - Test 10: `normalize_url("bit.ly/abc")` — bare domain — retourne une forme utile (au choix : `"https://bit.ly/abc"` — documenté dans la docstring comme "accepte aussi les URLs sans scheme en ajoutant https://").
  </behavior>

  <action>
  **Étape A — Créer le package `src/vidscope/adapters/text/`** :

  `src/vidscope/adapters/text/__init__.py` :

  ```python
  """Text-only adapters: regex URL extraction + URL normalization.

  This sub-package is structurally isolated by the import-linter contract
  ``text-adapter-is-self-contained`` — it imports only stdlib + domain +
  ports. No SQLAlchemy, no yt-dlp, no faster-whisper.

  Used by:
  - :class:`~vidscope.pipeline.stages.metadata_extract_stage.MetadataExtractStage`
    (M007/S03) to surface URLs from caption + transcript.
  - :class:`~vidscope.adapters.ocr.*` (M008/S02) to surface URLs from
    OCR output over the same regex.
  """

  from __future__ import annotations

  from vidscope.adapters.text.regex_link_extractor import RegexLinkExtractor
  from vidscope.adapters.text.url_normalizer import normalize_url

  __all__ = ["RegexLinkExtractor", "normalize_url"]
  ```

  **Étape B — Créer `src/vidscope/adapters/text/url_normalizer.py`** :

  ```python
  """Pure-Python URL normalization — stdlib only.

  Used by :class:`RegexLinkExtractor` to produce the ``normalized_url``
  deduplication key from a raw captured URL. Also importable directly
  for other adapters (M008 OCR) that need the same dedup shape.

  Normalization rules (per M007 CONTEXT §D-04 and RESEARCH §"URL
  normalizer"):

  1. Lowercase the scheme and host (path case is preserved — some URLs
     use case-sensitive paths).
  2. Strip the fragment (``#anchor``).
  3. Drop every query parameter whose key starts with ``utm_``
     (case-insensitive) — these are tracking params irrelevant for
     deduplication.
  4. Sort the remaining query parameters alphabetically by key.
  5. Strip the trailing slash from the path (``/`` at the very end).
  6. When the input has no scheme (``bit.ly/abc``), prepend ``https://``
     so the output is always a well-formed absolute URL.

  The function is idempotent: ``normalize_url(normalize_url(x)) ==
  normalize_url(x)`` for every input.
  """

  from __future__ import annotations

  from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

  __all__ = ["normalize_url"]


  def normalize_url(url: str) -> str:
      """Return the canonical normalized form of ``url``.

      See module docstring for the full rule list. Returns the original
      ``url`` unchanged when parsing fails (empty string, malformed
      input) — never raises.
      """
      raw = (url or "").strip()
      if not raw:
          return ""

      # Ensure a scheme is present so urlparse populates netloc
      # correctly. "bit.ly/abc" has no scheme → parsed.netloc == ''
      # and the whole string is treated as the path. We fix that by
      # prepending https:// when there is no "://" in the string.
      if "://" not in raw:
          raw = "https://" + raw

      parsed = urlparse(raw)
      scheme = parsed.scheme.lower()
      netloc = parsed.netloc.lower()

      # Strip trailing slash from path (but keep root "/" as empty).
      path = parsed.path
      if path.endswith("/") and len(path) > 1:
          path = path.rstrip("/")
      elif path == "/":
          path = ""

      # Filter utm_* (case-insensitive) then sort by key.
      qs_pairs = parse_qsl(parsed.query, keep_blank_values=True)
      filtered = [
          (k, v) for k, v in qs_pairs if not k.lower().startswith("utm_")
      ]
      sorted_qs = sorted(filtered, key=lambda kv: kv[0])
      query = urlencode(sorted_qs)

      # Fragment is always discarded.
      return urlunparse((scheme, netloc, path, parsed.params, query, ""))
  ```

  **Étape C — Écrire les tests (TDD).** Créer `tests/unit/adapters/text/__init__.py` (vide) puis `tests/unit/adapters/text/test_url_normalizer.py` avec les 10 comportements décrits dans `<behavior>` ; utiliser des assertions explicites pour chaque cas.
  </action>

  <acceptance_criteria>
    - `test -f src/vidscope/adapters/text/__init__.py`
    - `test -f src/vidscope/adapters/text/url_normalizer.py`
    - `test -f tests/unit/adapters/text/__init__.py`
    - `test -f tests/unit/adapters/text/test_url_normalizer.py`
    - `grep -q "def normalize_url" src/vidscope/adapters/text/url_normalizer.py` exit 0
    - `python -m uv run python -c "from vidscope.adapters.text import normalize_url; assert normalize_url('HTTPS://Example.COM/PATH/?utm_source=x&b=2&a=1#frag') == 'https://example.com/PATH?a=1&b=2'; print('OK')"` affiche `OK`
    - `python -m uv run python -c "from vidscope.adapters.text import normalize_url; u = 'https://example.com/?b=2&utm_source=x'; assert normalize_url(normalize_url(u)) == normalize_url(u); print('idempotent')"` affiche `idempotent`
    - `python -m uv run python -c "from vidscope.adapters.text import normalize_url; assert normalize_url('bit.ly/abc') == 'https://bit.ly/abc'; print('OK')"` affiche `OK`
    - `grep -c "def test_" tests/unit/adapters/text/test_url_normalizer.py` retourne un nombre ≥ 10
    - `python -m uv run pytest tests/unit/adapters/text/test_url_normalizer.py -x -q` exit 0
    - `python -m uv run mypy src` exit 0
  </acceptance_criteria>
</task>

<task id="T02-link-corpus-fixture-and-regex-extractor" tdd="true">
  <name>Créer le corpus ≥100 strings + RegexLinkExtractor + test parametrisé sur le corpus (gate non-négociable)</name>

  <read_first>
    - `src/vidscope/adapters/text/url_normalizer.py` (créé en T01) — `normalize_url` à utiliser pour produire `normalized_url`
    - `src/vidscope/ports/link_extractor.py` (créé en S02-P01) — contrat `LinkExtractor.extract(text, *, source) -> list[RawLink]`
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"Regex robuste pour URL extraction (R044)" (algo complet + stratégie 2 niveaux) et §"Corpus `tests/fixtures/link_corpus.json` — structure attendue"
    - `.gsd/milestones/M007/M007-ROADMAP.md` §"Regex corpus (to guarantee extractor quality)" — **le corpus ≥ 100 strings est gate non-négociable**
    - `.gsd/milestones/M007/M007-CONTEXT.md` §"Corpus regex `tests/fixtures/link_corpus.json` est une gate non-négociable — failing regression = broken build"
  </read_first>

  <behavior>
    - Test 1 (scheme explicite): `extract("visit https://example.com today", source="description")` retourne 1 `RawLink` avec `url == "https://example.com"` et `source == "description"`.
    - Test 2 (query + fragment): `extract("https://shop.com/p?id=1&utm_source=ig#frag", source="description")[0].normalized_url == "https://shop.com/p?id=1"`.
    - Test 3 (bare TLD connu): `extract("go to bit.ly/abc", source="description")` retourne 1 RawLink avec `normalized_url == "https://bit.ly/abc"`.
    - Test 4 (faux positif évité): `extract("hello.world is not a URL", source="description") == []`.
    - Test 5 (faux positif évité): `extract("version 1.0.0 and file.txt", source="description") == []`.
    - Test 6 (plusieurs URLs): `extract("url1 https://a.com and url2 https://b.com", source="description")` retourne 2 RawLink.
    - Test 7 (dédup par `normalized_url`): `extract("https://a.com and https://a.com/", source="description")` retourne 1 RawLink (pas 2).
    - Test 8 (ponctuation finale): `extract("(visit https://example.com)", source="description")` retourne 1 RawLink avec url sans `)` final.
    - Test 9 (empty input): `extract("", source="description") == []` ; `extract("no urls here", source="description") == []`.
    - Test 10 (source propagated): `extract("https://a.com", source="transcript")[0]["source"] == "transcript"`.
    - **Test parametrisé-corpus** (gate NON-NÉGOCIABLE) : charge `tests/fixtures/link_corpus.json` et pour chaque entrée vérifie que `sorted([l["normalized_url"] for l in extract(text, source="description")]) == sorted([normalize_url(u) for u in expected_urls])`.
  </behavior>

  <action>
  **Étape A — Créer `src/vidscope/adapters/text/regex_link_extractor.py`** :

  ```python
  """RegexLinkExtractor — pure-Python regex URL extraction.

  Strategy: two-pass regex.

  1. **Scheme-explicit pass** — ``https?://...`` is easy and high-
     precision. Matches most captions / descriptions.

  2. **Bare-domain pass** — captures ``bit.ly/abc``, ``shop.com/sale``
     where users omitted the scheme. To avoid false positives
     (``hello.world``, ``file.txt``, ``version 1.0.0``), bare matches
     require a TLD from a restricted list (``_COMMON_TLDS``). This
     trades recall for precision — preferred in M007 (the fixture
     corpus is the quality gate).

  After both passes, results are deduplicated by ``normalized_url``
  (per :func:`vidscope.adapters.text.url_normalizer.normalize_url`).

  See the non-negotiable fixture corpus at
  ``tests/fixtures/link_corpus.json`` (≥ 100 strings) for the quality
  gate. New edge cases → add to the corpus, re-run tests.
  """

  from __future__ import annotations

  import re
  from re import Pattern
  from typing import Final

  from vidscope.adapters.text.url_normalizer import normalize_url
  from vidscope.ports.link_extractor import RawLink

  __all__ = ["RegexLinkExtractor"]


  # Common TLDs used in the bare-domain pass. Tight list to minimise
  # false positives on file extensions / version strings. Add only
  # TLDs confirmed by the fixture corpus.
  _COMMON_TLDS: Final[tuple[str, ...]] = (
      "com", "net", "org", "io", "co", "fr", "uk", "de", "app",
      "dev", "ly", "gg", "tv", "me", "ai", "tech", "shop", "store",
      "xyz", "link", "page",
  )


  _SCHEME_URL: Final[Pattern[str]] = re.compile(
      r"https?://"
      r"[^\s<>\"'`{}|\\^\[\]]+",
      re.IGNORECASE,
  )


  # Bare domain: "host.tld[/path][?query]" where tld is in _COMMON_TLDS.
  # Negative lookbehind (?<!\w) prevents matching inside words like
  # "version1.0" or "file.txt". Negative lookahead at end anchors on
  # a separator.
  _BARE_DOMAIN: Final[Pattern[str]] = re.compile(
      r"(?<!\w)"
      r"(?:www\.)?"
      r"([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)"
      r"\.(" + "|".join(_COMMON_TLDS) + r")"
      r"(?:/[^\s<>\"'`{}|\\^\[\]]*)?"
      r"(?=[\s,;)>\]'\"!?.]|$)",
      re.IGNORECASE,
  )


  # Characters to strip from the end of a captured URL — common
  # sentence punctuation that should NOT be part of the URL itself.
  _TRAILING_PUNCT: Final[str] = ".,;:!?)]}>'\""


  class RegexLinkExtractor:
      """LinkExtractor implementation backed by regex.

      Pure — no I/O. Never raises on input: garbage in, empty out.
      """

      def extract(self, text: str, *, source: str) -> list[RawLink]:
          if not text:
              return []

          results: list[RawLink] = []
          seen_normalized: set[str] = set()

          # Pass 1: scheme-explicit URLs
          for match in _SCHEME_URL.finditer(text):
              raw = match.group(0).rstrip(_TRAILING_PUNCT)
              norm = normalize_url(raw)
              if not norm or norm in seen_normalized:
                  continue
              seen_normalized.add(norm)
              results.append(
                  RawLink(
                      url=raw,
                      normalized_url=norm,
                      source=source,
                      position_ms=None,
                  )
              )

          # Pass 2: bare domains (only when the normalized form is
          # not already captured — avoids double-counting a URL
          # matched by pass 1).
          for match in _BARE_DOMAIN.finditer(text):
              raw = match.group(0).rstrip(_TRAILING_PUNCT)
              if not raw:
                  continue
              candidate = "https://" + raw
              norm = normalize_url(candidate)
              if not norm or norm in seen_normalized:
                  continue
              seen_normalized.add(norm)
              results.append(
                  RawLink(
                      url=raw,
                      normalized_url=norm,
                      source=source,
                      position_ms=None,
                  )
              )

          return results
  ```

  **Étape B — Créer le corpus `tests/fixtures/link_corpus.json`** avec **≥ 100 entrées** (50 positifs + 30 négatifs + 20 edge) réellement discriminants. Le fichier DOIT contenir au MINIMUM les catégories suivantes pour valider le regex :

  Positifs (≥ 50) :
  - Plain HTTPS URL : `"Visitez https://example.com"`
  - Plain HTTP URL : `"Old link http://example.com"`
  - URL with path : `"https://shop.com/product/123"`
  - URL with query : `"https://search.com?q=test"`
  - URL with multiple query params : `"https://a.com/?b=2&a=1"`
  - URL with utm tracking : `"https://shop.com?utm_source=tt&id=5"` → expected normalized keeps `id=5` only
  - URL with fragment : `"https://a.com/page#section"`
  - bit.ly : `"Link: bit.ly/abc123"`
  - t.co : `"via t.co/xyz"`
  - www. prefix : `"check www.example.com"`
  - Bare domain no www : `"shop.com/sale today"`
  - Markdown-style `[text](url)` : `"[Buy here](https://shop.com)"`
  - URL in parentheses : `"(Visit https://example.com)"`
  - URL with trailing period : `"See https://example.com."`
  - URL with trailing comma : `"See https://example.com, for more"`
  - Multiple URLs same string : `"a https://a.com and b https://b.com"`
  - Dash in subdomain : `"https://my-shop.com"`
  - TLD .io : `"https://app.io/x"`
  - TLD .co : `"site.co/page"`
  - TLD .dev : `"go to dev.dev/test"`
  - TLD .app : `"app.app/download"`
  - Unicode path : `"https://example.com/café"` (expected normalized URL-encoded or preserved)
  - Long path : `"https://example.com/a/b/c/d/e"`
  - Port number : `"https://api.example.com:8080/endpoint"` (expected stored)
  - … (ajoutez jusqu'à 50)

  Négatifs (≥ 30) — STRINGS qui doivent produire `expected_urls: []` :
  - `"hello.world is not a URL"`
  - `"version 1.0.0"`
  - `"file.txt"`
  - `"my-file.doc"`
  - `"readme.md"`
  - `"main.py"`
  - `"photo.jpeg"`
  - `"2024.01.15"` (date-like)
  - `"ip 192.168.1.1"` (IP no TLD match)
  - `"name.txt in folder"`
  - `"etc.etc.etc"` (.etc not a TLD)
  - `"a.b.c.d"` (non-TLD chain)
  - `"price is 19.99"`
  - `"Math: 3.14"`
  - `"section 4.2.1"`
  - `"firstname.lastname@email.com"` (email — currently out of scope; should NOT match as URL)
  - `"plain text with no url"`
  - `""` (empty string)
  - `"   "` (whitespace only)
  - `"http://"` (scheme but no host)
  - `"https://"` (scheme but no host)
  - `"just https"` (word only)
  - `"www."` (www. but no domain)
  - `"abc.blah"` (blah not a TLD)
  - `"a.b"` (single-letter TLD, not in list)
  - … (ajoutez jusqu'à 30)

  Edge cases (≥ 20) :
  - URL with trailing exclamation : `"awesome! https://example.com!"` → expected `["https://example.com"]`
  - Multiple fragments : `"#tag1 https://a.com #tag2"`
  - URL surrounded by quotes : `'"https://example.com"'`
  - URL in parentheses with other text : `"Details (https://docs.com/api)"`
  - URL at very start : `"https://start.com text after"`
  - URL at very end : `"text before https://end.com"`
  - Two same URLs (dedup) : `"https://a.com and again https://a.com/"` → expected `["https://a.com"]`
  - Mixed case scheme : `"HTTPS://Example.com"` → expected normalized lowercase
  - IDN Punycode : `"https://xn--nxasmq6b.com"` (Chinese domain in punycode)
  - URL ending in dot : `"https://example.com."` → expected `["https://example.com"]`
  - URL ending in colon : `"example.com:"` — test behavior
  - URL with percent-encoded chars : `"https://example.com/path%20with%20spaces"`
  - URL with @ in path : `"https://instagram.com/@username"`
  - Emoji surrounded URL : `"✨ https://a.com 🎉"`
  - URL with newline separator : `"first\nhttps://a.com\nsecond"` (test doesn't cross lines inappropriately)
  - URL followed by parenthetical : `"site.com (English)"`
  - `"link: shop.com/?utm_campaign=x"` (tracking param only)
  - Empty query : `"https://example.com?"`
  - `"?"` only : expected `[]`
  - Very long URL : (construct 200-char URL)

  Schema JSON exact :

  ```json
  {
    "positive": [
      {"text": "Visitez https://example.com", "expected_urls": ["https://example.com"]},
      {"text": "Link: bit.ly/abc123", "expected_urls": ["https://bit.ly/abc123"]}
    ],
    "negative": [
      {"text": "hello.world is not a URL", "expected_urls": []},
      {"text": "version 1.0.0", "expected_urls": []}
    ],
    "edge": [
      {"text": "Details (https://docs.com/api)", "expected_urls": ["https://docs.com/api"]}
    ]
  }
  ```

  Le script de validation DOIT assurer ≥ 50 entries dans `positive`, ≥ 30 dans `negative`, ≥ 20 dans `edge`. `expected_urls` contient les URL dans leur forme BRUTE (pre-normalize) — les tests comparent via `normalize_url(expected) == rawlink.normalized_url`.

  **Étape C — Écrire les tests (TDD).** Créer `tests/unit/adapters/text/test_regex_link_extractor.py` :

  ```python
  """Unit tests for :class:`RegexLinkExtractor`.

  The non-negotiable corpus-driven test (:meth:`TestLinkCorpus.test_corpus`)
  iterates every entry in ``tests/fixtures/link_corpus.json`` and fails
  if the extractor misses a positive or produces a false positive. New
  edge cases go in the corpus, not here.
  """

  from __future__ import annotations

  import json
  from pathlib import Path
  from typing import Any

  import pytest

  from vidscope.adapters.text import RegexLinkExtractor, normalize_url


  CORPUS_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "link_corpus.json"


  @pytest.fixture(scope="module")
  def extractor() -> RegexLinkExtractor:
      return RegexLinkExtractor()


  @pytest.fixture(scope="module")
  def corpus() -> dict[str, list[dict[str, Any]]]:
      data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
      assert len(data["positive"]) >= 50, (
          f"corpus must have ≥50 positives (has {len(data['positive'])})"
      )
      assert len(data["negative"]) >= 30, (
          f"corpus must have ≥30 negatives (has {len(data['negative'])})"
      )
      assert len(data["edge"]) >= 20, (
          f"corpus must have ≥20 edge cases (has {len(data['edge'])})"
      )
      return data


  class TestRegexLinkExtractorBasics:
      def test_scheme_url(self, extractor: RegexLinkExtractor) -> None:
          hits = extractor.extract("visit https://example.com today", source="description")
          assert len(hits) == 1
          assert hits[0]["source"] == "description"

      def test_empty_text(self, extractor: RegexLinkExtractor) -> None:
          assert extractor.extract("", source="description") == []

      def test_no_url(self, extractor: RegexLinkExtractor) -> None:
          assert extractor.extract("plain text", source="description") == []

      def test_dedup_same_normalized(self, extractor: RegexLinkExtractor) -> None:
          hits = extractor.extract(
              "https://a.com and https://a.com/", source="description"
          )
          assert len(hits) == 1

      def test_strip_trailing_punctuation(self, extractor: RegexLinkExtractor) -> None:
          hits = extractor.extract("visit https://example.com.", source="description")
          assert len(hits) == 1
          assert "." not in hits[0]["url"] or hits[0]["url"].endswith(".com")

      def test_source_propagated_to_every_hit(
          self, extractor: RegexLinkExtractor
      ) -> None:
          hits = extractor.extract(
              "a https://a.com b https://b.com", source="transcript"
          )
          assert len(hits) == 2
          for h in hits:
              assert h["source"] == "transcript"

      def test_hello_world_is_not_url(self, extractor: RegexLinkExtractor) -> None:
          assert extractor.extract("hello.world", source="description") == []

      def test_version_string_is_not_url(
          self, extractor: RegexLinkExtractor
      ) -> None:
          assert extractor.extract("version 1.0.0", source="description") == []

      def test_file_extension_is_not_url(
          self, extractor: RegexLinkExtractor
      ) -> None:
          assert extractor.extract("file.txt", source="description") == []


  class TestLinkCorpus:
      """Gate qualité non-négociable (M007 ROADMAP).

      Itère le corpus complet ; fail si l'extracteur manque un positif
      ou produit un faux positif. Un échec = broken build.
      """

      def _compare(
          self,
          extractor: RegexLinkExtractor,
          entry: dict[str, Any],
          category: str,
      ) -> None:
          text = entry["text"]
          expected = {normalize_url(u) for u in entry["expected_urls"]}
          actual = {
              h["normalized_url"]
              for h in extractor.extract(text, source="description")
          }
          assert actual == expected, (
              f"{category} fixture mismatch for text={text!r}\n"
              f"  expected={sorted(expected)}\n"
              f"  actual  ={sorted(actual)}"
          )

      def test_positive_corpus(
          self,
          extractor: RegexLinkExtractor,
          corpus: dict[str, list[dict[str, Any]]],
      ) -> None:
          for entry in corpus["positive"]:
              self._compare(extractor, entry, "positive")

      def test_negative_corpus(
          self,
          extractor: RegexLinkExtractor,
          corpus: dict[str, list[dict[str, Any]]],
      ) -> None:
          for entry in corpus["negative"]:
              self._compare(extractor, entry, "negative")

      def test_edge_corpus(
          self,
          extractor: RegexLinkExtractor,
          corpus: dict[str, list[dict[str, Any]]],
      ) -> None:
          for entry in corpus["edge"]:
              self._compare(extractor, entry, "edge")
  ```

  **NOTE** : Si certaines entrées du corpus ne matchent pas le regex actuel, itérer sur le regex et/ou ajuster l'entrée dans le corpus (marquer les cas réellement hors de portée M007 avec un `skip_reason` et skipper dans `_compare`). L'important est que le test final PASSE avec ≥ 50/30/20 entries réellement actives.
  </action>

  <acceptance_criteria>
    - `test -f src/vidscope/adapters/text/regex_link_extractor.py`
    - `test -f tests/fixtures/link_corpus.json`
    - `test -f tests/unit/adapters/text/test_regex_link_extractor.py`
    - `grep -q "class RegexLinkExtractor:" src/vidscope/adapters/text/regex_link_extractor.py` exit 0
    - `grep -q "_COMMON_TLDS" src/vidscope/adapters/text/regex_link_extractor.py` exit 0
    - `python -m uv run python -c "import json; data = json.load(open('tests/fixtures/link_corpus.json', encoding='utf-8')); assert len(data['positive']) >= 50, f'{len(data[\"positive\"])} < 50'; assert len(data['negative']) >= 30, f'{len(data[\"negative\"])} < 30'; assert len(data['edge']) >= 20, f'{len(data[\"edge\"])} < 20'; total = sum(len(data[k]) for k in ('positive','negative','edge')); assert total >= 100, total; print(f'corpus size OK: total={total}')"` affiche `corpus size OK: total=<number>`
    - `python -m uv run python -c "from vidscope.adapters.text import RegexLinkExtractor; e = RegexLinkExtractor(); hits = e.extract('visit https://example.com today', source='description'); assert len(hits) == 1; assert hits[0]['source'] == 'description'; print('OK')"` affiche `OK`
    - `python -m uv run python -c "from vidscope.adapters.text import RegexLinkExtractor; e = RegexLinkExtractor(); assert e.extract('hello.world is not a URL', source='description') == []; assert e.extract('version 1.0.0', source='description') == []; assert e.extract('file.txt', source='description') == []; print('OK')"` affiche `OK`
    - `python -m uv run pytest tests/unit/adapters/text/test_regex_link_extractor.py::TestRegexLinkExtractorBasics -x -q` exit 0
    - `python -m uv run pytest tests/unit/adapters/text/test_regex_link_extractor.py::TestLinkCorpus -x -q` exit 0 (**gate non-négociable**)
    - `python -m uv run mypy src` exit 0
    - `python -m uv run ruff check src tests` exit 0
  </acceptance_criteria>
</task>

<task id="T03-importlinter-contract">
  <name>Ajouter le contrat import-linter `text-adapter-is-self-contained` + enforcer reciproquement sur les autres adapters</name>

  <read_first>
    - `.importlinter` — fichier complet, en particulier lignes 60-77 (contrat `llm-never-imports-other-adapters` à miroir) et lignes 45-58 (`sqlite-never-imports-fs`)
    - `.gsd/milestones/M007/M007-RESEARCH.md` §"Pattern import-linter pour adapters/text" (contenu exact du contrat à ajouter)
    - `.gsd/milestones/M007/M007-CONTEXT.md` §canonical_refs `.importlinter` (nouveau contrat `text-adapter-is-self-contained` requis pour S02 `adapters/text`)
    - `src/vidscope/adapters/text/` — nouveau sous-module créé en T01/T02, doit respecter ce contrat
    - `tests/architecture/` — localiser les tests d'architecture existants (si présents) pour étendre la liste de contrats attendus
  </read_first>

  <action>
  **Étape A — Ajouter le contrat `text-adapter-is-self-contained` dans `.importlinter`**. Insérer APRÈS le contrat `llm-never-imports-other-adapters` (ligne ~77) et AVANT la section `# Domain and ports must not depend on SQLAlchemy` :

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

  **Étape B — Ajouter `vidscope.adapters.text` en module interdit dans les contrats existants qui listent les autres adapters comme forbidden.** Parcourir `.importlinter` et pour chaque contrat du type `<adapter>-never-imports-<other-adapters>` (actuellement `sqlite-never-imports-fs`, `fs-never-imports-sqlite`, `llm-never-imports-other-adapters`), ajouter `vidscope.adapters.text` à la liste `forbidden_modules` :

  Pour `llm-never-imports-other-adapters`, ajouter `vidscope.adapters.text` dans la liste (entre `vidscope.adapters.heuristic` et `vidscope.infrastructure`).

  Pour `sqlite-never-imports-fs`, la liste n'inclut que `vidscope.adapters.fs`. Par cohérence avec `llm-never-imports-other-adapters`, l'étendre à `vidscope.adapters.text` OU créer un nouveau contrat `sqlite-never-imports-text`. **Choix retenu : étendre le contrat existant `sqlite-never-imports-fs` en lui ajoutant `vidscope.adapters.text`** et renommer le `name =` pour refléter l'élargissement :

  ```ini
  [importlinter:contract:sqlite-never-imports-fs]
  name = sqlite adapter does not import fs or text adapters
  type = forbidden
  source_modules =
      vidscope.adapters.sqlite
  forbidden_modules =
      vidscope.adapters.fs
      vidscope.adapters.text
  ```

  De même pour `fs-never-imports-sqlite` :

  ```ini
  [importlinter:contract:fs-never-imports-sqlite]
  name = fs adapter does not import sqlite or text adapters
  type = forbidden
  source_modules =
      vidscope.adapters.fs
  forbidden_modules =
      vidscope.adapters.sqlite
      vidscope.adapters.text
  ```

  **Étape C — Étendre le test d'architecture** (si `tests/architecture/test_architecture.py` existe). Sinon, vérifier qu'un test existant pour lint-imports attend désormais 10 contrats (au lieu de 9). Localiser le fichier via `grep -r "lint-imports\|lint_imports\|import-linter" tests/`. S'il y a une assertion sur le nombre de contrats, la mettre à jour.

  Si aucun test d'architecture n'existe, créer `tests/architecture/test_architecture.py` avec un test minimal qui lance `lint-imports` via subprocess et vérifie exit 0.
  </action>

  <acceptance_criteria>
    - `grep -q "\[importlinter:contract:text-adapter-is-self-contained\]" .importlinter` exit 0
    - `grep -q "text adapter does not import other adapters" .importlinter` exit 0
    - `grep -q "vidscope.adapters.text" .importlinter` retourne ≥ 4 occurrences (source dans le nouveau contrat + forbidden dans llm + sqlite + fs contrats) : `test $(grep -c 'vidscope.adapters.text' .importlinter) -ge 4`
    - `python -m uv run lint-imports` exit 0 (le nouveau sous-module adapters/text compile et respecte le contrat)
    - `python -m uv run lint-imports 2>&1 | grep -q "text-adapter-is-self-contained"` ou `python -m uv run lint-imports --verbose 2>&1 | grep -i "text"` montre que le contrat est évalué
    - Test additionnel : créer un fichier temp qui viole le contrat (p.ex. `adapters/text` important `adapters/sqlite`) et vérifier que `lint-imports` exit != 0, puis supprimer le fichier. Cette étape est manuelle ; documentée dans le PR.
    - `python -m uv run pytest -q` exit 0 (suite globale, aucune régression)
  </acceptance_criteria>
</task>

## Verification Criteria

```bash
# Tests (basics + corpus gate)
python -m uv run pytest tests/unit/adapters/text/ -x -q
python -m uv run pytest tests/unit/adapters/text/test_regex_link_extractor.py::TestLinkCorpus -x -q

# Vérifier corpus ≥ 100 strings
python -m uv run python -c "
import json
d = json.load(open('tests/fixtures/link_corpus.json', encoding='utf-8'))
total = sum(len(d[k]) for k in ('positive','negative','edge'))
assert len(d['positive']) >= 50 and len(d['negative']) >= 30 and len(d['edge']) >= 20
assert total >= 100
print(f'OK: total={total}')
"

# Vérifier contrats import-linter (10 contrats maintenant)
python -m uv run lint-imports
grep -c "^\[importlinter:contract:" .importlinter  # attendu: 10

# Suite complète + quality gates
python -m uv run pytest -q
python -m uv run ruff check src tests
python -m uv run mypy src
```

## Must-Haves

- Sous-module `vidscope.adapters.text` existe avec `RegexLinkExtractor` (implémente `LinkExtractor`) et `normalize_url` (pure-Python stdlib only).
- `URLNormalizer` (fonction `normalize_url`) : lowercase scheme+host, strip utm_*, strip fragment, sort query params, strip trailing slash, idempotent.
- `RegexLinkExtractor.extract(text, source=...)` retourne `list[RawLink]` dédupliqué par `normalized_url`, ne lève jamais.
- Corpus `tests/fixtures/link_corpus.json` avec ≥ 50 positifs + ≥ 30 négatifs + ≥ 20 edge (total ≥ 100) — **gate non-négociable**.
- Test parametrisé `TestLinkCorpus` qui itère chaque entrée du corpus et vérifie `expected_urls` exactement.
- Nouveau contrat `text-adapter-is-self-contained` dans `.importlinter`, structurellement enforçant que `adapters/text` n'importe AUCUN autre adapter + application + pipeline + cli + mcp + infrastructure.
- Les contrats existants `sqlite-never-imports-fs` et `fs-never-imports-sqlite` étendus pour interdire `adapters.text` réciproquement.
- `lint-imports` exit 0 avec 10 contrats verts.
- Tests unitaires ≥ 10 pour `URLNormalizer` + ≥ 9 pour `RegexLinkExtractor` basics + 3 tests de corpus (positive/negative/edge).

## Threat Model

| # | Catégorie STRIDE | Composant | Sévérité | Disposition | Mitigation |
|---|---|---|---|---|---|
| T-S02P02-01 | **Denial of Service (D)** — ReDoS catastrophic backtracking | `_SCHEME_URL`, `_BARE_DOMAIN` regex | MEDIUM | mitigate | Le regex n'a pas de nested quantificateurs `(a+)+` qui causent catastrophic backtracking. `[^\s<>\"'`{}|\\^\[\]]+` est greedy simple ; `_BARE_DOMAIN` a des classes bornées. Test de perf additionnel (optionnel) : `extract("a" * 10000)` doit retourner `[]` en < 100ms. |
| T-S02P02-02 | **Tampering (T) — URL spoofing via homograph/IDN** | `RegexLinkExtractor` + `normalize_url` | MEDIUM | accept | Le normalizer lowercase host encoding Punycode ⇒ les homographs IDN ne sont pas détectés comme tels (ex: `рaypal.com` en cyrillique). M007 stocke tel quel ; l'affichage CLI n'ouvre pas les URLs automatiquement (pas de clic). Couverture détection homograph = out of scope M007 (M011 pourra ajouter un lint "mixed-script domain"). |
| T-S02P02-03 | **Information Disclosure (I)** — leak de chemin absolu du corpus | `test_regex_link_extractor.py` | LOW | accept | Le test lit `tests/fixtures/link_corpus.json` via `Path(__file__).resolve()`. Chemin absolu visible dans les stacktraces en cas d'échec ; acceptable pour un outil single-user local (R032). |
| T-S02P02-04 | **Injection (T via T)** — URL contenant `'` ou `"` stockée | `RawLink.url` → `links.url` SQL | LOW | mitigate | L'injection est impossible côté SQLAlchemy Core bindé (cf. T-S01P02-01). La regex capture les caractères d'URL valides ; les `'` et `"` sont dans la classe negative (`[^\s<>\"'`{}|\\^\[\]]+`) donc exclus du match, mais même s'ils passaient via bare-domain, bindé = safe. |
| T-S02P02-05 | **Tampering (T)** — contrat import-linter contourné par import dynamique | `adapters/text` module | LOW | mitigate | import-linter détecte les `import` et `from ... import` statiques. Un `__import__("vidscope.adapters.sqlite")` dynamique n'est PAS détecté mais serait visible en code review. Pas de mécanisme de défense 100% dans le code Python ; acceptable comme surface conception-time. |
