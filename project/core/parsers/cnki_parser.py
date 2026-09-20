"""CNKI (China National Knowledge Infrastructure) export parser."""

import re
from pathlib import Path
from typing import List, Set
from core.parsers.base_parser import BaseParser, DocumentRecord


class CNKIParser(BaseParser):
    """Parser for CNKI Refworks and Custom Text exports."""

    @staticmethod
    def _split_keywords(raw_text: str) -> List[str]:
        """Split Chinese/English keywords using common CNKI delimiters.

        Supports full-width/half-width semicolons, double semicolons, and spaces.
        """
        # Normalize double semicolons and Chinese semicolons to single half-width semicolon
        norm = raw_text.replace("；；", ";").replace(";;", ";").replace("；", ";")
        parts = re.split(r"[;\n\r]+", norm)
        results = []
        for p in parts:
            item = p.strip()
            if item:
                results.append(item)
        return results

    def parse_file(self, file_path: Path | str) -> List[DocumentRecord]:
        """Parse CNKI export file with automatic character encoding detection.

        Args:
            file_path: Path to CNKI exported file.

        Returns:
            List of parsed DocumentRecord instances.
        """
        path = Path(file_path)
        content = ""
        # Detect encoding
        for enc in ["utf-8", "utf-8-sig", "gbk", "gb18030", "latin-1"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        lines = content.splitlines()
        records: List[DocumentRecord] = []

        # Check if CNKI Custom Text format (【来源篇名】 / 【关键词】)
        if any("【来源篇名】" in line or "【关键词】" in line for line in lines[:30]):
            current_id = ""
            current_keywords: Set[str] = set()

            for line in lines:
                line_str = line.strip()
                if line_str.startswith("【来源篇名】"):
                    if current_id or current_keywords:
                        records.append(
                            DocumentRecord(
                                doc_id=current_id or f"cnki_{len(records)+1}",
                                keywords=current_keywords,
                                source_database="CNKI",
                            )
                        )
                        current_keywords = set()
                    current_id = line_str.replace("【来源篇名】", "").strip()
                elif line_str.startswith("【关键词】"):
                    kw_content = line_str.replace("【关键词】", "").strip()
                    for kw in self._split_keywords(kw_content):
                        current_keywords.add(kw)

            if current_id or current_keywords:
                records.append(
                    DocumentRecord(
                        doc_id=current_id or f"cnki_{len(records)+1}",
                        keywords=current_keywords,
                        source_database="CNKI",
                    )
                )
            return records

        # Otherwise assume Refworks format (RT / T1 / K1)
        current_id = ""
        current_keywords = set()

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            tag = line_str[:2].strip()
            val = line_str[3:].strip() if len(line_str) > 2 else ""

            if line_str.startswith("RT ") and (current_id or current_keywords):
                records.append(
                    DocumentRecord(
                        doc_id=current_id or f"cnki_{len(records)+1}",
                        keywords=current_keywords,
                        source_database="CNKI",
                    )
                )
                current_id = ""
                current_keywords = set()

            if tag == "T1":
                current_id = val
            elif tag == "K1":
                for kw in self._split_keywords(val):
                    current_keywords.add(kw)

        if current_id or current_keywords:
            records.append(
                DocumentRecord(
                    doc_id=current_id or f"cnki_{len(records)+1}",
                    keywords=current_keywords,
                    source_database="CNKI",
                )
            )

        return records
