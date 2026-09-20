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
    def decouple_parentheses(cls, term: str) -> DecoupledPhrase:
        """Decouple expressions like 'androgen deprivation therapy (adt)' into full and acronym.

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

        # Check if inner content is an acronym (length <= 5, alphanumeric)
        is_inner_acronym = (
            len(candidate_inner) <= MAX_ACRONYM_LENGTH
            and re.match(r"^[A-Za-z0-9\-\+]+$", candidate_inner) is not None
        )

        # Reverse check: e.g. "ADT (androgen deprivation therapy)"
        is_outer_acronym = (
            len(candidate_full) <= MAX_ACRONYM_LENGTH
            and re.match(r"^[A-Za-z0-9\-\+]+$", candidate_full) is not None
        )

        if is_inner_acronym:
            return DecoupledPhrase(
                full_phrase=candidate_full,
                acronym=candidate_inner,
                is_acronym_valid=True,
            )
        elif is_outer_acronym:
            return DecoupledPhrase(
                full_phrase=candidate_inner,
                acronym=candidate_full,
                is_acronym_valid=True,
            )

        # Neither is a short acronym, return stripped phrase
        return DecoupledPhrase(full_phrase=candidate_full)
