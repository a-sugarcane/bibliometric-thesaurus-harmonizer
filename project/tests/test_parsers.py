"""Unit tests for multi-database parsers and format detection."""

import tempfile
import unittest
from pathlib import Path
from core.parsers.format_detector import DatabaseFormat, detect_format
from core.parsers.wos_parser import WoSParser
from core.parsers.pubmed_parser import PubMedParser
from core.parsers.cnki_parser import CNKIParser
from core.parsers.base_parser import BaseParser, DocumentRecord


class TestParsers(unittest.TestCase):

    def test_wos_parser_and_deduplication(self):
        sample_wos = (
            "PT J\n"
            "TI Sample Study\n"
            "DE prostate cancer; quality of life; prostate cancer\n"
            "ID neoplasms; depression\n"
            "UT WOS:0001234567\n"
            "ER\n"
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tmp:
            tmp.write(sample_wos)
            tmp_path = Path(tmp.name)

        self.assertEqual(detect_format(tmp_path), DatabaseFormat.WOS_PLAINTEXT)

        records = WoSParser().parse_file(tmp_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].doc_id, "WOS:0001234567")
        self.assertIn("prostate cancer", records[0].keywords)
        self.assertIn("quality of life", records[0].keywords)

        freqs = BaseParser.compute_frequencies(records)
        # Even though "prostate cancer" appeared twice in DE, document-level count must be exactly 1
        self.assertEqual(freqs["prostate cancer"], 1)

    def test_wos_parser_de_fallback(self):
        sample_data = (
            "PT J\n"
            "UT WOS:0001\n"
            "DE prostate cancer; depression\n"
            "ID quality of life\n"
            "ER\n"
            "PT J\n"
            "UT WOS:0002\n"
            "ID castration-resistant prostate cancer; docetaxel\n"
            "ER\n"
        )
        parser = WoSParser()
        records = parser.parse_string(sample_data)
        self.assertEqual(len(records), 2)
        # Record 1 has DE
        self.assertFalse(records[0].is_de_fallback)
        self.assertIn("prostate cancer", records[0].effective_keywords)
        self.assertIn("depression", records[0].author_keywords_de)
        self.assertIn("quality of life", records[0].keywords_plus_id)
        # Record 2 has empty DE -> fallback to ID
        self.assertTrue(records[1].is_de_fallback)
        self.assertEqual(len(records[1].author_keywords_de), 0)
        self.assertIn("castration-resistant prostate cancer", records[1].effective_keywords)
        self.assertIn("docetaxel", records[1].effective_keywords)


    def test_pubmed_parser_and_subheading_clean(self):
        sample_pm = (
            "PMID- 99887766\n"
            "TI  - Trial on oncology\n"
            "OT  - ADT\n"
            "MH  - *Prostatic Neoplasms/therapy\n"
            "MH  - Antineoplastic Agents/therapeutic use\n"
            "\n"
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tmp:
            tmp.write(sample_pm)
            tmp_path = Path(tmp.name)

        self.assertEqual(detect_format(tmp_path), DatabaseFormat.PUBMED_MEDLINE)

        records = PubMedParser().parse_file(tmp_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].doc_id, "PMID:99887766")
        self.assertIn("Prostatic Neoplasms", records[0].keywords)
        self.assertIn("Antineoplastic Agents", records[0].keywords)
        self.assertIn("ADT", records[0].keywords)

    def test_cnki_parser(self):
        sample_cnki = (
            "RT Journal\n"
            "T1 前列腺癌患者生活质量研究\n"
            "K1 前列腺肿瘤; 生活质量；；抑郁情绪; 心理护理\n"
            "\n"
        )
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tmp:
            tmp.write(sample_cnki)
            tmp_path = Path(tmp.name)

        self.assertEqual(detect_format(tmp_path), DatabaseFormat.CNKI_REFWORKS)

        records = CNKIParser().parse_file(tmp_path)
        self.assertEqual(len(records), 1)
        self.assertIn("前列腺肿瘤", records[0].keywords)
        self.assertIn("生活质量", records[0].keywords)
        self.assertIn("抑郁情绪", records[0].keywords)


if __name__ == "__main__":
    unittest.main()
