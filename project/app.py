"""Streamlit Web GUI for Thesaurus Harmonizer."""

import json
import sys
import tempfile
from pathlib import Path
import pandas as pd
import streamlit as st

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
from core.exporters.audit_reporter import AuditReporter

DRAFT_CHECKPOINT_FILE = Path(".draft_checkpoint.json")

st.set_page_config(
    page_title="Thesaurus Harmonizer",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Thesaurus Harmonizer: 文献计量学同义词自动化清洗与规范化系统")
st.caption("基于 NLM MeSH 知识库与单向特化差集拦截引擎 | 面向 Web of Science / PubMed / VOSviewer / Bibliometrix")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. 数据源上传")
    uploaded_file = st.file_uploader(
        "上传题录导出文件",
        type=["txt", "nbib", "csv", "tsv"],
        help="支持 WoS (savedrecs.txt), PubMed (.nbib/.txt), CNKI (Refworks/txt), Scopus (CSV), VOSviewer (terms.txt)",
    )

    st.header("2. 参数与过滤控制")
    min_occ = st.slider("界面呈现频次阈值 (Min Occurrences)", min_value=1, max_value=20, value=DEFAULT_MIN_OCCURRENCES)
    enable_mesh = st.checkbox("启用 NLM MeSH 概念级语义对齐", value=True)
    enable_interceptor = st.checkbox("启用临床概念防滑坡单向拦截器", value=True)

    if st.button("清空本地草稿重置"):
        if DRAFT_CHECKPOINT_FILE.exists():
            DRAFT_CHECKPOINT_FILE.unlink()
        st.success("已重置本地草稿缓存。")
        st.rerun()

if not uploaded_file:
    st.info("请在左侧边栏上传待清洗的文献计量学数据导出文件（例如 1,570 篇 WoS 纯文本 savedrecs.txt）。")
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
    wos_p = WoSParser()
    records = wos_p.parse_file(tmp_path)
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
    wos_p = WoSParser()
    records = wos_p.parse_file(tmp_path)
    freqs = WoSParser.compute_frequencies(records)

# Engine components
lemmatizer = HeadNounLemmatizer()
mesh_lookup = MeSHLookup() if enable_mesh else None
interceptor = ClinicalRiskInterceptor() if enable_interceptor else None

# Load Draft Checkpoint if exists
saved_draft = {}
if DRAFT_CHECKPOINT_FILE.exists():
    try:
        with open(DRAFT_CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            saved_draft = json.load(f)
    except Exception:
        saved_draft = {}

# Backend Stage 1: Silent execution on all terms (including singletons)
all_rules: list[HarmonizationRule] = []

for term, count in freqs.items():
    # 1. Syntax cleaner with acronym decoupling
    decoupled = SyntaxCleaner.decouple_parentheses(term)
    base_term = decoupled.full_phrase
    is_acronym = decoupled.is_acronym_valid

    # 2. Hyphen resolver
    hyphen_resolved = HyphenResolver.resolve_hyphen_term(
        base_term,
        corpus_frequencies=freqs,
        mesh_terms=mesh_lookup.all_indexed_terms if mesh_lookup else None,
    )

    # 3. Lemmatization
    lemmatized = lemmatizer.lemmatize_phrase(hyphen_resolved)

    # 4. MeSH Concept lookup
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
        corpus_frequencies=freqs,
        mesh_canonical=mesh_canonical,
    )

    # 6. Interceptor with acronym bypass
    if interceptor:
        interception = interceptor.inspect_pair(term, target, is_acronym_equivalent=is_acronym)
    else:
        from core.interceptor.risk_rules import InterceptionResult
        interception = InterceptionResult(is_blocked=False, risk_level="SAFE")

    # 7. Rule generation
    rule_source = "Lemmatization" if lemmatized != term else "Direct"
    if is_acronym:
        rule_source = "Acronym Match"
    elif descriptor_id:
        rule_source = f"MeSH ({descriptor_id})"

    rule = TierClassifier.classify(
        raw_term=term,
        target_term=target,
        rule_source=rule_source,
        interception=interception,
        raw_frequency=count,
    )

    # Apply saved checkpoint overrides
    if term in saved_draft:
        override = saved_draft[term]
        if "target" in override:
            rule.target_term = override["target"]
        if "selected" in override:
            rule.selected_for_export = override["selected"]

    all_rules.append(rule)

# Separate candidates into changed rules and identity rules
changed_rules = [r for r in all_rules if r.raw_term.strip().lower() != r.target_term.strip().lower()]

# Sort candidates strictly by raw_frequency descending
changed_rules.sort(key=lambda r: r.raw_frequency, reverse=True)

# Filter visible candidates based on threshold
visible_rules = [r for r in changed_rules if r.raw_frequency >= min_occ]
singleton_rules = [r for r in changed_rules if r.raw_frequency < min_occ]

# --- METRICS PANEL ---
col1, col2, col3, col4 = st.columns(4)
total_terms = len(freqs)
total_candidates = len(changed_rules)
visible_count = len(visible_rules)
blocked_count = sum(1 for r in changed_rules if r.tier == TIER_3_HIGH_RISK)

col1.metric("词表独立词数", total_terms)
col2.metric("有效合并候选对", total_candidates)
col3.metric("当前界面审查项", visible_count)
col4.metric("单向拦截高危项", blocked_count)

st.divider()

# --- FILTER TABS ---
st.subheader("人机在环：词频降序候选审查面板")
filter_tab = st.radio(
    "频段快速过滤",
    options=["当前阈值全部", "高频核心词 (≥20)", "中频词 (5~19)", "长尾词 (2~4)"],
    horizontal=True,
)

if filter_tab == "高频核心词 (≥20)":
    filtered_display_rules = [r for r in visible_rules if r.raw_frequency >= 20]
elif filter_tab == "中频词 (5~19)":
    filtered_display_rules = [r for r in visible_rules if 5 <= r.raw_frequency < 20]
elif filter_tab == "长尾词 (2~4)":
    filtered_display_rules = [r for r in visible_rules if 2 <= r.raw_frequency < 5]
else:
    filtered_display_rules = visible_rules

table_data = []
for r in filtered_display_rules:
    table_data.append(
        {
            "选中导出": r.selected_for_export,
            "原始词 (Raw)": r.raw_term,
            "规范目标词 (Target)": r.target_term,
            "置信层级 (Tier)": r.tier,
            "规则依据": r.rule_source,
            "临床安全校验": r.clinical_safety_check,
            "原始频次": r.raw_frequency,
        }
    )

df = pd.DataFrame(table_data)

edited_df = st.data_editor(
    df,
    use_container_width=True,
    disabled=["原始词 (Raw)", "置信层级 (Tier)", "规则依据", "临床安全校验", "原始频次"],
    hide_index=True,
    height=420,
)

# Persist edits to Checkpoint
has_changes = False
for idx, row in edited_df.iterrows():
    target_rule = filtered_display_rules[idx]
    new_target = str(row["规范目标词 (Target)"]).strip()
    new_selected = bool(row["选中导出"])

    if target_rule.target_term != new_target or target_rule.selected_for_export != new_selected:
        target_rule.target_term = new_target
        target_rule.selected_for_export = new_selected
        saved_draft[target_rule.raw_term] = {"target": new_target, "selected": new_selected}
        has_changes = True

if has_changes:
    with open(DRAFT_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(saved_draft, f, ensure_ascii=False, indent=2)

# --- COLLAPSIBLE SINGLETON LOG ---
with st.expander(f"查看底层静默合并日志（频次 < {min_occ} 的长尾项，共 {len(singleton_rules)} 条）"):
    st.caption("以下长尾单次词已在底层完成形态归一化，如需人工调整可在主界面降低频次阈值。")
    if singleton_rules:
        singleton_data = [
            {"原始词": r.raw_term, "规范目标词": r.target_term, "层级": r.tier, "频次": r.raw_frequency}
            for r in singleton_rules[:100]
        ]
        st.dataframe(pd.DataFrame(singleton_data), use_container_width=True, hide_index=True)
        if len(singleton_rules) > 100:
            st.info(f"仅显示前 100 条，其余 {len(singleton_rules)-100} 条已包含在完整导出文件中。")
    else:
        st.write("暂无低频合并项。")

st.divider()

# --- EXPORT SECTION ---
st.subheader("出厂导出：VOSviewer 与审稿级 Table S1")
c1, c2, c3, c4 = st.columns(4)

with tempfile.TemporaryDirectory() as out_dir:
    out_dir_path = Path(out_dir)

    vos_path = export_vosviewer_thesaurus(all_rules, out_dir_path / "thesaurus_vosviewer.txt")
    citespace_path = export_citespace_alias(all_rules, out_dir_path / "citespace.alias")
    bib_path = export_bibliometrix_synonyms(all_rules, out_dir_path / "synonyms.csv")

    reporter = AuditReporter()
    audit_path = reporter.export_table_s1(all_rules, records, out_dir_path / "Table_S1_Thesaurus_Audit.xlsx")

    with open(vos_path, "r", encoding="utf-8") as f:
        c1.download_button("下载 VOSviewer (.txt)", f.read(), file_name="thesaurus_vosviewer.txt")

    with open(citespace_path, "r", encoding="utf-8") as f:
        c2.download_button("下载 CiteSpace (.alias)", f.read(), file_name="citespace.alias")

    with open(bib_path, "r", encoding="utf-8") as f:
        c3.download_button("下载 Bibliometrix (.csv)", f.read(), file_name="synonyms.csv")

    with open(audit_path, "rb") as f:
        c4.download_button("下载 Table S1 审计表 (.xlsx)", f.read(), file_name="Table_S1_Thesaurus_Audit.xlsx")
