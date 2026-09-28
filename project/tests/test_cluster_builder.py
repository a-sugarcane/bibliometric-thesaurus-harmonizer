"""Unit tests for TargetClusterBuilder and Target-Centric Grouping."""

import unittest
from core.engine.cluster_builder import TargetClusterBuilder, TargetCluster
from config import TIER_1_SAFE, TIER_2_RECOMMENDED, TIER_3_HIGH_RISK


class TestTargetClusterBuilder(unittest.TestCase):
    """Test suite for target-centric grouping and cluster validation."""

    def setUp(self):
        self.builder = TargetClusterBuilder(enable_mesh=True, enable_interceptor=True)
        self.sample_corpus = {
            "prostate cancer": 300,
            "prostatic neoplasms": 80,
            "prostate-cancer": 25,
            "prostate cancers": 15,
            "castration-resistant prostate cancer": 50,
            "crpc": 35,
            "depression": 245,
            "depressions": 12,
            "depressive symptoms": 40,
            "quality of life": 120,
            "qol": 85,
            "quality-of-life": 20,
            "androgen deprivation therapy": 90,
            "adt": 65,
        }

    def test_no_self_merging_invariant(self):
        """CRITICAL: Ensure no cluster contains a variant where raw_term == target_term."""
        clusters = self.builder.build_clusters(self.sample_corpus)
        for cluster in clusters:
            for variant in cluster.variants:
                self.assertNotEqual(
                    variant.raw_term.strip().lower(),
                    cluster.target_term.strip().lower(),
                    f"Self-merging detected in cluster '{cluster.target_term}': variant '{variant.raw_term}'"
                )

    def test_prostate_cancer_cluster(self):
        """Verify prostate cancer gathers its morphological, hyphen, and MeSH variants."""
        clusters = self.builder.build_clusters(self.sample_corpus)
        cluster_map = {c.target_term: c for c in clusters}

        self.assertIn("prostate cancer", cluster_map)
        pc_cluster = cluster_map["prostate cancer"]
        self.assertEqual(pc_cluster.target_raw_freq, 300)

        variant_raws = {v.raw_term for v in pc_cluster.variants}
        self.assertIn("prostatic neoplasms", variant_raws)
        self.assertIn("prostate-cancer", variant_raws)
        self.assertIn("prostate cancers", variant_raws)

    def test_acronym_aligns_to_full_phrase(self):
        """Verify acronyms like QoL and ADT are subordinated under their full phrases."""
        clusters = self.builder.build_clusters(self.sample_corpus)
        cluster_map = {c.target_term: c for c in clusters}

        self.assertIn("quality of life", cluster_map)
        qol_cluster = cluster_map["quality of life"]
        self.assertIn("qol", {v.raw_term for v in qol_cluster.variants})

        self.assertIn("androgen deprivation therapy", cluster_map)
        adt_cluster = cluster_map["androgen deprivation therapy"]
        self.assertIn("adt", {v.raw_term for v in adt_cluster.variants})

    def test_clinical_risk_modifier_blocked(self):
        """Verify depressive symptoms under depression is intercepted as Tier 3 and unselected."""
        clusters = self.builder.build_clusters(self.sample_corpus)
        cluster_map = {c.target_term: c for c in clusters}

        self.assertIn("depression", cluster_map)
        dep_cluster = cluster_map["depression"]
        variant_map = {v.raw_term: v for v in dep_cluster.variants}

        self.assertIn("depressions", variant_map)
        self.assertTrue(variant_map["depressions"].selected_for_export)

        if "depressive symptoms" in variant_map:
            v_symp = variant_map["depressive symptoms"]
            self.assertEqual(v_symp.tier, TIER_3_HIGH_RISK)
            self.assertFalse(v_symp.selected_for_export)

    def test_combined_frequency_calculation(self):
        """Verify combined frequency dynamically reflects selected variants."""
        clusters = self.builder.build_clusters(self.sample_corpus)
        cluster_map = {c.target_term: c for c in clusters}

        pc_cluster = cluster_map["prostate cancer"]
        expected_combined = 300 + sum(v.raw_frequency for v in pc_cluster.variants if v.selected_for_export)
        self.assertEqual(pc_cluster.combined_freq, expected_combined)


if __name__ == "__main__":
    unittest.main()
