# Architecture Reference

This document describes the internal architecture of FabricAnalyzer, covering the data flow from trace collection through the 9-agent analysis pipeline to PDF export.

## System Overview

```
                          User Browser
                              |
                     React UI (:5173)
                   7 tabs, mathModel.js
                              |
                        fetch /api/*
                              |
                  Express Proxy (:3001)
                   proxy.js (1482 lines)
                    /                \
          curl -> Azure AI      Python subprocess
          (DeepSeek V3.2)       (pipeline.py)
                                    |
                  +---------+-------+--------+
                  |         |       |        |
              ChromaDB   SQLite  agents/  synthetic/
              538 chunks  session  9 agents  Monte Carlo
```

### Three-Tier Stack

| Tier | Technology | Port | Role |
|------|-----------|------|------|
| Frontend | React 18 + Vite | 5173 | 7-tab UI, client-side math model, PDF report template |
| Backend | Express (Node.js) | 3001 | API proxy, LLM routing, session management, PDF rendering |
| Pipeline | Python 3 | subprocess | 9-agent analysis, deterministic rules, Monte Carlo simulation |

## Data Flow

### 1. Collection Phase

```
Fabric Workspace ──OAuth──> collector/fabric_collector.py
                                    |
                         Power BI REST API
                         - GET /datasets/{id}
                         - GET /datasets/{id}/tables
                         - GET /datasets/{id}/measures
                         - Capacity CU metrics
                                    |
                              SQLite session DB
                              (tables, measures, columns,
                               traces, agent_config, cu_metrics)
```

Alternatively, the Connect tab offers:
- **Sample Dataset**: Loads `sample_dataset/sample.db` with 25 pre-built known issues
- **Direct Collection**: `/api/fabric/collect-direct` accepts workspace ID, agent ID, agent name, and instructions directly (bypasses OAuth)
- **Auto-Trace Generation**: Detects domain from agent instructions and generates realistic traces with latency breakdowns

### 2. Analysis Phase (9-Agent Pipeline)

The pipeline is orchestrated by `agents/pipeline.py`, called from `proxy.js` via `child_process.spawn`. Each agent runs sequentially, with outputs feeding into subsequent agents.

```
Agent 1: Domain Intelligence
    Rule-based domain inference (8 domains)
    Generates 20 probe questions (8 universal + 12 domain-specific)
    LLM enhancement: hypothesis generation, additional probes
         |
Agent 2: Adversarial Probe
    Analyzes traces against probe questions
    Builds BehavioralProfile (retries, routing gaps, governance, TOPN, outliers)
    Calibration alphas for Monte Carlo
         |
Agent 3: Schema Agent
    11 deterministic rules (instruction limits, scope bloat, verified answers, duplicates)
    LLM enhancement: cross-table optimization, naming conventions
         |
Agent 4: DAX Agent
    9 deterministic rules (retries, TOPN, routing, governance, measure errors)
    LLM enhancement: anti-patterns, routing logic gaps
         |
Agent 5: Execution Agent
    9 deterministic rules (outliers, phase dominance, CU throttling, V-Order)
    LLM enhancement: bottleneck patterns, capacity planning
         |
Agent 6: Synthesis Agent (LLM-only)
    Stack-ranks all findings by ms contribution
    Detects cross-model patterns
    Issues demo readiness verdict: NOT READY / CONDITIONAL / READY
         |
Agent 7: Monte Carlo Agent
    500 iterations with calibrated distributions per fix
    P10/P50/P90 percentiles per fix and combined
    Variance tracking for confidence scoring
         |
Agent 8: Remediation Agent (LLM-only)
    Generates paste-ready artifacts:
    - Optimized instructions (<3800 chars)
    - Verified answer DAX patterns
    - Schema scope include/exclude list
    - DAX few-shot examples
    - Prioritized action cards
         |
Agent 9: Validation Agent (LLM-only)
    Assesses fix effectiveness from Monte Carlo + Synthesis
    Lists effective vs ineffective fixes
    Final pipeline summary
```

### 3. Simulation Phase (Client-Side)

The Simulation tab uses a **pure synchronous JavaScript math model** (`client/src/simulation/mathModel.js`) that updates in <100ms with no API calls:

```
traces[] + activeFixes[] ──> mathModel.simulate()
                                   |
                    Per-phase reduction factors
                    (schemaF, daxF, execF per fix)
                              |
                    Apply caps: schema 78%, dax 82%, exec 65%
                              |
                    Floor: minimum 1600ms per trace
                              |
                    Output: avgMs, outlierMs, passRate,
                            reductionPct, perFix breakdown
```

### 4. PDF Export

