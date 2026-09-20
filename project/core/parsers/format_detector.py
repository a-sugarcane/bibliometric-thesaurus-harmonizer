"""Heuristic format detector for bibliographic database export files."""

from enum import Enum
from pathlib import Path


class DatabaseFormat(str, Enum):
    """Supported bibliographic database export formats."""

    WOS_PLAINTEXT = "wos_plaintext"
    PUBMED_MEDLINE = "pubmed_medline"
    CNKI_REFWORKS = "cnki_refworks"
    CNKI_TEXT = "cnki_text"
    SCOPUS_CSV = "scopus_csv"
    VOS_TSV = "vos_tsv"
    UNKNOWN = "unknown"


def detect_format(file_path: Path | str) -> DatabaseFormat:
    """Detect database format by sampling the first 50 lines of an export file.

    Args:
        file_path: Path to the input export file.

    Returns:
        DatabaseFormat enum indicating the detected database type.
    """
    path = Path(file_path)
    if not path.is_file():
        return DatabaseFormat.UNKNOWN

    sample_lines: list[str] = []
    # Try reading with utf-8 first, fallback to gbk for Chinese exports
    for enc in ["utf-8", "utf-8-sig", "gbk", "gb18030", "latin-1"]:
        try:
            with open(path, "r", encoding=enc, errors="ignore") as f:
                for _ in range(60):
                    line = f.readline()
                    if not line:
                        break
                    sample_lines.append(line)
            break
        except Exception:
            continue

    if not sample_lines:
        return DatabaseFormat.UNKNOWN

    sample_text = "".join(sample_lines)

    # 1. PubMed MEDLINE / NBIB check
    if any(line.startswith("PMID-") for line in sample_lines) or (
        "MH  -" in sample_text and "TI  -" in sample_text
    ):
        return DatabaseFormat.PUBMED_MEDLINE

    # 2. WoS Plaintext check
    if any(line.startswith("PT ") for line in sample_lines) or (
        "ER\n" in sample_text and ("DE " in sample_text or "ID " in sample_text)
    ):
        return DatabaseFormat.WOS_PLAINTEXT

    # 3. CNKI checks
    if "【来源篇名】" in sample_text or "【关键词】" in sample_text:
        return DatabaseFormat.CNKI_TEXT
    if "RT Journal" in sample_text or "RT Book" in sample_text or ("K1 " in sample_text and "A1 " in sample_text):
        return DatabaseFormat.CNKI_REFWORKS

    # 4. Scopus CSV check
    if (
        "Author Keywords" in sample_lines[0]
        or "Index Keywords" in sample_lines[0]
        or "EID" in sample_lines[0]
    ):
        return DatabaseFormat.SCOPUS_CSV

    # 5. VOSviewer TSV check
    if sample_lines:
        first_line = sample_lines[0].strip().split("\t")
        if len(first_line) in (2, 3) and (
            "occurrences" in sample_lines[0].lower() or "label" in sample_lines[0].lower()
        ):
            return DatabaseFormat.VOS_TSV

    return DatabaseFormat.UNKNOWN
