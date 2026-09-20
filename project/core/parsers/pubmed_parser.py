"""PubMed (MEDLINE / NBIB) format parser with MeSH subheading stripping."""

import re
from pathlib import Path
from typing import List, Set
from core.parsers.base_parser import BaseParser, DocumentRecord


class PubMedParser(BaseParser):
    """Parser for PubMed MEDLINE / NBIB plain text exports."""

    @staticmethod
    def clean_mesh_term(raw_term: str) -> str:
        """Strip major topic asterisks and subheading qualifiers from MeSH terms.

        Example:
            'Prostatic Neoplasms/*therapy' -> 'Prostatic Neoplasms'
            '*Depressive Disorder, Major/drug therapy' -> 'Depressive Disorder, Major'

        Args:
            raw_term: The uncleaned MeSH descriptor line.

        Returns:
            Cleaned base descriptor string.
        """
        # Remove major topic asterisk
        term = raw_term.replace("*", "").strip()
        # Remove subheadings starting with slash
        term = re.sub(r"/[^,;]+", "", term).strip()
        return term

    def parse_file(self, file_path: Path | str) -> List[DocumentRecord]:
        """Parse PubMed MEDLINE export file.

        Args:
            file_path: Path to PubMed .nbib or .txt file.

        Returns:
            List of parsed DocumentRecord instances.
        """
        path = Path(file_path)
        records: List[DocumentRecord] = []

        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = f.readlines()

        current_tag = ""
        current_keywords: Set[str] = set()
        current_pmid = ""

        for line in lines:
            line_str = line.rstrip("\r\n")

            # Check for standard 4-char tag with hyphen (e.g. 'PMID- 12345678', 'MH  - Neoplasms')
            if len(line_str) >= 6 and line_str[4] == "-" and line_str[5] == " ":
                current_tag = line_str[:4].strip()
                val = line_str[6:].strip()
            elif line_str.startswith("      "):  # Continuation line
                val = line_str.strip()
            else:
                # Blank line usually signals record separator in PubMed
                if not line_str.strip() and (current_pmid or current_keywords):
                    doc_id = f"PMID:{current_pmid}" if current_pmid else f"pm_doc_{len(records) + 1}"
                    records.append(
                        DocumentRecord(
                            doc_id=doc_id,
                            keywords=current_keywords,
                            source_database="PubMed",
                        )
                    )
                    current_tag = ""
                    current_keywords = set()
                    current_pmid = ""
                continue

            if current_tag == "PMID":
                current_pmid = val
            elif current_tag == "OT":
                # Author Keyword (Other Term)
                clean_ot = val.strip()
                if clean_ot:
                    current_keywords.add(clean_ot)
            elif current_tag == "MH":
                # MeSH Term with subheadings
                clean_mh = self.clean_mesh_term(val)
                if clean_mh:
                    current_keywords.add(clean_mh)

        # Handle last record if not terminated by empty line
        if current_pmid or current_keywords:
            doc_id = f"PMID:{current_pmid}" if current_pmid else f"pm_doc_{len(records) + 1}"
            records.append(
                DocumentRecord(
                    doc_id=doc_id,
                    keywords=current_keywords,
                    source_database="PubMed",
                )
            )

        return records
