"""Web of Science (WoS) Plaintext format parser."""

from pathlib import Path
from typing import List, Set
from core.parsers.base_parser import BaseParser, DocumentRecord


class WoSParser(BaseParser):
    """Parser for WoS Plaintext (savedrecs.txt) exports."""

    def parse_file(self, file_path: Path | str) -> List[DocumentRecord]:
        """Parse WoS plaintext file, extracting DE, ID, and UT for deduplication.

        Args:
            file_path: Path to WoS savedrecs.txt.

        Returns:
            List of parsed DocumentRecord instances.
        """
        path = Path(file_path)
        records: List[DocumentRecord] = []

        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()

        current_tag = ""
        current_keywords: Set[str] = set()
        current_ut = ""

        for line in lines:
            line_str = line.rstrip("\r\n")
            if not line_str:
                continue

            # Tag is in the first 2 characters
            tag = line_str[:2].strip()
            val = line_str[3:].strip() if len(line_str) > 2 else ""

            if line_str.startswith("   "):  # Continuation line
                val = line_str.strip()
            elif tag:
                current_tag = tag

            if current_tag == "UT":
                current_ut = val
            elif current_tag in ("DE", "ID"):
                # Semicolon-delimited keywords
                parts = val.split(";")
                for p in parts:
                    clean_p = p.strip()
                    if clean_p:
                        current_keywords.add(clean_p)
            elif current_tag == "ER":
                # End of single document record
                doc_id = current_ut if current_ut else f"wos_doc_{len(records) + 1}"
                records.append(
                    DocumentRecord(
                        doc_id=doc_id,
                        keywords=current_keywords,
                        source_database="Web of Science",
                    )
                )
                current_tag = ""
                current_keywords = set()
                current_ut = ""

        return records
