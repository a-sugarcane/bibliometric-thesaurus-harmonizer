"""Global configuration and path management for Thesaurus Harmonizer."""

from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent
RESOURCES_DIR = PROJECT_ROOT / "resources"

# Resource Files
PROTECTED_TERMS_FILE = RESOURCES_DIR / "protected_terms.txt"
STOPWORDS_FILE = RESOURCES_DIR / "stopwords.txt"
MESH_INDEX_FILE = RESOURCES_DIR / "mesh_index.json"

# Default Processing Thresholds
DEFAULT_MIN_OCCURRENCES = 2
MAX_ACRONYM_LENGTH = 5

# Confidence Tier Definitions
TIER_1_SAFE = "Tier 1 (Safe Auto-Merge)"
TIER_2_RECOMMENDED = "Tier 2 (Recommended Semantic Merge)"
TIER_3_HIGH_RISK = "Tier 3 (High-Risk Interception)"
