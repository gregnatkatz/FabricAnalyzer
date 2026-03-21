# Agent Reference

Detailed specification for each of the 9 agents in the FabricAnalyzer pipeline.

---

## Agent 1: Domain Intelligence

**File**: `agents/domain_intelligence.py`
**Type**: Rule-based (no LLM required) + optional LLM enhancement
**Purpose**: Classify the Data Agent's domain and generate targeted probe questions.

### Domain Classification

Uses keyword matching against table names, measure names, and column names to score across 8 domains:

| Domain | Signal Keywords |
|--------|----------------|
| CLINICAL_INPATIENT | encounter, admission, drg, los, discharge, physician, readmission |
| CLINICAL_QUALITY | sepsis, bundle, compliance, antibiotic, lactate, mortality |
| REVENUE_CYCLE | claim, denial, payer, ar, collection, billing, charge |
| WORKFORCE | staffing, hppd, nursing, agency, overtime, vacancy, shift |
| SUPPLY_CHAIN | inventory, vendor, purchase, contract, par, supply, spend |
| PATIENT_EXPERIENCE | hcahps, ganey, satisfaction, rounding, complaint, survey |
| OPERATIONAL | throughput, capacity, utilization, wait, flow, bed, turnaround |
| FINANCIAL | budget, variance, margin, cost, revenue, drg, contribution |

Confidence = best domain score / total signal count.

### Probe Question Generation

Generates 20 probe questions:
- **8 universal** questions (total count, filtered aggregate, ranking, time intelligence, KPI vs target, breakdown, system aggregate, trend)
- **12 domain-specific** questions based on actual measure names and table names from the semantic model

Each question has:
- `category`: e.g., `domain_kpi`, `cross_entity`, `secondary_table`
- `is_cross_entity`: Boolean flag for queries spanning multiple tables
- `hypothesis`: What the probe tests (e.g., "Tests routing to secondary table")
- `targets_table`: Expected primary table

### Config Issue Detection

Pre-screens `agent_config` for critical issues:
- Instruction char limit exceeded (>4800)
- Instructions near limit (>4000)
- Extreme schema scope bloat (>30 tables)
- High schema scope bloat (>20 tables)
- Zero or low verified answers

### Output

```json
{
  "domain": "CLINICAL_INPATIENT",
  "confidence": 0.85,
  "domain_scores": { "CLINICAL_INPATIENT": 6, "FINANCIAL": 1, ... },
  "probe_questions": [ { "question": "...", "category": "...", ... } ],
  "config_issues": [ "CRITICAL: Instruction char limit exceeded (5200 > 4800)" ],
  "findings": [ { "issue": "...", "severity": "CRITICAL", ... } ]
}
```

---

## Agent 2: Adversarial Probe

**File**: `agents/adversarial_probe.py`
**Type**: Rule-based (no LLM required)
**Purpose**: Analyze trace data against probe questions to build a statistical behavioral profile.

### BehavioralProfile

A structured evidence object that quantifies Data Agent behavior:

| Property | Description |
|----------|-------------|
| `retry_records` | List of traces with retries, including hypothesis and affected tables |
| `governance_gaps` | Traces where physician/provider data was visible |
| `topn_gaps` | Cross-entity queries missing TOPN guard |
| `outliers` | Traces exceeding 45s threshold |
| `routing_gaps` | Per-table retry counts suggesting missing routing rules |

### Calibration Alphas

The BehavioralProfile provides calibration factors (0.0-1.0) used by the Monte Carlo engine:

| Alpha | Calculation |
|-------|-------------|
| `retry_reduction_alpha` | `retry_rate * 0.5 + min(avg_retries / 5.0, 0.5)` |
| `routing_reduction_alpha` | `gap_count * 0.15 + total_gap_retries * 0.05` |
| `governance_risk_score` | `gap_count * 0.25` |
| `topn_reduction_alpha` | `topn_gap_count * 0.2` |
| `outlier_severity` | `worst_ms / 90000` |

### Findings Generated

- Retry summary (total retries across all traces)
- Routing gaps per table (confirmed when retries > 2)
- Governance violations (physician/provider data visible)
- TOPN gaps (cross-entity queries without row limits)
- Outlier count (traces > 45s)

### Output

```json
{
  "behavioral_profile": { "total_probes": 20, "total_retries": 8, ... },
  "behavioral_summary": "Probes: 20, Retries: 8, Governance gaps: 2, ...",
  "findings": [ { "issue": "...", "severity": "CRITICAL", ... } ]
}
```

---

## Agent 3: Schema Agent

**File**: `agents/schema_checks.py`
**Type**: Deterministic rules + optional LLM enhancement
**Purpose**: Analyze semantic model structure for latency-causing configuration issues.

### 11 Deterministic Rules

