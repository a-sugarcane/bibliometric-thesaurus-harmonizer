"""Peer-reviewer audit report exporter (Excel Table S1 / CSV)."""

import csv
from pathlib import Path
from typing import Dict, List, Optional
from core.engine.tier_classifier import HarmonizationRule
from core.parsers.base_parser import DocumentRecord


class AuditReporter:
    """Calculates dual-metric occurrence frequencies and exports Table S1 audit tables."""

    @staticmethod
    def calculate_frequencies(
        docs: List[DocumentRecord], mapping: Dict[str, str]
    ) -> Dict[str, Dict[str, int]]:
        """Calculate dual-metric frequencies for all canonical keywords across documents.

        Metrics:
            raw_sum: Total occurrences across all records (theoretical upper bound).
            doc_count: Unique documents where the canonical concept appears at least once
                       (Boolean document deduplication, exactly matching VOSviewer node degree).
            reduction: Intra-document duplicates removed (raw_sum - doc_count).

        Args:
            docs: Parsed bibliographic records with effective_keywords.
            mapping: Dictionary mapping raw keywords to canonical terms.

        Returns:
            Dictionary mapping canonical keyword to {raw_sum, doc_count, reduction}.
        """
        metrics: Dict[str, Dict[str, int]] = {}

        for doc in docs:
            kws = doc.effective_keywords if doc.effective_keywords else doc.keywords
            doc_canonical_seen = set()

            for kw in kws:
                clean_kw = kw.strip().lower()
                canonical = mapping.get(clean_kw, mapping.get(kw, kw)).strip().lower()
                if not canonical:
                    continue

                if canonical not in metrics:
                    metrics[canonical] = {"raw_sum": 0, "doc_count": 0, "reduction": 0}

                metrics[canonical]["raw_sum"] += 1
                if canonical not in doc_canonical_seen:
                    metrics[canonical]["doc_count"] += 1
                    doc_canonical_seen.add(canonical)

        for val in metrics.values():
            val["reduction"] = val["raw_sum"] - val["doc_count"]

        return metrics

    def export_table_s1(
        self,
        rules: List[HarmonizationRule],
        docs: List[DocumentRecord],
        output_path: Path | str,
    ) -> Path:
        """Export publication-ready Table S1 Excel workbook with dual metrics and methodology statement.

        Args:
            rules: Full list of harmonization rules (including Tier 3 blocked).
            docs: List of parsed DocumentRecords.
            output_path: Target .xlsx path.

        Returns:
            Path to the saved report file.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        mapping = {
            r.raw_term.strip().lower(): r.target_term.strip().lower()
            for r in rules
            if r.selected_for_export
        }
        freq_metrics = self.calculate_frequencies(docs, mapping)

        headers = [
            "Original Keyword (Raw)",
            "Canonical Keyword (Target)",
            "Harmonization Tier",
            "Rule / Knowledge Base Source",
            "Clinical Safety Check",
            "Raw Occurrence Sum",
            "Independent Document Count (VOSviewer Node Degree)",
            "Intra-Document Deduplication Reduction",
            "Export Status",
        ]

        rows = []
        for r in rules:
            target_key = r.target_term.strip().lower()
            m = freq_metrics.get(target_key, {"raw_sum": r.raw_frequency, "doc_count": r.raw_frequency, "reduction": 0})
            rows.append(
                [
                    r.raw_term,
                    r.target_term,
                    r.tier,
                    r.rule_source,
                    r.clinical_safety_check,
                    m["raw_sum"],
                    m["doc_count"],
                    m["reduction"],
                    "Included" if r.selected_for_export else "Excluded/Review Needed",
                ]
            )

        # Try openpyxl for multi-sheet professional workbook
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment

            wb = openpyxl.Workbook()
            ws1 = wb.active
            ws1.title = "Table S1 Harmonization Audit"

            # Header styling
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")

            ws1.append(headers)
            for cell in ws1[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            for row in rows:
                ws1.append(row)

            # Auto-adjust column widths
            for col in ws1.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                col_letter = col[0].column_letter
                ws1.column_dimensions[col_letter].width = max(max_len + 3, 12)

            # Sheet 2: Methodological Statement
            ws2 = wb.create_sheet(title="Methodological Statement")
            statement_title = "Standard Methodological Disclosure for Journal Submission"
            statement_body = (
                "Keyword Harmonization and Topological Deduplication Protocol:\n\n"
                "To eliminate semantic redundancy while rigorously preventing clinical concept slippage, "
                "keywords from author-defined keywords (DE) and citation-derived keywords plus (ID) were "
                "harmonized using NLM MeSH 2026 concept-level descriptors and morphological lemmatization. "
                "Synonym mappings were restricted to identical MeSH ConceptUIs, preventing broader/narrower "
                "concept confusion. In addition, an oncology risk interceptor blocked unauthorized collapse of "
                "disease stages, resistance phenotypes, or diagnostic subtypes.\n\n"
                "To ensure topological concordance with network analysis tools (e.g., VOSviewer and Bibliometrix), "
                "keyword occurrence frequencies are audited via dual metrics:\n"
                "1. Raw Occurrence Sum: Total keyword mentions across all records (theoretical upper bound).\n"
                "2. Independent Document Count: Boolean document-level deduplication, counting a concept at most "
                "once per bibliographic record regardless of intra-document synonym repetitions.\n\n"
                "The Independent Document Count strictly matches the node degree in downstream bibliometric networks, "
                "eliminating artificial edge inflation."
            )

            ws2.append([statement_title])
            ws2.cell(row=1, column=1).font = Font(size=14, bold=True, color="1F4E79")
            ws2.append([])
            ws2.append([statement_body])
            ws2.cell(row=3, column=1).alignment = Alignment(wrap_text=True)
            ws2.column_dimensions["A"].width = 100

            wb.save(path)
            return path
        except Exception:
            # Fallback to CSV
            csv_path = path.with_suffix(".csv")
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            return csv_path


def export_audit_report_excel(
    rules: List[HarmonizationRule],
    output_path: Path | str,
    docs: Optional[List[DocumentRecord]] = None,
) -> Path:
    """Wrapper function for exporting audit reports."""
    reporter = AuditReporter()
    if docs:
        return reporter.export_table_s1(rules, docs, output_path)
    # If no docs provided, create empty doc list
    return reporter.export_table_s1(rules, [], output_path)

