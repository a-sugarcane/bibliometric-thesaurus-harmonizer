"""Unit tests for MeSH lookup and canonicalization."""

import unittest
from core.ontology.mesh_lookup import MeSHLookup
from core.engine.canonicalizer import Canonicalizer


class TestOntology(unittest.TestCase):

    def test_mesh_lookup_seed(self):
        lookup = MeSHLookup()

        # Query Entry Term
        res1 = lookup.lookup("prostate cancer")
        self.assertTrue(res1.matched)
        self.assertEqual(res1.descriptor_id, "D011471")
        self.assertEqual(res1.canonical_name, "Prostatic Neoplasms")

        # Query Official Descriptor / Entry Term
        res2 = lookup.lookup("androgen antagonists")
        self.assertTrue(res2.matched)
        self.assertEqual(res2.descriptor_id, "D000726")

        # Unknown term
        res3 = lookup.lookup("non_existent_medical_word_xyz")
        self.assertFalse(res3.matched)

    def test_mesh_concept_level_synonym(self):
        lookup = MeSHLookup()
        # Same Concept M0017834: True synonym -> Tier 1
        rel1 = lookup.check_synonym_relation("prostate cancer", "cancer of the prostate")
        self.assertTrue(rel1.is_synonym)
        self.assertEqual(rel1.tier, "Tier 1")
        self.assertEqual(rel1.concept_id, "M0017834")

        # Different Concept under same Descriptor D015444: Broad/Narrow -> Tier 2
        rel2 = lookup.check_synonym_relation("exercise", "aerobic exercise")
        self.assertFalse(rel2.is_synonym)
        self.assertEqual(rel2.tier, "Tier 2")



    def test_canonicalizer(self):
        # Acronym vs full phrase
        target1 = Canonicalizer.arbitrate("ADT", "androgen deprivation therapy")
        self.assertEqual(target1, "androgen deprivation therapy")

        # Clinical frequency dominance
        freqs = {"prostatic neoplasms": 12, "prostate cancer": 550}
        target2 = Canonicalizer.arbitrate(
            "prostatic neoplasms",
            "prostate cancer",
            corpus_frequencies=freqs,
            mesh_canonical="Prostatic Neoplasms",
        )
        # High frequency clinical term wins over obscure standard
        self.assertEqual(target2, "prostate cancer")


if __name__ == "__main__":
    unittest.main()
