# 文献计量学同义词自动化清洗与规范化系统：AI 交接技术规格说明书

**文档目标**：作为下游自主代码生成 Agent 或开发人员的开发任务书（System Specification & Implementation Prompt）。  
**语言/环境要求**：Python 3.10+，支持跨平台（Windows / macOS / Linux）。

---

## 一、 系统定位与交付物目标

### 1.1 系统目标
开发一个面向生物医学文献计量学的关键词同义词自动化清洗、受控词对齐与 Thesaurus 导出系统。
系统可作为独立 Python 命令行工具（CLI）和交互式 Web 工具（基于 Streamlit）运行，并满足中国计算机软件著作权（软著）合规性审查要求。

### 1.2 核心交付物
1. **核心算法引擎包（Core Engine）**：完成语法清洗、形态还原、MeSH 离线匹配与风险拦截。
2. **离线 MeSH 词表索引构建器（MeSH Inverted Index Compiler）**：解析 NLM MeSH 原始数据并生成轻量级 JSON 索引。
3. **Streamlit 交互界面（Web GUI）**：提供数据上传、参数调节、三级置信度表格审查、一键导出功能。
4. **格式适配导出器（Universal Exporters）**：生成 VOSviewer、CiteSpace、Bibliometrix 专用格式文件，以及一份符合期刊投稿标准的《同义词清洗审计表（Excel）》。
5. **软著合规支撑代码结构**：完整的单元测试（`pytest`）、类型标注（Type Hints）、结构化分层设计，确保纯原创有效代码量达到 3,000 行以上。

---

## 二、 系统架构与工程目录规划

```
thesaurus_harmonizer/
├── app.py                      # Streamlit 前端入口
├── cli.py                      # CLI 命令行入口
├── config.py                   # 全局配置与默认阈值
├── core/
│   ├── __init__.py
│   ├── parsers/                # 数据解析层
│   │   ├── __init__.py
│   │   ├── wos_parser.py       # 解析 WoS savedrecs.txt (DE/ID/TI/AB)
│   │   ├── scopus_parser.py    # 解析 Scopus 导出的 CSV
│   │   └── vos_parser.py       # 解析 VOSviewer 的 terms.txt / map.txt
│   ├── normalizer/             # 句法与形态学清洗层
│   │   ├── __init__.py
│   │   ├── syntax_cleaner.py   # 括号提取、标点清洗、大小写控制
│   │   ├── lemmatizer.py       # 中心词词形还原 (结合 inflect 与 spaCy)
│   │   └── hyphen_resolver.py  # 连字符双候选碰撞探测
│   ├── ontology/               # 知识库层
│   │   ├── __init__.py
│   │   ├── mesh_compiler.py    # NLM MeSH 原始数据预编译器
│   │   └── mesh_lookup.py      # 本地倒排索引快速检索与 API 降级后备
│   ├── interceptor/            # 风险防护层
│   │   ├── __init__.py
│   │   └── risk_rules.py       # 分期/耐药/诊断等概念滑坡拦截器
│   ├── engine/                 # 仲裁与决策引擎
│   │   ├── __init__.py
│   │   ├── tier_classifier.py  # 三级置信度分流器 (Tier 1/2/3)
│   │   └── canonicalizer.py    # 规范词仲裁器 (频次优先 / MeSH 优先)
│   └── exporters/              # 多格式导出层
│       ├── __init__.py
│       ├── vosviewer.py        # 导出 thesaurus.txt
│       ├── citespace.py        # 导出 citespace.alias
│       ├── bibliometrix.py     # 导出 synonyms.csv
│       └── audit_reporter.py   # 导出审稿人核查报告 Excel
├── resources/                  # 静态资源
│   ├── mesh_index.json         # 编译好的 MeSH 倒排索引 (~15MB)
│   ├── stopwords.txt           # 通用计量停用词表
│   └── protected_terms.txt     # 专科保留词缀白名单
├── tests/                      # 单元测试 (软著与工程质量保障)
│   ├── test_parsers.py
│   ├── test_normalizer.py
│   ├── test_ontology.py
│   └── test_interceptor.py
└── requirements.txt
```

---

## 三、 核心模块功能规范与算法细节

