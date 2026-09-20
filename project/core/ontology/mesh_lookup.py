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
    canonical_name: Optional[str] = None
    query_term: str = ""


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

    @property
    def all_indexed_terms(self) -> Set[str]:
        """Return all indexed term strings for fast set-membership checks."""
        return set(self._index.keys())

    def lookup(self, term: str) -> MeSHMatchResult:
        """Query term in MeSH inverted index.

        Args:
            term: Cleaned keyword string.

        Returns:
            MeSHMatchResult with descriptor ID and canonical name if matched.
        """
        key = term.strip().lower()
        if key in self._index:
            entry = self._index[key]
            return MeSHMatchResult(
                matched=True,
                descriptor_id=entry.get("descriptor_id"),
                canonical_name=entry.get("canonical_name"),
                query_term=term,
            )
        return MeSHMatchResult(matched=False, query_term=term)
