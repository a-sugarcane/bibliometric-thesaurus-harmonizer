"""Web of Science (WoS) Plaintext format parser."""

from pathlib import Path
from typing import List, Set
from core.parsers.base_parser import BaseParser, DocumentRecord


class WoSParser(BaseParser):
    """Parser for WoS Plaintext (savedrecs.txt) exports."""

    def parse_string(self, text: str) -> List[DocumentRecord]:
        """Parse WoS plaintext records directly from a string."""
        lines = text.splitlines(keepends=True)
        return self.parse_lines(lines)

    def parse_file(self, file_path: Path | str) -> List[DocumentRecord]:
        """Parse WoS plaintext file, extracting DE, ID, and UT for deduplication.

        Args:
            file_path: Path to WoS savedrecs.txt.

        Returns:
            List of parsed DocumentRecord instances.
        """
        path = Path(file_path)
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()
        return self.parse_lines(lines)

    def parse_lines(self, lines: List[str]) -> List[DocumentRecord]:
        """Parse lines of WoS plaintext records."""
        records: List[DocumentRecord] = []
        current_tag = ""
        current_de: Set[str] = set()
        current_id: Set[str] = set()
        current_ut = ""

        for line in lines:
            line_str = line.rstrip("\r\n")
            if not line_str:
                continue

            tag = line_str[:2].strip()
            val = line_str[3:].strip() if len(line_str) > 2 else ""

            if line_str.startswith("   "):  # Continuation line
                val = line_str.strip()
            elif tag:
                current_tag = tag

            if current_tag == "UT":
                current_ut = val
            elif current_tag == "DE":
                parts = val.split(";")
                for p in parts:
                    clean_p = p.strip()
                    if clean_p:
                        current_de.add(clean_p)
            elif current_tag == "ID":
                parts = val.split(";")
                for p in parts:
                    clean_p = p.strip()
                    if clean_p:
                        current_id.add(clean_p)
            elif current_tag == "ER":
                doc_id = current_ut if current_ut else f"wos_doc_{len(records) + 1}"
                
                # Fallback logic: If DE is empty, fallback to ID
                if current_de:
                    effective = set(current_de)
                    is_fallback = False
                else:
                    effective = set(current_id)
                    is_fallback = bool(current_id)

                combined = set(current_de) | set(current_id)

                records.append(
                    DocumentRecord(
                        doc_id=doc_id,
                        keywords=effective,
                        author_keywords_de=current_de,
                        keywords_plus_id=current_id,
                        effective_keywords=effective,
                        is_de_fallback=is_fallback,
                        combined_keywords=combined,
                        source_database="Web of Science",
                    )
                )
                current_tag = ""
                current_de = set()
                current_id = set()
                current_ut = ""

        return records

