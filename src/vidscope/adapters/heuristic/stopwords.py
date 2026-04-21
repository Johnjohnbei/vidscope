"""Stopword lists for the heuristic analyzer.

French + English stopword sets. Stored as frozensets for O(1) lookup.

R063 extension (M012/S02) : the V1 tokenizer captures apostrophes as
part of tokens (``_WORD_PATTERN = r"[a-zàâäéèêëïîôöùûüÿçœæ']+"``), so
``"c'est"`` is one token, not three. To filter these correctly, we add
two auxiliary frozensets — ``_FRENCH_CONTRACTIONS`` (canonical
contracted forms) and ``_FRENCH_COMMON_VERBS`` (conjugated verbs that
carry no domain semantics) — unioned into :data:`FRENCH_STOPWORDS`.

Note: forms shorter than 4 characters (e.g. ``m'a``, ``t'a``) are
already eliminated by ``_MIN_KEYWORD_LENGTH = 4`` in analyzer.py and
are therefore not included here to avoid redundant entries.

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
    "n'est", "n'a", "n'ai", "n'avait", "n'ont", "n'était",
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
    "dit", "disait", "disais", "disent",
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
