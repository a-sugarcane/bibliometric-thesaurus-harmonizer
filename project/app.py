"""Streamlit Web GUI for Thesaurus Harmonizer."""

import sys
import tempfile
from pathlib import Path
import streamlit as st
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DEFAULT_MIN_OCCURRENCES, TIER_1_SAFE, TIER_2_RECOMMENDED, TIER_3_HIGH_RISK
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
from core.exporters.bibliometrix import export_bibliometrix_synonyms
from core.exporters.audit_reporter import export_audit_report_excel

st.set_page_config(
    page_title="Thesaurus Harmonizer",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Thesaurus Harmonizer: 文献计量学同义词自动化清洗与规范化系统")
st.caption("基于医学主题词知识库（MeSH）与临床概念防滑坡拦截引擎 | 面向 WoS / PubMed / CNKI / Scopus / VOSviewer")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. 数据源上传")
    uploaded_file = st.file_uploader(
        "上传题录导出文件",
        type=["txt", "nbib", "csv", "tsv"],
        help="支持 WoS (savedrecs.txt), PubMed (.nbib/.txt), CNKI (Refworks/txt), Scopus (CSV), VOSviewer (terms.txt)",
    )

    st.header("2. 参数设置")
    min_occ = st.slider("关键词最小频次截断 (Min Occurrences)", min_value=1, max_value=20, value=DEFAULT_MIN_OCCURRENCES)
    enable_mesh = st.checkbox("启用 NLM MeSH 语义对齐", value=True)
    enable_interceptor = st.checkbox("启用临床概念滑坡硬拦截器", value=True)

if not uploaded_file:
    st.info("请在左侧边栏上传待清洗的文献计量学数据导出文件。")
    st.stop()

# --- PROCESSING ---
with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name) as tmp_file:
    tmp_file.write(uploaded_file.getvalue())
    tmp_path = Path(tmp_file.name)

# Detect format
detected_format = detect_format(tmp_path)
st.sidebar.success(f"已自动识别格式: **{detected_format.value}**")

# Parse records
if detected_format == DatabaseFormat.WOS_PLAINTEXT:
    records = WoSParser().parse_file(tmp_path)
    freqs = WoSParser.compute_frequencies(records)
elif detected_format == DatabaseFormat.PUBMED_MEDLINE:
    records = PubMedParser().parse_file(tmp_path)
    freqs = PubMedParser.compute_frequencies(records)
elif detected_format in (DatabaseFormat.CNKI_REFWORKS, DatabaseFormat.CNKI_TEXT):
    records = CNKIParser().parse_file(tmp_path)
    freqs = CNKIParser.compute_frequencies(records)
elif detected_format == DatabaseFormat.SCOPUS_CSV:
    records = ScopusParser().parse_file(tmp_path)
    freqs = ScopusParser.compute_frequencies(records)
elif detected_format == DatabaseFormat.VOS_TSV:
    vos_p = VOSParser()
    records = vos_p.parse_file(tmp_path)
    freqs = vos_p.get_term_frequencies(tmp_path)
else:
    records = WoSParser().parse_file(tmp_path)
    freqs = WoSParser.compute_frequencies(records)

# Filter candidate keywords
candidate_terms = {t: c for t, c in freqs.items() if c >= min_occ}

# Engine components
lemmatizer = HeadNounLemmatizer()
mesh_lookup = MeSHLookup() if enable_mesh else None
interceptor = ClinicalRiskInterceptor() if enable_interceptor else None

harmonization_rules = []

