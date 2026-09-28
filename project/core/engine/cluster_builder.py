"""Target-Centric Grouping Engine: clusters corpus keywords into canonical target clusters."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from config import TIER_1_SAFE, TIER_2_RECOMMENDED, TIER_3_HIGH_RISK
from core.engine.canonicalizer import Canonicalizer
from core.engine.tier_classifier import HarmonizationRule
from core.interceptor.risk_rules import ClinicalRiskInterceptor
from core.normalizer.hyphen_resolver import HyphenResolver
from core.normalizer.lemmatizer import HeadNounLemmatizer
from core.normalizer.morpheme_matcher import MedicalMorphemeMatcher
from core.normalizer.syntax_cleaner import SyntaxCleaner
from core.ontology.mesh_lookup import MeSHLookup


@dataclass
class TargetCluster:
    """Represents a canonical target keyword and all candidate merging variants."""

    target_term: str
    target_raw_freq: int
    variants: List[HarmonizationRule] = field(default_factory=list)

    @property
    def variant_count(self) -> int:
        """Total number of candidate variants under this target."""
        return len(self.variants)

    @property
    def selected_variant_count(self) -> int:
        """Number of variants currently selected by the user for merging."""
        return sum(1 for v in self.variants if v.selected_for_export)

    @property
    def combined_freq(self) -> int:
        """Dynamically calculated combined frequency (target + selected variants)."""
        return self.target_raw_freq + sum(
            v.raw_frequency for v in self.variants if v.selected_for_export
        )

    @property
    def total_potential_freq(self) -> int:
        """Theoretical maximum frequency if all variants are merged."""
        return self.target_raw_freq + sum(v.raw_frequency for v in self.variants)

    @property
    def has_blocked_variants(self) -> bool:
        """Indicates whether this cluster contains Tier 3 intercepted items."""
        return any(v.tier == TIER_3_HIGH_RISK for v in self.variants)


class TargetClusterBuilder:
    """Clusters corpus terms into TargetClusters using morphological, acronym, MeSH, and morpheme logic."""

    def __init__(
        self,
        enable_mesh: bool = True,
        enable_interceptor: bool = True,
        enable_morphemes: bool = True,
        mesh_lookup: Optional[MeSHLookup] = None,
        interceptor: Optional[ClinicalRiskInterceptor] = None,
        morpheme_matcher: Optional[MedicalMorphemeMatcher] = None,
    ):
        self.lemmatizer = HeadNounLemmatizer()
        self.mesh_lookup = mesh_lookup if (mesh_lookup and enable_mesh) else (MeSHLookup() if enable_mesh else None)
        self.interceptor = interceptor if (interceptor and enable_interceptor) else (ClinicalRiskInterceptor() if enable_interceptor else None)
        self.morpheme_matcher = morpheme_matcher if (morpheme_matcher and enable_morphemes) else (MedicalMorphemeMatcher() if enable_morphemes else None)

    @staticmethod
    def is_acronym_candidate(term: str) -> bool:
        """Check if term matches short acronym pattern (<= 6 chars, alphanumeric, no spaces)."""
        clean = term.strip()
        return 1 <= len(clean) <= 6 and " " not in clean and clean.isalnum()

    def build_clusters(self, freqs: Dict[str, int]) -> List[TargetCluster]:
        """Group corpus terms into TargetClusters.

        Guarantees:
            1. No self-merging: for all v in cluster.variants, v.raw_term != cluster.target_term.
            2. Each term belongs to at most one cluster as a variant.
            3. Full phrase preferred over acronyms for target name.
            4. Highest corpus frequency within equivalence group elects the canonical target.

        Args:
            freqs: Dictionary of term to raw occurrence count.

        Returns:
            List of TargetCluster objects sorted by combined frequency descending.
        """
        # Step 1: Pre-process each term
        term_props = {}
        for raw_term in freqs:
            decoupled = SyntaxCleaner.decouple_parentheses(raw_term)
            base_term = decoupled.full_phrase
            is_acr = (
                decoupled.is_acronym_valid
                or Canonicalizer.is_acronym(raw_term)
                or self.is_acronym_candidate(raw_term)
            )

            hyphen_resolved = HyphenResolver.resolve_hyphen_term(
                base_term,
                corpus_frequencies=freqs,
                mesh_terms=self.mesh_lookup.all_indexed_terms if self.mesh_lookup else None,
            )

            lemmatized = self.lemmatizer.lemmatize_phrase(hyphen_resolved)

            mesh_res = None
            if self.mesh_lookup:
                mesh_res = self.mesh_lookup.lookup(lemmatized)
                if not mesh_res.matched:
                    mesh_res = self.mesh_lookup.lookup(base_term)

            term_props[raw_term] = {
                "base_term": base_term,
                "is_acronym": is_acr,
                "hyphen_resolved": hyphen_resolved,
                "lemmatized": lemmatized,
                "mesh_matched": mesh_res.matched if mesh_res else False,
                "descriptor_id": mesh_res.descriptor_id if mesh_res else None,
                "concept_id": mesh_res.concept_id if mesh_res else None,
                "mesh_canonical": mesh_res.canonical_name if mesh_res else None,
            }

        # Step 2: Build candidate equivalence edges (source, target_candidate, rule_source, is_acronym_flag)
        # We use a directed mapping: variant -> target
        variant_to_target: Dict[str, Tuple[str, str, bool]] = {}

        # 2.1 Morphological & Hyphen reduction
        for raw_term, p in term_props.items():
            if p["is_acronym"]:
                continue

            # Check hyphen resolution in corpus
            hyphen_target = p["hyphen_resolved"]
            if hyphen_target != raw_term and hyphen_target in freqs:
                variant_to_target[raw_term] = (hyphen_target, "Hyphen Resolution", False)
                continue

            # Check lemmatization in corpus
            lemma_target = p["lemmatized"]
            if lemma_target != raw_term and lemma_target in freqs:
                variant_to_target[raw_term] = (lemma_target, "Lemmatization", False)
                continue

        # 2.2 Acronym alignment
        # Map acronyms to their corresponding full phrases in the corpus
        for raw_term, p in term_props.items():
            if not p["is_acronym"]:
                continue

            # Find matching full phrase in corpus
            best_full = None
            best_freq = -1
            for other_term, op in term_props.items():
                if op["is_acronym"] or other_term == raw_term:
                    continue
                if SyntaxCleaner.check_acronym_alignment(raw_term, other_term):
                    other_freq = freqs.get(other_term, 0)
                    if other_freq > best_freq:
                        best_freq = other_freq
                        best_full = other_term

            if best_full:
                variant_to_target[raw_term] = (best_full, "Acronym Decoupling", True)

        # 2.3 MeSH Semantic Alignment
        if self.mesh_lookup:
            # Group by DescriptorUI / ConceptUI
            desc_to_terms = defaultdict(list)
            for raw_term, p in term_props.items():
                if p["descriptor_id"] and not p["is_acronym"]:
                    desc_to_terms[p["descriptor_id"]].append(raw_term)

            for desc_id, terms in desc_to_terms.items():
                if len(terms) <= 1:
                    continue

                # Find dominant term in corpus for this Descriptor
                dominant_term = max(terms, key=lambda t: freqs.get(t, 0))

                for t in terms:
                    if t == dominant_term or t in variant_to_target:
                        continue

                    # Concept level vs Descriptor level
                    p_t = term_props[t]
                    p_dom = term_props[dominant_term]

                    same_concept = (
                        p_t["concept_id"]
                        and p_dom["concept_id"]
                        and p_t["concept_id"] == p_dom["concept_id"]
                    )

                    # Inspect pair with risk interceptor before establishing MeSH edge
                    is_acr = p_t["is_acronym"] or Canonicalizer.is_acronym(t)
                    if self.interceptor:
                        inter_check = self.interceptor.inspect_pair(t, dominant_term, is_acronym_equivalent=is_acr)
                    else:
                        from core.interceptor.risk_rules import InterceptionResult
                        inter_check = InterceptionResult(is_blocked=False, risk_level="SAFE")

                    rule_label = (
                        f"MeSH Concept ({p_t['concept_id']})"
                        if same_concept
                        else f"MeSH Descriptor ({desc_id})"
                    )
                    variant_to_target[t] = (dominant_term, rule_label, is_acr)

        # Step 3: Resolve transitive paths (A -> B -> C => A -> C) and detect loops
        final_mapping: Dict[str, Tuple[str, str, bool]] = {}
        for raw, (target, rule_src, is_acr) in variant_to_target.items():
            curr = target
            visited = {raw}
            while curr in variant_to_target and curr not in visited:
                visited.add(curr)
                curr, _, _ = variant_to_target[curr]

            if curr != raw:
                final_mapping[raw] = (curr, rule_src, is_acr)

        # Step 4: Build TargetClusters
        # Find all unique targets and all unmerged independent terms
        all_targets = set()
        for raw, (target, _, _) in final_mapping.items():
            all_targets.add(target)

        # Ensure all terms not mapped to another target are recognized as independent targets
        for term in freqs:
            if term not in final_mapping:
                all_targets.add(term)

        # Initialize clusters
        clusters: Dict[str, TargetCluster] = {
            t: TargetCluster(target_term=t, target_raw_freq=freqs.get(t, 0), variants=[])
            for t in all_targets
        }

        # Populate variants
        for raw, (target, rule_src, is_acr) in final_mapping.items():
            # STRICT CHECK: NEVER self-merge
            if raw.strip().lower() == target.strip().lower():
                continue

            # Clinical Safety Check
            if self.interceptor:
                interception = self.interceptor.inspect_pair(raw, target, is_acronym_equivalent=is_acr)
            else:
                from core.interceptor.risk_rules import InterceptionResult
                interception = InterceptionResult(is_blocked=False, risk_level="SAFE")

            if interception.is_blocked:
                tier = TIER_3_HIGH_RISK
                safety = f"Blocked: {interception.reason}"
                selected = False
            else:
                if any(k in rule_src for k in ("Lemmatization", "Hyphen", "Syntax", "Concept")):
                    tier = TIER_1_SAFE
                else:
                    tier = TIER_2_RECOMMENDED
                safety = "Passed"
                selected = True

            rule = HarmonizationRule(
                raw_term=raw,
                target_term=target,
                tier=tier,
                rule_source=rule_src,
                clinical_safety_check=safety,
                raw_frequency=freqs.get(raw, 1),
                selected_for_export=selected,
            )

            if target in clusters:
                clusters[target].variants.append(rule)

        # Step 4.5: Medical Morpheme Peripheral Candidate Matching (Tier 3 Exploratory)
        if self.morpheme_matcher:
            # Active candidate targets (clusters with existing variants or frequency >= 2)
            active_targets = sorted(
                [c for c in clusters.values() if c.variant_count > 0 or c.target_raw_freq >= 2],
                key=lambda c: (c.combined_freq, c.target_raw_freq),
                reverse=True,
            )

            already_variant_keys = set(final_mapping.keys())

            for target_cluster in active_targets:
                target_name = target_cluster.target_term
                existing_variant_raws = {v.raw_term.lower() for v in target_cluster.variants}
                existing_variant_raws.add(target_name.lower())

                for term, freq in freqs.items():
                    term_lower = term.lower()
                    if term_lower in existing_variant_raws or term in already_variant_keys:
                        continue

                    # Prevent absorbing another active target that already has its own candidate variants
                    if term in clusters and clusters[term].variant_count > 0:
                        continue

                    shared_roots = self.morpheme_matcher.get_shared_roots(target_name, term)
                    if shared_roots:
                        primary_root = sorted(list(shared_roots))[0]

                        # Verify with clinical risk interceptor
                        if self.interceptor:
                            inter_check = self.interceptor.inspect_pair(term, target_name)
                            safety = (
                                f"Blocked: {inter_check.reason}"
                                if inter_check.is_blocked
                                else f"Peripheral Morpheme: shared root '{primary_root}' (Manual confirmation required)"
                            )
                        else:
                            safety = f"Peripheral Morpheme: shared root '{primary_root}' (Manual confirmation required)"

                        peripheral_rule = HarmonizationRule(
                            raw_term=term,
                            target_term=target_name,
                            tier=TIER_3_HIGH_RISK,
                            rule_source=f"Medical Morpheme ({primary_root})",
                            clinical_safety_check=safety,
                            raw_frequency=freq,
                            selected_for_export=False,  # STRICT: Default unselected!
                        )
                        target_cluster.variants.append(peripheral_rule)
                        already_variant_keys.add(term)
                        # Remove standalone empty cluster for this term to avoid duplicate UI clutter
                        clusters.pop(term, None)

        # Step 5: Sort variants and clusters
        cluster_list = list(clusters.values())
        for c in cluster_list:
            c.variants.sort(key=lambda v: v.raw_frequency, reverse=True)

        # Sort clusters by combined frequency descending
        cluster_list.sort(key=lambda c: (c.combined_freq, c.variant_count), reverse=True)

        return cluster_list
