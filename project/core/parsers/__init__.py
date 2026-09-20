"""Data parsing layer supporting WoS, PubMed, CNKI, Scopus, and VOSviewer."""

from core.parsers.base_parser import BaseParser, DocumentRecord
from core.parsers.format_detector import DatabaseFormat, detect_format
from core.parsers.wos_parser import WoSParser
from core.parsers.pubmed_parser import PubMedParser
from core.parsers.cnki_parser import CNKIParser
from core.parsers.scopus_parser import ScopusParser
from core.parsers.vos_parser import VOSParser

__all__ = [
    "BaseParser",
    "DocumentRecord",
    "DatabaseFormat",
    "detect_format",
    "WoSParser",
    "PubMedParser",
    "CNKIParser",
    "ScopusParser",
    "VOSParser",
]