```
ArtifactsTab ──POST /api/pdf──> proxy.js
                                    |
                          buildReportHtml()
                          (inline HTML template)
                                    |
                          Puppeteer headless Chrome
                          page.setContent(html)
                          page.pdf({ format: 'A4' })
                                    |
                          Binary PDF response
```

## Storage

### SQLite (Per-Session)

Each analysis session creates a SQLite database in `server/data/`:

| Table | Purpose |
|-------|---------|
| `models` | Semantic model metadata (name, workspace, storage mode) |
| `tables` | Table inventory (name, row count, column count, descriptions) |
| `measures` | Measure inventory (name, DAX expression, descriptions) |
| `columns` | Column inventory (name, type, hidden flag) |
| `relationships` | Table relationships |
| `agent_config` | Data Agent configuration (instruction text, table count, VA count) |
| `traces` | Query traces with latency breakdowns (schema, DAX, execution phases) |
| `cu_metrics` | Capacity Unit consumption (AI CU, Query CU, throttle events) |
| `findings` | Analysis findings written by each agent |
| `monte_carlo_results` | Simulation output (P10/P50/P90, per-fix, calibration) |

### ChromaDB (Shared Knowledge Base)

Persistent vector store at `chroma_db/` with two collections:

| Collection | Chunks | Source |
|-----------|--------|--------|
| `microsoft_docs` | 538 | 38 scraped docs + 500 issue catalog entries |
| `past_findings` | Variable | Findings from previous analysis sessions |

Used for RAG grounding in LLM-backed agents (Schema, DAX, Execution, Synthesis, Remediation).

## LLM Integration

### Model Routing

The Express proxy supports per-model endpoint configuration:

```
Request -> /api/agent { modelOverride: "DeepSeek-V3.2-Speciale" }
                |
        getModelConfig(modelId)
                |
        MODEL_ENDPOINTS[modelId] || fallback to LLM_ENDPOINT
                |
        Azure OpenAI URL format:
        {base}/openai/deployments/{model}/chat/completions?api-version=2025-01-01-preview
                |
        curl -s -m 180 (execSync)
        (Node.js fetch hangs on Azure AI endpoints)
```

### Auth Modes

| Mode | Header | When |
|------|--------|------|
| API Key | `api-key: {key}` | `LLM_API_KEY` is set in `.env` |
| Azure AD | `Authorization: Bearer {token}` | No API key; uses `DefaultAzureCredential` |

### Why curl Instead of fetch

Node.js v22's native `fetch` and the `https` module both hang indefinitely when connecting to Azure AI endpoints. The workaround is `execSync('curl ...')` which completes reliably in ~1.6s. The request body is written to a temp file and cleaned up after.

## Deterministic Rules Engine

29 rules run without any LLM call, ensuring baseline analysis works even without Azure AI access:

| Agent | Rules | Examples |
|-------|-------|---------|
| Schema | 11 | Instruction char limit (>4800 CRITICAL), scope bloat (>30 CRITICAL), zero verified answers, duplicate measures, missing descriptions |
| DAX | 9 | High retry (>2 CRITICAL), TOPN absent on cross-entity, wrong table first, physician visible, NL2DAX/NL2SQL contamination |
| Execution | 9 | Outlier >45s (CRITICAL), slow >20s, execution/DAX/schema phase dominant, CU throttling, V-Order, Direct Lake framing |

Detection rate from acceptance tests: **80% (20/25)**, false positive rate: **4%**.

## 500-Issue Latency Catalog

`knowledge/issue_catalog.py` contains 500 known latency issues across 25 categories (20 each). Each issue has:
- `id`: ISS-0001 through ISS-0500
- `category`: One of 25 categories (SCHEMA_DESIGN, INSTRUCTION_TUNING, DAX_PATTERNS, etc.)
- `severity`: CRITICAL / HIGH / MEDIUM / LOW
- `description`: Detailed explanation of the issue
- `impact_ms`: Estimated latency impact in milliseconds
- `fix`: Recommended remediation
- `detection_hint`: Rule for automated detection

These are embedded into ChromaDB via `knowledge/embedder.py` and used for RAG grounding during LLM analysis.

## Monte Carlo Simulation

### Fix Distributions

Each fix has calibrated reduction factors per latency phase (mean, stddev):

| Fix | Schema | DAX | Execution |
|-----|--------|-----|-----------|
| instruction_trim | (0.05, 0.02) | (0.30, 0.08) | (0.02, 0.01) |
| schema_scope | (0.55, 0.12) | (0.05, 0.02) | (0.03, 0.01) |
| routing_rules | (0.02, 0.01) | (0.25, 0.10) | (0.05, 0.02) |
| verified_answers | (0.03, 0.01) | (0.60, 0.15) | (0.02, 0.01) |
| topn_guard | (0.01, 0.005) | (0.08, 0.03) | (0.30, 0.10) |
| measure_dedup | (0.02, 0.01) | (0.15, 0.05) | (0.01, 0.005) |
| vorder | (0.01, 0.005) | (0.01, 0.005) | (0.20, 0.06) |