| # | Rule | Threshold | Severity | Impact |
|---|------|-----------|----------|--------|
| 1 | Instruction char limit exceeded | >4800 chars | CRITICAL | 8000ms |
| 2 | Instructions near limit | >4000 chars | HIGH | 4000ms |
| 3 | Extreme schema scope bloat | >30 tables | CRITICAL | 8000ms |
| 4 | High schema scope bloat | >20 tables | HIGH | 4800ms |
| 5 | Zero verified answers | va_count == 0 | HIGH | 6000ms |
| 6 | Low verified answers | va_count < 5 | MEDIUM | 3000ms |
| 7 | Exact duplicate measure names | exact match | CRITICAL | 5000ms |
| 8 | Fuzzy duplicate measures | >85% similarity | HIGH | 2000ms |
| 9 | Missing table descriptions | >30% null | MEDIUM | 1500ms |
| 10 | Hidden columns in model | any hidden | MEDIUM | 1000ms |
| 11 | Schema/agent table mismatch | count differs | HIGH | 3000ms |

### Name Similarity

Rule 8 uses a character-level similarity function:
```
similarity = (2 * matching_chars) / (len(a) + len(b))
```
Names are normalized (lowercase, remove spaces/underscores) before comparison.

### LLM Enhancement

When LLM is available, the Schema Agent prompt additionally analyzes:
- Cross-table relationship opportunities
- Naming convention inconsistencies
- Measure organization patterns
- Schema optimization beyond the 11 rules

ChromaDB query: `"fabric data agent schema design table scope description"`

---

## Agent 4: DAX Agent

**File**: `agents/dax_checks.py`
**Type**: Deterministic rules + optional LLM enhancement
**Purpose**: Analyze DAX generation patterns, retries, and routing behavior.

### 9 Deterministic Rules

| # | Rule | Threshold | Severity | Impact |
|---|------|-----------|----------|--------|
| 1 | High retry count | retries > 2 | CRITICAL | retries * 3100ms |
| 2 | Single retry | retries == 1 | MEDIUM | 3100ms |
| 3 | TOPN absent on cross-entity | >1 table, no TOP/TOPN | HIGH | 4000ms |
| 4 | Wrong table first | retries > 0 + multi-table | HIGH | retries * 3100ms |
| 5 | Physician/provider visible | physician_visible flag | CRITICAL | 0ms (governance) |
| 6 | Measure not found | "not found"/"error" in DAX | CRITICAL | total_ms |
| 7 | Empty results, no error | pass_fail=="fail" + <20s | HIGH | total_ms |
| 8 | Ambiguous time filter | >2 traces with date refs | HIGH | 2000ms |
| 9 | NL2DAX/NL2SQL contamination | SQL + DAX patterns mixed | HIGH | 3000ms |

### Per-Trace vs Global Rules

Rules 1-7 run **per trace** (each trace is evaluated independently).
Rules 8-9 run **globally** (across all traces in the session).

### Deduplication

Findings are deduplicated by the first 60 characters of the issue text to prevent flooding from traces that trigger the same rule.

### LLM Enhancement

ChromaDB query: `"fabric data agent DAX generation retry routing pattern"`

---

## Agent 5: Execution Agent

**File**: `agents/execution_checks.py`
**Type**: Deterministic rules + optional LLM enhancement
**Purpose**: Analyze query execution performance, phase breakdown, and infrastructure constraints.

### 9 Deterministic Rules

| # | Rule | Threshold | Severity | Impact |
|---|------|-----------|----------|--------|
| 1 | Outlier trace | >45000ms | CRITICAL | total_ms |
| 2 | Slow trace | >20000ms | HIGH | total_ms - 10000 |
| 3 | Execution phase dominant | bd_exec/total > 35% | HIGH | bd_exec |
| 4 | DAX generation dominant | bd_nldax/total > 55% | HIGH | bd_nldax |
| 5 | Retry dominant | retries*3100 > total*0.4 | HIGH | retries * 3100 |
| 6 | Schema lookup dominant | bd_schema/total > 25% | HIGH | bd_schema |
| 7 | High CU throttling | throttle_events > 50 | CRITICAL | 5000ms |
| 8 | V-Order not confirmed | Direct Lake mode | MEDIUM | 2000ms |
| 9 | Direct Lake framing risk | >500K rows + Direct Lake | HIGH | 3000ms |

### Phase Breakdown Fields

Each trace has latency split into phases:
- `bd_schema`: Schema resolution time (table lookup, metadata loading)
- `bd_nldax`: NL-to-DAX generation time (LLM reasoning)
- `bd_exec`: Query execution time (VertiPaq/DirectQuery)
- `bd_parse`: Parse/planning time
- `bd_synth`: Response synthesis time

### LLM Enhancement

