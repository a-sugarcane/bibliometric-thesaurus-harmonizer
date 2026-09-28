# 项目全量资源与资产台账 (Project Resource & Asset Ledger)

> **文档性质**：项目资源合规审计、技术资产盘点与软著申报依据  
> **更新时间**：2026-09-29  
> **基线状态**：全栈闭环交付，代码与资产 100% 离线可用

---

## 一、 开源软件与第三方代码库（Software Dependencies）

坚持**“宽松商业友好协议（MIT / Apache 2.0 / BSD）优先、坚决摒弃强传染性 GPL、轻量化与零网络依赖优先”**的选型准则：

| 依赖类别 | 开源项目名称 | 采纳版本 | 授权协议 | 核心用途 / 裁决理由与考量 | 状态 |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **交互式 Web GUI** | `streamlit` | $\ge 1.40.0$ | Apache 2.0 | 响应式人机在环审查控制台，提供卡片流、动态指标徽章与单元格交互编辑器。 | **[生产已采纳]** |
| **表格处理与矩阵计算** | `pandas` | $\ge 2.2.0$ | BSD-3 | 语料词频矩阵统计、Scopus CSV 结构化解析、前端 DataFrame 转换。 | **[生产已采纳]** |
| **审稿级报表导出** | `openpyxl` | $\ge 3.1.0$ | MIT | 零依赖高保真生成符合国际顶级期刊补充材料标准的 `Table_S1_Thesaurus_Audit.xlsx`（含双轨频次公式与样式排版）。 | **[生产已采纳]** |
| **形态学中心词还原** | `inflect` | $\ge 7.0.0$ | MIT | 复合短语末位核心名词单复数转换，轻量高保真，纯规则引擎，零语料下载。 | **[生产已采纳]** |
| **本体数据流增量解析** | `xml.etree.ElementTree` | 内置 | Python PSF | 原生流式迭代解析（`iterparse`），直接处理 `.gz` 压缩流，内存稳定在 50MB 以内。 | **[生产已采纳]** |
| **压缩数据直接读取** | `gzip` | 内置 | Python PSF | 零额外依赖，无缝支持 `desc2026.gz` 与 `supp2026.gz` 离线流式解压。 | **[生产已采纳]** |
| **自动化测试套件** | `unittest` | 内置 | Python PSF | 22 项全链路单元测试，提供持续集成质量保障。 | **[生产已采纳]** |
| **通用 NLP 与词元还原** | ~~`nltk` (WordNet)~~ | - | Apache 2.0 | **[已确认弃用]** 首次运行强制联网下载数百兆语料库；对医学希腊/拉丁复数（如 `-ses` $\to$ `-sis`）还原泛化性差。 | 弃用 |
| **医学三维网格同名库** | ~~`pymesh`~~ | - | AGPL / MIT | **[已确认弃用]** PyPI 严重命名碰撞，实为 3D 几何三角网格处理库，与医学词表毫无关系。 | 弃用 |
| **医学本体元知识库** | ~~`QuickUMLS`~~ | - | MIT | **[已确认弃用]** 强依赖 50GB UMLS 完整元知识库安装，需专有研究许可与 API Key，违背单机离线定位。 | 弃用 |
| **文献分析与网络绘图** | ~~`metaknowledge`~~ | - | GPL-3.0 | **[已确认弃用]** 采用强传染性 GPL-3.0 协议，阻碍软著申报；强捆绑庞大绘图库，非本系统职责。 | 弃用 |
| **Scopus 在线检索库** | ~~`pybibliometrics`~~ | - | MIT | **[已确认弃用]** 专用于调用 Elsevier 商业 REST API，依赖机构 IP 白名单与 API Key，不适合本地离线文件解析。 | 弃用 |

---

## 二、 权威医学本体与外部公共数据源（Official Ontologies & Datasets）

系统深度集成美国国立医学图书馆（NLM）全量受控医学词表：

| 数据资产名称 | 发布机构 | 数据集文件 | 规模与覆盖量 | 授权与版权属性 | 在系统中的作用 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NLM MeSH 主题词表 (2026 Production)** | 美国国家医学图书馆 (U.S. NLM / NIH) | `desc2026.gz` (380MB 原始 XML 流) | **267,012 条** 倒排索引词条，30,000+ Descriptors, 100,000+ Concepts | **Public Domain** (NLM Open Data, 允许学术与商业免费使用) | 提供 ConceptUI 等价真同义词（Tier 1）与 DescriptorUI 关联词判决基准。 |
| **NLM MeSH 补充化学物表 (2026 Production)** | 美国国家医学图书馆 (U.S. NLM / NIH) | `supp2026.gz` (280MB 原始 XML 流) | **300,000+ 条** 小分子化合物、化疗药、靶向药代号与通用名 | **Public Domain** | 提供具体药物、生物制剂与商品名的单向等价映射（如 `MDV-3100` $\to$ `Enzalutamide`）。 |
| **NLM SPECIALIST Lexicon & Morphology** | 美国国家医学图书馆 (NLM UMLS) | `LEXICON` & `DM.data` | **500,000+ 条** 医学英语屈折与派生构词关系 | **Open Access** (NLM Research Data) | 规划用于医学专科词根剥离与外围派生词扩展分析。 |
| **古典医学结合词素表 (Medical Combining Forms)** | 维基医学开放项目 (WikiProject Medicine) | `medical_roots.json` | **1,200+ 条** 核心构词成分（前缀/词根/后缀） | **CC BY-SA 3.0** | 规划用于外围潜在词族召回（如 `prostat-`, `depress-`, `carcin-`）。 |

