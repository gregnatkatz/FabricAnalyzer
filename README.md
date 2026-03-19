# Fabric Data Agent Latency Analyzer

A locally-installed diagnostic tool that connects to Microsoft Fabric workspaces via OAuth, analyzes Data Agents using a 9-agent AI pipeline, generates synthetic datasets, runs Monte Carlo simulations, validates recommendations, and exports PDFs with findings and fix artifacts.

## Screenshots

### Connect Tab
Connect to a Fabric workspace via OAuth or load the built-in sample dataset for immediate analysis.

![Connect Tab](https://app.devin.ai/attachments/375ec86b-4db6-4e26-8cd5-a0657f5305ce/01-connect-tab.png)

### Traces Tab
View all collected traces with latency breakdowns (Schema/DAX/Execution), retry counts, and status indicators.

![Traces Tab](https://app.devin.ai/attachments/bcbcbeb8-960b-44f9-a3e5-2f63162fc0d0/02-traces-tab.png)

### Workflow Tab — 9-Agent Pipeline with Model Selection
Run the full 9-agent analysis pipeline with per-agent model selection. Choose from GPT-5.4 Pro, Grok 4.1 Fast Reasoning, DeepSeek V3.2 Speciale, or Phi-4 Reasoning for each agent.

![Workflow Tab](https://app.devin.ai/attachments/e01b0e7e-5aee-4c1d-8a3c-679628afa161/03-workflow-tab.png)

### Simulation Tab — Math Model
Pure client-side JavaScript math model updates instantly (<100ms) as you toggle fixes. Shows projected average latency, outlier latency, and pass rate.

![Simulation Tab - Baseline](https://app.devin.ai/attachments/64e9c8e2-aaf7-4b68-ad2b-b6543aa4cab5/05-simulation-tab.png)

Toggle fixes to see instant impact projections — here "Trim Instructions" and "Add Verified Answers" reduce avg latency from 26.6s to 19.9s (-25%).

![Simulation Tab - With Fixes](https://app.devin.ai/attachments/77f6b5e0-50a6-4de1-988c-7858f5f3e869/05b-simulation-with-fixes.png)

### Validation Tab
Select fixes to validate with a 4-phase validation pipeline: baseline battery, fix application, post-fix battery, and delta + resolution analysis.

![Validation Tab](https://app.devin.ai/attachments/cb6beb12-e4f3-4f12-8eb5-04991c8328a3/06-validation-tab.png)

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
│  agents/ — 9-agent pipeline (29 deterministic rules)      │
│  knowledge/ — ChromaDB RAG (40+ knowledge chunks)         │
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

### Prerequisites
- Node.js 18+
- Python 3.10+
- ChromaDB (`pip install chromadb`)

### Setup

```bash
# Clone
git clone https://github.com/gnkatz26/FabricAnalyzer.git
cd FabricAnalyzer

# Install dependencies
npm install
cd client && npm install && cd ..
cd server && npm install && cd ..

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

### Real Fabric Connection
1. Click **Connect to Fabric (OAuth)** — signs in via browser popup
2. Select workspace and semantic model
3. Collector gathers metadata and runs question battery
4. Run analysis pipeline with selected models
5. Validate fixes against real Fabric Data Agent

## 29 Deterministic Rules

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

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| LLM_ENDPOINT | Yes | Azure OpenAI or compatible endpoint URL |
| LLM_MODEL | Yes | Model deployment name |
| LLM_API_KEY | No* | API key (*not needed if using Azure AD auth) |
| CHROMADB_PATH | No | ChromaDB storage path (default: ./chroma_db) |
| SQLITE_DIR | No | SQLite data directory (default: ./data) |
| TMP_DIR | No | Temporary/synthetic data directory (default: ./tmp) |
| MONTE_CARLO_N | No | Monte Carlo iterations (default: 500) |
| PORT | No | Express proxy port (default: 3001) |

## License

MIT