ChromaDB query: `"fabric data agent execution latency CU throttling performance"`

---

## Agent 6: Synthesis Agent

**File**: `agents/pipeline.py` (inline, lines 335-358)
**Type**: LLM-only (no deterministic rules)
**Purpose**: Cross-correlate findings across all agents, rank by impact, assess demo readiness.

### Template Variables

The Synthesis prompt receives:
- `all_findings_json`: All findings from Agents 1-5
- `behavioral_evidence`: BehavioralProfile from Agent 2

### Output

- Stack-ranked findings by ms contribution
- Cross-model pattern detection
- **Demo Readiness Verdict**: `NOT READY` / `CONDITIONAL` / `READY`

### Fallback (No LLM)

When no LLM is available, the pipeline sorts findings by impact_ms descending and generates a deterministic summary.

---

## Agent 7: Monte Carlo Agent

**File**: `synthetic/monte_carlo_engine.py`
**Type**: Statistical simulation (no LLM)
**Purpose**: Project latency reduction from applying fixes using calibrated distributions.

### Simulation Parameters

- **Iterations**: 500 (configurable via `--n`)
- **Fix distributions**: Gaussian (mean, stddev) per fix per phase
- **Phase caps**: Schema 78%, DAX 82%, Execution 65%
- **Floor**: 1600ms minimum per trace

### Algorithm

```
for each iteration (500):
    for each trace:
        for each active fix:
            sample reduction from Gaussian(mean, stddev) per phase
        apply caps to cumulative reduction
        projected = parse + schema*(1-R) + dax*(1-R) + exec*(1-R) + synth
        projected = max(projected, 1600ms)
    record iteration average and P95
```

### Output

```json
{
  "n_iterations": 500,
  "baseline": { "avg_ms": 29000, "p95_ms": 45000 },
  "projected": { "p10": 12000, "p50": 15000, "p90": 19000 },
  "per_fix": {
    "verified_answers": { "p10": 18000, "p50": 20000, "p90": 23000, "reduction_ms": 9000 },
    ...
  },
  "variance_record": { "avg_stddev": 800, "p95_stddev": 2100 },
  "calibration": { "retry_alpha": 0.6, "routing_alpha": 0.3, ... }
}
```

### Persistence

Results are written to the `monte_carlo_results` SQLite table with 25+ columns including per-fix P50 values, confidence rating, and reduction percentage.

---

## Agent 8: Remediation Agent

**File**: `agents/pipeline.py` (inline, lines 372-390)
**Type**: LLM-only
**Purpose**: Generate actionable, paste-ready fix artifacts.

### Template Variables

- `all_findings_json`: All findings from Agents 1-7
- `mc_results_json`: Monte Carlo output with per-fix P50 values

### Generated Artifacts

1. **Optimized instructions** (<3800 chars, preserving routing rules)
2. **Verified answer DAX patterns** (for top KPI queries)
3. **Schema scope list** (tables to include/exclude in Prep for AI)
4. **DAX few-shot examples** (TOPN guards, routing hints)
5. **Prioritized action cards** (ordered by projected ms reduction)

---

## Agent 9: Validation Agent

**File**: `agents/pipeline.py` (inline, lines 393-437)
**Type**: LLM-only (with deterministic fallback)
**Purpose**: Validate fix effectiveness and produce final pipeline summary.

### Template Variables

- `fixes_applied`: Active fix list from Monte Carlo
- `baseline_results`: Pre-fix baseline metrics
- `postfix_results`: Projected post-fix metrics
- `delta_analysis`: Reduction percentages and confidence
- `resolution_status`: Critical/high counts, artifact availability

### Fallback

Without LLM, produces:
```
"Pipeline identified {N} findings. Monte Carlo projects {X}% latency reduction
(P50: {Y}ms). {Z} critical issues."
```
Plus effective fixes (reduction > 500ms) and ineffective fixes (reduction < 100ms).

---

## Agent Execution Order

All 9 agents run sequentially. The pipeline aborts early only if no traces are available. Agents 1-5 produce deterministic findings that work without LLM. Agents 6-9 produce richer output when LLM is available but fall back to deterministic summaries.

```
Agent 1 → domain, probe_questions
Agent 2 → behavioral_profile (uses probe_questions from Agent 1)
Agent 3 → schema_findings (uses db context)
Agent 4 → dax_findings (uses db context)
Agent 5 → execution_findings (uses db context + cu_metrics)
Agent 6 → synthesis (uses all_findings from 1-5 + behavioral_profile)
Agent 7 → monte_carlo (uses traces + behavioral_profile)
Agent 8 → remediation (uses all_findings + monte_carlo)
Agent 9 → validation (uses monte_carlo + synthesis)
```

Total pipeline time: ~2 minutes with live DeepSeek V3.2 Speciale (~2s per LLM call).
