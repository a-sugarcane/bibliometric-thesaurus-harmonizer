"""Syntax cleaner: bracket decoupling, acronym extraction, and punctuation cleanup."""

import re
from dataclasses import dataclass
from typing import Optional, Tuple
from config import MAX_ACRONYM_LENGTH


@dataclass
class DecoupledPhrase:
    """Represents a term decomposed from parentheses."""

    full_phrase: str
    acronym: Optional[str] = None
    is_acronym_valid: bool = False


class SyntaxCleaner:
    """Performs punctuation normalization and parenthesis/acronym decoupling."""

    # Matches "Full Phrase (ACRONYM)" or "Full Phrase （ACRONYM）"
    PARENTHESIS_PATTERN = re.compile(r"^(.*?)\s*[\(\（](.*?)[\)\）]$")

    @classmethod
    def clean_basic_syntax(cls, term: str) -> str:
        """Strip surrounding quotes, redundant whitespaces, and dangling punctuation.

        Args:
            term: Raw keyword string.

        Returns:
            Cleaned keyword string.
        """
        cleaned = term.strip().strip("'\"`")
        # Collapse multiple spaces into one
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    @classmethod
    def check_acronym_alignment(cls, acronym: str, phrase: str) -> bool:
        """Verify whether an acronym legitimately aligns with a full phrase."""
        acronym_clean = re.sub(r"[^A-Za-z0-9]", "", acronym)
        if not acronym_clean or len(acronym_clean) > 8:
            return False

        words = re.findall(r"[A-Za-z0-9]+", phrase)
        if not words:
            return False

        # Case 1: Direct all-words initial matching (e.g. ADT -> Androgen Deprivation Therapy, QoL -> Quality of Life)
        all_initials = "".join(w[0] for w in words).lower()
        if acronym_clean.lower() == all_initials:
            return True

        # Case 2: Content-words initial matching (ignoring stopwords)
        stopwords = {"of", "in", "for", "and", "the", "with", "to", "on", "at", "by", "from", "a", "an"}
        content_words = [w for w in words if w.lower() not in stopwords]
        if content_words:
            content_initials = "".join(w[0] for w in content_words).lower()
            if acronym_clean.lower() == content_initials:
                return True

        # Case 3: Biomedical lowercase prefix tolerance (e.g. mCRPC -> metastatic castration-resistant prostate cancer)
        if len(acronym_clean) >= 2 and acronym_clean[0].islower():
            prefix = acronym_clean[0].lower()
            rest_acronym = acronym_clean[1:].lower()
            if words[0][0].lower() == prefix:
                rest_all = "".join(w[0] for w in words[1:]).lower()
                rest_content = (
                    "".join(w[0] for w in content_words[1:]).lower()
                    if len(content_words) > 1
                    else ""
                )
                if rest_acronym == rest_all or rest_acronym == rest_content:
                    return True

        return False

    @classmethod
    def decouple_parentheses(cls, term: str) -> DecoupledPhrase:
        """Decouple expressions like 'androgen deprivation therapy (adt)' into full and acronym.

        If the parentheses contain non-acronym descriptive qualifiers (e.g. 'depression (geriatric)'),
        the entire expression is preserved without truncation.

        Args:
            term: Cleaned keyword string.

        Returns:
            DecoupledPhrase containing full_phrase, acronym, and validity flag.
        """
        match = cls.PARENTHESIS_PATTERN.match(term)
        if not match:
            return DecoupledPhrase(full_phrase=term)

        candidate_full = match.group(1).strip()
        candidate_inner = match.group(2).strip()

        # Check: Candidate inner is acronym for outer full phrase
        if cls.check_acronym_alignment(candidate_inner, candidate_full):
            return DecoupledPhrase(
                full_phrase=candidate_full,
                acronym=candidate_inner,
                is_acronym_valid=True,
            )

        # Check reverse: Candidate full is acronym for inner phrase, e.g. "QoL (quality of life)"
        if cls.check_acronym_alignment(candidate_full, candidate_inner):
            return DecoupledPhrase(
                full_phrase=candidate_inner,
                acronym=candidate_full,
                is_acronym_valid=True,
            )

        # Not an acronym pair -> preserve full term intact to protect clinical specificity
        return DecoupledPhrase(full_phrase=term, acronym=None, is_acronym_valid=False)

