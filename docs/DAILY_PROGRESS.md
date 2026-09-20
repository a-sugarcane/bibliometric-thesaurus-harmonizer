# 项目研发日志与每日进展报告 (Daily Progress Log)

本项目通过每日日志严格存证研发动态、技术决策、数据资产归档与开源组件变动。

---

## 2026-09-20 ~ 2026-09-21（第 1 天）：项目开题、架构搭建、全量 MeSH 归档与 Skill 固化

### 1. 今日核心里程碑任务
- [x] **规格书与前置报告系统解读**：深入解析工作目录下的交接技术规格书、可行性分析报告、用户决策报告与项目开题报告，确定六大分层架构与软著合规路线。
- [x] **多数据库解析技术路线确立**：制定涵盖 Web of Science (`WoS`)、PubMed (`MEDLINE/NBIB`)、中国知网 (`CNKI`)、`Scopus` 与 `VOSviewer` 的自适应格式识别机制，设计统一篇级二值去重模型。
- [x] **独立工程目录与核心模块代码落地**：
  - 在工作区根目录下创建独立的 `project/` 代码主目录。
  - 完成数据解析层（`core/parsers/`）、形态学清洗层（`core/normalizer/`）、本体检索层（`core/ontology/`）、临床防滑坡拦截层（`core/interceptor/`）、规范词仲裁层（`core/engine/`）、多格式导出层（`core/exporters/`）。
  - 实现基于 Streamlit 的 Web GUI（`project/app.py`）、命令行工具（`project/cli.py`）及软著 60 页源代码抽取脚本（`project/scripts/generate_copyright_docs.py`）。
- [x] **版本控制与环境配置**：
  - 编写针对 Python 与 R 的 `.gitignore`，隔离系统临时文件与缓存。
  - 初始化本地 Git 仓库并完成首个代码提交（Initial Commit: `cc166c2`）。
  - 配置 `~/.gemini/config/mcp_config.json` 挂载官方 GitHub MCP 服务。
- [x] **NLM 官方全量 MeSH 数据下载与归档**：
  - 官方渠道直连：`https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/`。
  - 成功拉取全套 4 大核心数据包至 `project/resources/mesh_raw/`：
    1. `desc2026.gz`（16.03 MB，主题词与入口词）；
    2. `qual2026.xml`（0.28 MB，限定副题词）；
    3. `pa2026.xml`（5.06 MB，药理作用映射表）；
    4. `supp2026.gz`（45.10 MB，补充化学与新药记录）。
- [x] **MeSH 极速倒排索引预编译**：
  - 实现内存友好型的 `gzip.open` + `iterparse` 流式解析器。
  - 在 3.34 秒内完成 380MB 官方 MeSH XML 的全量编译，生成收录 267,012 条权威概念与同义词映射的本地索引 `resources/mesh_index.json`（28.49 MB），实现单机 $O(1)$ 毫秒级查表。
- [x] **MeSH 解读与代码工程 Skill 固化**：
  - 总结四大 XML 文件语义嵌套结构、概念树（Tree Numbers）与倒排置换词机制。
  - 在项目内（`.agents/skills/mesh-thesaurus-processing/SKILL.md`）及全局配置目录（`~/.gemini/config/skills/mesh-thesaurus-processing/SKILL.md`）同步发布 `mesh-thesaurus-processing` 技能。
- [x] **开源生态调研与选型存证**：
  - 创建 `docs/OPEN_SOURCE_INVENTORY.md`，明确“能用成熟开源项目就先用”的工程原则。
  - 明确采用 `inflect`、`spacy`、`pandas`、`openpyxl`、`streamlit`，严谨驳回并用删除线标注 ~~`pymesh`~~（几何碰撞）、~~`QuickUMLS`~~（体积庞大需授权）、~~`metaknowledge`~~（GPL传染）等不适宜项目。
- [x] **全套单元测试验证**：
  - 编写 11 项单元测试，覆盖多源解析去重、PubMed 修剪、希腊/拉丁复数还原（修复 `-ses` $\to$ `-sis` 医学特化规则）、MeSH 全量索引检索、肿瘤分期差集拦截，全量通过（100% Pass）。

---

## 明日 / 下一阶段重点工作计划

1. **真实文献计量测试集回归测试**：
   - 导入课题组现有 1570 篇前列腺癌与抑郁情绪的真实 WoS 关键词数据，运行完整清洗流水线。
   - 对比人工维护的原有 1489 行 `thesaurus` 表，测算自动化对齐率与高危概念拦截精确度。
2. **多语言与中文知网（CNKI）同义词清洗实验**：
   - 针对知网常见的中英文混合导出格式进行分词清洗测试，评估引入 `jieba` 专科词典的可行性。
3. **Streamlit 界面调优与交互验证**：
   - 在本地启动 Streamlit 仪表盘，测试大文件上传、三级置信度高亮编辑及 Excel 审计报表的一键下载功能。
