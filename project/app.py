"""Streamlit Web GUI for Thesaurus Harmonizer."""

import copy
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


# --- CACHED PIPELINE EXECUTION ---
@st.cache_data(show_spinner="正在解析文献题录并执行知识库对齐与规则裁决...")
def run_harmonization_pipeline(
    file_bytes: bytes,
    file_name: str,
    enable_mesh: bool,
    enable_interceptor: bool,
):
    """Run full parsing and harmonization pipeline once and cache results in memory."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_name) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = Path(tmp_file.name)

    try:
        detected_format = detect_format(tmp_path)
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
    finally:
        tmp_path.unlink(missing_ok=True)

    lemmatizer = HeadNounLemmatizer()
    mesh_lookup = MeSHLookup() if enable_mesh else None
    interceptor = ClinicalRiskInterceptor() if enable_interceptor else None

    base_rules: list[HarmonizationRule] = []

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
        base_rules.append(rule)

    return detected_format.value, records, freqs, base_rules


# --- CACHED EXPORT BUILDER ---
@st.cache_data(show_spinner="正在打包生成 VOSviewer 与 Table S1 审计表...")
def prepare_export_payloads(cache_key: str, _rules: list[HarmonizationRule], _records):
    """Generate export bundle in memory, recomputing only when rules change."""
    with tempfile.TemporaryDirectory() as out_dir:
        out_dir_path = Path(out_dir)

        vos_path = export_vosviewer_thesaurus(_rules, out_dir_path / "thesaurus_vosviewer.txt")
        citespace_path = export_citespace_alias(_rules, out_dir_path / "citespace.alias")
        bib_path = export_bibliometrix_synonyms(_rules, out_dir_path / "synonyms.csv")

        reporter = AuditReporter()
        audit_path = reporter.export_table_s1(_rules, _records, out_dir_path / "Table_S1_Thesaurus_Audit.xlsx")

        with open(vos_path, "r", encoding="utf-8") as f:
            vos_content = f.read()
        with open(citespace_path, "r", encoding="utf-8") as f:
            citespace_content = f.read()
        with open(bib_path, "r", encoding="utf-8") as f:
            bib_content = f.read()
        with open(audit_path, "rb") as f:
            audit_bytes = f.read()

        return vos_content, citespace_content, bib_content, audit_bytes


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


# --- EXECUTE / LOAD FROM CACHE ---
format_label, records, freqs, cached_base_rules = run_harmonization_pipeline(
    file_bytes=uploaded_file.getvalue(),
    file_name=uploaded_file.name,
    enable_mesh=enable_mesh,
    enable_interceptor=enable_interceptor,
)
st.sidebar.success(f"已自动识别格式: **{format_label}**")

# Load Draft Checkpoint if exists
saved_draft = {}
if DRAFT_CHECKPOINT_FILE.exists():
    try:
        with open(DRAFT_CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            saved_draft = json.load(f)
    except Exception:
        saved_draft = {}

# Clone rules from cache to apply session overrides without cache mutation warnings
all_rules: list[HarmonizationRule] = []
for r in cached_base_rules:
    new_rule = HarmonizationRule(
        raw_term=r.raw_term,
        target_term=r.target_term,
        tier=r.tier,
        rule_source=r.rule_source,
        clinical_safety_check=r.clinical_safety_check,
        raw_frequency=r.raw_frequency,
        selected_for_export=r.selected_for_export,
    )
    if r.raw_term in saved_draft:
        override = saved_draft[r.raw_term]
        if "target" in override:
            new_rule.target_term = override["target"]
        if "selected" in override:
            new_rule.selected_for_export = override["selected"]
    all_rules.append(new_rule)

# Separate rules
changed_rules = [r for r in all_rules if r.raw_term.strip().lower() != r.target_term.strip().lower()]
anchor_rules = [r for r in all_rules if r.raw_term.strip().lower() == r.target_term.strip().lower()]
blocked_rules = [r for r in all_rules if r.tier == TIER_3_HIGH_RISK]

# Sort all candidate lists strictly by raw frequency descending
all_rules.sort(key=lambda r: r.raw_frequency, reverse=True)
changed_rules.sort(key=lambda r: r.raw_frequency, reverse=True)
anchor_rules.sort(key=lambda r: r.raw_frequency, reverse=True)
blocked_rules.sort(key=lambda r: r.raw_frequency, reverse=True)

# Build quick lookup by raw_term for safe user editing
rule_by_raw = {r.raw_term: r for r in all_rules}


# --- METRICS PANEL ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("语料总独立词数", len(freqs))
col2.metric("核心基准词数 (原形)", len(anchor_rules))
col3.metric("建议合并词对 (变体)", len(changed_rules))
col4.metric("单向拦截高危项", len(blocked_rules))

st.divider()


# --- INTERACTIVE VIEW & SEARCH CONTROLS ---
st.subheader("人机在环：词频降序候选审查面板")

view_mode = st.radio(
    "查看模式切换",
    options=[
        "全部高频词族总览 (含核心基准词与合并项)",
        "仅看建议合并审查表 (Raw ≠ Target)",
        "仅看临床高危拦截项 (Tier 3 阻断项)",
    ],
    horizontal=True,
    help="默认展示全部高频词（含未改变的基准词）；可一键切换为仅看存在合并动作的审查表。",
)

c_search, c_bracket, c_size = st.columns([3, 2, 1])

search_query = c_search.text_input(
    "🔍 关键词即时检索 (如 depression / prostate)",
    placeholder="输入词根或缩写实时检索词族...",
    help="支持模糊搜索原始词或规范目标词，快速查看相关同义词族分布",
).strip().lower()

bracket_filter = c_bracket.radio(
    "频段快速过滤",
    options=["全部", "高频核心 (≥20)", "中频 (5~19)", "长尾 (2~4)"],
    horizontal=True,
)

page_size_option = c_size.selectbox(
    "单页展示条数",
    options=[50, 100, 200, "全部"],
    index=1,
)


# Determine candidate pool based on view mode
if view_mode == "仅看建议合并审查表 (Raw ≠ Target)":
    base_pool = changed_rules
elif view_mode == "仅看临床高危拦截项 (Tier 3 阻断项)":
    base_pool = blocked_rules
else:
    base_pool = all_rules

# Apply filtering
filtered_pool = []
for r in base_pool:
    # If user explicitly searched, prioritize keyword match across all frequencies
    if search_query:
        if search_query not in r.raw_term.lower() and search_query not in r.target_term.lower():
            continue
    else:
        # Threshold filter
        if r.raw_frequency < min_occ:
            continue
        # Bracket filter
        if bracket_filter == "高频核心 (≥20)" and r.raw_frequency < 20:
            continue
        elif bracket_filter == "中频 (5~19)" and not (5 <= r.raw_frequency < 20):
            continue
        elif bracket_filter == "长尾 (2~4)" and not (2 <= r.raw_frequency < 5):
            continue

    filtered_pool.append(r)

# Slicing for fast DOM rendering
total_matched = len(filtered_pool)
if page_size_option != "全部":
    page_limit = int(page_size_option)
    display_rules = filtered_pool[:page_limit]
else:
    display_rules = filtered_pool

st.caption(
    f"共匹配到 **{total_matched}** 条词目，当前显示前 **{len(display_rules)}** 条"
    + ("（导出文件将包含全量记录）。" if total_matched > len(display_rules) else "。")
)


# Build Table DataFrame
table_data = []
for r in display_rules:
    is_changed = (r.raw_term.strip().lower() != r.target_term.strip().lower())
    action_type = "建议合并项" if is_changed else "核心基准词"
    display_tier = r.tier if is_changed else "基准词 (Anchor)"

    table_data.append(
        {
            "选中导出": r.selected_for_export,
            "处理动作": action_type,
            "原始词 (Raw)": r.raw_term,
            "规范目标词 (Target)": r.target_term,
            "置信层级 (Tier)": display_tier,
            "规则依据": ("语料基准词" if not is_changed else r.rule_source),
            "临床安全校验": r.clinical_safety_check,
            "语料频次": r.raw_frequency,
        }
    )

df = pd.DataFrame(table_data)

edited_df = st.data_editor(
    df,
    disabled=["处理动作", "原始词 (Raw)", "置信层级 (Tier)", "规则依据", "临床安全校验", "语料频次"],
    hide_index=True,
    height=450,
)

# Persist edits to Checkpoint safely via raw_term lookup
has_changes = False
for idx, row in edited_df.iterrows():
    raw_key = str(row["原始词 (Raw)"]).strip()
    target_rule = rule_by_raw.get(raw_key)
    if not target_rule:
        continue

    new_target = str(row["规范目标词 (Target)"]).strip()
    new_selected = bool(row["选中导出"])

    if target_rule.target_term != new_target or target_rule.selected_for_export != new_selected:
        target_rule.target_term = new_target
        target_rule.selected_for_export = new_selected
        saved_draft[raw_key] = {"target": new_target, "selected": new_selected}
        has_changes = True

if has_changes:
    with open(DRAFT_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(saved_draft, f, ensure_ascii=False, indent=2)


# --- COLLAPSIBLE SINGLETON LOG ---
singleton_rules = [r for r in changed_rules if r.raw_frequency < min_occ]
with st.expander(f"查看底层静默合并日志（频次 < {min_occ} 的长尾项，共 {len(singleton_rules)} 条）"):
    st.caption("以下长尾单次词已在底层完成形态归一化，如需人工调整可在主界面降低频次阈值。")
    if singleton_rules:
        singleton_data = [
            {"原始词": r.raw_term, "规范目标词": r.target_term, "层级": r.tier, "频次": r.raw_frequency}
            for r in singleton_rules[:100]
        ]
        st.dataframe(pd.DataFrame(singleton_data), hide_index=True)
        if len(singleton_rules) > 100:
            st.info(f"仅显示前 100 条，其余 {len(singleton_rules)-100} 条已包含在完整导出文件中。")
    else:
        st.write("暂无低频合并项。")

st.divider()


# --- EXPORT SECTION ---
st.subheader("出厂导出：VOSviewer 与审稿级 Table S1")

# Create export hash key based on rule targets and selection status
export_hash_key = f"{len(all_rules)}_{sum(1 for r in all_rules if r.selected_for_export)}_{hash(tuple((r.target_term, r.selected_for_export) for r in all_rules[:100]))}"

vos_txt, citespace_alias, bib_csv, audit_xlsx_bytes = prepare_export_payloads(
    cache_key=export_hash_key,
    _rules=all_rules,
    _records=records,
)

c1, c2, c3, c4 = st.columns(4)
c1.download_button("下载 VOSviewer (.txt)", vos_txt, file_name="thesaurus_vosviewer.txt")
c2.download_button("下载 CiteSpace (.alias)", citespace_alias, file_name="citespace.alias")
c3.download_button("下载 Bibliometrix (.csv)", bib_csv, file_name="synonyms.csv")
c4.download_button("下载 Table S1 审计表 (.xlsx)", audit_xlsx_bytes, file_name="Table_S1_Thesaurus_Audit.xlsx")
