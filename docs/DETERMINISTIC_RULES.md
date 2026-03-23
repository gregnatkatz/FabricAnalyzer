# Deterministic Rules Reference

FabricAnalyzer uses 38 deterministic rules that run without any LLM call. These rules provide baseline detection of common Fabric Data Agent latency issues, ensuring the tool produces actionable findings even without Azure AI access.

## Overview

| Agent | Rule Count | Data Source | Detection Scope |
|-------|-----------|-------------|-----------------|
| Schema Agent | 11 | `agent_config`, `tables`, `measures`, `columns` | Model structure and configuration |
| DAX Expression Agent | 10 | `measures.expression` | Measure DAX expression anti-patterns |
| DAX Agent | 9 | `traces` (per-trace + global) | DAX generation patterns and routing |
| Execution Agent | 9 | `traces`, `cu_metrics`, `models`, `tables` | Runtime performance and infrastructure |
| XMLA Agent | 7 | `column_stats`, `relationship_stats` | Deep model analysis (VertiPaq, relationships, orphaned columns) |

Combined acceptance test detection rate: **80% (20/25 known issues)**, false positive rate: **15% (4/26)**.

The DAX Expression Agent runs 10 deterministic regex-based rules on `measures.expression` fields, detecting anti-patterns without requiring XMLA access or LLM calls.

---

## Schema Agent Rules (11)

### Rule S1: Instruction Character Limit Exceeded

- **Condition**: `agent_config.instr_chars > 4800`
- **Severity**: CRITICAL
- **Impact**: 8000ms
- **Why**: Fabric Data Agent silently truncates instructions beyond 4800 characters. Truncation destroys routing rules, metric definitions, and domain terminology, causing every query to pay full NL-to-DAX cost with no guidance.
- **Fix**: Trim instructions to under 3,800 characters using LLM summarization. Preserve routing rules, metric definitions, and domain terminology. Remove verbose examples and redundant explanations.
- **Example finding**: `Instruction character limit exceeded: 5200 chars (limit: 4800)`

### Rule S2: Instructions Near Limit

- **Condition**: `agent_config.instr_chars > 4000` (and <= 4800)
- **Severity**: HIGH
- **Impact**: 4000ms
- **Why**: Close to truncation threshold. Edge cases with certain characters or encodings may trigger silent truncation.
- **Fix**: Trim instructions to under 3,800 characters.

### Rule S3: Extreme Schema Scope Bloat

- **Condition**: `agent_config.tables_checked > 30`
- **Severity**: CRITICAL
- **Impact**: 8000ms
- **Why**: The Data Agent must resolve schema for every checked table on every query. At 30+ tables, schema resolution alone takes ~8 seconds, dominating total latency.
- **Fix**: Reduce to 12 core tables via AI Data Schema (Prep for AI). Remove staging, archive, temp, and system tables.
- **Example finding**: `Extreme schema scope bloat: 42 tables checked`

### Rule S4: High Schema Scope Bloat

- **Condition**: `agent_config.tables_checked > 20` (and <= 30)
- **Severity**: HIGH
- **Impact**: 4800ms
- **Fix**: Reduce table count via AI Data Schema.

### Rule S5: Zero Verified Answers

- **Condition**: `agent_config.va_count == 0`
- **Severity**: HIGH
- **Impact**: 6000ms
- **Why**: Verified answers bypass the NL-to-DAX engine for matched queries. Without any, every KPI query pays the full generation cost (~6s for complex queries).
- **Fix**: Add 8+ verified answer DAX patterns for high-frequency KPI queries (simple aggregates, filtered counts, rankings).
- **Example finding**: `Zero verified answers configured`

### Rule S6: Low Verified Answers

- **Condition**: `agent_config.va_count < 5` (and > 0)
- **Severity**: MEDIUM
- **Impact**: 3000ms
- **Fix**: Add more verified answers for common KPI queries.

### Rule S7: Exact Duplicate Measure Names

- **Condition**: Two or more measures with identical names
- **Severity**: CRITICAL
- **Impact**: 5000ms
- **Why**: When the Data Agent encounters ambiguous measure names, it picks randomly or falls back to retry logic. This causes unpredictable results and wasted retries.
- **Fix**: Rename or remove duplicate measures. Use `_v2` or `_legacy` suffixes for deprecated versions, or hide them from the AI Data Schema.
- **Example finding**: `Exact duplicate measure name: "Total Revenue"`

