"""Unit tests for normalizer: syntax cleaner, lemmatizer, and hyphen resolver."""

import unittest
from core.normalizer.syntax_cleaner import SyntaxCleaner
from core.normalizer.lemmatizer import HeadNounLemmatizer
from core.normalizer.hyphen_resolver import HyphenResolver


class TestNormalizer(unittest.TestCase):

    def test_syntax_cleaner_parenthesis(self):
        res1 = SyntaxCleaner.decouple_parentheses("androgen deprivation therapy (adt)")
        self.assertEqual(res1.full_phrase, "androgen deprivation therapy")
        self.assertEqual(res1.acronym, "adt")
        self.assertTrue(res1.is_acronym_valid)

        res2 = SyntaxCleaner.decouple_parentheses("QoL (quality of life)")
        self.assertEqual(res2.full_phrase, "quality of life")
        self.assertEqual(res2.acronym, "QoL")
        self.assertTrue(res2.is_acronym_valid)

    def test_head_noun_lemmatizer(self):
        lem = HeadNounLemmatizer()

        # Regular plural
        self.assertEqual(lem.lemmatize_phrase("prostate cancers"), "prostate cancer")
        self.assertEqual(lem.lemmatize_phrase("bone metastases"), "bone metastasis")

        # Only final head word is modified
        self.assertEqual(lem.lemmatize_phrase("depressive symptoms"), "depressive symptom")

        # Protected terms MUST NOT be modified
        self.assertEqual(lem.lemmatize_phrase("psychological distress"), "psychological distress")
        self.assertEqual(lem.lemmatize_phrase("cancer genomics"), "cancer genomics")
        self.assertEqual(lem.lemmatize_phrase("clinical diagnosis"), "clinical diagnosis")

    def test_hyphen_resolver(self):
        res = HyphenResolver.resolve_hyphen_term("quality-of-life")
        self.assertEqual(res, "quality of life")

        # Corpus collision
        freqs = {"co-occurrence": 5, "cooccurrence": 20, "co occurrence": 2}
        res_co = HyphenResolver.resolve_hyphen_term("co-occurrence", corpus_frequencies=freqs)
        self.assertEqual(res_co, "cooccurrence")


if __name__ == "__main__":
    unittest.main()
