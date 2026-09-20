"""VOSviewer thesaurus.txt exporter."""

from pathlib import Path
from typing import List
from core.engine.tier_classifier import HarmonizationRule


def export_vosviewer_thesaurus(
    rules: List[HarmonizationRule],
    output_path: Path | str,
    include_unselected: bool = False,
) -> Path:
    """Export mappings into VOSviewer thesaurus file.

    Format:
        label\treplace by
        prostate cancers\tprostate cancer

    Args:
        rules: List of HarmonizationRule objects.
        output_path: Target destination file path.
        include_unselected: Whether to export unselected/blocked rules.

    Returns:
        Path to the generated file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write("label\treplace by\n")
        for r in rules:
            if not include_unselected and not r.selected_for_export:
                continue
            if r.raw_term.strip().lower() != r.target_term.strip().lower():
                f.write(f"{r.raw_term}\t{r.target_term}\n")

    return path
