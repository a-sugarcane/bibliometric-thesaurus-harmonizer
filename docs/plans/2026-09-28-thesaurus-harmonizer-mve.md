# Biomedical Bibliometrics Thesaurus Harmonizer (MVE) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a robust, peer-reviewer-defensible keyword normalization and audit system for biomedical bibliometrics (validating on 1,570 WoS prostate cancer and depression papers), featuring MeSH Concept-level linking, unidirectional risk interception, dual-metric frequency auditing (Raw Sum vs Independent Doc Count), and a frequency-descending interactive curation table.

**Architecture:** A 6-stage pipeline (Data Parsing & Fallback -> Morphology & Biomedical Acronym Alignment -> MeSH Concept Linking -> Unidirectional Risk Interception -> Interactive Frequency-Descending Review Panel -> Dual-Metric VOSviewer/Table S1 Exporter). All processing maintains bipartite document-keyword mappings for strict boolean deduplication.

**Tech Stack:** Python 3.13, Streamlit, Openpyxl, NLM MeSH 2026 XML/GZ offline indices, standard library (dataclasses, re, json, gzip).

**Spec:** [开题报告/文献计量学同义词清洗系统_项目开题报告v2.md](file:///Users/a_sugarcan3/antigravity%20workplace/bibliometric%20thesaurus/开题报告/文献计量学同义词清洗系统_项目开题报告v2.md)

## Global Constraints

- **Python Environment**: Python 3.13+ at `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`.
- **Testing Standard**: All tests run with `PYTHONPATH=project python3 -m unittest discover -s project/tests`.
- **No External CDNs**: All processing and MeSH queries run 100% offline via `project/resources/mesh_index.json`.
- **Zero Clinical Stage Collapse**: Severe False Merges (e.g. `mCRPC` -> `prostate cancer`) must strictly equal 0 in automated Tier 1.
- **Topological Integrity**: Output `thesaurus.txt` must have no self-loops, be single-hop ($A \to B$), and load into VOSviewer 1.6.20+ with zero errors.
- **Two-Stage Threshold Protocol**: Backend morphology runs silently on all terms (including frequency=1 singletons); UI defaults to candidates with combined frequency $\ge 2$ with collapsible singleton audit log.

## Review Focus

- **Input Case 1: DE Field Missing**: WoS record has empty `DE` but non-empty `ID`. Expected: auto-fallback to `ID`, set `is_de_fallback=True`, keep document in bipartite graph.
- **Input Case 2: Biomedical Acronym with Stopword**: Keyword `quality of life (QoL)`. Expected: skip `of`, align `QoL` $\leftrightarrow$ `quality of life`.
- **Input Case 3: Biomedical Acronym with Lowercase Prefix**: Keyword `metastatic castration-resistant prostate cancer (mCRPC)`. Expected: tolerate `m-` prefix, decouple without breaking phrase.
- **Input Case 4: Modifier Dropping Concept Slippage**: Candidate `metastatic prostate cancer` -> `prostate cancer`. Expected: interceptor detects dropped `metastatic`, forces Tier 3 block with red alert.
- **Input Case 5: Intra-document Duplicate Keywords**: A paper contains both `prostate cancer` and `prostate neoplasms`. After merging to canonical `prostate cancer`, document count must increment by exactly 1, while raw occurrence sum increments by 2.

---

## Tasks

### Task 1: WoS Parser with DE/ID Fallback Protocol

**Files:**
- Modify: `project/core/parsers/wos_parser.py`
- Test: `project/tests/test_parsers.py`

**Interfaces:**
- Consumes: Raw WoS plain text records (`savedrecs.txt` format with `PT J`, `UT WOS:...`, `DE ...`, `ID ...`, `ER`).
- Produces: `DocumentRecord(doc_id: str, author_keywords_de: Set[str], keywords_plus_id: Set[str], effective_keywords: Set[str], is_de_fallback: bool, combined_keywords: Set[str])`.

- [ ] **Step 1: Write the failing test for DE fallback and bipartite extraction**

```python
# In project/tests/test_parsers.py
def test_wos_parser_de_fallback():
    from core.parsers.wos_parser import WoSParser
    sample_data = """PT J
UT WOS:0001
DE prostate cancer; depression
ID quality of life
ER
PT J
UT WOS:0002
ID castration-resistant prostate cancer; docetaxel
ER
"""
    parser = WoSParser()
    records = parser.parse_string(sample_data)
    self.assertEqual(len(records), 2)
    self.assertFalse(records[0].is_de_fallback)
    self.assertIn("prostate cancer", records[0].effective_keywords)
    self.assertTrue(records[1].is_de_fallback)
    self.assertIn("castration-resistant prostate cancer", records[1].effective_keywords)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=project python3 -m unittest project/tests/test_parsers.py`
Expected: FAIL with `AttributeError` or missing `is_de_fallback`/`effective_keywords`.

- [ ] **Step 3: Implement minimal code in `wos_parser.py`**

Add `effective_keywords` and `is_de_fallback` fields to `DocumentRecord`. In `parse_record`:
If `author_keywords_de` is non-empty, `effective_keywords = author_keywords_de`, `is_de_fallback = False`.
If `author_keywords_de` is empty, `effective_keywords = keywords_plus_id`, `is_de_fallback = True`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=project python3 -m unittest project/tests/test_parsers.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add project/core/parsers/wos_parser.py project/tests/test_parsers.py
git commit -m "feat(parser): add DE/ID fallback protocol and effective keywords"
```

---

### Task 2: Biomedical Acronym Matcher and Morphology Normalizer

**Files:**
- Modify: `project/core/normalizer/syntax_cleaner.py`
- Modify: `project/core/normalizer/lemmatizer.py`
- Test: `project/tests/test_normalizer.py`

**Interfaces:**
- Consumes: Raw keyword string (e.g. `quality of life (QoL)`, `metastatic castration-resistant prostate cancer (mCRPC)`, `metastases`).
- Produces: Normalized string, extracted acronym pairs, or unchanged string if non-acronym parenthetical.

- [ ] **Step 1: Write failing tests for QoL and mCRPC acronym alignment**

```python
# In project/tests/test_normalizer.py
def test_biomedical_acronym_alignment():
    from core.normalizer.syntax_cleaner import SyntaxCleaner
    cleaner = SyntaxCleaner()
    # Test 1: Stopword skip in QoL
    res1 = cleaner.extract_acronym_pair("quality of life (QoL)")
    self.assertIsNotNone(res1)
    self.assertEqual(res1.full_form, "quality of life")
    self.assertEqual(res1.acronym, "QoL")

    # Test 2: Lowercase prefix tolerance in mCRPC
    res2 = cleaner.extract_acronym_pair("metastatic castration-resistant prostate cancer (mCRPC)")
    self.assertIsNotNone(res2)
    self.assertEqual(res2.full_form, "metastatic castration-resistant prostate cancer")
    self.assertEqual(res2.acronym, "mCRPC")

    # Test 3: Descriptive parentheses preserved
    res3 = cleaner.extract_acronym_pair("depression (geriatric)")
    self.assertIsNone(res3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=project python3 -m unittest project/tests/test_normalizer.py`
Expected: FAIL due to strict initial-letter mismatch on `of` and `m-`.

- [ ] **Step 3: Implement stopword filtering and prefix tolerance in `syntax_cleaner.py`**

In `SyntaxCleaner.extract_acronym_pair`:
1. Extract text outside parentheses and inside parentheses.
2. Define stopwords: `{'of', 'in', 'for', 'and', 'the', 'with', 'to', 'on', 'at'}`.
3. Define valid biomedical prefixes: `{'m', 'p', 'mi', 'lnc', 'circ', 't'}`.
4. Filter tokens outside parentheses to compare initials against the inner acronym, allowing first letter of acronym to match a lowercase prefix. If matching fails, return `None` (preserving phrase).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=project python3 -m unittest project/tests/test_normalizer.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add project/core/normalizer/syntax_cleaner.py project/tests/test_normalizer.py
git commit -m "feat(normalizer): add biomedical acronym matching with stopword filter and prefix tolerance"
```

---

### Task 3: MeSH Concept-Level Indexing and SCR Drug Mapping

**Files:**
- Modify: `project/core/ontology/mesh_lookup.py`
- Modify: `project/core/ontology/mesh_compiler.py`
- Test: `project/tests/test_ontology.py`

**Interfaces:**
- Consumes: Term string (e.g. `enzalutamide`, `mdv-3100`, `aerobic exercise`, `exercise`).
- Produces: `MeSHMatchResult(found: bool, descriptor_ui: str, concept_ui: str, preferred_term: str, is_concept_preferred: bool, tier: str)`.

- [ ] **Step 1: Write failing tests for ConceptUI vs DescriptorUI discrimination**

```python
# In project/tests/test_ontology.py
def test_mesh_concept_level_synonym():
    from core.ontology.mesh_lookup import MeSHLookup
    lookup = MeSHLookup()
    # Same Concept: True synonym -> Tier 1
    rel1 = lookup.check_synonym_relation("androgen deprivation therapy", "ADT")
    # Different Concept under same Descriptor: Broad/Narrow -> Tier 2
    rel2 = lookup.check_synonym_relation("exercise", "aerobic exercise")
    self.assertNotEqual(rel1.concept_ui, rel2.concept_ui)
    self.assertEqual(rel1.tier, "Tier 1")
    self.assertNotEqual(rel2.tier, "Tier 1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=project python3 -m unittest project/tests/test_ontology.py`
Expected: FAIL.

- [ ] **Step 3: Implement ConceptUI indexing in `mesh_compiler.py` and `mesh_lookup.py`**

Store `concept_ui` in `mesh_index.json` dictionary: `term -> {"descriptor_ui": "...", "concept_ui": "...", "preferred_term": "..."}`.
When evaluating candidate pair $(A, B)$, check if `concept_ui(A) == concept_ui(B)`. Only assign Tier 1 if both share the exact same `concept_ui`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=project python3 -m unittest project/tests/test_ontology.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add project/core/ontology/mesh_lookup.py project/core/ontology/mesh_compiler.py project/tests/test_ontology.py
git commit -m "feat(ontology): enforce MeSH ConceptUI-level synonym resolution"
```

---

### Task 4: Unidirectional Modifier Difference Interceptor

**Files:**
- Modify: `project/core/interceptor/risk_rules.py`
- Test: `project/tests/test_interceptor.py`

**Interfaces:**
- Consumes: `source_term: str`, `target_term: str`, `is_acronym_equivalent: bool`.
- Produces: `RiskCheckResult(is_blocked: bool, tier: str, dropped_modifiers: List[str], reason: str)`.

- [ ] **Step 1: Write failing test for unidirectional modifier dropping**

```python
# In project/tests/test_interceptor.py
def test_unidirectional_modifier_interception():
    from core.interceptor.risk_rules import RiskInterceptor
    interceptor = RiskInterceptor()
    # Dropping high-risk modifier "metastatic" -> Block!
    res1 = interceptor.check_merge_risk("metastatic prostate cancer", "prostate cancer")
    self.assertTrue(res1.is_blocked)
    self.assertEqual(res1.tier, "Tier 3")
    self.assertIn("metastatic", res1.dropped_modifiers)

    # Valid acronym equivalence -> Safe pass
    res2 = interceptor.check_merge_risk("mCRPC", "metastatic castration-resistant prostate cancer", is_acronym=True)
    self.assertFalse(res2.is_blocked)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=project python3 -m unittest project/tests/test_interceptor.py`
Expected: FAIL.

- [ ] **Step 3: Implement unidirectional difference check in `risk_rules.py`**

Define `HIGH_RISK_MODIFIERS = {'metastatic', 'advanced', 'castration-resistant', 'crpc', 'mcrpc', 'recurrent', 'refractory', 'resistant', 'mdd', 'major', 'distress'}`.
Compute `dropped_words = set(tokenize(source_term)) - set(tokenize(target_term))`.
If `is_acronym` is False and `dropped_words & HIGH_RISK_MODIFIERS` is non-empty:
Mark `is_blocked = True`, `tier = "Tier 3"`, reason = "Clinical Stage/Subtype Collapse Intercepted".

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=project python3 -m unittest project/tests/test_interceptor.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add project/core/interceptor/risk_rules.py project/tests/test_interceptor.py
git commit -m "feat(interceptor): implement unidirectional clinical stage difference interceptor"
```

---

### Task 5: Dual-Metric Exporter & Peer-Review Table S1 Generator

**Files:**
- Modify: `project/core/exporters/audit_reporter.py`
- Modify: `project/core/exporters/vosviewer.py`
- Create: `project/tests/test_exporters.py`

**Interfaces:**
- Consumes: Bipartite document graph, finalized thesaurus mappings `Dict[str, str]`, rule audit metadata.
- Produces: `thesaurus_vosviewer.txt`, `Table_S1_Thesaurus_Audit.xlsx`.

- [ ] **Step 1: Write failing test for dual-metric calculation**

```python
# In project/tests/test_exporters.py
def test_dual_metric_frequency():
    from core.exporters.audit_reporter import AuditReporter
    from core.parsers.wos_parser import DocumentRecord
    
    docs = [
        DocumentRecord("W1", {"prostate cancer", "prostate neoplasms"}, set(), {"prostate cancer", "prostate neoplasms"}, False, set()),
        DocumentRecord("W2", {"prostate cancer"}, set(), {"prostate cancer"}, False, set())
    ]
    mapping = {"prostate neoplasms": "prostate cancer"}
    reporter = AuditReporter()
    metrics = reporter.calculate_frequencies(docs, mapping)
    
    # prostate neoplasms raw sum = 1, doc count = 1
    # canonical prostate cancer raw sum = 3, independent doc count = 2
    self.assertEqual(metrics["prostate cancer"]["raw_sum"], 3)
    self.assertEqual(metrics["prostate cancer"]["doc_count"], 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=project python3 -m unittest project/tests/test_exporters.py`
Expected: FAIL.

- [ ] **Step 3: Implement dual-metric calculation and Excel exporter**

In `audit_reporter.py`:
1. Calculate `raw_sum`: sum of occurrences across all records.
2. Calculate `doc_count`: count documents where canonical term appears in `effective_keywords` at least once after mapping.
3. Export Excel with two sheets: `Table S1 Harmonization Audit` and `Methodological Statement`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=project python3 -m unittest project/tests/test_exporters.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add project/core/exporters/audit_reporter.py project/core/exporters/vosviewer.py project/tests/test_exporters.py
git commit -m "feat(exporter): implement dual-metric frequency auditing and Table S1 exporter"
```

---

### Task 6: Frequency-Descending Streamlit Curation Panel with Two-Stage Threshold

**Files:**
- Modify: `project/app.py`
- Test: Manual UI verification & integration run with 1,570 WoS dataset

**Interfaces:**
- Consumes: Raw WoS savedrecs file, precompiled MeSH index.
- Produces: Interactive Web UI for frequency-descending curation, auto-saved `.draft_checkpoint.json`, exported `thesaurus_vosviewer.txt` and `Table_S1_Thesaurus_Audit.xlsx`.

- [ ] **Step 1: Implement Two-Stage Threshold and Draft Checkpoint in `app.py`**
1. Backend Tier 1 executes silently on all vocabulary terms (including frequency=1 singletons).
2. Filter candidates for display: default combined frequency $\ge 2$.
3. Render data table sorted by `raw_frequency` descending.
4. Enable in-place cell editing for `target_canonical`.
5. On any edit or checkbox toggle, auto-persist to `.draft_checkpoint.json`.
6. Add bottom collapsible expander: "View Singleton / Low-Frequency Merge Log".

- [ ] **Step 2: Execute integration test on 1,570 WoS dataset**
Run: `PYTHONPATH=project python3 project/cli.py run-batch --input "savedrecs.txt" --threshold 2`
Verify: Table S1 generated, zero clinical false merges on gold standard, VOSviewer loads `thesaurus.txt` with 0 errors.

- [ ] **Step 3: Commit and Push to GitHub**

```bash
git add project/app.py project/cli.py
git commit -m "feat(ui): implement frequency-descending curation panel with two-stage threshold"
git push origin main
```
