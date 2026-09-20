"""Abstract base parser and unified document record model."""

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set


@dataclass
class DocumentRecord:
    """Represents keywords extracted from a single bibliographic document."""

    doc_id: str
    keywords: Set[str] = field(default_factory=set)
    source_database: str = "Unknown"


class BaseParser(ABC):
    """Abstract base class for all bibliographic database parsers."""

    @abstractmethod
    def parse_file(self, file_path: Path | str) -> List[DocumentRecord]:
        """Parse raw bibliographic export file into unified DocumentRecord list.

        Args:
            file_path: Path to the raw export file.

        Returns:
            List of DocumentRecord instances.
        """
        pass

    @staticmethod
    def compute_frequencies(records: List[DocumentRecord]) -> Dict[str, int]:
        """Compute document-level deduplicated occurrence counts for all keywords.

        Args:
            records: List of bibliographic document records.

        Returns:
            Dictionary mapping normalized keyword to document occurrence count.
        """
        counter: Counter[str] = Counter()
        for doc in records:
            # Document-level deduplication: each term counts at most once per document
            for kw in doc.keywords:
                clean_kw = kw.strip().lower()
                if clean_kw:
                    counter[clean_kw] += 1
        return dict(counter)
