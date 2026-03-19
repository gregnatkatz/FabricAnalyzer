# Fabric Data Agent Latency Analyzer

A locally-installed diagnostic tool that connects to Microsoft Fabric workspaces via OAuth, analyzes Data Agents using a 9-agent AI pipeline, generates synthetic datasets, runs Monte Carlo simulations, validates recommendations, and exports PDFs with findings and fix artifacts.

## Key Features

- **Automated Latency Diagnostics** — 29 deterministic rules + 500 RAG-grounded issue patterns detect root causes
- **PDF Report Export** — Puppeteer-rendered PDF with executive summary, root cause ranking, before/after comparison, CU cost correlation, and fix recommendations
- **ChromaDB Knowledge Base** — 538 embedded chunks (38 docs + 500 latency issues) for RAG-grounded LLM analysis
- **Before/After Comparison** — Projected impact of all fixes with per-fix breakdown showing latency reduction percentages
- **CU Cost Correlation** — AI CU, Query CU, Throttle Events, P50/P95 latency with estimated CU savings
- **Adaptive Question Battery** — 30-50 domain-specific questions auto-generated from semantic model schema
- **20 Test Scenarios** — Pre-built scenarios across 8 domains (Revenue Cycle, Supply Chain, Clinical, Financial, etc.)
- **Per-Agent Model Selection** — Choose from 4 Azure AI models per pipeline agent

## Video Walkthrough

A full end-to-end walkthrough showing sample data loading, findings analysis, and PDF export:

https://github.com/user-attachments/assets/walkthrough.mp4

[Download walkthrough video](docs/walkthrough.mp4)

## Screenshots

### Connect Tab
Connect to a Fabric workspace via OAuth or load the built-in sample dataset. Setup Checklist guides prerequisite configuration with "Test Connection" buttons.

![Connect Tab](docs/screenshots/01-connect-tab.png)

### Traces Tab
View all collected traces with latency breakdowns (Schema/DAX/Execution), retry counts, and CU Correlation metrics (AI CU, Query CU, Throttle Events, P50/P95).

![Traces Tab](docs/screenshots/02-traces-tab.png)

### Workflow Tab — 9-Agent Pipeline with Model Selection
Run the full 9-agent analysis pipeline with per-agent model selection. Choose from GPT-5.4 Pro, Grok 4.1 Fast Reasoning, DeepSeek V3.2 Speciale, or Phi-4 Reasoning for each agent.

![Workflow Tab](docs/screenshots/03-workflow-tab.png)

### Findings Tab — Root Cause Ranking
All issues ranked by latency impact (biggest offenders first). Each finding shows affected tables, detailed explanation, resolution steps, and severity. 15 findings across 6 CRITICAL, 7 HIGH, and 2 MEDIUM with 105.5s total impact.

![Findings Tab](docs/screenshots/04-findings-tab.png)

### Simulation Tab — Math Model
Pure client-side JavaScript math model updates instantly (<100ms) as you toggle fixes. Shows projected average latency, outlier latency, pass rate, and before/after comparison chart.

![Simulation Tab - Baseline](docs/screenshots/05-simulation-tab.png)

Toggle fixes to see instant impact projections — here "Trim Instructions" and "Add Verified Answers" reduce avg latency from 26.6s to 19.9s (-25%).

![Simulation Tab - With Fixes](docs/screenshots/05b-simulation-with-fixes.png)

### Validation Tab
Select fixes to validate with a 4-phase validation pipeline: baseline battery, fix application, post-fix battery, and delta + resolution analysis.

