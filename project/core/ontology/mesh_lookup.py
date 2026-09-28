"""In-memory O(1) hash lookup engine for pre-compiled MeSH index."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set
from config import MESH_INDEX_FILE
from core.ontology.mesh_compiler import MeSHCompiler


@dataclass
class MeSHMatchResult:
    """Result of MeSH inverted index query."""

    matched: bool
    descriptor_id: Optional[str] = None
    concept_id: Optional[str] = None
    canonical_name: Optional[str] = None
    query_term: str = ""


@dataclass
class SynonymRelationResult:
    """Result of Concept-level synonym comparison between two terms."""

    is_synonym: bool
    tier: str
    concept_id: Optional[str] = None
    descriptor_id: Optional[str] = None
    reason: str = ""


class MeSHLookup:
    """Provides high-throughput O(1) in-memory lookup for MeSH concepts."""

    def __init__(self, index_file_path: Optional[Path | str] = None):
        """Initialize lookup table, generating seed index if missing."""
        path = Path(index_file_path) if index_file_path else MESH_INDEX_FILE
        if not path.is_file():
            # Automatically bootstrap seed index for instant functionality
            MeSHCompiler.generate_seed_index(path)

        with open(path, "r", encoding="utf-8") as f:
            self._index: Dict[str, Dict[str, str]] = json.load(f)
        self._all_terms_set: Set[str] = set(self._index.keys())

    @property
    def all_indexed_terms(self) -> Set[str]:
        """Return all indexed term strings for fast set-membership checks."""
        return self._all_terms_set

    def lookup(self, term: str) -> MeSHMatchResult:
        """Query term in MeSH inverted index.

        Args:
            term: Cleaned keyword string.

        Returns:
            MeSHMatchResult with descriptor ID, concept ID, and canonical name if matched.
        """
        key = term.strip().lower()
        if key in self._index:
            entry = self._index[key]
            return MeSHMatchResult(
                matched=True,
                descriptor_id=entry.get("descriptor_id"),
                concept_id=entry.get("concept_id"),
                canonical_name=entry.get("canonical_name"),
                query_term=term,
            )
        return MeSHMatchResult(matched=False, query_term=term)

    def check_synonym_relation(self, term1: str, term2: str) -> SynonymRelationResult:
        """Evaluate if two terms are MeSH synonyms at the ConceptUI level.

        Tier 1: Both terms share the exact same ConceptUI (True Synonyms).
        Tier 2: Both terms belong to the same DescriptorUI but different ConceptUIs (Broad/Narrow relation).
        Tier 3: Different Descriptors or terms not indexed in MeSH.
        """
        res1 = self.lookup(term1)
        res2 = self.lookup(term2)

        if not res1.matched or not res2.matched:
            return SynonymRelationResult(
                is_synonym=False,
                tier="Tier 3",
                reason="One or both terms not found in MeSH index",
            )

        # Same ConceptUI -> Tier 1 True Synonym
        if res1.concept_id and res2.concept_id and res1.concept_id == res2.concept_id:
            return SynonymRelationResult(
                is_synonym=True,
                tier="Tier 1",
                concept_id=res1.concept_id,
                descriptor_id=res1.descriptor_id,
                reason=f"True synonyms under MeSH Concept {res1.concept_id}",
            )

        # Same DescriptorUI but different ConceptUI -> Tier 2 (Broad/Narrow)
        if res1.descriptor_id and res2.descriptor_id and res1.descriptor_id == res2.descriptor_id:
            return SynonymRelationResult(
                is_synonym=False,
                tier="Tier 2",
                concept_id=None,
                descriptor_id=res1.descriptor_id,
                reason=f"Related concepts under MeSH Descriptor {res1.descriptor_id} (Broad/Narrow relation)",
            )

        return SynonymRelationResult(
            is_synonym=False,
            tier="Tier 3",
            reason="Distinct MeSH descriptors",
        )