### Phase Caps

Maximum cumulative reduction per phase:
- Schema: 78%
- DAX: 82%
- Execution: 65%

### Floor

Minimum projected latency per trace: **1600ms** (network + overhead floor).

### Calibration

The BehavioralProfile from Agent 2 provides calibration alphas:
- `retry_alpha`: Confidence in retry reduction (0.0-1.0)
- `routing_alpha`: Confidence in routing fix impact
- `governance_risk`: Risk score for governance gaps
- `topn_alpha`: Confidence in TOPN guard effectiveness
- `outlier_severity`: Worst-case outlier score

## File Structure

```
FabricAnalyzer/
├── client/                          # React frontend
│   ├── src/
│   │   ├── App.jsx                  # Tab router, session state management
│   │   ├── api/proxy.js             # API client
│   │   ├── auth/msalConfig.js       # MSAL OAuth config
│   │   ├── components/
│   │   │   ├── ConnectTab.jsx       # OAuth, sample dataset, direct collection
│   │   │   ├── TracesTab.jsx        # Trace table with latency breakdowns
│   │   │   ├── WorkflowTab.jsx      # 9-agent pipeline UI with model selection
│   │   │   ├── FindingsTab.jsx      # Expandable findings with severity/impact
│   │   │   ├── SimulationTab.jsx    # Fix toggles + before/after chart
│   │   │   ├── ValidationTab.jsx    # Fix selection + validation pipeline
│   │   │   ├── ArtifactsTab.jsx     # PDF export
│   │   │   └── StatusHeader.jsx     # 4 status lights
│   │   ├── constants/
│   │   │   ├── agentMeta.js         # Agent display names, icons, descriptions
│   │   │   ├── domainSignals.js     # Domain classification keywords
│   │   │   ├── fixes.js             # 8 fix definitions with reduction factors
│   │   │   └── models.js            # Available LLM models
│   │   ├── simulation/
│   │   │   └── mathModel.js         # Pure sync JS simulation (<100ms)
│   │   └── report/
│   │       └── ReportView.jsx       # PDF report template
│   └── .env                         # MSAL client ID
├── server/
│   ├── proxy.js                     # Express backend (1482 lines)
│   ├── .env                         # API keys, model config
│   └── .env.example                 # Template
├── agents/
│   ├── pipeline.py                  # 9-agent orchestrator
│   ├── prompts.py                   # System prompts for all LLM agents
│   ├── domain_intelligence.py       # Agent 1: rule-based domain inference
│   ├── adversarial_probe.py         # Agent 2: BehavioralProfile builder
│   ├── schema_checks.py             # Agent 3: 11 deterministic rules
│   ├── dax_checks.py                # Agent 4: 9 deterministic rules
│   └── execution_checks.py          # Agent 5: 9 deterministic rules
├── knowledge/
│   ├── issue_catalog.py             # 500 issues x 25 categories
│   ├── embedder.py                  # ChromaDB embedder
│   └── scraper.py                   # Microsoft docs scraper
├── collector/
│   ├── fabric_collector.py          # Power BI REST API collector
│   ├── question_battery.py          # Adaptive question generation
│   └── auth.py                      # OAuth helpers
├── synthetic/
│   ├── monte_carlo_engine.py        # 500-iteration simulation
│   ├── generator.py                 # Synthetic data generator
│   ├── fix_applicator.py            # Fix application logic
│   ├── delta_computer.py            # Before/after delta
│   ├── percentiles.py               # Percentile calculations
│   ├── query_simulator.py           # Query execution simulator
│   ├── resolution_checker.py        # Resolution verification
│   └── wipe.py                      # Data cleanup
├── sample_dataset/
│   ├── build_sample.py              # Sample DB builder + schema SQL
│   ├── build_scenarios.py           # 21 test scenarios across 8 domains
│   ├── known_issues.json            # 25 known issue patterns
│   ├── sample.db                    # Pre-built sample database
│   └── scenarios/                   # Domain-specific scenario files
├── docs/
│   ├── ARCHITECTURE.md              # This file
│   ├── screenshots/                 # Tab screenshots
│   └── walkthrough.mp4              # Demo video
├── setup.sh                         # One-click setup (Linux/Mac)
├── setup.bat                        # One-click setup (Windows)
├── docker-compose.yml               # (if present)
└── package.json                     # Workspace root with dev/build scripts
```
