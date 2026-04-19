"""YamlVocabularySource — construit l'initial_prompt Whisper depuis vocabulary.yaml + DB.

Deux sources fusionnées :
  1. Termes statiques depuis ``config/vocabulary.yaml`` (prioritaires, toujours inclus)
  2. Termes dynamiques depuis la DB : titres vidéo courts, hashtags, handles créateurs

Le résultat est tronqué à ``_MAX_PROMPT_CHARS`` pour rester dans la limite de tokens
Whisper (~224 tokens ≈ 900 caractères).

Si le fichier YAML est absent, seuls les termes DB sont utilisés.
Si l'engine est None, seuls les termes YAML sont utilisés.
Dans les deux cas : jamais de crash — l'absence de prompt n'empêche pas la transcription.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from sqlalchemy import Engine

__all__ = ["YamlVocabularySource"]

_logger = logging.getLogger(__name__)

# Whisper initial_prompt est limité à ~224 tokens. À ~4 chars/token → 900 chars.
_MAX_PROMPT_CHARS = 900


class YamlVocabularySource:
    """Construit un initial_prompt Whisper depuis YAML + DB.

    Parameters
    ----------
    path:
        Chemin vers ``vocabulary.yaml``. Absent = pas de termes statiques.
    engine:
        SQLAlchemy Engine pour les requêtes DB dynamiques. None = pas de termes DB.
    """

    def __init__(self, path: Path, engine: "Engine | None" = None) -> None:
        self._path = path
        self._engine = engine

    def build_hotwords(self) -> str | None:
        """Retourne les hotwords sous forme de chaîne pour faster-whisper.

        Les hotwords boostent directement les tokens dans le beam search,
        plus efficace que l'initial_prompt pour les noms propres ambigus.
        """
        raw = self._read_yaml()
        if raw is None:
            return None
        entries = raw.get("hotwords", [])
        if not isinstance(entries, list):
            return None
        terms = [str(e).strip() for e in entries if isinstance(e, str) and str(e).strip()]
        if not terms:
            return None
        return ", ".join(terms)

    def load_corrections(self) -> list[tuple[str, str]]:
        """Retourne la liste (wrong, right) depuis la section ``corrections``.

        Utilisé par FasterWhisperTranscriber pour post-traiter les transcripts.
        Jamais de crash : absent ou invalide → liste vide.
        """
        raw = self._read_yaml()
        if raw is None:
            return []
        entries = raw.get("corrections", [])
        if not isinstance(entries, list):
            return []
        result: list[tuple[str, str]] = []
        for entry in entries:
            if isinstance(entry, dict):
                wrong = entry.get("wrong")
                right = entry.get("right")
                if isinstance(wrong, str) and isinstance(right, str) and wrong.strip():
                    result.append((wrong.strip(), right.strip()))
        _logger.debug("Vocabulary corrections : %d règles chargées", len(result))
        return result

    def build_prompt(self) -> str | None:
        """Retourne une chaîne de termes séparés par des virgules, ou None.

        Priorité : termes YAML d'abord, puis termes DB jusqu'à épuisement du budget.
        """
        yaml_terms = self._load_yaml_terms()
        db_terms = self._load_db_terms() if self._engine is not None else []

        all_terms = _deduplicate(yaml_terms + db_terms)
        if not all_terms:
            return None

        return _pack_into_budget(all_terms, _MAX_PROMPT_CHARS) or None

    # ------------------------------------------------------------------
    # Chargement YAML
    # ------------------------------------------------------------------

    def _read_yaml(self) -> dict[str, object] | None:
        """Lit et parse vocabulary.yaml. Retourne None si absent ou invalide."""
        if not self._path.is_file():
            _logger.debug("vocabulary.yaml absent (%s)", self._path)
            return None
        try:
            with self._path.open(encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
        except Exception as exc:
            _logger.warning("Impossible de lire vocabulary.yaml : %s", exc)
            return None
        if not isinstance(raw, dict):
            _logger.warning("vocabulary.yaml : format invalide (attendu: dict de sections)")
            return None
        return raw

    def _load_yaml_terms(self) -> list[str]:
        raw = self._read_yaml()
        if raw is None:
            return []

        terms: list[str] = []
        for _section, entries in raw.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, str) and entry.strip():
                    terms.append(entry.strip())

        _logger.debug("Vocabulary YAML : %d termes chargés", len(terms))
        return terms

    # ------------------------------------------------------------------
    # Chargement DB
    # ------------------------------------------------------------------

    def _load_db_terms(self) -> list[str]:
        """Requêtes légères en lecture seule sur la bibliothèque DB."""
        from sqlalchemy import text  # noqa: PLC0415

        terms: list[str] = []
        try:
            with self._engine.connect() as conn:  # type: ignore[union-attr]
                # Titres courts : utilisés tels quels si < 60 chars
                rows = conn.execute(
                    text(
                        "SELECT DISTINCT title FROM videos "
                        "WHERE title IS NOT NULL AND length(title) < 60 "
                        "ORDER BY id DESC LIMIT 150"
                    )
                ).fetchall()
                for (title,) in rows:
                    if title:
                        terms.append(str(title).strip())

                # Hashtags (colonne `tag`)
                try:
                    rows = conn.execute(
                        text("SELECT DISTINCT tag FROM hashtags LIMIT 300")
                    ).fetchall()
                    for (tag,) in rows:
                        if tag:
                            terms.append(str(tag).strip())
                except Exception:
                    pass  # table peut ne pas encore exister

                # Handles de créateurs
                try:
                    rows = conn.execute(
                        text(
                            "SELECT DISTINCT handle FROM creators "
                            "WHERE handle IS NOT NULL LIMIT 100"
                        )
                    ).fetchall()
                    for (handle,) in rows:
                        if handle:
                            terms.append(str(handle).strip())
                except Exception:
                    pass
        except Exception as exc:
            _logger.debug("Impossible de charger les termes DB : %s", exc)

        _logger.debug("Vocabulary DB : %d termes chargés", len(terms))
        return terms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deduplicate(terms: list[str]) -> list[str]:
    """Déduplique en préservant l'ordre (clé = lowercase)."""
    seen: set[str] = set()
    result: list[str] = []
    for t in terms:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            result.append(t)
    return result


def _pack_into_budget(terms: list[str], max_chars: int) -> str:
    """Assemble les termes séparés par ', ' jusqu'à ``max_chars``."""
    parts: list[str] = []
    total = 0
    for term in terms:
        needed = len(term) + (2 if parts else 0)  # ", " separator
        if total + needed > max_chars:
            break
        parts.append(term)
        total += needed
    return ", ".join(parts)
