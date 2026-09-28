"""Medical morpheme and combining form matcher for peripheral keyword clustering."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

DEFAULT_ROOTS_FILE = Path(__file__).resolve().parent.parent.parent / "resources" / "medical_roots.json"


class MedicalMorphemeMatcher:
    """Extracts and compares medical Greek/Latin combining forms and roots across terms."""

    def __init__(self, roots_file_path: Optional[Path | str] = None):
        path = Path(roots_file_path) if roots_file_path else DEFAULT_ROOTS_FILE
        self._roots: Dict[str, dict] = {}
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                self._roots = json.load(f)

    @property
    def total_roots(self) -> int:
        """Total number of registered medical combining forms."""
        return len(self._roots)

    def extract_roots(self, term: str) -> Set[str]:
        """Extract all matching registered medical combining forms from a term.

        Guarantees:
            - Length of root >= 4 characters to prevent false-positive explosion.
            - Matches against individual tokens.

        Args:
            term: Medical keyword or multi-word phrase.

        Returns:
            Set of matched root strings.
        """
        clean = term.lower().strip()
        tokens = re.findall(r"[a-z]+", clean)
        matched = set()

        for token in tokens:
            for root in self._roots:
                if len(root) >= 4 and root in token:
                    matched.add(root)

        return matched

    def get_shared_roots(self, term_a: str, term_b: str) -> Set[str]:
        """Find intersection of medical combining forms between two terms."""
        roots_a = self.extract_roots(term_a)
        roots_b = self.extract_roots(term_b)
        return roots_a.intersection(roots_b)

    def has_shared_morpheme(self, term_a: str, term_b: str) -> bool:
        """Check if two terms share at least one registered medical root."""
        return len(self.get_shared_roots(term_a, term_b)) > 0
