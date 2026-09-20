"""Command Line Interface (CLI) for Thesaurus Harmonizer."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DEFAULT_MIN_OCCURRENCES
from core.parsers.format_detector import DatabaseFormat, detect_format
from core.parsers.wos_parser import WoSParser
from core.parsers.pubmed_parser import PubMedParser
from core.parsers.cnki_parser import CNKIParser
from core.parsers.scopus_parser import ScopusParser
from core.parsers.vos_parser import VOSParser
from core.normalizer.syntax_cleaner import SyntaxCleaner
from core.normalizer.lemmatizer import HeadNounLemmatizer
from core.normalizer.hyphen_resolver import HyphenResolver
from core.ontology.mesh_lookup import MeSHLookup
from core.interceptor.risk_rules import ClinicalRiskInterceptor
from core.engine.tier_classifier import TierClassifier, HarmonizationRule
from core.engine.canonicalizer import Canonicalizer
from core.exporters.vosviewer import export_vosviewer_thesaurus
from core.exporters.citespace import export_citespace_alias
from core.exporters.audit_reporter import export_audit_report_excel


def main():
    parser = argparse.ArgumentParser(
        description="Thesaurus Harmonizer: Automated Keyword Normalization & MeSH Alignment for Bibliometrics."
    )
    parser.add_argument("input_file", help="Path to raw export file (WoS, PubMed, CNKI, Scopus, or VOS)")
    parser.add_argument("--min-occ", type=int, default=DEFAULT_MIN_OCCURRENCES, help="Minimum occurrences threshold")
    parser.add_argument("--output-dir", default="./output", help="Directory to save output files")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Format Detection
    db_format = detect_format(input_path)
    print(f"[*] Detected file format: {db_format.value}")

    # 2. Parsing & Document-Level Deduplication
    if db_format == DatabaseFormat.WOS_PLAINTEXT:
        records = WoSParser().parse_file(input_path)
        freqs = WoSParser.compute_frequencies(records)
    elif db_format == DatabaseFormat.PUBMED_MEDLINE:
        records = PubMedParser().parse_file(input_path)
        freqs = PubMedParser.compute_frequencies(records)
    elif db_format in (DatabaseFormat.CNKI_REFWORKS, DatabaseFormat.CNKI_TEXT):
        records = CNKIParser().parse_file(input_path)
        freqs = CNKIParser.compute_frequencies(records)
    elif db_format == DatabaseFormat.SCOPUS_CSV:
        records = ScopusParser().parse_file(input_path)
        freqs = ScopusParser.compute_frequencies(records)
    elif db_format == DatabaseFormat.VOS_TSV:
        vos_p = VOSParser()
        records = vos_p.parse_file(input_path)
        freqs = vos_p.get_term_frequencies(input_path)
    else:
        print(f"[!] Warning: Unknown format. Attempting fallback parse.")
        records = WoSParser().parse_file(input_path)
        freqs = WoSParser.compute_frequencies(records)

    print(f"[*] Total parsed documents: {len(records)}")
    print(f"[*] Unique keywords extracted: {len(freqs)}")

    # 3. Filtering by frequency
    candidate_terms = {t: c for t, c in freqs.items() if c >= args.min_occ}
    print(f"[*] Terms meeting min occurrence (>= {args.min_occ}): {len(candidate_terms)}")

    # 4. Engine Initialization
    lemmatizer = HeadNounLemmatizer()
    mesh_lookup = MeSHLookup()
    interceptor = ClinicalRiskInterceptor()

    harmonization_rules = []

    # 5. Pipeline execution
    for term, count in candidate_terms.items():
        # Syntax & parenthesis
        decoupled = SyntaxCleaner.decouple_parentheses(term)
        base_term = decoupled.full_phrase

        # Hyphen collision
        hyphen_resolved = HyphenResolver.resolve_hyphen_term(
            base_term, corpus_frequencies=candidate_terms, mesh_terms=mesh_lookup.all_indexed_terms
        )

        # Lemmatization
        lemmatized = lemmatizer.lemmatize_phrase(hyphen_resolved)

        # MeSH Lookup
        mesh_result = mesh_lookup.lookup(lemmatized)
        mesh_canonical = mesh_result.canonical_name if mesh_result.matched else None

        # Canonical arbitration
        target = Canonicalizer.arbitrate(
            term,
            lemmatized,
            corpus_frequencies=candidate_terms,
            mesh_canonical=mesh_canonical,
        )

        # Interception check
        interception = interceptor.inspect_pair(term, target)

        # Rule derivation
        rule_source = "Lemmatization" if lemmatized != term else "Direct"
        if mesh_result.matched:
            rule_source = f"MeSH ({mesh_result.descriptor_id})"

        rule = TierClassifier.classify(
            raw_term=term,
            target_term=target,
            rule_source=rule_source,
            interception=interception,
            raw_frequency=count,
        )
        harmonization_rules.append(rule)

    # 6. Export outputs
    export_vosviewer_thesaurus(harmonization_rules, output_dir / "thesaurus_vosviewer.txt")
    export_citespace_alias(harmonization_rules, output_dir / "citespace.alias")
    export_audit_report_excel(harmonization_rules, output_dir / "Thesaurus_Audit_Report.xlsx")

    print(f"[+] Processing completed. Output files generated in: {output_dir}")


if __name__ == "__main__":
    main()