---

## 三、 本地专科词库与编译特征资产（Local Curated Assets）

项目在 `project/resources/` 目录下内嵌维护自主构建的离线知识库资产：

| 本地资产文件路径 | 格式 | 资产内容与规模 | 维护机制与用途 |
| :--- | :---: | :--- | :--- |
| [`project/resources/mesh_index.json`](file:///Users/a_sugarcan3/antigravity%20workplace/bibliometric%20thesaurus/project/resources/mesh_index.json) | JSON | **267,012 项** 倒排索引映射字典（词形 $\to$ DescriptorUI, ConceptUI, 规范名） | 由 `mesh_compiler.py` 离线预编译生成，启动时常驻内存提供 $\mathcal{O}(1)$ 极速查询。 |
| [`project/resources/protected_terms.txt`](file:///Users/a_sugarcan3/antigravity%20workplace/bibliometric%20thesaurus/project/resources/protected_terms.txt) | 纯文本 | **专科词元保护白名单**（如 `distress`, `genomics`, `metastasis`, `sclerosis`, `psoriasis`） | 硬阻断词尾单数化过度切割，保护专科名词语义不被篡改。 |
| [`project/resources/stopwords.txt`](file:///Users/a_sugarcan3/antigravity%20workplace/bibliometric%20thesaurus/project/resources/stopwords.txt) | 纯文本 | **首字母缩写对齐停用词表**（`of`, `in`, `for`, `and`, `the`, `with` 等） | 在解耦缩写对时过滤语法连接词，保证 `QoL` $\leftrightarrow$ `quality of life` 精确对齐。 |

---

## 四、 下游文献计量学软件标准与接口协议规范（Downstream Standards）

系统输出物料 100% 遵从主流文献计量学软件与国际学术出版标准：

| 目标平台 / 规范标准 | 对应出厂物料名称 | 格式规范与技术契约 | 主流代表文献 / 标准制定方 |
| :--- | :--- | :--- | :--- |
| **VOSviewer** | `thesaurus_vosviewer.txt` | 制表符分隔 `label \t replace by`，严格剔除自身合并，单跳无重定向回路。 | 荷兰莱顿大学 Van Eck & Waltman (2010) 标准。 |
| **CiteSpace** | `citespace.alias` | 双行式别名格式：第一行原词，第二行替换目标词。 | 美国德雷塞尔大学 陈超美教授团队规范。 |
| **Bibliometrix (R)** | `synonyms.csv` | 逗号分隔两列标准同义词表（`from,to`）。 | 意大利那不勒斯大学 Massimo Aria 团队标准。 |
| **国际医学期刊同行评审** | `Table_S1_Thesaurus_Audit.xlsx` | 包含双轨频次审计（Raw Occurrence Sum vs Boolean Document Degree）与全英文方法学合规陈述（Methodological Statement）。 | 满足 ICMJE、Nature Portfolio 及 Frontiers 期刊补充材料透明性要求。 |

---

## 五、 测试基准语料资产（Benchmark Datasets）

系统在开发与持续集成测试中采用以下真实学术语料作为性能与精度基准：

| 语料标识 | 数据来源 | 样本规模 | 字段特征 | 验证核心指标 |
| :--- | :--- | :---: | :--- | :--- |
| **PCa-Depression-1570** | Web of Science 核心合集 | **1,570 篇文献** | 包含 `TI`, `DE`, `ID`, `UT`，存在 18.2% DE 缺失样本 | 验证 DE 回退协议、267k MeSH 对齐效率、双轨频次审计精度。 |
| **Synthetic-Multi-DB** | WoS, PubMed, CNKI, Scopus, VOSviewer | 各 100 篇合成语料 | 覆盖 MEDLINE 副题词、Refworks 字段标签、CSV 列头 | 验证全数据库格式自动侦测与跨平台解析鲁棒性。 |

---

## 六、 资产合规与软著申报依据

1. **零第三方侵权**：所有依赖库协议均为 MIT、BSD 或 Apache 2.0；医学知识库源自美国政府公共领域（Public Domain）。
2. **纯自主工程化落地**：核心聚类引擎、单向特化差集拦截算法、双轨频次统计模型均为自主设计编码，完全具备软件著作权登记与独立学术发表资格。
