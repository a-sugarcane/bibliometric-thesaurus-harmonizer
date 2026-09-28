"""Unit tests for MedicalMorphemeMatcher and peripheral morpheme clustering."""

import unittest
from core.normalizer.morpheme_matcher import MedicalMorphemeMatcher
from core.engine.cluster_builder import TargetClusterBuilder
from config import TIER_3_HIGH_RISK


class TestMedicalMorphemeMatcher(unittest.TestCase):
    """Test suite for medical combining forms extraction and peripheral matching."""

    def setUp(self):
        self.matcher = MedicalMorphemeMatcher()

    def test_extract_roots_specificity(self):
        """Ensure specific medical terms match their combining forms without false positives."""
        roots_prostate = self.matcher.extract_roots("prostate cancer")
        self.assertIn("prostat", roots_prostate)

        roots_prostatitis = self.matcher.extract_roots("acute prostatitis")
        self.assertIn("prostat", roots_prostatitis)

        roots_prostatectomy = self.matcher.extract_roots("radical prostatectomy")
        self.assertIn("prostat", roots_prostatectomy)

        roots_depression = self.matcher.extract_roots("major depression")
        self.assertIn("depress", roots_depression)

        roots_antidepressant = self.matcher.extract_roots("antidepressants")
        self.assertIn("depress", roots_antidepressant)

    def test_anti_collision_guardrails(self):
        """Ensure generic English words with similar prefixes (pro-, de-) do not collide."""
        self.assertEqual(self.matcher.extract_roots("protein synthesis"), set())
        self.assertEqual(self.matcher.extract_roots("disease progression"), set())
        self.assertEqual(self.matcher.extract_roots("department of health"), set())

    def test_shared_roots_detection(self):
        """Verify shared root detection between related terms."""
        self.assertTrue(self.matcher.has_shared_morpheme("prostate cancer", "prostatitis"))
        self.assertTrue(self.matcher.has_shared_morpheme("depression", "depressive disorder"))
        self.assertFalse(self.matcher.has_shared_morpheme("prostate cancer", "depression"))

    def test_cluster_builder_peripheral_integration(self):
        """Verify TargetClusterBuilder absorbs morpheme relatives as Tier 3 unselected variants."""
        sample_corpus = {
            "prostate cancer": 300,
            "prostate-cancer": 25,
            "prostatitis": 20,
            "prostatectomy": 15,
            "depression": 245,
            "depressions": 10,
            "antidepressants": 18,
            "protein": 50,
        }

        builder = TargetClusterBuilder(enable_mesh=True, enable_interceptor=True, enable_morphemes=True)
        clusters = builder.build_clusters(sample_corpus)
        cluster_map = {c.target_term: c for c in clusters}

        # 1. Prostate cancer checks
        self.assertIn("prostate cancer", cluster_map)
        pc_variants = {v.raw_term: v for v in cluster_map["prostate cancer"].variants}
        self.assertIn("prostatitis", pc_variants)
        self.assertIn("prostatectomy", pc_variants)

        # Peripheral morphemes MUST be Tier 3 and unselected by default
        self.assertEqual(pc_variants["prostatitis"].tier, TIER_3_HIGH_RISK)
        self.assertFalse(pc_variants["prostatitis"].selected_for_export)
        self.assertIn("Medical Morpheme (prostat)", pc_variants["prostatitis"].rule_source)

        # 2. Depression checks
        self.assertIn("depression", cluster_map)
        dep_variants = {v.raw_term: v for v in cluster_map["depression"].variants}
        self.assertIn("antidepressants", dep_variants)
        self.assertEqual(dep_variants["antidepressants"].tier, TIER_3_HIGH_RISK)
        self.assertFalse(dep_variants["antidepressants"].selected_for_export)

        # 3. Protein should NEVER be pulled in
        all_variants = [v.raw_term for c in clusters for v in c.variants]
        self.assertNotIn("protein", all_variants)

        # 4. Invariant: Absolute zero self-merging across all clusters
        for c in clusters:
            for v in c.variants:
                self.assertNotEqual(
                    v.raw_term.strip().lower(),
                    c.target_term.strip().lower(),
                    f"Self-merging detected: {v.raw_term} -> {c.target_term}"
                )


if __name__ == "__main__":
    unittest.main()