### Rule S8: Fuzzy Duplicate Measures

- **Condition**: Two measures with >85% character-level similarity
- **Severity**: HIGH
- **Impact**: 2000ms
- **Why**: Near-identical names (e.g., "Total Revenue" vs "TotalRevenue") force extra LLM reasoning on every ambiguous query.
- **Fix**: Clarify measure names or add descriptions to disambiguate.
- **Example finding**: `Fuzzy duplicate measures: "Total Revenue" vs "TotalRevenue" (92% similar)`

### Rule S9: Missing Table Descriptions

- **Condition**: More than 30% of tables have no description
- **Severity**: MEDIUM
- **Impact**: 1500ms
- **Why**: Without descriptions, the LLM guesses table purpose from name alone, leading to misrouting.
- **Fix**: Add descriptions to all tables in the semantic model.

### Rule S10: Hidden Columns in Model

- **Condition**: Any column with `is_hidden = true`
- **Severity**: MEDIUM
- **Impact**: 1000ms
- **Why**: Hidden columns may be referenced by verified answer DAX or routing rules, causing silent failures when the agent cannot resolve them.
- **Fix**: Verify no verified answer DAX references hidden columns.

### Rule S11: Schema/Agent Table Mismatch

- **Condition**: `agent_config.tables_checked != len(tables)`
- **Severity**: HIGH
- **Impact**: 3000ms
- **Why**: Prep for AI table selection differs from the actual semantic model table count. This causes unpredictable routing as the agent sees a different schema than expected.
- **Fix**: Align Prep for AI table selection with intended agent scope.

---

## DAX Expression Agent Rules (10)

These rules analyze the `expression` field of each measure in the semantic model using regex pattern matching. They detect DAX anti-patterns that cause latency, incorrect results, or silent failures in Data Agent scenarios.

### Rule EX-1: Nested CALCULATE Depth > 2

- **Condition**: Expression contains more than 2 `CALCULATE(` calls
- **Severity**: HIGH
- **Impact**: `depth * 800ms`
- **Why**: Deep CALCULATE nesting causes exponential filter context expansion. Each nested CALCULATE multiplies the filter evaluation work.
- **Fix**: Flatten CALCULATE nesting using VAR/RETURN pattern to precompute intermediate results.

### Rule EX-2: Iterator on Large Table

- **Condition**: `SUMX`, `AVERAGEX`, `COUNTX`, `MAXX`, `MINX`, `RANKX`, or `PRODUCTX` scanning a table starting with "Fact" or "Dim"
- **Severity**: HIGH
- **Impact**: 2500ms
- **Why**: Row-by-row iteration on fact/dimension tables is extremely expensive. These functions evaluate an expression for every row.
- **Fix**: Replace iterator with aggregation function (SUM, AVERAGE) where possible, or add TOPN guard.

### Rule EX-3: Unsafe Division

- **Condition**: Expression uses bare `/` operator without `DIVIDE()` wrapper
- **Severity**: MEDIUM
- **Impact**: 0ms (correctness, not latency)
- **Why**: Bare division risks divide-by-zero errors at runtime, causing query failures.
- **Fix**: Replace `A / B` with `DIVIDE(A, B, 0)` for divide-by-zero safety.

### Rule EX-4: FILTER on Full Table

- **Condition**: `FILTER(TableName, ...)` where TableName is not VALUES/ALL/ALLSELECTED/DISTINCT
- **Severity**: HIGH
- **Impact**: 1800ms
- **Why**: FILTER scans every row of the table. Direct predicates in CALCULATE push filters down to the engine level.
- **Fix**: Replace `FILTER(Table, ...)` with `CALCULATE(..., Table[Column] = Value)` for predicate pushdown.

### Rule EX-5: Cartesian Product Risk

- **Condition**: Expression contains `CROSSJOIN(` or `GENERATE(`
- **Severity**: CRITICAL
- **Impact**: 5000ms
- **Why**: CROSSJOIN/GENERATE creates cartesian products that can explode row counts exponentially.
- **Fix**: Replace with SUMMARIZE or TREATAS for controlled expansion.

### Rule EX-6: ALL() Without ALLSELECTED

- **Condition**: Expression uses `ALL()` inside `CALCULATE()` without `ALLSELECTED()`
- **Severity**: MEDIUM
- **Impact**: 0ms (correctness, not latency)
- **Why**: ALL() removes all filters, ignoring user slicer selections. In Data Agent scenarios, this causes unexpected results.
- **Fix**: Use ALLSELECTED() instead of ALL() to preserve user filter context.

