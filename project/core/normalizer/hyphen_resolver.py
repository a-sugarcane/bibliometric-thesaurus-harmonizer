"""Hyphen dual-candidate collision detection and resolution."""

from typing import Callable, Dict, Optional, Set


class HyphenResolver:
    """Resolves hyphenated expressions by testing space-separated vs joined candidates."""

    @staticmethod
    def generate_candidates(term: str) -> tuple[str, str]:
        """Generate candidate A (space replaced) and candidate B (hyphen deleted).

        Examples:
            'quality-of-life' -> ('quality of life', 'qualityoflife')
            'co-occurrence' -> ('co occurrence', 'cooccurrence')
        """
        cand_space = term.replace("-", " ").strip()
        cand_closed = term.replace("-", "").strip()
        return cand_space, cand_closed

    @classmethod
    def resolve_hyphen_term(
        cls,
        term: str,
        corpus_frequencies: Optional[Dict[str, int]] = None,
        mesh_terms: Optional[Set[str]] = None,
    ) -> str:
        """Resolve hyphenated term based on corpus frequency and MeSH presence.

        Args:
            term: Term containing hyphens.
            corpus_frequencies: Dictionary mapping lowercase terms to occurrences.
            mesh_terms: Set of known MeSH descriptor or entry terms.

        Returns:
            Best resolved target term.
        """
        if "-" not in term:
            return term

        cand_space, cand_closed = cls.generate_candidates(term)
        cand_space_lower = cand_space.lower()
        cand_closed_lower = cand_closed.lower()

        # 1. MeSH dictionary priority
        if mesh_terms:
            if cand_space_lower in mesh_terms:
                return cand_space
            if cand_closed_lower in mesh_terms:
                return cand_closed

        # 2. Corpus frequency priority
        if corpus_frequencies:
            freq_space = corpus_frequencies.get(cand_space_lower, 0)
            freq_closed = corpus_frequencies.get(cand_closed_lower, 0)

            if freq_space > 0 or freq_closed > 0:
                return cand_space if freq_space >= freq_closed else cand_closed

        # 3. Default standard modern English convention: space separated
        return cand_space