### 3.1 模块 1：数据解析层（Parsers）
* **支持格式**：
  1. `VOSviewer Terms TSV`：两列或三列（`Term`, `Occurrences`, `Total link strength`）。
  2. `WoS Plaintext (savedrecs.txt)`：按行读取，通过标签提取 `DE`（作者关键词）和 `ID`（Keywords Plus），以分号（`;`）切分。
* **篇级去重（Document-Level Deduplication）机制**：
  * 在 WoS 数据解析中，每篇文献内的关键词维护一个 `set`。当同义词合并后，若单篇文献内产生同名重复，计数只累加 1 次，严禁在同一文献内双重计数。

### 3.2 模块 2：句法与形态学清洗层（Normalizer）
* **缩写与括号解耦（Syntax Cleaner）**：
  * 正则模式：`r"^(.*?)\s*[\(\（](.*?)[\)\）]$"`
  * 提取出 `full_phrase` 与 `acronym`。
  * 若 `acronym` 长度 $\le 5$ 且符合大写缩写特征，将其登记为别名，映射回规范词。
* **中心词词形还原（Lemmatizer）**：
  * 规则：英文多词名词短语中，**仅还原末位中心词**。
  * 算法库：优先使用 `inflect.engine().singular_noun(last_word)`；若未识别，降级使用 `spaCy` 的词元还原。
  * 白名单防护：若词尾在 `protected_terms.txt`（如 `genomics`, `proteomics`, `distress`, `metastasis`）中，**坚决不执行去 's' 逻辑**。
* **连字符双候选碰撞探测（Hyphen Resolver）**：
  * 对于包含 `-` 的短语：
    - 生成候选 A（替换为空格）：`"quality-of-life"` $\to$ `"quality of life"`
    - 生成候选 B（直接删除连字符）：`"co-occurrence"` $\to$ `"cooccurrence"`
  * 探测策略：检查候选 A 与候选 B 在当前原始高频词表与 MeSH 词典中的出现频次。
  * 命中判断：以“高频胜出”或“MeSH 收录胜出”原则决定目标词；若均未出现，默认采用带空格的候选 A。

### 3.3 模块 3：MeSH 知识库倒排索引层（Ontology）
* **预编译格式**：
  * 从 NLM 下载 `desc2026.xml`，预先提取每个 `<DescriptorRecord>` 下的 `<DescriptorName>` 与全部 `<EntryTerm>`。
  * 构建扁平化倒排哈希字典（全部转小写键值）：
    ```json
    {
      "cancer of prostate": {
        "descriptor_id": "D011471",
        "canonical_name": "Prostatic Neoplasms"
      },
      "prostate cancer": {
        "descriptor_id": "D011471",
        "canonical_name": "Prostatic Neoplasms"
      },
      "androgen deprivation therapy": {
        "descriptor_id": "D000726",
        "canonical_name": "Androgen Antagonists"
      }
    }
    ```
* **检索契约**：
  * 查询输入字符串（清洗后）是否在字典中。
  * 若命中，返回其对应的唯一概念 ID 与标准 Descriptor。

### 3.4 模块 4：风险防护与概念滑坡拦截器（Risk Interceptor）
* **拦截清单（硬编码/外部正则库）**：
  1. **肿瘤分期与治疗抵抗限定词**：`metastatic`, `advanced`, `castration-resistant`, `mcrpc`, `crpc`, `hormone-sensitive`, `localized`, `early-stage`, `recurrent`, `refractory`。
  2. **诊断与症状边界**：`distress`, `depressive symptoms`, `major depressive disorder`, `mdd`, `bipolar`, `anxiety`, `fatigue`。
* **拦截逻辑**：
  * 当规则建议将词 $X$ 与词 $Y$ 合并时，比对两者的 token 差异集 $\Delta = (X \cup Y) \setminus (X \cap Y)$。
  * 若 $\Delta$ 中包含上述高危拦截词（例如 `prostate cancer` 与 `metastatic prostate cancer`，差异词包含 `metastatic`），**强行阻断自动合并**，标记为 `Tier 3 (Blocked / High Risk)`，并强制要求人工在 UI 界面显式确认。