### Rule EX-7: Excessive Expression Length

- **Condition**: Expression length > 500 characters
- **Severity**: MEDIUM
- **Impact**: 600ms
- **Why**: Complex measures increase NL2DAX generation time as the LLM must reason about longer expressions.
- **Fix**: Break into smaller sub-measures using VAR/RETURN or helper measures.

### Rule EX-8: Single-Select Dependency

- **Condition**: Expression uses `SELECTEDVALUE()` or `HASONEVALUE()`
- **Severity**: MEDIUM
- **Impact**: 0ms (correctness, not latency)
- **Why**: Measure depends on single-select filter context. In Data Agent scenarios where filter context is dynamic, this may return BLANK unexpectedly.
- **Fix**: Add fallback logic: `IF(HASONEVALUE(...), SELECTEDVALUE(...), DEFAULT)`.

### Rule EX-9: Hardcoded Date Literals

- **Condition**: Expression contains hardcoded 4-digit year values (e.g., `YEAR([Date]) = 2024`, `[FiscalYear] = 2023`)
- **Severity**: CRITICAL
- **Impact**: 9999ms (sentinel — always sorts to top of findings list)
- **Why**: Once the current year advances past the hardcoded value, the measure silently returns BLANK. Queries succeed with no error, but the Data Agent returns empty results. This is the classic "demo-killer" — a measure that worked last quarter stops working with no visible error.
- **Fix**: Replace hardcoded years with dynamic expressions: `YEAR(TODAY())`, `YEAR(MAX(DateTable[Date]))`, or a fiscal year parameter. Never use a literal 4-digit year in a measure used beyond the current reporting period.
- **Example finding**: `Hardcoded date literal(s) in measure "Revenue YTD": 2024`

### Rule EX-10: USERELATIONSHIP Direction Validation

- **Condition**: Expression contains `USERELATIONSHIP(ColA, ColB)`
- **Severity**: HIGH
- **Impact**: 4000ms
- **Why**: USERELATIONSHIP activates an inactive relationship. If the column order is reversed (many-side listed second instead of first), the relationship activates in the wrong direction. Aggregations return incorrect values with no error and no retry — a silent wrong answer.
- **Fix**: Verify many-side column is listed first: `USERELATIONSHIP(FactTable[FK], DimTable[PK])`. Confirm in Power BI Desktop → Model view → relationship properties.
- **Example finding**: `USERELATIONSHIP in measure "Sales by Ship Date" — direction validation required`

---

## DAX Agent Rules (9)

### Rule D1: High Retry Count

- **Condition**: `trace.retries > 2`
- **Severity**: CRITICAL
- **Impact**: `retries * 3100ms`
- **Why**: Each retry costs ~3100ms (DAX regeneration + execution attempt). More than 2 retries indicates a fundamental routing gap.
- **Fix**: Add routing rule for the targeted table.
- **Example finding**: `High retry count (4) on routing-gap trace`

### Rule D2: Single Retry

- **Condition**: `trace.retries == 1`
- **Severity**: MEDIUM
- **Impact**: 3100ms
- **Fix**: Review routing configuration.

### Rule D3: TOPN Absent on Cross-Entity Query

- **Condition**: No `TOPN` or `TOP` in DAX + query uses >1 table
- **Severity**: HIGH
- **Impact**: 4000ms
- **Why**: Cross-entity queries without row limits cause full table scans. On large tables (200K+ rows), this triggers timeouts.
- **Fix**: Add `TOP 25` few-shot examples to instructions.
- **Example finding**: `TOPN absent in cross-entity query across 3 tables`

### Rule D4: Wrong Table First

- **Condition**: `retries > 0` and multiple tables used
- **Severity**: HIGH
- **Impact**: `retries * 3100ms`
- **Why**: The agent targeted the wrong table initially, then retried against other tables. Indicates missing or ambiguous routing rules.
- **Fix**: Add explicit routing rule for secondary table.

### Rule D5: Physician/Provider Visible

- **Condition**: `trace.physician_visible == true`
- **Severity**: CRITICAL
- **Impact**: 0ms (governance, not latency)
- **Why**: Deployment blocker. Physician-level data visible in query results violates HIPAA/governance requirements.
- **Fix**: GOVERNANCE REQUIRED. Restrict physician-level data visibility via RLS and instruction guardrails.

