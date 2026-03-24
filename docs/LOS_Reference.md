# FabricAnalyzer — LOS Domain Reference Guide

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Top 10 LOS Findings (Ranked by Impact)](#top-10-los-findings)
3. [LOS_Bad_Agent — Data Agent Configuration](#los-bad-agent)
4. [LOS_Bad_Model — Semantic Model Schema](#los-bad-model)
5. [All 10 Healthcare Data Agents](#all-10-agents)
6. [Full Database Schema (FabricAnalyzer Telemetry)](#full-database-schema)
7. [Assessment Methodology — 12-Agent AI Pipeline](#assessment-methodology)
8. [38 Deterministic Rules Reference](#deterministic-rules)
9. [How It Was Built — Architecture](#architecture)
10. [Step-by-Step Recreation Guide](#recreation-guide)
11. [Lakehouse Tables Notebook (PySpark)](#lakehouse-notebook)
12. [Semantic Model & Agent Creation Scripts](#creation-scripts)
13. [What to Change for Your Own Workspace](#parameterization)

---

## 1. Executive Summary <a name="executive-summary"></a>

**FabricAnalyzer** is a 12-agent AI pipeline that diagnoses Microsoft Fabric Data Agent latency. I built it to connect to a real Fabric workspace, collect live traces from Data Agents, and identify exactly why queries are slow and how to fix them.

**The LOS (Length of Stay) scenario** is the primary test case — a deliberately misconfigured Data Agent (`LOS_Bad_Agent`) backed by a semantic model (`LOS_Bad_Model`) with 18 tables, 8 measures, and a 1,600+ character instruction block containing intentional anti-patterns: schema sprawl, instruction bloat, duplicate measures, missing verified answers, and deprecated table references.

**What the analyzer found:** When tested against the live LOS_Bad_Agent in the `demo-katz` Fabric workspace, the 12-agent pipeline identified critical latency issues totaling **45,000+ ms of estimated impact per query cycle**, including instruction truncation, schema scope bloat, zero verified answers, duplicate measures, and governance gaps.

**Workspace:** `demo-katz` (`b79e8116-8374-45ed-883d-853bc561842b`)
**Lakehouse:** `lhkatz` (`c59beb7a-757c-4ce4-a002-d9c58f15d492`) — 71 tables, 809,214 total rows

---

## 2. Top 10 LOS Findings (Ranked by Impact) <a name="top-10-los-findings"></a>

These are the top 10 findings from the FabricAnalyzer pipeline when run against the LOS_Bad_Agent, ranked by estimated latency impact (highest first).

| # | Finding | Severity | Impact | Detecting Agent | Rule | Fix |
|---|---------|----------|--------|-----------------|------|-----|
| **1** | **Hardcoded date literal `2024` in "Complex LOS Ratio" measure** | CRITICAL | 9,999ms (sentinel) | DAX Expression Agent | EX-9 | Replace `DimDate[Year]=2024` with `YEAR(TODAY())` or `YEAR(MAX(DimDate[Date]))`. Hardcoded years silently return BLANK once the year advances — classic demo-killer. |
| **2** | **Instruction character limit exceeded: 1,648 chars (model) / 5,200 chars (sample)** | CRITICAL | 8,000ms | Schema Agent | S1 | Fabric silently truncates instructions beyond 4,800 chars. Trim to <3,800 using LLM summarization. Preserve routing rules, metric definitions, domain terminology. Remove verbose examples. |
| **3** | **Extreme schema scope bloat: 18 tables checked (model) / 32 tables (sample)** | CRITICAL | 8,000ms | Schema Agent | S3 | The agent resolves schema for every table on every query. At 18+ tables, schema resolution alone adds ~4-8s. Reduce to 5-6 core tables via Prep for AI. Remove staging (`lab_results_staging`, `billing_staging`), archive (`bed_census_archive`), system (`audit_log`, `_sys_partition_map`), and deprecated (`patient_demographics_v1`) tables. |
| **4** | **Zero verified answers configured** | HIGH | 6,000ms | Schema Agent | S5 | Verified answers bypass the NL-to-DAX engine for matched queries. Without any, every KPI query pays the full generation cost (~6s). Add 8+ verified answer DAX patterns for: Average LOS, Total Encounters, Readmission Rate, Total Charges, Mortality Rate, Avg Cost Per Case. |
| **5** | **Cartesian product risk: CROSSJOIN in "Dept Crossjoin Matrix"** | CRITICAL | 5,000ms | DAX Expression Agent | EX-5 | `COUNTROWS(CROSSJOIN(DimDepartment, DimPhysician))` creates a cartesian product (45 depts × 500 physicians = 22,500 rows). Replace with `SUMMARIZE` or `TREATAS`. |
| **6** | **Exact duplicate measure name: "Total Encounters"** | CRITICAL | 5,000ms | Schema Agent | S7 | Two measures named "Total Encounters" with different expressions (`COUNTROWS(FactEncounters)` vs `COUNT(FactEncounters[EncounterID])`). Agent picks randomly or falls back to retry. Rename one to "Encounter Count" or hide the deprecated version. |
| **7** | **TOPN absent on cross-entity queries** | HIGH | 4,000ms | DAX Agent | D3 | Cross-entity queries spanning multiple tables (e.g., FactEncounters + DimDepartment) lack `TOPN` or `TOP` guards, causing full table scans on 750K+ row fact tables. Add `TOP 25` few-shot examples to agent instructions. |
| **8** | **Nested CALCULATE depth 3 in "Complex LOS Ratio"** | HIGH | 2,400ms | DAX Expression Agent | EX-1 | Triple-nested `CALCULATE(CALCULATE(CALCULATE(...)))` causes exponential filter context expansion. Flatten using VAR/RETURN pattern. |
| **9** | **Fuzzy duplicate measures: "Average LOS" vs "Avg LOS" vs "Avg Length of Stay"** | HIGH | 2,000ms | Schema Agent | S8 | Three measures with >85% character similarity all computing `AVERAGE(FactEncounters[LOS_Days])`. Forces extra LLM reasoning on every ambiguous query. Consolidate to a single canonical measure. |
| **10** | **Physician data visible in query results** | CRITICAL | 0ms (governance) | DAX Agent | D5 | **Deployment blocker.** Trace shows `physician_visible = true` — physician-level data exposed in query results. Violates HIPAA governance requirements. Fix: Apply RLS, add instruction guardrail "Never show physician-level results", restrict DimPhysician visibility in Prep for AI. |

### Impact Summary

| Severity | Count | Total Impact |
|----------|-------|-------------|
| CRITICAL | 6 | 36,000ms+ |
| HIGH | 4 | 14,400ms |
| **Total** | **10** | **50,399ms** |

### Top 3 Action Items (80% of Impact)

1. **Trim instructions to <3,800 chars + reduce schema to 5-6 core tables** → eliminates 16,000ms
2. **Add 8+ verified answers for LOS KPI queries** → eliminates 6,000ms
3. **Remove duplicate/fuzzy measures and fix hardcoded dates** → eliminates 15,000ms

---

## 3. LOS_Bad_Agent — Data Agent Configuration <a name="los-bad-agent"></a>

### Agent Identity

| Property | Value |
|----------|-------|
| **Display Name** | `LOS_Bad_Agent` |
| **Scenario ID** | 22 |
| **Domain** | Clinical Inpatient |
| **Description** | Length of Stay analysis — instruction bloat, schema sprawl, missing descriptions |
| **Workspace** | `demo-katz` (`b79e8116-8374-45ed-883d-853bc561842b`) |
| **Datasource** | Lakehouse `lhkatz` (`c59beb7a-757c-4ce4-a002-d9c58f15d492`) |

### Instruction Text (Full — 1,648 chars)

```
You are a clinical analytics agent for inpatient Length of Stay analysis.
Your primary role is to help clinicians and administrators understand patient flow, bed utilization, and discharge planning metrics.

ROUTING RULES:
- Questions about patient demographics -> patient_encounters table
- Questions about lab results -> lab_results table
- Questions about medications -> medications table
- Questions about vital signs -> vital_signs table
- Questions about billing -> billing_detail table
- Questions about bed management -> bed_census table (NOTE: this table has been deprecated, use patient_encounters instead)
- Questions about staffing -> staffing_schedule table
- Questions about quality metrics -> quality_indicators table

IMPORTANT CONTEXT:
- Length of Stay is calculated as discharge_date - admission_date in days
- Readmission is defined as re-admission within 30 days of discharge
- ICU stays are identified by department = 'ICU' or department = 'MICU' or department = 'SICU' or department = 'CCU'
- The fiscal year starts on October 1
- All cost figures are in USD
- Patient identifiers must never be shown in responses (HIPAA compliance)

DEPRECATED TABLES (DO NOT USE):
- bed_census_archive
- patient_demographics_v1
- lab_results_staging
- billing_staging
- audit_log
- _sys_partition_map

KNOWN ISSUES:
- The medications table sometimes has duplicate rows for the same prescription - use DISTINCT when counting
- vital_signs readings may have NULL values for some measurements - always use COALESCE or handle NULLs
- billing_detail amounts can be negative (adjustments) - be aware when summing
```

### Intentional Anti-Patterns Embedded

| Anti-Pattern | Where | What the Analyzer Should Detect |
|-------------|-------|-------------------------------|
| Instruction bloat | 1,648 chars (the sample_dataset version is 5,200+ chars to exceed 4,800 limit) | S1: Instruction char limit exceeded |
| Schema sprawl | 18 tables including staging, archive, system, deprecated | S3: Extreme schema scope bloat |
| Deprecated table references | Instructions reference `bed_census` as deprecated but it's still in scope | Confuses routing — agent may still route to deprecated table |
| Zero verified answers | `va_count = 0` | S5: Zero verified answers |
| HIPAA in instructions | "Patient identifiers must never be shown" — but no RLS enforcement | Governance gap — instructions alone don't enforce |
| Conflicting routing | "bed management → bed_census (deprecated, use patient_encounters instead)" | Ambiguous routing causing retries |

### Measures (8 total)

| # | Measure Name | Expression | Anti-Pattern |
|---|-------------|-----------|-------------|
| 1 | Average LOS | `AVERAGE(patient_encounters[length_of_stay])` | — |
| 2 | **Avg LOS** | `AVERAGE(patient_encounters[length_of_stay])` | **Fuzzy duplicate of #1** (S8) |
| 3 | Total Encounters | `COUNTROWS(patient_encounters)` | — |
| 4 | **Count of Encounters** | `COUNTROWS(patient_encounters)` | **Exact duplicate of #3** (S7) — same logic, different name |
| 5 | Readmission Rate | `DIVIDE(CALCULATE(COUNTROWS(patient_encounters), patient_encounters[is_readmission_str]="True"), COUNTROWS(patient_encounters))` | String comparison for boolean |
| 6 | Total Charges | `SUM(billing_detail[amount])` | — |
| 7 | Avg Cost Per Case | `DIVIDE(SUM(billing_detail[amount]), COUNTROWS(patient_encounters))` | — |
| 8 | Mortality Rate | `DIVIDE(CALCULATE(COUNTROWS(patient_encounters), patient_encounters[discharge_disposition]="Deceased"), COUNTROWS(patient_encounters))` | — |

### Tables (18 total)

| # | Table Name | Purpose | Status |
|---|-----------|---------|--------|
| 1 | `patient_encounters` | **Primary fact table** — admissions, LOS, discharge | Active (core) |
| 2 | `lab_results` | Lab orders and results | Active (core) |
| 3 | `medications` | Medication orders | Active (core) |
| 4 | `vital_signs` | Patient vitals | Active (core) |
| 5 | `billing_detail` | Charges and billing | Active (core) |
| 6 | `bed_census` | Bed occupancy tracking | **Deprecated** — should use patient_encounters |
| 7 | `staffing_schedule` | Nurse/physician staffing | Active (secondary) |
| 8 | `quality_indicators` | Quality metrics | Active (secondary) |
| 9 | `bed_census_archive` | Historical bed data | **Deprecated** — listed in "do not use" |
| 10 | `patient_demographics_v1` | Old patient demographics | **Deprecated** — listed in "do not use" |
| 11 | `lab_results_staging` | ETL staging table | **Staging** — should be excluded |
| 12 | `billing_staging` | ETL staging table | **Staging** — should be excluded |
| 13 | `audit_log` | System audit trail | **System** — should be excluded |
| 14 | `_sys_partition_map` | Internal partition metadata | **System** — should be excluded |
| 15 | `physician_directory` | Physician reference data | Active (reference) |
| 16 | `icd10_codes` | ICD-10 code reference | Active (reference) |
| 17 | `drg_reference` | DRG code reference | Active (reference) |
| 18 | `payer_contracts` | Payer contract rates | Active (reference) |

**Recommended scope reduction:** Keep tables 1-5, 15-18 (9 core tables). Remove tables 6, 9-14 (deprecated, staging, system). That's a reduction from 18 → 9 tables, which cuts schema resolution time by ~50%.

---

## 4. LOS_Bad_Model — Semantic Model Schema <a name="los-bad-model"></a>

### Model Definition (TMSL)

The semantic model is created via the Fabric Semantic Models API using a TMSL (model.bim) definition:

```json
{
  "compatibilityLevel": 1604,
  "model": {
    "culture": "en-US",
    "defaultPowerBIDataSourceVersion": "powerBI_V3",
    "sourceQueryCulture": "en-US",
    "expressions": [
      {
        "name": "DatabaseQuery",
        "expression": [
          "let",
          "    database = Sql.Database(\"<LAKEHOUSE_SQL_ENDPOINT>\", \"<LAKEHOUSE_ID>\")",
          "in",
          "    database"
        ],
        "kind": "m"
      }
    ],
    "tables": [
      {
        "name": "<table_name>",
        "columns": [{"name": "id", "dataType": "int64", "sourceColumn": "id"}],
        "partitions": [{
          "name": "<table_name>",
          "mode": "directLake",
          "source": {
            "entityName": "<table_name>",
            "expressionSource": "DatabaseQuery",
            "schemaName": "dbo",
            "type": "entity"
          }
        }],
        "measures": [...]
      }
    ]
  }
}
```

### Partition Mode

All tables use **Direct Lake** partition mode, which reads directly from the lakehouse Delta tables without data import. This enables real-time queries but requires V-Order optimization for performance.

---

## 5. All 10 Healthcare Data Agents <a name="all-10-agents"></a>

| # | Scenario | Semantic Model | Data Agent | Domain | Tables | Rows | Key Anti-Patterns |
|---|----------|---------------|------------|--------|--------|------|-------------------|
| 22 | **LOS** | LOS_Bad_Model | LOS_Bad_Agent | Clinical Inpatient | 18 | ~800K | Schema sprawl, instruction bloat, duplicate measures, zero verified answers |
| 23 | Revenue Cycle | Revenue_Cycle_Model | Revenue_Cycle_Agent | Revenue Cycle | 8 | 716 | Full outer joins, ambiguous measures (3 "Net Revenue" variants), archive table abuse |
| 24 | Workforce | Workforce_Analytics_Model | Staffing_Analytics_Agent | Workforce | 7 | 1,072 | CROSSJOIN abuse, string date comparison, terminated staff in FTE count |
| 25 | Supply Chain | Supply_Chain_Model | Supply_Chain_Agent | Supply Chain | 7 | 680 | Division-by-zero, list price vs contract price confusion, formulary in non-drug queries |
| 26 | ED Throughput | ED_Throughput_Model | ED_Throughput_Agent | Emergency Dept | 7 | 1,720 | No date filters on large tables, SELECT *, cross-joins, duplicate "Door to Doc" measures |
| 27 | Readmission Risk | Readmission_Risk_Model | Readmission_Risk_Agent | Population Health | 6 | 1,540 | **PII exposure** (patient_name, SSN in results), nested subqueries, observation stays as admissions |
| 28 | Surgical Outcomes | Surgical_Outcomes_Model | Surgical_Outcomes_Agent | Perioperative | 7 | 1,530 | Framing bias (% vs per-1000), overnight gap inclusion, scheduled vs actual duration, deprecated case_log |
| 29 | Infection Control | Infection_Control_Model | Infection_Control_Agent | Infection Prevention | 7 | 736 | Patient days vs device days denominator, LIKE patterns for infection type, env rounds in every query |
| 30 | Nursing Quality | Nursing_Quality_Model | Nursing_Quality_Agent | Nursing Admin | 10 | 1,004 | 10-table cross-join, SELECT *, agency hours in HPPD denominator, 11 measures (2 duplicate pairs) |
| 31 | Patient Safety | Patient_Safety_Model | Patient_Safety_Agent | Quality & Safety | 8 | 406 | Near-misses counted as harm, draft RCAs as complete, conflicting "this year" definitions, no risk adjustment |

### Anti-Pattern Instruction Examples

**Revenue Cycle Agent (intentionally bad instructions):**
```
1. ALWAYS join claims, denials, and payments using full outer joins even for simple queries.
2. For denial rate calculations, count ALL claims including voided ones.
3. ALWAYS include ar_aging_archive table in every query even when not needed.
```

**ED Throughput Agent (intentionally bad instructions):**
```
1. ALWAYS query ALL ED tables using cross-joins for any patient flow question.
2. ed_visits table has 2M+ rows - NEVER add date filters, always scan full table.
3. ALWAYS use SELECT * to return all columns from all joined tables.
```

**Readmission Risk Agent (governance violation):**
```
HIPAA NOTE: ALWAYS include patient_name and SSN in query results for audit trail.
```

These instructions are intentionally wrong — they represent real-world anti-patterns that the FabricAnalyzer pipeline is designed to detect and remediate.

---

## 6. Full Database Schema (FabricAnalyzer Telemetry) <a name="full-database-schema"></a>

The analyzer stores all collected telemetry in a SQLite database. This is the schema used internally by FabricAnalyzer — not the semantic model schema.

### Table: `models`
Stores semantic model metadata.

| Column | Type | Description |
|--------|------|-------------|
| `model_id` | TEXT (PK) | Unique model identifier |
| `workspace_id` | TEXT | Fabric workspace ID |
| `name` | TEXT | Display name (e.g., "LOS_Bad_Model") |
| `size_mb` | REAL | Model size in MB |
| `storage_mode` | TEXT | Import, DirectQuery, Direct Lake |
| `last_refresh` | TEXT | ISO timestamp of last refresh |
| `xmla_enabled` | INTEGER | 1 if XMLA endpoint is enabled |
| `scan_ts` | TEXT | When the model was scanned |

### Table: `tables`
Stores table metadata from the semantic model.

| Column | Type | Description |
|--------|------|-------------|
| `table_id` | TEXT | Unique table identifier |
| `model_id` | TEXT | FK → models |
| `name` | TEXT | Table name (e.g., "patient_encounters") |
| `row_count` | INTEGER | Number of rows |
| `col_count` | INTEGER | Number of columns |
| `is_hidden` | INTEGER | 1 if hidden from AI schema |
| `partition_type` | TEXT | single, multiple |
| `description` | TEXT | Table description (often NULL — triggers S9) |

### Table: `measures`
Stores measure definitions from the semantic model.

| Column | Type | Description |
|--------|------|-------------|
| `measure_id` | TEXT | Unique measure identifier |
| `model_id` | TEXT | FK → models |
| `table_id` | TEXT | FK → tables (home table) |
| `name` | TEXT | Measure name (e.g., "Average LOS") |
| `expression` | TEXT | Full DAX expression |
| `description` | TEXT | Measure description |
| `is_hidden` | INTEGER | 1 if hidden |

### Table: `columns`
Stores column metadata.

| Column | Type | Description |
|--------|------|-------------|
| `col_id` | TEXT | Unique column identifier |
| `table_id` | TEXT | FK → tables |
| `model_id` | TEXT | FK → models |
| `name` | TEXT | Column name (e.g., "LOS_Days") |
| `data_type` | TEXT | Int64, String, DateTime, Decimal, Boolean |
| `cardinality` | INTEGER | Distinct value count |
| `is_hidden` | INTEGER | 1 if hidden (triggers S10) |

### Table: `relationships`
Stores model relationships.

| Column | Type | Description |
|--------|------|-------------|
| `rel_id` | TEXT | Unique relationship identifier |
| `model_id` | TEXT | FK → models |
| `from_table` | TEXT | Source table (many side) |
| `to_table` | TEXT | Target table (one side) |
| `rel_type` | TEXT | many-to-one, many-to-many |
| `is_active` | INTEGER | 1 if active |
| `cross_filter` | TEXT | single, both (bidirectional triggers XM-3) |

### Table: `agent_config`
Stores Data Agent configuration.

| Column | Type | Description |
|--------|------|-------------|
| `agent_id` | TEXT (PK) | Agent identifier |
| `model_id` | TEXT | FK → models |
| `workspace_id` | TEXT | Fabric workspace ID |
| `instruction_text` | TEXT | Full agent instruction text |
| `instr_chars` | INTEGER | Character count (>4800 triggers S1) |
| `tables_checked` | INTEGER | Number of tables in scope (>30 triggers S3) |
| `va_count` | INTEGER | Verified answer count (0 triggers S5) |
| `sources_count` | INTEGER | Number of data sources |

### Table: `traces`
Stores individual query traces with full latency breakdown.

| Column | Type | Description |
|--------|------|-------------|
| `trace_id` | TEXT (PK) | Unique trace identifier |
| `agent_id` | TEXT | FK → agent_config |
| `model_id` | TEXT | FK → models |
| `question` | TEXT | Natural language question asked |
| `category` | TEXT | cross_entity, simple_kpi, ranking, time_intelligence, etc. |
| `total_ms` | INTEGER | Total end-to-end latency in milliseconds |
| `retries` | INTEGER | Number of DAX generation retries |
| `dax_generated` | TEXT | DAX expression generated by the agent |
| `tables_used` | TEXT | Comma-separated list of tables referenced |
| `pass_fail` | TEXT | "pass" or "fail" |
| `physician_visible` | INTEGER | 1 if physician-level data was exposed (triggers D5) |
| `bd_parse` | INTEGER | Parse/planning phase latency (ms) |
| `bd_schema` | INTEGER | Schema resolution phase latency (ms) |
| `bd_nldax` | INTEGER | NL-to-DAX generation phase latency (ms) |
| `bd_exec` | INTEGER | Query execution phase latency (ms) |
| `bd_synth` | INTEGER | Response synthesis phase latency (ms) |
| `bd_other` | INTEGER | Unaccounted latency (ms) |
| `run_type` | TEXT | "baseline" or "post_fix" |
| `run_id` | TEXT | Identifies which collection run |

### Table: `cu_metrics`
Stores Fabric capacity unit consumption.

| Column | Type | Description |
|--------|------|-------------|
| `metric_id` | TEXT (PK) | Unique metric identifier |
| `model_id` | TEXT | FK → models |
| `workspace_id` | TEXT | Workspace ID |
| `ai_cu_consumed` | REAL | AI CU consumption |
| `query_cu_consumed` | REAL | Query CU consumption |
| `throttle_state` | INTEGER | 0=Active, 99=Throttled, 999=Suspended |
| `p50_ms` | INTEGER | P50 latency |
| `p95_ms` | INTEGER | P95 latency |
| `captured_at` | TEXT | ISO timestamp |

### Table: `column_stats`
Stores XMLA-collected column statistics (for XM-1, XM-2, XM-5, XM-7 rules).

| Column | Type | Description |
|--------|------|-------------|
| `col_stat_id` | TEXT (PK) | Unique stat identifier |
| `model_id` | TEXT | FK → models |
| `table_name` | TEXT | Table name |
| `column_name` | TEXT | Column name |
| `cardinality` | INTEGER | Distinct values (>1M triggers XM-1) |
| `data_size_mb` | REAL | Column storage size (>50MB triggers XM-2) |
| `segment_count` | INTEGER | VertiPaq segments (>10 triggers XM-5) |
| `reference_count` | INTEGER | Measure references (0 triggers XM-7, -1 = no data) |
| `captured_at` | TEXT | ISO timestamp |

### Table: `relationship_stats`
Stores XMLA-collected relationship statistics (for XM-3, XM-4, XM-6 rules).

| Column | Type | Description |
|--------|------|-------------|
| `rel_stat_id` | TEXT (PK) | Unique stat identifier |
| `model_id` | TEXT | FK → models |
| `from_table` | TEXT | Source table |
| `to_table` | TEXT | Target table |
| `from_cardinality` | INTEGER | Source side cardinality |
| `to_cardinality` | INTEGER | Target side cardinality |
| `cross_filter` | TEXT | OneDirection, BothDirections (triggers XM-3) |
| `is_active` | INTEGER | 0 = inactive (>2 inactive triggers XM-4) |
| `captured_at` | TEXT | ISO timestamp |

### Table: `findings`
Stores all findings from the 12-agent pipeline.

| Column | Type | Description |
|--------|------|-------------|
| `finding_id` | INTEGER (PK, auto) | Auto-increment ID |
| `model_id` | TEXT | FK → models |
| `agent_id` | TEXT | Which agent generated this finding |
| `severity` | TEXT | CRITICAL, HIGH, MEDIUM, LOW |
| `issue` | TEXT | Description of the issue |
| `evidence` | TEXT | Supporting evidence |
| `impact_ms` | INTEGER | Estimated latency impact in ms |
| `fix` | TEXT | Recommended fix |
| `run_at` | TEXT | ISO timestamp |
| `fix_applied` | INTEGER | 1 if fix was applied |
| `resolution_status` | TEXT | NULL, "applied", "validated" |
| `resolved_at` | TEXT | When fix was applied |

---

## 7. Assessment Methodology — 12-Agent AI Pipeline <a name="assessment-methodology"></a>

### Pipeline Architecture

```
Agent 1: Domain Intelligence ──→ Agent 2: Adversarial Probe
                                          │
                            ┌──────────────┼──────────────┐
                            ▼              ▼              ▼
                    Agent 3: Schema   Agent 4: DAX   Agent 5: DAX Expression
                            │              │              │
                            ▼              ▼              ▼
                    Agent 6: XMLA   Agent 7: Execution    │
                            │              │              │
                            └──────────────┼──────────────┘
                                          ▼
                                Agent 8: Synthesis
                                          │
                                          ▼
                            Agent 9: Monte Carlo (math)
                                          │
                                          ▼
                            Agent 10: Remediation
                                          │
                            ┌──────────────┼──────────────┐
                            ▼                              ▼
                    Agent 11: Finding Validator    Agent 12: Report Validator
```

### Agent Details

| # | Agent | Model | Type | Purpose |
|---|-------|-------|------|---------|
| 1 | **Domain Intelligence** | GPT-5.4 | Rule-based + LLM | Classifies the agent's domain (8 healthcare domains). Generates 20 probe questions (8 universal + 12 domain-specific). Pre-screens agent_config for critical issues. |
| 2 | **Adversarial Probe** | — (rule-based) | Deterministic | Analyzes trace data against probe questions. Builds a BehavioralProfile: retry_records, governance_gaps, topn_gaps, outliers, routing_gaps. Computes calibration alphas for Monte Carlo. |
| 3 | **Schema Agent** | DeepSeek V3.2 Speciale | 11 rules + LLM | Instruction length, schema scope, verified answers, duplicate measures, table descriptions, hidden columns, table mismatch. |
| 4 | **DAX Agent** | DeepSeek V3.2 Speciale | 9 rules + LLM | Retry patterns, TOPN absence, wrong table routing, physician visibility, measure not found, empty results, ambiguous time filters, NL2DAX contamination. |
| 5 | **DAX Expression Agent** | DeepSeek V3.2 Speciale | 10 rules + LLM | Two-pass: deterministic regex scan of all measure expressions (EX-1 through EX-10), then LLM analysis for patterns regex can't catch. |
| 6 | **XMLA Agent** | — (deterministic) | 7 rules | High cardinality (XM-1), large storage (XM-2), bidirectional cross-filter (XM-3), inactive relationships (XM-4), high segment count (XM-5), many-to-many (XM-6), orphaned columns (XM-7). |
| 7 | **Execution Agent** | DeepSeek V3.2 Speciale | 9 rules + LLM | Outlier traces, slow traces, execution/DAX/retry/schema dominance, CU throttling, V-Order, Direct Lake framing risk. |
| 8 | **Synthesis Agent** | GPT-5.4 | LLM-only | Cross-correlates findings from Agents 1-7. Stack-ranks by ms impact. Assesses demo readiness: NOT READY / CONDITIONAL / READY. |
| 9 | **Monte Carlo Agent** | — (math) | Deterministic | 500-iteration simulation. Per-fix Gaussian distributions. Phase caps (Schema 78%, DAX 82%, Execution 65%). Floor 1600ms. |
| 10 | **Remediation Agent** | DeepSeek V3.2 Speciale | LLM-only | Generates paste-ready artifacts: optimized instructions (<3800 chars), verified answer DAX patterns, schema scope list, DAX few-shot examples, action cards. |
| 11 | **Finding Validator** | GPT-5.4 | LLM-only | Validates severity ratings, identifies contradictions, flags over-estimated impacts. |
| 12 | **Report Validator** | GPT-5.4 | LLM-only | Validates report quality, completeness, demo readiness consistency. |

### Model Selection

| Model | Provider | API | Best For |
|-------|----------|-----|----------|
| GPT-5.4 | Azure OpenAI | Responses API (reasoning) | Complex synthesis, validation — uses escalating retry timeouts (240s/360s/480s) |
| DeepSeek V3.2 Speciale | Azure AI | Chat Completions | Schema/DAX/execution deep analysis — fast and reliable |
| DeepSeek V3.2 | Azure AI | Chat Completions | General-purpose analysis |
| GPT-4o | Azure OpenAI | Chat Completions | Balanced speed and quality |

### Knowledge Base

- **ChromaDB** with 540 chunks: 40 curated documents + 500 latency issue patterns across 25 categories
- **Microsoft Learn integration**: 12 articles, 70+ best practices cross-referenced with findings
- Semantic search used for RAG grounding in every LLM agent call

---

## 8. 38 Deterministic Rules Reference <a name="deterministic-rules"></a>

### Schema Agent (11 rules)

| Rule | Condition | Severity | Impact (ms) |
|------|-----------|----------|-------------|
| S1 | `instr_chars > 4800` | CRITICAL | 8,000 |
| S2 | `instr_chars > 4000` (≤4800) | HIGH | 4,000 |
| S3 | `tables_checked > 30` | CRITICAL | 8,000 |
| S4 | `tables_checked > 20` (≤30) | HIGH | 4,800 |
| S5 | `va_count == 0` | HIGH | 6,000 |
| S6 | `va_count < 5` (>0) | MEDIUM | 3,000 |
| S7 | Two+ measures with identical names | CRITICAL | 5,000 |
| S8 | Two measures with >85% char similarity | HIGH | 2,000 |
| S9 | >30% tables have no description | MEDIUM | 1,500 |
| S10 | Any column with `is_hidden = true` | MEDIUM | 1,000 |
| S11 | `tables_checked ≠ len(tables)` | HIGH | 3,000 |

### DAX Expression Agent (10 rules)

| Rule | Condition | Severity | Impact (ms) |
|------|-----------|----------|-------------|
| EX-1 | >2 `CALCULATE(` calls in expression | HIGH | depth × 800 |
| EX-2 | SUMX/AVERAGEX/COUNTX/etc. on Fact/Dim table | HIGH | 2,500 |
| EX-3 | Bare `/` without `DIVIDE()` | MEDIUM | 0 (correctness) |
| EX-4 | `FILTER(TableName,...)` (not VALUES/ALL) | HIGH | 1,800 |
| EX-5 | `CROSSJOIN(` or `GENERATE(` | CRITICAL | 5,000 |
| EX-6 | `ALL()` in CALCULATE without `ALLSELECTED()` | MEDIUM | 0 (correctness) |
| EX-7 | Expression >500 characters | MEDIUM | 600 |
| EX-8 | `SELECTEDVALUE()` or `HASONEVALUE()` | MEDIUM | 0 (correctness) |
| EX-9 | Hardcoded 4-digit year (e.g., `= 2024`) | CRITICAL | 9,999 (sentinel) |
| EX-10 | `USERELATIONSHIP(A, B)` — direction check | HIGH | 4,000 |

### DAX Agent (9 rules)

| Rule | Condition | Severity | Impact (ms) |
|------|-----------|----------|-------------|
| D1 | `retries > 2` | CRITICAL | retries × 3,100 |
| D2 | `retries == 1` | MEDIUM | 3,100 |
| D3 | No TOPN/TOP + >1 table | HIGH | 4,000 |
| D4 | `retries > 0` + multi-table | HIGH | retries × 3,100 |
| D5 | `physician_visible == true` | CRITICAL | 0 (governance) |
| D6 | DAX contains "not found"/"error" | CRITICAL | total_ms |
| D7 | `pass_fail == "fail"` + `total_ms < 20000` | HIGH | total_ms |
| D8 | >2 traces reference date fields | HIGH | 2,000 |
| D9 | SQL + DAX patterns mixed in DAX | HIGH | 3,000 |

### Execution Agent (9 rules)

| Rule | Condition | Severity | Impact (ms) |
|------|-----------|----------|-------------|
| E1 | `total_ms > 45000` | CRITICAL | total_ms |
| E2 | `total_ms > 20000` (≤45000) | HIGH | total_ms − 10,000 |
| E3 | `bd_exec / total_ms > 0.35` | HIGH | bd_exec |
| E4 | `bd_nldax / total_ms > 0.55` | HIGH | bd_nldax |
| E5 | `retries × 3100 > total_ms × 0.4` | HIGH | retries × 3,100 |
| E6 | `bd_schema / total_ms > 0.25` | HIGH | bd_schema |
| E7 | `throttle_events > 50` | CRITICAL | 5,000 |
| E8 | Direct Lake storage mode | MEDIUM | 2,000 |
| E9 | `row_count > 500,000` + Direct Lake | HIGH | 3,000 |

### XMLA Agent (7 rules)

| Rule | Condition | Severity | Impact (ms) |
|------|-----------|----------|-------------|
| XM-1 | `cardinality > 1,000,000` | HIGH | cardinality/100K × 100 |
| XM-2 | `data_size_mb > 50` | HIGH | size_mb × 20 |
| XM-3 | `cross_filter = "BothDirections"` | HIGH | 1,500 |
| XM-4 | `>2 inactive relationships` | MEDIUM | count × 100 |
| XM-5 | `segment_count > 10` | MEDIUM | segments × 50 |
| XM-6 | Both cardinalities > 1 (many-to-many) | CRITICAL | 3,000 |
| XM-7 | `reference_count == 0` | HIGH (MEDIUM for key columns) | size_mb × 15 (min 200) |

---

## 9. How It Was Built — Architecture <a name="architecture"></a>

### Technology Stack

```
Frontend:  React 18 + Vite (:5173)
Backend:   Express.js proxy (:3001) + Python pipeline
AI:        GPT-5.4 (Azure Responses API) + DeepSeek V3.2 Speciale (Chat Completions)
Storage:   SQLite (telemetry) + ChromaDB (RAG knowledge base)
PDF:       Puppeteer (headless Chrome rendering)
Auth:      Azure AD OAuth + token paste
```

### System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     React UI (:5173)                          │
│  ConnectTab │ TracesTab │ WorkflowTab │ FindingsTab           │
│  SimulationTab │ ValidationTab │ ArtifactsTab │ TrendingTab   │
│  mathModel.js (pure sync JS, <100ms updates)                 │
│  MS Learn enrichment │ Auto-save history │ Schedule mgmt      │
└────────────────────────┬─────────────────────────────────────┘
                         │ fetch() to /api/*
┌────────────────────────▼─────────────────────────────────────┐
│               Express Proxy (:3001)                           │
│  /api/health │ /api/agent │ /api/models │ /api/sample         │
│  /api/analyze │ /api/reset │ /api/validate (SSE)              │
│  /api/pdf │ /api/fabric/* │ /api/fabric/xmla-collect          │
│  /api/mslearn/* │ /api/schedules │ /api/history               │
│  Azure AD + API Key auth │ Per-agent model routing            │
└────────────────────────┬─────────────────────────────────────┘
                         │ subprocess spawn
┌────────────────────────▼─────────────────────────────────────┐
│               Python Backend                                  │
│  agents/ — 12-agent pipeline (38 deterministic + 500 RAG)     │
│  knowledge/ — ChromaDB RAG (540 chunks: 40 docs + 500 issues) │
│  knowledge/ — MS Learn integration (12 articles, 70+ practices)│
│  collector/ — Fabric API + XMLA (Admin Scanner API)           │
│  synthetic/ — Monte Carlo, validation, query simulator        │
│  sample_dataset/ — 31 scenarios, 10 core healthcare agents     │
└──────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `agents/pipeline.py` | Main 12-agent orchestration. Spawns agents in parallel where possible. |
| `agents/prompts.py` | All agent prompt templates with `{variable}` substitution |
| `agents/schema_checks.py` | Schema Agent — 11 deterministic rules |
| `agents/dax_checks.py` | DAX Agent — 9 deterministic rules |
| `agents/dax_expression_checks.py` | DAX Expression Agent — 10 deterministic rules (regex-based) |
| `agents/execution_checks.py` | Execution Agent — 9 deterministic rules |
| `agents/xmla_checks.py` | XMLA Agent — 7 deterministic rules |
| `collector/fabric_collector.py` | Real Fabric Data Agent collection via `/chat` API |
| `collector/xmla_collector.py` | XMLA metadata collection via Admin Scanner API |
| `synthetic/monte_carlo_engine.py` | 500-iteration simulation engine |
| `client/src/components/SimulationTab.jsx` | Client-side Monte Carlo math model (<100ms) |
| `server/proxy.js` | Express proxy with Azure AD auth, per-model routing, retry logic |
| `sample_dataset/build_sample.py` | Builds sample.db with 25 known issues for testing |
| `scripts/fabric_notebook_create_agents.py` | Creates all 10 models + agents in Fabric |
| `scripts/create_lakehouse_tables_notebook.py` | PySpark notebook to create all lakehouse tables |

### Data Flow

1. **Connect** → User pastes Fabric token or signs in via OAuth
2. **Discover** → Analyzer lists workspace items, scans agents (publish status)
3. **Collect** → LLM generates 50 domain-specific questions from the semantic model schema → sends to Data Agent `/chat` API in parallel → captures latency traces with phase breakdowns
4. **Analyze** → 12-agent pipeline runs (38 deterministic rules first, then LLM enhancement)
5. **Simulate** → Monte Carlo engine projects latency reduction per fix (500 iterations)
6. **Remediate** → Paste-ready artifacts generated (optimized instructions, verified answers, schema scope)
7. **Validate** → Before/after comparison with fix application
8. **Export** → PDF report via Puppeteer

---

## 10. Step-by-Step Recreation Guide <a name="recreation-guide"></a>

### Prerequisites

- A Microsoft Fabric workspace with **Contributor** or **Admin** access
- Fabric capacity **F2 or higher** (F8 recommended for testing)
- A Fabric **Lakehouse** created in the workspace
- A Fabric **Notebook** attached to the workspace
- `az` CLI installed for token generation

### Step 1: Get Your Workspace and Lakehouse IDs

1. Open your Fabric workspace in the browser
2. The URL contains the workspace ID: `https://app.fabric.microsoft.com/groups/<WORKSPACE_ID>/...`
3. Click on your Lakehouse → the URL contains the lakehouse ID
4. Get the SQL endpoint:
   - In Lakehouse settings → SQL analytics endpoint → copy the endpoint URL
   - Format: `<random>.datawarehouse.fabric.microsoft.com`

### Step 2: Create Lakehouse Tables (PySpark Notebook)

1. Open your Fabric workspace
2. Create a new **Notebook**
3. Attach it to your lakehouse
4. Paste the contents of `scripts/create_lakehouse_tables_notebook.py` into Cell 1

**What to change at the top of the notebook:**

```python
# METADATA ********************
# META {
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "<YOUR_LAKEHOUSE_ID>",           # ← Change this
# META       "default_lakehouse_name": "<YOUR_LAKEHOUSE_NAME>",    # ← Change this
# META       "default_lakehouse_workspace_id": "<YOUR_WORKSPACE_ID>" # ← Change this
# META     }
# META   }
# META }
```

5. Run all cells — creates **71 tables** with ~809,214 total rows across 10 healthcare scenarios
6. Verify: `spark.sql("SHOW TABLES").show()` should list all 71 tables

### Step 3: Create Semantic Models + Data Agents

**Option A: Fabric Notebook (Recommended — uses built-in auth)**

1. Create another Notebook in your workspace
2. Paste the contents of `scripts/fabric_notebook_create_agents.py`
3. Change the configuration block:

```python
# ============================================================================
# CONFIGURATION — Update these values
# ============================================================================
WORKSPACE_ID = "<YOUR_WORKSPACE_ID>"  # ← Change this
```

4. Run the notebook — creates 10 semantic models + 10 data agents (~2 minutes)

**Option B: Local Python Script (requires token)**

```bash
# Get a Fabric token
export FABRIC_TOKEN=$(az account get-access-token \
  --resource https://api.fabric.microsoft.com \
  --query accessToken -o tsv)

# Save token to file (scripts read from this path)
echo $FABRIC_TOKEN > ~/.fabric_token

# Edit the scripts with your IDs:
# In scripts/create_semantic_models.py, change:
#   WORKSPACE_ID = "<YOUR_WORKSPACE_ID>"
#   LAKEHOUSE_ID = "<YOUR_LAKEHOUSE_ID>"
#   LAKEHOUSE_SQL = "<YOUR_SQL_ENDPOINT>"

python3 scripts/create_semantic_models.py
```

**Option C: Direct Lake (requires lakehouse SQL endpoint)**

For Direct Lake models that read directly from lakehouse Delta tables, use `scripts/create_semantic_models.py` which creates partitions with `mode: "directLake"`. You'll need:

```python
WORKSPACE_ID = "<YOUR_WORKSPACE_ID>"
LAKEHOUSE_ID = "<YOUR_LAKEHOUSE_ID>"
LAKEHOUSE_SQL = "<YOUR_SQL_ENDPOINT>"  # e.g., "abc123.datawarehouse.fabric.microsoft.com"
```

### Step 4: Publish Data Agents

After creating the agents, they need to be **published** before they can accept chat queries:

1. Open each Data Agent in the Fabric portal
2. Click **Publish**
3. Wait for publish to complete (usually 30-60 seconds per agent)
4. The analyzer's agent scan will show publish status for each agent

### Step 5: Connect the Analyzer

```bash
# Clone and setup
git clone https://github.com/gregnatkatz/FabricAnalyzer.git
cd FabricAnalyzer
./setup.sh  # or: npm install && cd client && npm install && cd ../server && npm install && cd ..

# Configure LLM endpoint
cat > server/.env << EOF
LLM_ENDPOINT=https://<your-azure-openai>.openai.azure.com/openai/v1
LLM_MODEL=gpt-5.4
LLM_API_KEY=<your-api-key>
EOF

# Start servers
npm run dev

# Get Fabric token
az login
az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv
```

1. Open `http://localhost:5173`
2. Paste the Fabric token on the Connect tab
3. Enter your workspace ID → agents appear in the dropdown
4. Select an agent → click Collect (50 questions, ~1 min)
5. Go to Workflow → Run Analysis (12-agent pipeline, ~5-10 min)
6. Review Findings → Simulation → Artifacts → Export PDF

---

## 11. Lakehouse Tables Notebook (PySpark) <a name="lakehouse-notebook"></a>

The full notebook code is in `scripts/create_lakehouse_tables_notebook.py`. Here's what it creates:

### Tables by Scenario

**Scenario 22: LOS (Clinical Inpatient)** — Tables created by `fabric_notebook_create_agents.py` directly via model definition. The LOS model uses these 18 table references (5 core + 13 overhead).

**Scenario 23: Revenue Cycle (716 rows)**

| Table | Schema | Rows |
|-------|--------|------|
| `claims` | claim_id, patient_id, encounter_id, payer_id, submitted_amount, submit_date, claim_status, cpt_code, diagnosis_code | 200 |
| `denials` | denial_id, claim_id, denial_reason, denial_date, appeal_status, denied_amount | 68 |
| `payments` | payment_id, claim_id, payment_amount, adjustment_amount, payment_date, payer_name | 68 |
| `charges` | charge_id, encounter_id, charge_amount, charge_date, department, cpt_code | 200 |
| `ar_aging` | ar_id, payer_id, days_outstanding, outstanding_amount, bucket | 100 |
| `payer_contracts` | contract_id, payer_id, payer_name, rate_type, effective_date | 20 |
| `ar_aging_archive` | ar_id, payer_id, days_outstanding, outstanding_amount, archive_date | 60 |

**Scenario 24: Workforce (1,072 rows)**

| Table | Schema | Rows |
|-------|--------|------|
| `staff_roster` | staff_id, name, department, role, hire_date, termination_date, status, fte_status | 160 |
| `shift_assignments` | shift_id, staff_id, shift_date, scheduled_hours, actual_hours, unit | 400 |
| `productivity_metrics` | metric_id, staff_id, metric_date, patients_seen, procedures_done, rvu_total | 200 |
| `overtime_log` | overtime_id, staff_id, overtime_date, overtime_hours, reason, approved_by | 100 |
| `certifications` | cert_id, staff_id, cert_name, expiry_date, status | 120 |
| `time_off_requests` | request_id, staff_id, request_date, days_requested, type, status | 80 |
| `department_budget` | budget_id, department, fiscal_year, allocated_fte, salary_budget | 12 |

**Scenario 25: Supply Chain (680 rows)**

| Table | Schema | Rows |
|-------|--------|------|
| `inventory` | item_id, item_name, category, on_hand_qty, reorder_point, unit_cost, location | 120 |
| `purchase_orders` | po_id, item_id, vendor_id, ordered_qty, filled_qty, order_date, status | 160 |
| `vendors` | vendor_id, vendor_name, list_price, lead_time_days, rating | 20 |
| `formulary` | formulary_id, drug_name, ndc_code, therapeutic_class, formulary_status | 60 |
| `drug_dispensing` | dispense_id, drug_name, patient_id, dispense_date, quantity, daily_usage | 200 |
| `par_levels` | par_id, item_id, location, par_qty, last_review_date | 60 |
| `contract_pricing` | contract_id, vendor_id, item_id, contract_price, effective_date | 60 |

**Scenario 26: ED Throughput (1,720 rows)**

| Table | Schema | Rows |
|-------|--------|------|
| `ed_visits` | visit_id, patient_id, arrival_time, triage_time, provider_assign, depart_time, disposition, acuity, chief_complaint | 300 |
| `ed_orders` | order_id, visit_id, order_type, order_time, complete_time, status | 400 |
| `ed_staffing` | staff_id, shift_date, role, hours_worked, patients_assigned | 120 |
| `bed_tracker` | bed_id, unit, status, patient_id, assign_time, release_time | 80 |
| `ed_vitals` | vital_id, visit_id, vital_type, value, recorded_time | 400 |
| `ed_imaging` | imaging_id, visit_id, modality, order_time, result_time, finding | 120 |
| `ed_labs` | lab_id, visit_id, test_name, order_time, result_time, result_value | 300 |

**Scenario 27: Readmission Risk (1,540 rows)**

| Table | Schema | Rows |
|-------|--------|------|
| `admissions` | admission_id, patient_id, admit_date, discharge_date, is_readmission, days_to_readmit, discharge_disposition, drg_code | 240 |
| `risk_scores` | score_id, patient_id, readmit_risk_score, score_date, model_version | 240 |
| `social_determinants` | sdoh_id, patient_id, housing_status, food_insecurity, transportation_access, insurance_type | 200 |
| `interventions` | intervention_id, patient_id, intervention_type, start_date, outcome, provider_id | 160 |
| `diagnoses` | diagnosis_id, patient_id, icd10_code, description, diagnosis_date, is_primary | 300 |
| `patient_demographics` | patient_id, patient_name, date_of_birth, gender, zip_code, primary_language | 400 |

**Scenario 28: Surgical Outcomes (1,530 rows)**

| Table | Schema | Rows |
|-------|--------|------|
| `surgical_cases` | case_id, patient_id, surgeon_id, procedure_name, case_date, scheduled_duration, actual_duration, case_class | 200 |
| `complications` | complication_id, case_id, complication_type, severity, detected_date | 40 |
| `or_utilization` | util_id, or_room, case_date, allocated_minutes, used_minutes, turnover_minutes | 160 |
| `surgeon_directory` | surgeon_id, surgeon_name, specialty, department | 30 |
| `surgical_supplies` | supply_id, case_id, item_name, quantity, unit_cost | 300 |
| `anesthesia_records` | record_id, case_id, anesthesia_type, start_time, end_time, provider_id | 200 |
| `case_log` | log_id, case_id, event_type, event_time, notes | 400 |

**Scenario 29: Infection Control (736 rows)**

| Table | Schema | Rows |
|-------|--------|------|
| `hai_events` | event_id, patient_id, infection_type, onset_date, unit, organism, hai_category | 80 |
| `surveillance_cultures` | culture_id, patient_id, specimen_type, collection_date, organism, susceptibility | 120 |
| `device_days` | device_id, unit, device_type, report_date, device_count, patient_days | 96 |
| `hand_hygiene` | observation_id, unit, observer, observation_date, compliant, role_observed | 200 |
| `antibiotic_usage` | usage_id, patient_id, antibiotic_name, start_date, end_date, route, dose | 120 |
| `environmental_rounds` | round_id, unit, round_date, score, deficiencies, inspector | 60 |
| `isolation_precautions` | precaution_id, patient_id, precaution_type, start_date, end_date, unit | 60 |

**Scenario 30: Nursing Quality (1,004 rows)**

| Table | Schema | Rows |
|-------|--------|------|
| `falls` | fall_id, patient_id, fall_date, unit, injury_level, with_injury, fall_type | 70 |
| `pressure_injuries` | pi_id, patient_id, onset_date, stage, location, unit, is_hapi | 40 |
| `nurse_assessments` | assessment_id, patient_id, assessment_date, braden_score, morse_score, pain_score | 200 |
| `patient_satisfaction` | survey_id, unit, survey_date, overall_score, nurse_communication, responsiveness | 60 |
| `safety_events` | event_id, patient_id, event_date, event_type, severity, unit | 80 |
| `unit_census` | census_id, unit, census_date, patient_days, admissions, discharges | 144 |
| `workforce` | staff_id, unit, role, shift, fte | 100 |
| `staffing_hours` | staffing_id, unit, staffing_date, rn_hours, cna_hours, agency_hours | 120 |
| `restraints` | restraint_id, patient_id, restraint_date, type, duration_hours, unit | 30 |
| `education_compliance` | compliance_id, staff_id, course_name, completion_date, status | 160 |

**Scenario 31: Patient Safety (406 rows)**

| Table | Schema | Rows |
|-------|--------|------|
| `event_reports` | event_id, patient_id, event_date, event_type, harm_level, department, reporter_role, description | 120 |
| `root_cause_analyses` | rca_id, event_id, start_date, status, root_cause, team_lead | 40 |
| `improvement_actions` | action_id, rca_id, action_description, due_date, status, responsible_party | 80 |
| `mortality_reviews` | review_id, patient_id, death_date, review_date, preventability, review_committee | 30 |
| `peer_review` | review_id, provider_id, case_id, review_date, outcome, reviewer_id | 50 |
| `claims_data` | claim_id, patient_id, claim_date, claim_type, settlement_amount, status | 24 |
| `psi_indicators` | psi_id, indicator_code, numerator, denominator, rate, report_period | 48 |
| `safety_culture_survey` | survey_id, department, survey_date, teamwork_score, reporting_score, management_score, response_rate | 24 |

---

## 12. Semantic Model & Agent Creation Scripts <a name="creation-scripts"></a>

### Script Overview

| Script | What It Creates | Auth Method |
|--------|----------------|-------------|
| `scripts/fabric_notebook_create_agents.py` | 10 semantic models + 10 data agents | Fabric Notebook built-in auth (`notebookutils`) |
| `scripts/create_semantic_models.py` | 9 semantic models + 9 agents (Direct Lake) | Token from `~/.fabric_token` |
| `scripts/create_data_agents.py` | 9 data agents with multi-part definition | Token from `~/.fabric_token` |
| `scripts/create_lakehouse_tables_notebook.py` | 71 lakehouse tables (PySpark) | Fabric Notebook built-in auth |

### Agent Definition Structure

Each Data Agent is created with this multi-part definition:

```
Files/Config/data_agent.json                          ← Agent schema metadata
Files/Config/draft/stage_config.json                  ← Instructions (AI instructions text)
Files/Config/draft/<datasource>/datasource.json       ← Lakehouse connection
Files/Config/publish_info.json                        ← Description for publishing
Files/Config/published/stage_config.json              ← Published instructions (same as draft)
Files/Config/published/<datasource>/datasource.json   ← Published datasource (same as draft)
```

The datasource folder name follows the pattern: `lakehouse-tables-<lakehouse_name>`

### Semantic Model Definition

Each model uses a TMSL `model.bim` file with:
- `compatibilityLevel: 1604`
- Tables with `directLake` partitions pointing to lakehouse entities
- Measures added to the first table
- An M expression connecting to the lakehouse SQL endpoint

---

## 13. What to Change for Your Own Workspace <a name="parameterization"></a>

### Configuration Checklist

When recreating in a different workspace, update these values:

| Parameter | Where to Find It | Files to Update |
|-----------|-----------------|----------------|
| **WORKSPACE_ID** | URL: `https://app.fabric.microsoft.com/groups/<WORKSPACE_ID>/...` | `fabric_notebook_create_agents.py` (line 27), `create_semantic_models.py` (line 9), `create_data_agents.py` (line 6) |
| **LAKEHOUSE_ID** | Lakehouse URL or Properties pane in Fabric portal | `create_semantic_models.py` (line 10), `create_data_agents.py` (line 7), notebook metadata block |
| **LAKEHOUSE_NAME** | Display name of your lakehouse (e.g., "lhkatz") | `create_data_agents.py` (line 8), notebook metadata block |
| **LAKEHOUSE_SQL** | Lakehouse → Settings → SQL analytics endpoint | `create_semantic_models.py` (line 11) |
| **Fabric Token** | `az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv` | `~/.fabric_token` for local scripts; automatic in Fabric Notebooks |

### Token Commands

```bash
# Azure login (one-time)
az login

# Get Fabric token (expires in ~1 hour)
az account get-access-token \
  --resource https://api.fabric.microsoft.com \
  --query accessToken -o tsv

# Save to file for scripts
az account get-access-token \
  --resource https://api.fabric.microsoft.com \
  --query accessToken -o tsv > ~/.fabric_token
```

### Quick Substitution (sed)

```bash
# Replace workspace ID across all scripts
OLD_WS="b79e8116-8374-45ed-883d-853bc561842b"
NEW_WS="<your-workspace-id>"
sed -i "s/$OLD_WS/$NEW_WS/g" scripts/*.py

# Replace lakehouse ID
OLD_LH="c59beb7a-757c-4ce4-a002-d9c58f15d492"
NEW_LH="<your-lakehouse-id>"
sed -i "s/$OLD_LH/$NEW_LH/g" scripts/*.py

# Replace lakehouse name
sed -i 's/lhkatz/<your-lakehouse-name>/g' scripts/*.py

# Replace SQL endpoint
OLD_SQL="nkhahdl5to4ezo6p5bg76flepa-c2az5n3uqpwulcb5qu54kymefm.datawarehouse.fabric.microsoft.com"
NEW_SQL="<your-sql-endpoint>"
sed -i "s/$OLD_SQL/$NEW_SQL/g" scripts/*.py
```

### Full Recreation Sequence

```bash
# 1. Login
az login

# 2. Get token
export FABRIC_TOKEN=$(az account get-access-token \
  --resource https://api.fabric.microsoft.com \
  --query accessToken -o tsv)
echo $FABRIC_TOKEN > ~/.fabric_token

# 3. Create lakehouse tables (in Fabric Notebook — paste notebook content and run)
#    → Creates 71 tables with ~809K rows

# 4. Create semantic models + data agents
python3 scripts/create_semantic_models.py
#    → Creates 9 Direct Lake semantic models + 9 data agents

# 5. For LOS_Bad_Agent specifically (included in fabric_notebook_create_agents.py):
python3 scripts/fabric_notebook_create_agents.py
#    → Creates all 10 models + agents including LOS_Bad_Agent

# 6. Publish agents (manual step in Fabric portal)
#    Open each agent → click Publish

# 7. Connect analyzer
cd FabricAnalyzer
./setup.sh
npm run dev
# Open http://localhost:5173 → paste token → select workspace → analyze
```

---

## Appendix: Sample Dataset (Offline Testing)

The sample dataset (`sample_dataset/build_sample.py`) creates a self-contained SQLite database with 25 known issues embedded for acceptance testing without needing a real Fabric workspace. It uses:

- **1 model**: "Hospital Operations Model" (2,048 MB, Import mode)
- **32 tables**: 8 fact tables, 8 dimension tables, 4 staging tables, 3 archive tables, 3 system tables, 1 bridge table, 5 miscellaneous
- **18 measures**: Including duplicate names, fuzzy duplicates, nested CALCULATE, iterators, CROSSJOIN, unsafe division, FILTER on full table, ALL without ALLSELECTED, excessive length, HASONEVALUE, hardcoded dates
- **10 traces**: Each embedding specific known issues (high retries, physician visible, outlier >45s, TOPN absent, etc.)
- **XMLA stats**: Column stats (high cardinality, large storage, high segments) and relationship stats (bidirectional, many-to-many, inactive)

Run offline: `python3 sample_dataset/build_sample.py` → produces `sample_dataset/sample.db`

---

*Built by Greg Katz — BrakeKat Studios*
*Repository: https://github.com/gregnatkatz/FabricAnalyzer*
*PR: https://github.com/gregnatkatz/FabricAnalyzer/pull/15*
