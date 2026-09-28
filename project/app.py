"""Streamlit Web GUI for Thesaurus Harmonizer (Target-Centric Grouping Architecture)."""

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
from core.engine.cluster_builder import TargetClusterBuilder, TargetCluster
from core.engine.tier_classifier import HarmonizationRule
from core.exporters.vosviewer import export_vosviewer_thesaurus
from core.exporters.citespace import export_citespace_alias
from core.exporters.bibliometrix import export_bibliometrix_synonyms
from core.exporters.audit_reporter import AuditReporter

DRAFT_CHECKPOINT_FILE = Path(".draft_checkpoint.json")

st.set_page_config(
    page_title="Thesaurus Harmonizer (靶向词族系统)",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Thesaurus Harmonizer: 靶向词族同义词清洗与规范化系统")
st.caption("基于 NLM MeSH 知识库与单向特化差集拦截引擎 | 目标词聚类架构 (Target-Centric Grouping) | 面向 VOSviewer / Bibliometrix / CiteSpace")


# --- CACHED PIPELINE EXECUTION ---
@st.cache_data(show_spinner="正在解析文献题录并执行全局语义聚类分析...")
def run_cluster_pipeline(
    file_bytes: bytes,
    file_name: str,
    enable_mesh: bool,
    enable_interceptor: bool,
    enable_morphemes: bool = True,
):
    """Run full parsing and target-centric clustering pipeline once and cache in memory."""
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

    builder = TargetClusterBuilder(
        enable_mesh=enable_mesh,
        enable_interceptor=enable_interceptor,
        enable_morphemes=enable_morphemes,
    )
    clusters = builder.build_clusters(freqs)

    return detected_format.value, records, freqs, clusters


# --- CACHED EXPORT BUILDER ---
@st.cache_data(show_spinner="正在打包生成 VOSviewer 与 Table S1 审计表...")
def prepare_export_payloads(cache_key: str, _rules: list[HarmonizationRule], _records):
    """Generate export bundle in memory, recomputing only when exportable rules change."""
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

    st.header("2. 聚类引擎控制")
    enable_mesh = st.checkbox("启用 NLM MeSH 语义对齐", value=True)
    enable_interceptor = st.checkbox("启用临床特化防滑坡单向拦截器", value=True)
    enable_morphemes = st.checkbox(
        "启用医学词根外围候选召回 (Tier 3 默认未选)",
        value=True,
        help="利用专科医学结合词素表（如 prostat-, depress-），将外围潜在关联词拉入目标词族，强制标记为高危且默认不勾选，供学者自主裁决",
    )

    if st.button("清空本地草稿并重置"):
        if DRAFT_CHECKPOINT_FILE.exists():
            DRAFT_CHECKPOINT_FILE.unlink()
        st.success("已重置本地修改缓存。")
        st.rerun()

if not uploaded_file:
    st.info("请在左侧边栏上传待清洗的文献题录导出文件（如 1,570 篇 WoS 纯文本 savedrecs.txt）。")
    st.stop()


# --- EXECUTE / LOAD FROM CACHE ---
format_label, records, freqs, cached_clusters = run_cluster_pipeline(
    file_bytes=uploaded_file.getvalue(),
    file_name=uploaded_file.name,
    enable_mesh=enable_mesh,
    enable_interceptor=enable_interceptor,
    enable_morphemes=enable_morphemes,
)
st.sidebar.success(f"已识别数据格式: **{format_label}**")

# Load Draft Checkpoint if exists
saved_draft = {}
if DRAFT_CHECKPOINT_FILE.exists():
    try:
        with open(DRAFT_CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            saved_draft = json.load(f)
    except Exception:
        saved_draft = {}

# Clone clusters from cache to safely apply interactive session state
clusters: list[TargetCluster] = []
for c in cached_clusters:
    new_variants: list[HarmonizationRule] = []
    for v in c.variants:
        rule_copy = HarmonizationRule(
            raw_term=v.raw_term,
            target_term=v.target_term,
            tier=v.tier,
            rule_source=v.rule_source,
            clinical_safety_check=v.clinical_safety_check,
            raw_frequency=v.raw_frequency,
            selected_for_export=v.selected_for_export,
        )
        if v.raw_term in saved_draft:
            override = saved_draft[v.raw_term]
            if "selected" in override:
                rule_copy.selected_for_export = override["selected"]
            if "target" in override:
                rule_copy.target_term = override["target"]
        new_variants.append(rule_copy)

    new_cluster = TargetCluster(
        target_term=c.target_term,
        target_raw_freq=c.target_raw_freq,
        variants=new_variants,
    )
    clusters.append(new_cluster)


# --- METRICS PANEL ---
clusters_with_variants = [c for c in clusters if c.variant_count > 0]
singletons = [c for c in clusters if c.variant_count == 0]
total_variants = sum(c.variant_count for c in clusters)
approved_variants = sum(c.selected_variant_count for c in clusters)
blocked_variants = sum(1 for c in clusters for v in c.variants if v.tier == TIER_3_HIGH_RISK)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("语料独立词总数", len(freqs))
col2.metric("聚合同义词族数", len(clusters_with_variants))
col3.metric("候选合并变体数", total_variants)
col4.metric("当前已选合并项", approved_variants)
col5.metric("临床高危拦截项", blocked_variants)

st.divider()


# --- INTERACTIVE SEARCH & FILTER CONTROLS ---
st.subheader("人机在环：靶向词族审查与合并决策面板")

c_search, c_filter, c_sort, c_page = st.columns([3, 2, 2, 1])

search_query = c_search.text_input(
    "🔍 词族实时检索 (如 depression / prostate)",
    placeholder="输入关键词检索目标词或其下属变体...",
    help="跨目标词与下属变体联合检索，即时调出目标词族",
).strip().lower()

cluster_filter_mode = c_filter.radio(
    "词族视图范围",
    options=["仅看有合并建议的词族 (Variants > 0)", "仅看含高危拦截项的词族 (Tier 3)", "查看全部词目 (含独立词)"],
    horizontal=False,
)

sort_mode = c_sort.selectbox(
    "排序规则",
    options=["按合并后总词频降序", "按候选变体数量降序", "按目标词原生频次降序"],
    index=0,
)

page_size_option = c_page.selectbox(
    "每页词族数",
    options=[10, 25, 50, "全部"],
    index=1,
)


# Filter clusters
filtered_clusters = []
for c in clusters:
    # Search filter: matches target_term or any variant raw_term
    if search_query:
        target_match = search_query in c.target_term.lower()
        variant_match = any(search_query in v.raw_term.lower() for v in c.variants)
        if not (target_match or variant_match):
            continue

    # Scope filter
    if cluster_filter_mode == "仅看有合并建议的词族 (Variants > 0)" and c.variant_count == 0:
        continue
    elif cluster_filter_mode == "仅看含高危拦截项的词族 (Tier 3)" and not c.has_blocked_variants:
        continue

    filtered_clusters.append(c)

# Sort clusters
if sort_mode == "按候选变体数量降序":
    filtered_clusters.sort(key=lambda c: (c.variant_count, c.combined_freq), reverse=True)
elif sort_mode == "按目标词原生频次降序":
    filtered_clusters.sort(key=lambda c: (c.target_raw_freq, c.variant_count), reverse=True)
else:
    filtered_clusters.sort(key=lambda c: (c.combined_freq, c.variant_count), reverse=True)


# Slicing
total_filtered = len(filtered_clusters)
if page_size_option != "全部":
    page_limit = int(page_size_option)
    display_clusters = filtered_clusters[:page_limit]
else:
    display_clusters = filtered_clusters

# --- GLOBAL BATCH ACTIONS ---
col_g1, col_g2, col_g3, _ = st.columns([2, 2, 2, 4])
if col_g1.button("⚡ 全局：一键批准全量安全项 (Tier 1 & 2)", help="将所有词族中的 Tier 1 和 Tier 2 安全变体一键勾选，保持 Tier 3 高危项不勾选"):
    for c in clusters:
        for v in c.variants:
            is_safe = (v.tier != TIER_3_HIGH_RISK)
            v.selected_for_export = is_safe
            saved_draft[v.raw_term] = {"selected": is_safe, "target": c.target_term}
    with open(DRAFT_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(saved_draft, f, ensure_ascii=False, indent=2)
    for k in list(st.session_state.keys()):
        if k.startswith("editor_"):
            del st.session_state[k]
    st.rerun()

if col_g2.button("🚫 全局：一键排除所有高危项 (Tier 3)", help="仅取消全量词族中的 Tier 3 高危/外围拦截项"):
    for c in clusters:
        for v in c.variants:
            if v.tier == TIER_3_HIGH_RISK:
                v.selected_for_export = False
                saved_draft[v.raw_term] = {"selected": False, "target": c.target_term}
    with open(DRAFT_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(saved_draft, f, ensure_ascii=False, indent=2)
    for k in list(st.session_state.keys()):
        if k.startswith("editor_"):
            del st.session_state[k]
    st.rerun()

if col_g3.button("🔄 全局：重置为系统推荐默认", help="清空本地草稿缓存并重置为系统默认推荐状态"):
    if DRAFT_CHECKPOINT_FILE.exists():
        DRAFT_CHECKPOINT_FILE.unlink()
    for k in list(st.session_state.keys()):
        if k.startswith("editor_"):
            del st.session_state[k]
    st.rerun()

st.caption(
    f"共匹配到 **{total_filtered}** 个目标词族，当前展示前 **{len(display_clusters)}** 个"
    + ("（出厂导出文件将自动包含全部已批准项）。" if total_filtered > len(display_clusters) else "。")
)


# --- RENDER TARGET CLUSTERS ---
has_checkpoint_updates = False

if not display_clusters:
    st.info("当前筛选条件下未检索到匹配的词族。")
else:
    for idx, cluster in enumerate(display_clusters):
        # Cluster Header Metrics
        badge_diff = cluster.combined_freq - cluster.target_raw_freq
        diff_str = f"(+{badge_diff})" if badge_diff > 0 else ""
        alert_str = " | 🚨 存在高危拦截项" if cluster.has_blocked_variants else ""

        expander_title = (
            f"🎯 规范目标词: 【{cluster.target_term}】 "
            f"— 原生频次: {cluster.target_raw_freq} | 纳入合并后总频次: {cluster.combined_freq} {diff_str} "
            f"| 待审变体: {cluster.variant_count} 项{alert_str}"
        )

        with st.expander(expander_title, expanded=(cluster.variant_count > 0)):
            if cluster.variant_count == 0:
                st.write(f"此词目在语料中为独立基准词（原生频次: {cluster.target_raw_freq}），无待合并变体。")
                continue

            # Batch action buttons
            col_b1, col_b2, col_b3, _ = st.columns([1, 1, 1, 3])
            key_suffix = f"{idx}_{cluster.target_term}"
            editor_widget_key = f"editor_{key_suffix}"

            if col_b1.button("全部纳入", key=f"all_{key_suffix}"):
                for v in cluster.variants:
                    v.selected_for_export = True
                    saved_draft[v.raw_term] = {"selected": True, "target": cluster.target_term}
                with open(DRAFT_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                    json.dump(saved_draft, f, ensure_ascii=False, indent=2)
                if editor_widget_key in st.session_state:
                    del st.session_state[editor_widget_key]
                st.rerun()

            if col_b2.button("仅选安全项", key=f"safe_{key_suffix}"):
                for v in cluster.variants:
                    is_safe = (v.tier != TIER_3_HIGH_RISK)
                    v.selected_for_export = is_safe
                    saved_draft[v.raw_term] = {"selected": is_safe, "target": cluster.target_term}
                with open(DRAFT_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                    json.dump(saved_draft, f, ensure_ascii=False, indent=2)
                if editor_widget_key in st.session_state:
                    del st.session_state[editor_widget_key]
                st.rerun()

            if col_b3.button("全部排除", key=f"none_{key_suffix}"):
                for v in cluster.variants:
                    v.selected_for_export = False
                    saved_draft[v.raw_term] = {"selected": False, "target": cluster.target_term}
                with open(DRAFT_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                    json.dump(saved_draft, f, ensure_ascii=False, indent=2)
                if editor_widget_key in st.session_state:
                    del st.session_state[editor_widget_key]
                st.rerun()

            # Variant Editor Table
            table_rows = []
            for v in cluster.variants:
                table_rows.append(
                    {
                        "纳入合并": v.selected_for_export,
                        "原始变体词 (Raw)": v.raw_term,
                        "变体原生频次": v.raw_frequency,
                        "置信层级 (Tier)": v.tier,
                        "对齐规则依据": v.rule_source,
                        "临床安全校验": v.clinical_safety_check,
                    }
                )

            df_variants = pd.DataFrame(table_rows)

            edited_variants = st.data_editor(
                df_variants,
                disabled=["原始变体词 (Raw)", "变体原生频次", "置信层级 (Tier)", "对齐规则依据", "临床安全校验"],
                hide_index=True,
                key=f"editor_{key_suffix}",
            )

            # Persist Checkbox toggles
            for _, row in edited_variants.iterrows():
                raw_kw = str(row["原始变体词 (Raw)"]).strip()
                new_sel = bool(row["纳入合并"])

                for v in cluster.variants:
                    if v.raw_term == raw_kw and v.selected_for_export != new_sel:
                        v.selected_for_export = new_sel
                        saved_draft[v.raw_term] = {"selected": new_sel, "target": cluster.target_term}
                        has_checkpoint_updates = True

if has_checkpoint_updates:
    with open(DRAFT_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(saved_draft, f, ensure_ascii=False, indent=2)


st.divider()


# --- EXPORT SECTION ---
st.subheader("出厂导出：VOSviewer 与审稿级 Table S1 审计表")

# Extract strictly user-selected, non-self-merging variant rules
exportable_rules: list[HarmonizationRule] = []
for c in clusters:
    for v in c.variants:
        # ABSOLUTE INVARIANT: Must be selected AND raw != target
        if v.selected_for_export and (v.raw_term.strip().lower() != c.target_term.strip().lower()):
            exportable_rules.append(v)

st.write(
    f"当前已就绪导出规则：**{len(exportable_rules)}** 条有效合并对（严格杜绝自身合并，覆盖全量已勾选变体）。"
)

export_hash_key = f"{len(exportable_rules)}_{hash(tuple((r.raw_term, r.target_term, r.selected_for_export) for r in exportable_rules))}"

vos_txt, citespace_alias, bib_csv, audit_xlsx_bytes = prepare_export_payloads(
    cache_key=export_hash_key,
    _rules=exportable_rules,
    _records=records,
)

c1, c2, c3, c4 = st.columns(4)
c1.download_button("下载 VOSviewer (.txt)", vos_txt, file_name="thesaurus_vosviewer.txt")
c2.download_button("下载 CiteSpace (.alias)", citespace_alias, file_name="citespace.alias")
c3.download_button("下载 Bibliometrix (.csv)", bib_csv, file_name="synonyms.csv")
c4.download_button("下载 Table S1 审计表 (.xlsx)", audit_xlsx_bytes, file_name="Table_S1_Thesaurus_Audit.xlsx")