### Rule D6: Measure Not Found

- **Condition**: DAX contains "not found" or "error"
- **Severity**: CRITICAL
- **Impact**: `total_ms` (entire query wasted)
- **Fix**: Fix measure reference in the semantic model.

### Rule D7: Empty Results, No Error

- **Condition**: `pass_fail == "fail"` and `total_ms < 20000`
- **Severity**: HIGH
- **Impact**: `total_ms`
- **Why**: Query completed fast but returned nothing. Likely wrong filter context or table routing.
- **Fix**: Review filter context and table routing.

### Rule D8: Ambiguous Time Filter

- **Condition**: More than 2 traces reference date fields in DAX
- **Severity**: HIGH
- **Impact**: 2000ms
- **Why**: Multiple date fields (e.g., AdmitDate vs DischargeDate) cause the agent to pick the wrong one inconsistently.
- **Fix**: Clarify date field usage in instructions.

### Rule D9: NL2DAX/NL2SQL Cross-Contamination

- **Condition**: DAX contains both SQL patterns (`SELECT`, `FROM`, `WHERE`, `JOIN`) and DAX patterns (`EVALUATE`, `SUMMARIZE`)
- **Severity**: HIGH
- **Impact**: 3000ms
- **Why**: Instructions mix SQL and DAX few-shot examples, confusing the generation engine.
- **Fix**: Separate NL2DAX and NL2SQL few-shot examples in instructions.

---

## Execution Agent Rules (9)

### Rule E1: Outlier Trace

- **Condition**: `total_ms > 45000`
- **Severity**: CRITICAL
- **Impact**: `total_ms`
- **Why**: Any trace over 45 seconds indicates a severe compounding issue (typically retry + scope + DAX combined).
- **Fix**: Deep investigation required. Break down by phase and check for retry storms.

### Rule E2: Slow Trace

- **Condition**: `total_ms > 20000` (and <= 45000)
- **Severity**: HIGH
- **Impact**: `total_ms - 10000`
- **Fix**: Apply targeted fixes based on phase breakdown analysis.

### Rule E3: Execution Phase Dominant

- **Condition**: `bd_exec / total_ms > 0.35`
- **Severity**: HIGH
- **Impact**: `bd_exec`
- **Why**: More than 35% of latency is in VertiPaq/DirectQuery execution. Indicates large table scans, missing indexes, or Direct Lake framing issues.
- **Fix**: Apply V-Order optimization or check Direct Lake configuration.

### Rule E4: DAX Generation Dominant

- **Condition**: `bd_nldax / total_ms > 0.55`
- **Severity**: HIGH
- **Impact**: `bd_nldax`
- **Why**: More than 55% of latency is in NL-to-DAX generation. The bottleneck is LLM reasoning, not query execution.
- **Fix**: Add verified answers and simplify instructions to reduce generation time.

### Rule E5: Retry Dominant

- **Condition**: `retries * 3100 > total_ms * 0.4`
- **Severity**: HIGH
- **Impact**: `retries * 3100`
- **Why**: Retries account for 40%+ of total latency. A routing fix would halve response time.
- **Fix**: Add routing rules.

### Rule E6: Schema Lookup Dominant

- **Condition**: `bd_schema / total_ms > 0.25`
- **Severity**: HIGH
- **Impact**: `bd_schema`
- **Why**: More than 25% of latency is schema resolution. Too many tables in scope.
- **Fix**: Reduce schema scope to core tables only.

### Rule E7: High CU Throttling

- **Condition**: `cu_metrics.throttle_events > 50`
- **Severity**: CRITICAL
- **Impact**: 5000ms
- **Why**: Fabric capacity is saturated. All queries are being throttled regardless of optimization.
- **Fix**: Increase capacity units or optimize workload distribution.

### Rule E8: V-Order Not Confirmed

- **Condition**: Model storage mode contains "direct" or "lake"
- **Severity**: MEDIUM
- **Impact**: 2000ms
- **Why**: Direct Lake tables without V-Order lose 15-25% execution performance.
- **Fix**: Apply V-Order to Direct Lake tables.

### Rule E9: Direct Lake Framing Risk

- **Condition**: Table `row_count > 500,000` and Direct Lake storage mode
- **Severity**: HIGH
- **Impact**: 3000ms
- **Why**: Large tables near capacity limits may silently fall back to DirectQuery mode, which is significantly slower.
- **Fix**: Monitor for DirectQuery fallback; consider partitioning.

