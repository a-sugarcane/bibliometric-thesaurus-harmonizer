"""VOSviewer Terms TSV file parser."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from core.parsers.base_parser import BaseParser, DocumentRecord


@dataclass
class VOSTermRecord:
    """Represents a term record from VOSviewer terms.txt."""

    term: str
    occurrences: int
    total_link_strength: float = 0.0


class VOSParser(BaseParser):
    """Parser for VOSviewer terms.txt / map.txt exports."""

    def parse_file(self, file_path: Path | str) -> List[DocumentRecord]:
        """Convert VOS terms into pseudo DocumentRecords for pipeline compatibility."""
        path = Path(file_path)
        term_records = self.parse_terms(path)
        records: List[DocumentRecord] = []
        for idx, tr in enumerate(term_records):
            records.append(
                DocumentRecord(
                    doc_id=f"vos_term_{idx+1}",
                    keywords={tr.term},
                    source_database="VOSviewer",
                )
            )
        return records

    def parse_terms(self, file_path: Path | str) -> List[VOSTermRecord]:
        """Parse raw VOSviewer TSV file into VOSTermRecord list."""
        path = Path(file_path)
        records: List[VOSTermRecord] = []

        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            for line_idx, line in enumerate(f):
                line_str = line.strip()
                if not line_str:
                    continue

                parts = line_str.split("\t")
                # Skip header if present
                if line_idx == 0 and ("term" in parts[0].lower() or "label" in parts[0].lower()):
                    continue

                term = parts[0].strip()
                occurrences = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 1
                tls = float(parts[2].strip()) if len(parts) > 2 else 0.0

                records.append(VOSTermRecord(term=term, occurrences=occurrences, total_link_strength=tls))

        return records

    def get_term_frequencies(self, file_path: Path | str) -> Dict[str, int]:
        """Extract dictionary mapping term string to its precomputed occurrence count."""
        records = self.parse_terms(file_path)
        return {r.term.lower(): r.occurrences for r in records}