for term, count in candidate_terms.items():
    # 1. Syntax cleaner
    decoupled = SyntaxCleaner.decouple_parentheses(term)
    base_term = decoupled.full_phrase

    # 2. Hyphen resolver
    hyphen_resolved = HyphenResolver.resolve_hyphen_term(
        base_term,
        corpus_frequencies=candidate_terms,
        mesh_terms=mesh_lookup.all_indexed_terms if mesh_lookup else None,
    )

    # 3. Lemmatization
    lemmatized = lemmatizer.lemmatize_phrase(hyphen_resolved)

    # 4. MeSH lookup
    mesh_canonical = None
    descriptor_id = None
    if mesh_lookup:
        mesh_res = mesh_lookup.lookup(lemmatized)
        if mesh_res.matched:
            mesh_canonical = mesh_res.canonical_name
            descriptor_id = mesh_res.descriptor_id

    # 5. Canonical arbitration
    target = Canonicalizer.arbitrate(
        term,
        lemmatized,
        corpus_frequencies=candidate_terms,
        mesh_canonical=mesh_canonical,
    )

    # 6. Interceptor
    if interceptor:
        interception = interceptor.inspect_pair(term, target)
    else:
        from core.interceptor.risk_rules import InterceptionResult
        interception = InterceptionResult(is_blocked=False, risk_level="SAFE")

    # 7. Rule generation
    rule_source = "Lemmatization" if lemmatized != term else "Direct"
    if descriptor_id:
        rule_source = f"MeSH ({descriptor_id})"

    rule = TierClassifier.classify(
        raw_term=term,
        target_term=target,
        rule_source=rule_source,
        interception=interception,
        raw_frequency=count,
    )
    harmonization_rules.append(rule)

# --- METRICS PANEL ---
col1, col2, col3, col4 = st.columns(4)
total_terms = len(candidate_terms)
merge_candidates = sum(1 for r in harmonization_rules if r.raw_term.lower() != r.target_term.lower())
blocked_candidates = sum(1 for r in harmonization_rules if r.tier == TIER_3_HIGH_RISK)
expected_compression = f"{(merge_candidates / max(total_terms, 1)) * 100:.1f}%"

col1.metric("候选关键词总数", total_terms)
col2.metric("建议合并对数", merge_candidates)
col3.metric("拦截高危对数", blocked_candidates)
col4.metric("节点压缩率", expected_compression)

st.divider()

# --- INTERACTIVE DATA TABLE ---
st.subheader("同义词规范化三级审查表格")

table_data = []
for r in harmonization_rules:
    table_data.append(
        {
            "选中导出": r.selected_for_export,
            "原始词 (Raw)": r.raw_term,
            "规范目标词 (Target)": r.target_term,
            "置信层级 (Tier)": r.tier,
            "规则依据": r.rule_source,
            "临床安全校验": r.clinical_safety_check,
            "频次": r.raw_frequency,
        }
    )

df = pd.DataFrame(table_data)
edited_df = st.data_editor(
    df,
    use_container_width=True,
    disabled=["原始词 (Raw)", "置信层级 (Tier)", "规则依据", "临床安全校验", "频次"],
    hide_index=True,
)

# Sync edits back to rules
updated_rules = []
for idx, row in edited_df.iterrows():
    orig_rule = harmonization_rules[idx]
    orig_rule.target_term = row["规范目标词 (Target)"]
    orig_rule.selected_for_export = row["选中导出"]
    updated_rules.append(orig_rule)

st.divider()

# --- EXPORT SECTION ---
st.subheader("一键多格式导出")
c1, c2, c3, c4 = st.columns(4)

with tempfile.TemporaryDirectory() as out_dir:
    out_dir_path = Path(out_dir)

    vos_path = export_vosviewer_thesaurus(updated_rules, out_dir_path / "thesaurus_vosviewer.txt")
    citespace_path = export_citespace_alias(updated_rules, out_dir_path / "citespace.alias")
    bib_path = export_bibliometrix_synonyms(updated_rules, out_dir_path / "synonyms.csv")
    audit_path = export_audit_report_excel(updated_rules, out_dir_path / "Thesaurus_Audit_Report.xlsx")

    with open(vos_path, "r", encoding="utf-8") as f:
        c1.download_button("下载 VOSviewer (.txt)", f.read(), file_name="thesaurus_vosviewer.txt")

    with open(citespace_path, "r", encoding="utf-8") as f:
        c2.download_button("下载 CiteSpace (.alias)", f.read(), file_name="citespace.alias")

    with open(bib_path, "r", encoding="utf-8") as f:
        c3.download_button("下载 Bibliometrix (.csv)", f.read(), file_name="synonyms.csv")

    with open(audit_path, "rb") as f:
        c4.download_button("下载 审稿人核查表 (.xlsx)", f.read(), file_name="Thesaurus_Audit_Report.xlsx")