---

## XMLA Agent Rules (7)

These rules analyze `column_stats` and `relationship_stats` collected via DAX INFO functions (Strategy 1) or the Fabric Admin Scanner API (Strategy 2). They detect VertiPaq storage issues, relationship anti-patterns, and orphaned columns.

### Rule XM-1: High Cardinality Column

- **Condition**: `cardinality > 1,000,000`
- **Severity**: HIGH
- **Impact**: `cardinality / 100K * 100ms`
- **Why**: VertiPaq dictionary encoding is inefficient above 1M distinct values, increasing memory and query time.
- **Fix**: Consider bucketing or hashing the column to reduce cardinality, or exclude from model if unused.

### Rule XM-2: Large Column Storage

- **Condition**: `data_size_mb > 50`
- **Severity**: HIGH
- **Impact**: `size_mb * 20ms`
- **Why**: Large columns slow scan operations and increase memory pressure.
- **Fix**: Review if the column needs full precision — consider aggregation or removing unused columns.

### Rule XM-3: Bidirectional Cross-Filter

- **Condition**: Relationship has `cross_filter` = BothDirections/Both/Bidirectional
- **Severity**: HIGH
- **Impact**: 1500ms
- **Why**: Bidirectional cross-filtering causes VertiPaq to evaluate filters in both directions — exponential cost with multiple bidir relationships.
- **Fix**: Change to single-direction unless bidirectional is specifically required by a measure.

### Rule XM-4: Excessive Inactive Relationships

- **Condition**: More than 2 inactive relationships in model
- **Severity**: MEDIUM
- **Impact**: `count * 100ms`
- **Why**: Inactive relationships add model complexity without benefit unless used via USERELATIONSHIP().
- **Fix**: Remove those not referenced by USERELATIONSHIP() in any measure.

### Rule XM-5: High Segment Count

- **Condition**: `segment_count > 10`
- **Severity**: MEDIUM
- **Impact**: `segments * 50ms`
- **Why**: High segment count indicates suboptimal partitioning or very large table, reducing scan efficiency.
- **Fix**: Consider repartitioning or enabling V-Order optimization to reduce segment count.

### Rule XM-6: Many-to-Many Relationship

- **Condition**: Both sides of relationship have cardinality > 1
- **Severity**: CRITICAL
- **Impact**: 3000ms
- **Why**: Many-to-many relationships cause fan-out that multiplies row counts during queries.
- **Fix**: Add a bridge table to resolve the many-to-many, or use TREATAS for virtual relationships.

### Rule XM-7: Orphaned Column (0 Measure References)

- **Condition**: `reference_count == 0` (from INFO.CALCDEPENDENCY())
- **Severity**: HIGH (non-key columns) / MEDIUM (key-like columns)
- **Impact**: `size_mb * 15ms` (min 200ms) for non-key / 100ms for key-like
- **Why**: Column is physically present in the model yet never referenced by any measure, relationship, or calculated column. These are pure overhead — they consume VertiPaq memory and slow scan operations even though the Data Agent never touches them.
- **Fix**: Remove the column from the semantic model in Power BI Desktop (not just hide it — physical removal reclaims VertiPaq memory). If the column is needed for future use, move it to a staging layer instead.
- **Example finding**: `Orphaned column: FactEncounters.BatchID — never referenced by any measure`

> **XM-7 requires XMLA collection with INFO.CALCDEPENDENCY() data.**
> Fires only when `reference_count = 0` — columns where the DMV returned
> no data show `reference_count = -1` and are skipped. Key-like column names
> (containing id, key, pk, fk, code, guid, uuid) are downgraded to MEDIUM
> since they may be used as relationship join columns not captured by
> CALCDEPENDENCY.

---

## Finding Schema

Every finding from all agents uses this structure:

```json
{
  "issue": "Human-readable description of the finding",
  "severity": "CRITICAL | HIGH | MEDIUM | LOW",
  "evidence": "Technical evidence supporting the finding",
  "impact_ms": 5000,
  "fix": "Recommended remediation action",
  "agent_id": "schema | dax | dax_expression | execution | domain_intelligence | adversarial_probe"
}
```

Impact values are in milliseconds and represent the estimated latency contribution of the issue. Findings are persisted to the `findings` SQLite table and embedded into ChromaDB's `past_findings` collection for cross-session pattern detection.
