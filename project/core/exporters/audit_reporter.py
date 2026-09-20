"""Peer-reviewer audit report exporter (Excel / CSV)."""

from pathlib import Path
from typing import List
from core.engine.tier_classifier import HarmonizationRule


def export_audit_report_excel(rules: List[HarmonizationRule], output_path: Path | str) -> Path:
    """Export comprehensive harmonization audit report for peer reviewers.

    Columns:
        1. Original Keyword (Raw)
        2. Canonical Keyword (Target)
        3. Harmonization Tier
        4. Rule / Knowledge Base Source
        5. Clinical Safety Check
        6. Raw Frequency
        7. Export Status

    Args:
        rules: Complete list of HarmonizationRule objects (including blocked).
        output_path: Target .xlsx (or fallback .csv) path.

    Returns:
        Path to the saved report file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for r in rules:
        rows.append(
            {
                "Original Keyword (Raw)": r.raw_term,
                "Canonical Keyword (Target)": r.target_term,
                "Harmonization Tier": r.tier,
                "Rule / Knowledge Base Source": r.rule_source,
                "Clinical Safety Check": r.clinical_safety_check,
                "Raw Frequency": r.raw_frequency,
                "Export Status": "Included" if r.selected_for_export else "Excluded/Review Needed",
            }
        )

    try:
        import pandas as pd
        df = pd.DataFrame(rows)
        if path.suffix.lower() in (".xlsx", ".xls"):
            df.to_excel(path, index=False, engine="openpyxl")
        else:
            df.to_csv(path, index=False, encoding="utf-8-sig")
    except Exception:
        # Fallback to direct CSV writer if pandas/openpyxl are not available in current environment
        import csv
        csv_path = path.with_suffix(".csv")
        fieldnames = [
            "Original Keyword (Raw)",
            "Canonical Keyword (Target)",
            "Harmonization Tier",
            "Rule / Knowledge Base Source",
            "Clinical Safety Check",
            "Raw Frequency",
            "Export Status",
        ]
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return csv_path

    return path
