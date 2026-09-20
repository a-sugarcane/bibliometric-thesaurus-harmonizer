"""Scopus CSV export format parser."""

import csv
from pathlib import Path
from typing import List, Set
from core.parsers.base_parser import BaseParser, DocumentRecord


class ScopusParser(BaseParser):
    """Parser for Scopus CSV export files."""

    def parse_file(self, file_path: Path | str) -> List[DocumentRecord]:
        """Parse Scopus CSV export.

        Args:
            file_path: Path to Scopus CSV file.

        Returns:
            List of parsed DocumentRecord instances.
        """
        path = Path(file_path)
        records: List[DocumentRecord] = []

        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                doc_id = row.get("EID") or row.get("DOI") or f"scopus_{idx + 1}"
                keywords: Set[str] = set()

                author_kw = row.get("Author Keywords", "")
                if author_kw:
                    for kw in author_kw.split(";"):
                        clean_kw = kw.strip()
                        if clean_kw:
                            keywords.add(clean_kw)

                index_kw = row.get("Index Keywords", "")
                if index_kw:
                    for kw in index_kw.split(";"):
                        clean_kw = kw.strip()
                        if clean_kw:
                            keywords.add(clean_kw)

                records.append(
                    DocumentRecord(
                        doc_id=doc_id,
                        keywords=keywords,
                        source_database="Scopus",
                    )
                )

        return records
