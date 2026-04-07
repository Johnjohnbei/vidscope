"""Stopword lists for the heuristic analyzer.

Minimal French + English stopword sets. Not exhaustive — just the
most common words that would otherwise dominate the keyword
extraction. Stored as a frozenset for O(1) lookup.

Sources: standard linguistic stopword lists (public domain).
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

# French — top ~150 most frequent words
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
})

ALL_STOPWORDS: frozenset[str] = ENGLISH_STOPWORDS | FRENCH_STOPWORDS
