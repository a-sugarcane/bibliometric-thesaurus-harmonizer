"""Head noun lemmatization with protected biomedical term whitelist."""

from pathlib import Path
from typing import Optional, Set
from config import PROTECTED_TERMS_FILE

try:
    import inflect
    _INFLECT_ENGINE = inflect.engine()
except ImportError:
    _INFLECT_ENGINE = None


class HeadNounLemmatizer:
    """Lemmatizes English multi-word phrases by modifying only the final head noun."""

    def __init__(self, protected_terms_file: Optional[Path | str] = None):
        """Initialize lemmatizer and load protected terms."""
        self.protected_terms: Set[str] = set()
        file_path = Path(protected_terms_file) if protected_terms_file else PROTECTED_TERMS_FILE
        if file_path.is_file():
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    term = line.strip().lower()
                    if term and not term.startswith("#"):
                        self.protected_terms.add(term)

    def is_protected(self, word: str) -> bool:
        """Check if a word matches the protected whitelist or protected suffixes."""
        word_lower = word.lower()
        if word_lower in self.protected_terms:
            return True
        # Check standard Latin/Greek medical endings that end in 's'
        protected_endings = ("omics", "sis", "itis", "osis", "x")
        return any(word_lower.endswith(end) for end in protected_endings)

    def lemmatize_word(self, word: str) -> str:
        """Lemmatize a single word if it is plural and not protected."""
        word_lower = word.lower()
        if self.is_protected(word_lower):
            return word

        if _INFLECT_ENGINE is not None:
            # singular_noun returns False if word is already singular
            singular = _INFLECT_ENGINE.singular_noun(word_lower)
            if singular and isinstance(singular, str):
                return singular

        # Classical Greek/Latin biomedical plural: -ses -> -sis (e.g. metastases -> metastasis, analyses -> analysis)
        if word_lower.endswith("ses") and not word_lower.endswith("sses"):
            candidate_sis = word_lower[:-3] + "sis"
            if candidate_sis in self.protected_terms or len(word_lower) > 5:
                return candidate_sis

        # Fallback heuristic: regular -s / -es rule if inflect is not installed
        if word_lower.endswith("ies") and len(word_lower) > 4:
            return word_lower[:-3] + "y"
        elif word_lower.endswith("es") and len(word_lower) > 4:
            if word_lower.endswith(("ches", "shes", "xes", "zes", "sses")):
                return word_lower[:-2]
            return word_lower[:-1]
        elif word_lower.endswith("s") and not word_lower.endswith(("ss", "us", "is")):
            return word_lower[:-1]

        return word

    def lemmatize_phrase(self, phrase: str) -> str:
        """Lemmatize only the last head word in a multi-word phrase.

        Examples:
            'prostate cancers' -> 'prostate cancer'
            'breast cancer patients' -> 'breast cancer patient'
            'bone metastases' -> 'bone metastasis'
            'psychological distress' -> 'psychological distress' (protected)

        Args:
            phrase: Full keyword phrase.

        Returns:
            Normalized phrase with singular head noun.
        """
        words = phrase.strip().split()
        if not words:
            return ""

        last_word = words[-1]
        lemmatized_last = self.lemmatize_word(last_word)

        words[-1] = lemmatized_last
        return " ".join(words)
