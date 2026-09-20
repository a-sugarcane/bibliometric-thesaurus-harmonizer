---
name: mesh-thesaurus-processing
description: >-
  NLM MeSH (Medical Subject Headings) 全量官方数据源解析、语义同义词挖掘与文献计量学受控词表构建专业技能。
  涵盖 desc/qual/pa/supp 四大核心 XML/GZ 结构解析、概念树（Tree Numbers）层级推演、入口词（Entry Terms）倒排索引构建、
  以及防概念滑坡（Anti-Concept-Slippage）代码设计规范。
---

# MeSH 官方数据源系统解读与文献计量学代码工程指南 (MeSH Thesaurus Processing Skill)

本技能提供从美国国家医学图书馆（NLM）官方获取、解构、提炼 MeSH（Medical Subject Headings）并在文献计量学清洗工程中实施受控词对齐的完整方法论与代码规范。

---

## 一、 NLM MeSH 官方数据全景架构解读

NLM 每年发布的 MeSH 官方分发包（`xmlmesh/`）包含四大互为支撑的 XML 数据源：

| 文件名（以2026版为例） | 压缩大小 / 解压大小 | 核心概念定义与实体对象 | 文献计量学关键提取字段 |
| :--- | :--- | :--- | :--- |
| **`desc2026.gz` (`desc2026.xml`)** | ~16 MB / ~380 MB | **核心医学主题词（Descriptors）**<br>涵盖解剖、生物、疾病、化学、精神、诊疗技术等 16 大类、约 30,000+ 标准记录。 | `<DescriptorUI>`（如 D011471）<br>`<DescriptorName>`（规范名）<br>`<TreeNumberList>`（层级树路径）<br>`<TermList>`（全部 Entry Terms 同义词） |
| **`qual2026.xml`** | ~290 KB / ~1.5 MB | **副主题词/限定副词（Qualifiers）**<br>约 80 余个修饰词，表示疾病的分支侧面（如 `/therapy`, `/genetics`）。 | `<QualifierUI>`（如 Q000628）<br>`<QualifierName>`（如 therapy）<br>用于剥离 PubMed 中的预组配修饰。 |
| **`pa2026.xml`** | ~5.1 MB / ~45 MB | **药理作用映射表（Pharmacological Action）**<br>将药物分子/活性成分映射至作用分类。 | `<DescriptorReferredTo>` 与 `<PharmacologicalAction>`<br>用于药理学研究中的“同类药物大类合并”。 |
| **`supp2026.gz` (`supp2026.xml`)** | ~47 MB / ~320 MB | **补充概念记录（Supplementary Concepts）**<br>300,000+ 罕见化学品、实验性新药、突变体及罕见病。 | `<SupplementalRecordUI>`（C 开头）<br>`<HeadingMappedToList>`（映射至的父级 D 码 Descriptor）。 |

---

## 二、 `desc.xml` 核心数据结构与语义关系深度解构

在 `desc2026.xml` 中，每个 `<DescriptorRecord>` 呈现三层同心圆语义嵌套：

```
DescriptorRecord (D 级唯一概念，如 D011471: Prostatic Neoplasms)
│
├── DescriptorName: "Prostatic Neoplasms" (标准规范名)
├── TreeNumberList (层级树号码，用于计算概念距离与父子关系)
│   ├── C04.588.274.761 (Neoplasms by Site -> Urogenital Neoplasms -> ...)
│   └── C12.294.565.500 (Male Urogenital Diseases -> ...)
│
└── ConceptList (概念簇)
    ├── Concept (Preferred Concept, ConceptPreferredTermYN="Y")
    │   └── TermList (同义词/入口词列表)
    │       ├── Term: "Prostatic Neoplasms" (Preferred, RecordPreferredTermYN="Y")
    │       ├── Term: "Prostate Neoplasms"
    │       ├── Term: "Prostate Cancer"
    │       ├── Term: "Cancer of the Prostate"
    │       └── Term: "Prostate Cancers"
    │
    └── Concept (Subordinate Narrower Concept, ConceptPreferredTermYN="N")
        └── Term: "Prostatic Cancer, Familial" (家族性前列腺癌，属更窄概念)
```