![Validation Tab](docs/screenshots/06-validation-tab.png)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React UI (:5173)                       │
│  ConnectTab │ TracesTab │ WorkflowTab │ FindingsTab       │
│  SimulationTab │ ValidationTab │ ArtifactsTab             │
│  mathModel.js (pure sync JS, <100ms updates)             │
└───────────────────────┬─────────────────────────────────┘
                        │ fetch() to /api/*
┌───────────────────────▼─────────────────────────────────┐
│              Express Proxy (:3001)                        │
│  /api/health │ /api/agent │ /api/models │ /api/sample     │
│  /api/analyze │ /api/reset │ /api/validate (SSE)          │
│  /api/pdf │ /api/fabric/*                                 │
│  Azure AD + API Key auth │ Per-agent model routing        │
└───────────────────────┬─────────────────────────────────┘
                        │ subprocess spawn
┌───────────────────────▼─────────────────────────────────┐
│              Python Backend                               │
│  agents/ — 9-agent pipeline (29 deterministic + 500 RAG)   │
│  knowledge/ — ChromaDB RAG (540 chunks: 40 docs + 500 issues) │
│  synthetic/ — Monte Carlo, validation, query simulator     │
│  collector/ — Fabric API collector, question battery       │
│  sample_dataset/ — 25 known issues, acceptance tests       │
└─────────────────────────────────────────────────────────┘
```

## 9-Agent Pipeline

| # | Agent | Model Default | Purpose |
|---|-------|---------------|---------|
| 1 | Domain Intelligence | Grok 4.1 Fast | Domain classification, probe question generation |
| 2 | Adversarial Probe | Grok 4.1 Fast | Behavioral profiling from probe results |
| 3 | Schema Agent | DeepSeek V3.2 | 11 deterministic rules + LLM schema analysis |
| 4 | DAX Agent | DeepSeek V3.2 | 9 deterministic rules + LLM DAX pattern analysis |
| 5 | Execution Agent | DeepSeek V3.2 | 9 deterministic rules + LLM execution analysis |
| 6 | Synthesis Agent | GPT-5.4 Pro | Root cause ranking, demo readiness verdict |
| 7 | Monte Carlo Agent | GPT-5.4 Pro | Calibrated distributions, P10/P50/P90 per fix |
| 8 | Remediation Agent | GPT-5.4 Pro | Paste-ready artifacts for Prep for AI |
| 9 | Validation Agent | Phi-4 Reasoning | On-demand fix validation with before/after |

## Available Models

| Model | Provider | Auth | Best For |
|-------|----------|------|----------|
| GPT-5.4 Pro | Azure OpenAI | API Key / Entra ID | Complex reasoning, synthesis, remediation |
| Grok 4.1 Fast Reasoning | Azure AI (xAI) | Entra ID | Fast domain intelligence, adversarial probing |
| DeepSeek V3.2 Speciale | Azure AI (DeepSeek) | API Key | Schema/DAX/execution deep analysis |
| Phi-4 Reasoning | Azure AI (Microsoft) | API Key | Efficient validation, quick checks |

## Quick Start

### One-Click Setup (Recommended)

The fastest way to get running — installs all dependencies, builds the knowledge base, and starts servers:

```bash
git clone https://github.com/gregnatkatz/FabricAnalyzer.git
cd FabricAnalyzer
chmod +x setup.sh
./setup.sh
```

`setup.sh` handles everything:
1. Checks Node.js 18+ and Python 3 are installed
2. Installs npm dependencies (root, client, server)
3. Installs Python packages (chromadb, numpy, requests)
4. Creates `server/.env` with defaults
5. Verifies sample dataset exists
6. Builds ChromaDB knowledge base (538 issue patterns)
7. Starts Express backend (:3001) and React frontend (:5173)

> **Windows?** Run `setup.bat` instead — same steps, same result.

### Manual Setup

```bash
# Clone
git clone https://github.com/gregnatkatz/FabricAnalyzer.git
cd FabricAnalyzer

# Install dependencies
npm install
cd client && npm install && cd ..
cd server && npm install && cd ..

# Install Python dependencies
pip install chromadb numpy requests

# Configure environment
cp server/.env.example server/.env
# Edit server/.env with your LLM endpoint and API key

# Build sample dataset + knowledge base
python3 sample_dataset/build_sample.py
python3 knowledge/embedder.py

# Start development servers
npm run dev
# Opens React at http://localhost:5173
# Express proxy at http://localhost:3001
```

### Sample Dataset Mode (No Azure Required)
1. Click **Sample Dataset** on the Connect tab
2. View 10 traces on the Traces tab
3. Select models per agent on the Workflow tab
4. Click **Run Analysis** to run the 9-agent pipeline
5. Toggle fixes on the Simulation tab to see instant impact projections
6. Select fixes and click **Run Validation** on the Validation tab
7. Export PDF from the Artifacts tab

### Connecting to a Real Fabric Data Agent (Step-by-Step)

Follow these steps to connect the analyzer to your Microsoft Fabric workspace and test a live Data Agent.

#### Step 1: Register an Azure AD App

1. Go to [Azure Portal → App registrations → New registration](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/CreateApplicationBlade)
2. **Name**: `Fabric Analyzer` (or any name you prefer)
3. **Supported account types**: "Accounts in any organizational directory" (Multi-tenant)
4. **Redirect URI**: Select **Single-page application (SPA)** and enter:
   ```
   http://localhost:5173
   ```
5. Click **Register**
6. Copy the **Application (client) ID** — you'll need this in Step 3

#### Step 2: Add API Permissions

1. In your app registration, go to **API permissions → Add a permission**
2. Select **Power BI Service** (or search for it under "APIs my organization uses")
3. Select **Delegated permissions** and add:
   - `Dataset.Read.All` — read semantic model metadata
   - `Workspace.Read.All` — list workspaces
4. Click **Add permissions**
5. **No admin consent needed** — these are delegated permissions that run as your user

#### Step 3: Configure the Analyzer

1. Open the app at `http://localhost:5173`
2. On the **Connect** tab, click **Connect to Fabric (OAuth)**
3. Paste your **Client ID** from Step 1 into the Client ID field
4. Optionally enter your **Tenant ID** (found in Azure Portal → Azure Active Directory → Overview)
   - Leave blank for multi-tenant (works with any Microsoft account)

#### Step 4: Sign In & Select Data Agent

1. Click **Sign In** — a Microsoft login popup opens
2. Sign in with your Microsoft account that has access to the Fabric workspace
3. Grant consent when prompted (first time only)
4. After sign-in, the **Workspace picker** appears — select your workspace
5. The **Semantic Model picker** loads — select the model backing your Data Agent
6. Click **Collect** — the tool:
   - Fetches model metadata (tables, measures, columns, relationships)
   - Reads agent configuration (instructions, verified answers, schema scope)
   - Runs a 30-50 question adaptive battery against the Data Agent
   - Captures full latency traces (Schema lookup → DAX generation → Execution)

#### Step 5: Run Analysis

1. Go to the **Workflow** tab
2. Select which Azure AI model to use for each agent (optional — defaults are pre-configured)
3. Click **Run Analysis** — the 9-agent pipeline runs:
   - Agents 1-2: Domain intelligence + adversarial probing
   - Agents 3-5: Schema, DAX, and execution analysis (29 deterministic rules + LLM)
   - Agent 6: Synthesis — root cause ranking and demo readiness verdict
   - Agent 7: Monte Carlo — 500 iterations, P10/P50/P90 projections
   - Agent 8: Remediation — paste-ready fix artifacts
   - Agent 9: Validation — fix effectiveness assessment

#### Step 6: Review Findings & Simulate Fixes

1. **Findings tab** — All issues ranked by latency impact (biggest offenders first)
   - Each finding shows: affected table/model, detailed explanation, resolution steps
   - Click any finding to expand full details
2. **Simulation tab** — Toggle fixes on/off to see instant latency projections
   - Before/after comparison chart updates in real-time
3. **Validation tab** — Select fixes and run validation to measure actual improvement

#### Step 7: Export PDF Report

1. Go to the **Artifacts** tab
2. Click **Export PDF** — generates a comprehensive report with:
   - Executive summary and demo readiness verdict
   - Root cause ranking (biggest latency offenders first)
   - Detailed findings with explanations and resolution steps
   - Before/after comparison and per-fix impact breakdown
   - CU cost correlation and estimated savings
   - Paste-ready artifacts (optimized instructions, verified answers, schema scope)

#### Troubleshooting

| Issue | Solution |
|-------|----------|
| "No workspaces found" | Ensure your account has access to at least one Fabric workspace |
| Sign-in popup blocked | Allow popups for localhost:5173 in your browser settings |
| "AADSTS65001" consent error | Ask your Azure AD admin to grant consent, or use a test tenant |
| Data Agent not responding | Verify the Data Agent is deployed and the semantic model is online |
| Slow collection (>2 min) | Normal for large models — the battery runs 30-50 questions |
| No traces captured | Check that the Data Agent is configured with at least one semantic model |

## 500 Latency Issue Catalog

The tool includes a comprehensive catalog of **500 known latency issues** across 25 categories, embedded in ChromaDB for LLM RAG grounding:

| Category | Count | Examples |
|----------|-------|----------|
| Schema Design | 20 | Star schema violations, orphan tables, circular paths |
| Schema Scope | 20 | Scope bloat, unused dimensions, stale scope |
| Instruction Tuning | 20 | Char limit exceeded, missing routing, conflicting rules |
| Verified Answers | 20 | Zero VAs, missing TOPN, syntax errors, hardcoded dates |
| Routing Rules | 20 | Wrong table routing, ambiguous keywords, missing routing |
| DAX Generation | 20 | Generation dominant, timeout, skipped VA match |
| DAX Patterns | 20 | Missing TOPN, CROSSJOIN, iterator on large table |
| DAX Antipatterns | 20 | NL2DAX contamination, implicit measures, circular refs |
| Execution Engine | 20 | Outlier traces, memory spill, cold cache penalty |
| Direct Lake | 20 | V-Order missing, DirectQuery fallback, framing risk |
| VertiPaq | 20 | High cardinality, wide strings, GUID columns |
| CU/Capacity | 20 | Throttling, burst limits, cross-region latency |
| Retry Patterns | 20 | Cascading retries, wrong table retries, retry rate |
| Measure Design | 20 | Duplicates, missing descriptions, hardcoded filters |
| Relationship Model | 20 | Bi-directional, M2M, snowflake chains, role-playing |
| Column Design | 20 | Ambiguous names, type mismatches, encoding issues |
| Governance | 20 | PHI exposure, RLS gaps, audit logging |
| Question Battery | 20 | Missing test categories, schema adaptation |
| NL Parsing | 20 | Ambiguous pronouns, date parsing, domain jargon |
| Response Synthesis | 20 | Verbose responses, missing units, timeout |
| Knowledge Sources | 20 | Outdated docs, missing glossary, chunking issues |
| Workspace Config | 20 | Shared capacity, wrong region, refresh conflicts |
| Agent Config | 20 | Empty setup, missing SLA, no feedback loop |
| Monitoring | 20 | No alerting, no baseline, no trend analysis |
| Cross-Agent | 20 | Inconsistent configs, routing confusion, drift |

## 29 Deterministic Rules (Pre-Checks)

### Schema (11 rules)
- Instruction char limit exceeded (>4800) — CRITICAL
- Instructions near limit (>4000) — HIGH
- Extreme schema scope bloat (>30 tables) — CRITICAL
- High schema scope bloat (>20 tables) — HIGH
- Zero verified answers — HIGH
- Low verified answers (<5) — MEDIUM
- Exact duplicate measure names — CRITICAL
- Fuzzy duplicate measures (>85% similarity) — HIGH
- Missing table descriptions (>30%) — MEDIUM
- Hidden columns referenced — MEDIUM
- Schema/agent table mismatch — HIGH

### DAX (9 rules)
- High retry count (>2) — CRITICAL
- Single retry — MEDIUM
- TOPN absent on cross-entity query — HIGH
- Wrong table targeted first — HIGH
- Physician/provider visible — CRITICAL
- Measure not found — CRITICAL
- Empty results with no error — HIGH
- Ambiguous time filter — HIGH
- NL2DAX/NL2SQL cross-contamination — HIGH

### Execution (9 rules)
- Outlier trace (>45000ms) — CRITICAL
- Slow trace (>20000ms) — HIGH
- Execution dominant (>35% of total) — HIGH
- DAX generation dominant (>55% of total) — HIGH
- Retry dominant — HIGH
- Schema lookup dominant (>25% of total) — HIGH
- High CU throttling (>50 events) — CRITICAL
- V-Order not confirmed for Direct Lake — MEDIUM
- Direct Lake framing risk — HIGH

## Acceptance Test Results

```
Detection rate: 20/25 = 80%
False positive rate: 4%
Total deterministic findings: 26
```

## API Endpoints

### Core
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/sample` | POST | Load sample dataset (returns traces, findings, CU metrics) |
| `/api/sample/scenario` | POST | Load specific test scenario by ID |
| `/api/scenarios` | GET | List available test scenarios |
| `/api/analyze` | POST | Run 9-agent analysis pipeline |
| `/api/validate` | POST | Run 4-phase validation (SSE stream) |
| `/api/pdf` | POST | Export PDF report via Puppeteer (accepts full session data) |
| `/api/reset` | POST | Reset session data |

### Knowledge Base (ChromaDB)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/knowledge/status` | GET | Collection counts (microsoft_docs, past_findings) |
| `/api/knowledge/query` | POST | Semantic search: `{ query, nResults, collection }` |

### Fabric Integration
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/fabric/workspaces` | GET | List Fabric workspaces (requires OAuth token) |
| `/api/fabric/models` | GET | List semantic models in workspace |
| `/api/fabric/collect` | POST | Collect data from Fabric Data Agent |

## Environment Variables

### Core Settings
| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_ENDPOINT` | Yes | Default Azure OpenAI or compatible endpoint URL |
| `LLM_MODEL` | Yes | Default model deployment name |
| `LLM_API_KEY` | No* | API key (*not needed if using Azure AD auth) |
| `CHROMADB_PATH` | No | ChromaDB storage path (default: `./chroma_db`) |
| `SQLITE_DIR` | No | SQLite data directory (default: `./data`) |
| `TMP_DIR` | No | Temporary/synthetic data directory (default: `./tmp`) |
| `MONTE_CARLO_N` | No | Monte Carlo iterations (default: 500) |
| `PORT` | No | Express proxy port (default: 3001) |

### Per-Model Endpoint Routing (Optional)
Configure separate endpoints/keys for each Azure AI model. If not set, all models use the default `LLM_ENDPOINT` and `LLM_API_KEY`.

| Variable | Description |
|----------|-------------|
| `LLM_ENDPOINT_GPT` | Endpoint for GPT-5.4 Pro |
| `LLM_API_KEY_GPT` | API key for GPT-5.4 Pro |
| `LLM_ENDPOINT_GROK` | Endpoint for Grok 4.1 Fast Reasoning |
| `LLM_API_KEY_GROK` | API key for Grok 4.1 Fast Reasoning |
| `LLM_ENDPOINT_DEEPSEEK` | Endpoint for DeepSeek V3.2 Speciale |
| `LLM_API_KEY_DEEPSEEK` | API key for DeepSeek V3.2 Speciale |
| `LLM_ENDPOINT_PHI` | Endpoint for Phi-4 Reasoning |
| `LLM_API_KEY_PHI` | API key for Phi-4 Reasoning |

## License

MIT
