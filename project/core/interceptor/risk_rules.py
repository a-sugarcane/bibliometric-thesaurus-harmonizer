"""Clinical risk rules and token-difference-set concept slippage interceptor."""

import re
from dataclasses import dataclass, field
from typing import List, Set


@dataclass
class InterceptionResult:
    """Outcome of risk interception check."""

    is_blocked: bool
    risk_level: str  # "SAFE" or "HIGH_RISK"
    conflicting_tokens: Set[str] = field(default_factory=set)
    reason: str = ""


class ClinicalRiskInterceptor:
    """Guards against concept slippage by detecting critical clinical modifiers in token differences."""

    # High-risk modifier lists (Oncology stages, drug resistance, psychiatric boundaries)
    ONCOLOGY_RISK_TERMS: Set[str] = {
        "metastatic",
        "advanced",
        "castration-resistant",
        "crpc",
        "mcrpc",
        "hormone-sensitive",
        "localized",
        "early-stage",
        "recurrent",
        "refractory",
        "non-metastatic",
        "stage",
        "grade",
    }

    PSYCHIATRIC_RISK_TERMS: Set[str] = {
        "distress",
        "depressive symptoms",
        "major depressive disorder",
        "mdd",
        "bipolar",
        "anxiety",
        "fatigue",
        "insomnia",
        "suicide",
        "suicidal",
        "delirium",
    }

    def __init__(self, custom_risk_terms: Set[str] | None = None):
        """Initialize interceptor with default and optional custom risk terms."""
        self.all_risk_terms: Set[str] = set()
        self.all_risk_terms.update(self.ONCOLOGY_RISK_TERMS)
        self.all_risk_terms.update(self.PSYCHIATRIC_RISK_TERMS)
        if custom_risk_terms:
            self.all_risk_terms.update(t.lower() for t in custom_risk_terms)

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """Tokenize text into lowercase alphanumeric tokens."""
        return set(re.findall(r"[a-zA-Z0-9\-]+", text.lower()))

    def inspect_pair(self, term_x: str, term_y: str) -> InterceptionResult:
        r"""Inspect proposed merge of term_x and term_y using difference set analysis.

        Formula:
            Delta = (Tokens(X) union Tokens(Y)) \ (Tokens(X) intersect Tokens(Y))

        If any token in Delta is in all_risk_terms, intercept and block.

        Args:
            term_x: First keyword.
            term_y: Second keyword.

        Returns:
            InterceptionResult with blockage status and reason.
        """
        toks_x = self._tokenize(term_x)
        toks_y = self._tokenize(term_y)

        # Token difference set Delta
        delta = (toks_x | toks_y) - (toks_x & toks_y)

        # Direct token intersection check
        conflicting = delta & self.all_risk_terms

        # Phrase-level check (e.g. 'major depressive disorder' vs 'depression')
        phrase_x = term_x.strip().lower()
        phrase_y = term_y.strip().lower()

        for risk_phrase in self.all_risk_terms:
            if " " in risk_phrase:
                # If one phrase contains the risk phrase and the other does not
                in_x = risk_phrase in phrase_x
                in_y = risk_phrase in phrase_y
                if in_x != in_y:
                    conflicting.add(risk_phrase)

        if conflicting:
            conflict_str = ", ".join(sorted(conflicting))
            return InterceptionResult(
                is_blocked=True,
                risk_level="HIGH_RISK",
                conflicting_tokens=conflicting,
                reason=f"Concept slippage detected: conflicting high-risk modifiers ({conflict_str})",
            )

        return InterceptionResult(
            is_blocked=False,
            risk_level="SAFE",
            conflicting_tokens=set(),
            reason="Clinical safety check passed.",
        )
