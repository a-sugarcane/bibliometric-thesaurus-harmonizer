"""Canonical term arbitration protocol: choosing the standard target keyword."""

from typing import Dict, Optional


class Canonicalizer:
    """Arbitrates which term becomes the canonical target ('replace by') keyword."""

    @staticmethod
    def is_acronym(term: str) -> bool:
        """Check if term matches short acronym pattern (<= 5 chars, uppercase/alphanumeric)."""
        clean = term.strip()
        return len(clean) <= 5 and clean.isupper()

    @classmethod
    def arbitrate(
        cls,
        term_a: str,
        term_b: str,
        corpus_frequencies: Optional[Dict[str, int]] = None,
        mesh_canonical: Optional[str] = None,
    ) -> str:
        """Decide the canonical target keyword between two synonymous expressions.

        Protocol:
            1. If one is an acronym and the other is a full phrase -> choose the full phrase.
            2. If both are full expressions: check local corpus frequencies.
               If one has significantly higher frequency, choose the clinical convention.
            3. Fallback: choose the official MeSH descriptor if available; otherwise term_a.

        Args:
            term_a: First candidate.
            term_b: Second candidate.
            corpus_frequencies: Map of lowercase term to occurrence count.
            mesh_canonical: Official MeSH DescriptorName if known.

        Returns:
            The selected canonical target term.
        """
        # Step 1: Acronym vs Full Phrase
        a_is_acronym = cls.is_acronym(term_a)
        b_is_acronym = cls.is_acronym(term_b)

        if a_is_acronym and not b_is_acronym:
            return term_b
        if b_is_acronym and not a_is_acronym:
            return term_a

        # Step 2: Corpus frequency dominance (Clinical convention over obscure standard)
        if corpus_frequencies:
            freq_a = corpus_frequencies.get(term_a.lower(), 0)
            freq_b = corpus_frequencies.get(term_b.lower(), 0)

            if freq_a > freq_b:
                return term_a
            elif freq_b > freq_a:
                return term_b

        # Step 3: MeSH official descriptor preference
        if mesh_canonical:
            if term_a.lower() == mesh_canonical.lower():
                return term_a
            if term_b.lower() == mesh_canonical.lower():
                return term_b

        # Step 4: Fallback to shorter or alphabetically earlier
        return term_a if len(term_a) <= len(term_b) else term_b
