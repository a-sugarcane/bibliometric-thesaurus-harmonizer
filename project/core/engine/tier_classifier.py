"""Confidence tier classification for thesaurus harmonization candidates."""

from dataclasses import dataclass
from typing import Optional
from config import TIER_1_SAFE, TIER_2_RECOMMENDED, TIER_3_HIGH_RISK
from core.interceptor.risk_rules import InterceptionResult


@dataclass
class HarmonizationRule:
    """Represents a validated synonym harmonization mapping."""

    raw_term: str
    target_term: str
    tier: str  # TIER_1_SAFE, TIER_2_RECOMMENDED, or TIER_3_HIGH_RISK
    rule_source: str  # e.g., "Lemmatization", "MeSH (D011471)", "Acronym Decoupling"
    clinical_safety_check: str  # "Passed" or "Blocked: High Risk" or "Manual Confirmed"
    raw_frequency: int = 1
    selected_for_export: bool = True


class TierClassifier:
    """Classifies proposed synonym pairs into appropriate confidence tiers."""

    @staticmethod
    def classify(
        raw_term: str,
        target_term: str,
        rule_source: str,
        interception: InterceptionResult,
        raw_frequency: int = 1,
    ) -> HarmonizationRule:
        """Assign confidence tier based on interception outcome and rule category.

        Args:
            raw_term: The original uncleaned keyword.
            target_term: Proposed canonical keyword.
            rule_source: Mechanism proposing the merge.
            interception: Output from ClinicalRiskInterceptor.
            raw_frequency: Frequency in the dataset.

        Returns:
            HarmonizationRule object with assigned tier.
        """
        # Tier 3: Blocked by risk interceptor
        if interception.is_blocked:
            return HarmonizationRule(
                raw_term=raw_term,
                target_term=target_term,
                tier=TIER_3_HIGH_RISK,
                rule_source=rule_source,
                clinical_safety_check=f"Blocked: {interception.reason}",
                raw_frequency=raw_frequency,
                selected_for_export=False,  # High risk is unselected by default
            )

        # Tier 1: Syntax, Lemmatization, Hyphen collision
        if any(src in rule_source for src in ("Lemmatization", "Hyphen", "Punctuation", "Syntax")):
            return HarmonizationRule(
                raw_term=raw_term,
                target_term=target_term,
                tier=TIER_1_SAFE,
                rule_source=rule_source,
                clinical_safety_check="Passed",
                raw_frequency=raw_frequency,
                selected_for_export=True,
            )

        # Tier 2: MeSH semantic alignment or Acronym mapping
        return HarmonizationRule(
            raw_term=raw_term,
            target_term=target_term,
            tier=TIER_2_RECOMMENDED,
            rule_source=rule_source,
            clinical_safety_check="Passed",
            raw_frequency=raw_frequency,
            selected_for_export=True,
        )