### 3.5 模块 5：规范词仲裁与置信度分流（Decision Engine）
* **置信度分层（Confidence Tiers）**：
  * **Tier 1 (Safe Auto-Merge)**：单复数还原、连字符处理、首尾空格与英美拼写差异。默认在 UI 中预勾选为通过。
  * **Tier 2 (Recommended Semantic Merge)**：权威 MeSH Entry Terms 映射、标准公认缩写。默认在 UI 中推荐勾选。
  * **Tier 3 (High-Risk Interception)**：触发了拦截器规则的高危概念。默认不勾选，界面标红显示警示说明。
* **规范词判定仲裁（Canonicalization Protocol）**：
  * 当判定词 $A$ 与词 $B$ 确属同义关系时，选择谁作为 `replace by` 目标：
    1. 若一方是缩写、一方是全称 $\to$ **选择全称**。
    2. 若两者均为完整表达（如 `prostatic neoplasms` vs `prostate cancer`）$\to$ **查验在当前文献集中的真实出现频次，以频次极高者作为目标词（高频临床惯例优先）**。

---

## 四、 输入与输出数据接口定义

### 4.1 输入接口
* `terms.txt`（TSV 格式）：
  ```tsv
  Term	Occurrences	Total link strength
  prostate cancers	120	850
  prostate cancer	818	5643
  androgen deprivation therapy (adt)	35	210
  ```

### 4.2 输出接口
1. **`thesaurus_vosviewer.txt`**（标准制表符分隔，两列无表头或带 `label \t replace by`）：
   ```tsv
   label	replace by
   prostate cancers	prostate cancer
   androgen deprivation therapy (adt)	androgen deprivation therapy
   adt	androgen deprivation therapy
   ```
2. **`citespace.alias`**（CiteSpace 标准格式，制表符分隔）：
   ```tsv
   prostate cancers	prostate cancer
   ```
3. **`Thesaurus_Audit_Report.xlsx`**（随文投稿补充材料，必须包含以下列）：
   - `Original Keyword (Raw)`：原始脏词
   - `Canonical Keyword (Target)`：规范目标词
   - `Harmonization Tier`：Tier 1 / Tier 2 / Tier 3
   - `Rule / Knowledge Base Source`：如 `Lemmatization`, `MeSH (D011471)`, `Hyphen Collision`
   - `Clinical Safety Check`：`Passed` / `Manual Confirmed`
   - `Raw Frequency`：原始频次

---

## 五、 Streamlit 交互界面设计规范

1. **左侧边栏（Sidebar）**：
   - 数据源上传：支持 `WoS savedrecs.txt` 或 `VOSviewer terms.txt`。
   - 阈值设定：关键词频次截断滑动条（默认 $\ge 2$）。
   - 算法开关：是否启用 MeSH 映射、是否开启高危概念强制拦截。
2. **主区域（Main Panel）**：
   - **数据指标概览（Metrics）**：原始关键词总数、建议合并对数、拦截高危对数、预期压缩率。
   - **交互式数据表格（AgGrid / Data Editor）**：
     - 展示待合并词对列表。
     - 按 Tier 1（绿）、Tier 2（黄）、Tier 3（红）提供视觉区分。
     - 允许用户在表格中直接修改 `Target Keyword` 或取消勾选某一行。
   - **一键导出区（Export Section）**：
     - 下载 `VOSviewer Thesaurus (.txt)`。
     - 下载 `CiteSpace Alias (.alias)`。
     - 下载 `Supplementary Audit Table (.xlsx)`。

---

## 六、 软著申报合规性工程要求

为了使该项目顺利通过中国版权保护中心（CPCC）的软件著作权审核：

1. **源码总量要求**：
   - 核心自研代码量（去除空行和注释后）应维持在 **3,200 ~ 4,500 行** 之间，结构严整。
2. **模块独立性**：
   - 严禁把第三方库的代码复制到工程中；所有第三方库通过 `import` 调用。
   - 每个模块均需编写标准 Docstrings，包含函数入参、出参、异常说明及作者信息。
3. **软著输出辅助脚本（`generate_copyright_docs.py`）**：
   - 编写一个辅助脚本，自动扫描 `core/` 与 `app.py`，格式化提取出**前 30 页与后 30 页（单页 50 行，共 3,000 行连续源代码）的 Word/PDF 文档**，并自动剔除敏感路径，以便直接打印申报。
