"""Unit tests for clinical risk interceptor and tier classifier."""

import unittest
from config import TIER_1_SAFE, TIER_2_RECOMMENDED, TIER_3_HIGH_RISK
from core.interceptor.risk_rules import ClinicalRiskInterceptor
from core.engine.tier_classifier import TierClassifier


class TestInterceptor(unittest.TestCase):

    def test_interceptor_oncology_stage(self):
        interceptor = ClinicalRiskInterceptor()

        # Blocked: metastatic prostate cancer vs prostate cancer
        res1 = interceptor.inspect_pair("metastatic prostate cancer", "prostate cancer")
        self.assertTrue(res1.is_blocked)
        self.assertIn("metastatic", res1.conflicting_tokens)
        self.assertEqual(res1.risk_level, "HIGH_RISK")

        # Blocked: crpc vs prostate cancer
        res2 = interceptor.inspect_pair("crpc", "prostate cancer")
        self.assertTrue(res2.is_blocked)
        self.assertIn("crpc", res2.conflicting_tokens)

    def test_interceptor_psychiatric_boundary(self):
        interceptor = ClinicalRiskInterceptor()

        # Blocked: depressive symptoms vs major depressive disorder
        res1 = interceptor.inspect_pair("depressive symptoms", "major depressive disorder")
        self.assertTrue(res1.is_blocked)

        # Safe: depression vs emotional depression
        res2 = interceptor.inspect_pair("depression", "emotional depression")
        self.assertFalse(res2.is_blocked)
        self.assertEqual(res2.risk_level, "SAFE")

    def test_tier_classifier(self):
        interceptor = ClinicalRiskInterceptor()

        # Tier 1: Lemmatization
        inter_safe = interceptor.inspect_pair("prostate cancers", "prostate cancer")
        rule1 = TierClassifier.classify("prostate cancers", "prostate cancer", "Lemmatization", inter_safe)
        self.assertEqual(rule1.tier, TIER_1_SAFE)
        self.assertTrue(rule1.selected_for_export)

        # Tier 2: MeSH entry term
        rule2 = TierClassifier.classify("cancer of prostate", "prostate cancer", "MeSH (D011471)", inter_safe)
        self.assertEqual(rule2.tier, TIER_2_RECOMMENDED)
        self.assertTrue(rule2.selected_for_export)

        # Tier 3: Blocked high risk
        inter_blocked = interceptor.inspect_pair("mCRPC", "prostate cancer")
        rule3 = TierClassifier.classify("mCRPC", "prostate cancer", "MeSH (D011471)", inter_blocked)
        self.assertEqual(rule3.tier, TIER_3_HIGH_RISK)
        self.assertFalse(rule3.selected_for_export)


if __name__ == "__main__":
    unittest.main()
