"""Software copyright (CPCC) source code extraction script.

Extracts exactly the first 30 pages and last 30 pages (50 lines per page, 3,000 lines total)
from the proprietary project codebase, filtering sensitive paths and dependencies.
"""

from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def collect_source_lines() -> List[str]:
    """Collect all non-empty proprietary python source lines in orderly sequence."""
    scan_order = [
        PROJECT_ROOT / "config.py",
        PROJECT_ROOT / "core" / "parsers" / "base_parser.py",
        PROJECT_ROOT / "core" / "parsers" / "format_detector.py",
        PROJECT_ROOT / "core" / "parsers" / "wos_parser.py",
        PROJECT_ROOT / "core" / "parsers" / "pubmed_parser.py",
        PROJECT_ROOT / "core" / "parsers" / "cnki_parser.py",
        PROJECT_ROOT / "core" / "parsers" / "scopus_parser.py",
        PROJECT_ROOT / "core" / "parsers" / "vos_parser.py",
        PROJECT_ROOT / "core" / "normalizer" / "syntax_cleaner.py",
        PROJECT_ROOT / "core" / "normalizer" / "lemmatizer.py",
        PROJECT_ROOT / "core" / "normalizer" / "hyphen_resolver.py",
        PROJECT_ROOT / "core" / "ontology" / "mesh_compiler.py",
        PROJECT_ROOT / "core" / "ontology" / "mesh_lookup.py",
        PROJECT_ROOT / "core" / "interceptor" / "risk_rules.py",
        PROJECT_ROOT / "core" / "engine" / "canonicalizer.py",
        PROJECT_ROOT / "core" / "engine" / "tier_classifier.py",
        PROJECT_ROOT / "core" / "exporters" / "vosviewer.py",
        PROJECT_ROOT / "core" / "exporters" / "citespace.py",
        PROJECT_ROOT / "core" / "exporters" / "bibliometrix.py",
        PROJECT_ROOT / "core" / "exporters" / "audit_reporter.py",
        PROJECT_ROOT / "cli.py",
        PROJECT_ROOT / "app.py",
    ]

    all_lines: List[str] = []
    for fpath in scan_order:
        if fpath.is_file():
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:  # Keep non-empty lines
                        all_lines.append(line.rstrip("\r\n"))

    return all_lines


def generate_cpcc_submission_text(output_path: Path | str):
    """Generate 60 pages of formatted source code (3000 lines)."""
    lines = collect_source_lines()
    total_lines = len(lines)
    print(f"[*] Total proprietary code lines collected: {total_lines}")

    lines_per_page = 50
    pages_target = 60
    total_needed = lines_per_page * pages_target  # 3000 lines

    if total_lines < total_needed:
        print(f"[!] Warning: Code lines ({total_lines}) < target ({total_needed}).")
        submission_lines = lines
    else:
        # First 30 pages (1500 lines) + Last 30 pages (1500 lines)
        first_1500 = lines[:1500]
        last_1500 = lines[-1500:]
        submission_lines = first_1500 + last_1500

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with open(out_file, "w", encoding="utf-8") as f:
        page = 1
        for i, l in enumerate(submission_lines):
            f.write(f"{l}\n")
            if (i + 1) % lines_per_page == 0:
                f.write(f"\n--- [PAGE {page} / {pages_target}] ---\n\n")
                page += 1

    print(f"[+] Soft-cert source code doc generated: {out_file}")


if __name__ == "__main__":
    out_txt = PROJECT_ROOT / "resources" / "soft_cert_source_code_60pages.txt"
    generate_cpcc_submission_text(out_txt)