### 关键属性识别契约
1. **`RecordPreferredTermYN="Y"`**：整个记录唯一的标准英文 Descriptor 题名。
2. **`ConceptPreferredTermYN="Y"`**：当前概念簇的首选表达。
3. **`IsPermutedTermYN="Y"`**：倒排置换词（如 `Neoplasms, Prostatic`，由 NLM 算法自动翻转），在计量匹配中应统一还原为自然语序。
4. **`TreeNumber` 语义距离**：
   - 具有相同前缀的树号代表同宗医学概念（例如 `C04.588` 均为各部位肿瘤）。
   - **防概念滑坡法则**：在医学计量中，**绝对不可将父级节点（如 `C04.588`）直接作为同义词合并到叶子节点（`C04.588.274.761`）**，只能做平行 Entry Term 归一。

---

## 三、 代码设计与工程落地规范

### 1. 内存友好的流式迭代解析（Stream Parsing with Gzip）
- **禁止**使用 `xml.etree.ElementTree.parse()` 一次性加载整个 400MB XML（会导致占用超 2GB 内存并严重拖慢进程）。
- **必须**使用 `gzip.open` 结合 `iterparse(stream, events=("end",))` 并在处理完后立即调用 `elem.clear()`：

```python
import gzip
import xml.etree.ElementTree as ET

def stream_parse_mesh_gz(gz_path: str):
    with gzip.open(gz_path, "rb") as gz_file:
        context = ET.iterparse(gz_file, events=("end",))
        for event, elem in context:
            if elem.tag == "DescriptorRecord":
                # 提取 DescriptorUI 与 Entry Terms
                ui = elem.findtext("DescriptorUI")
                name = elem.findtext("DescriptorName/String")
                # 提取全部 Entry Terms
                entry_terms = [t.text.strip() for t in elem.findall(".//Term/String") if t.text]
                yield ui, name, entry_terms
                # 显式清除节点，维持内存稳定在 50MB 以内
                elem.clear()
```

### 2. 倒排哈希索引构建策略
- 将所有 Entry Terms 与 DescriptorName 转为纯小写字符串后作为 Hash Key。
- Value 保存精简的 Payload：`{"descriptor_id": ui, "canonical_name": name}`。
- 编译输出为 ~15MB ~ 25MB 的轻量 JSON 文件（`mesh_index.json`），实现运行期毫秒级 $O(1)$ 检索。

### 3. 多数据库输入字段映射与副题词剥离规范
- **PubMed 数据源**：`MH` 字段中的副题词修剪正则：
  ```python
  clean_mh = re.sub(r"/[^,;]+", "", raw_mh).replace("*", "").strip()
  ```
- **WoS 数据源**：`DE`（作者词）与 `ID`（Keywords Plus）分离解析，以 `UT` 实行单篇二值去重。
- **CNKI 数据源**：统一中文分号（`；`）、双分号（`;;`）与空格切分，保留中文与英文词对。

---

## 四、 开源生态调用准则与工程纪律

1. **坚持轻量独立，拒绝盲目臃肿**：
   - 词形还原优先使用 `inflect`（小巧精悍，专注英文名词单复数）；
   - 基础文本处理使用 Python 原生库（`re`, `collections`, `gzip`, `xml.etree`）；
   - 数据组织使用 `pandas`，报告导出使用 `openpyxl`；
   - 严禁引入带笨重二进制依赖（如 C++ 编译失败）或需授权许可证（如 UMLS 50GB 庞然大物）的重型框架。
2. **开源组件动态跟踪机制**：
   - 任何引入的第三方库必须在 `docs/OPEN_SOURCE_INVENTORY.md` 中记录版本号、协议与引入理由。
   - 若后续因兼容性、体积或性能决定废弃某开源库，必须用删除线标注（如 ~~`pymesh`~~）并客观记录剔除原因。
