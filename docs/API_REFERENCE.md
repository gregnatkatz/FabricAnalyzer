# API Reference

All endpoints are served by `server/proxy.js` on port 3001 (configurable via `PORT` env var).

---

## Health & Status

### `GET /api/health`

Returns backend health status including ChromaDB chunk count and available models.

**Response**:
```json
{
  "status": "ok",
  "chromadb": { "chunks": 538 },
  "models": ["DeepSeek-V3.2-Speciale", "DeepSeek-V3.2"],
  "pythonAvailable": true
}
```

### `GET /api/models`

Returns list of available LLM models.

**Response**:
```json
{
  "models": [
    { "id": "DeepSeek-V3.2-Speciale", "name": "DeepSeek V3.2 Speciale" },
    { "id": "DeepSeek-V3.2", "name": "DeepSeek V3.2" }
  ]
}
```

---

## LLM Proxy

### `POST /api/agent`

Proxies requests to Azure OpenAI. Supports per-model endpoint routing.

**Request body**:
```json
{
  "messages": [
    { "role": "system", "content": "You are a schema analyst..." },
    { "role": "user", "content": "Analyze these findings..." }
  ],
  "modelOverride": "DeepSeek-V3.2-Speciale",
  "temperature": 0.3,
  "max_tokens": 4000
}
```

**Response**: Proxied Azure OpenAI chat completion response.

**Notes**:
- Uses `curl` via `execSync` instead of Node.js fetch (Azure AI endpoint compatibility)
- Timeout: 180 seconds
- Auth: `api-key` header (API key mode) or `Authorization: Bearer` (Azure AD mode)

---

## Data Collection

### `POST /api/fabric/collect`

Collects metadata from a Fabric workspace via Power BI REST API.

**Request body**:
```json
{
  "workspaceId": "b79e8116-...",
  "modelId": "abc123...",
  "token": "eyJ0eXAi..."
}
```

**Response**:
```json
{
  "sessionId": "fabric_a1b2c3d4",
  "dbPath": "./data/fabric_a1b2c3d4.db",
  "modelName": "LOS_Bad_Model",
  "domain": "auto",
  "traces": [],
  "cuMetrics": { "ai_cu": 0, "query_cu": 1, "throttle_events": 0 }
}
```

### `POST /api/fabric/collect-direct`

Direct collection endpoint that bypasses Power BI REST API token scope issues. Accepts agent metadata directly and generates traces from instructions.

**Request body**:
```json
{
  "workspaceId": "b79e8116-...",
  "agentId": "5c449e0f-...",
  "agentName": "LOS_Bad_Agent",
  "instructions": "When user asks about LOS, always use patient_encounters...",
  "token": "eyJ0eXAi..."
}
```

**Response**: Same as `/api/fabric/collect` but with auto-generated traces based on domain detection from instructions.

### `POST /api/sample`

Loads the sample dataset (no Fabric connection needed).

**Request body**: None required.

**Response**:
```json
{
  "sessionId": "sample_20260320",
  "dbPath": "./data/sample.db",
  "modelName": "Sample Dataset",
  "domain": "CLINICAL_INPATIENT",
  "traces": [ ... ]
}
```

---

## Analysis Pipeline

### `POST /api/pipeline/run`

Runs the 9-agent analysis pipeline on collected data.

**Request body**:
```json
{
  "sessionId": "fabric_a1b2c3d4",
  "dbPath": "./data/fabric_a1b2c3d4.db",
  "agentId": "all",
  "domain": "auto",
  "sampleMode": false
}
```

**Query parameter alternative**: `?agentId=schema` to run a single agent.

**Response** (streamed via Server-Sent Events when available, or JSON):
```json
{
  "domain": "CLINICAL_INPATIENT",
  "findings": [ { "issue": "...", "severity": "CRITICAL", ... } ],
  "synthesis": { "summary": "...", "demo_readiness": "NOT READY" },
  "remediation": { "artifacts": [ ... ] },
  "monte_carlo": { "baseline": { "avg_ms": 29000 }, "projected": { "p50": 15000 } },
  "validation": { "summary": "...", "effective_fixes": [ ... ] },
  "agent_results": {
    "domain_intelligence": { "finding_count": 2 },
    "adversarial_probe": { "finding_count": 3 },
    ...
  }
}
```

### `GET /api/findings/:sessionId`

Retrieves findings for a session.

**Response**:
```json
{
  "findings": [
    {
      "issue": "Instruction character limit exceeded: 5200 chars",
      "severity": "CRITICAL",
      "evidence": "agent_config.instr_chars = 5200",
      "impact_ms": 8000,
      "fix": "Trim instructions to under 3,800 chars",
      "agent_id": "schema"
    }
  ]
}
```

### `GET /api/traces/:sessionId`

Retrieves trace data for a session.

**Response**:
```json
{
  "traces": [
    {
      "trace_id": "t_001",
      "question": "What is the average length of stay?",
      "total_ms": 29000,
      "bd_schema": 5000,
      "bd_nldax": 12000,
      "bd_exec": 8000,
      "retries": 1,
      "pass_fail": "pass"
    }
  ]
}
```

---

## Simulation

### `POST /api/simulate`

Runs Monte Carlo simulation (server-side, 500 iterations).

**Request body**:
```json
{
  "sessionId": "fabric_a1b2c3d4",
  "dbPath": "./data/fabric_a1b2c3d4.db",
  "activeFixes": ["instruction_trim", "schema_scope", "verified_answers"],
  "n": 500
}
```

**Response**: Monte Carlo results (see Agent 7 output in AGENTS.md).

> **Note**: The Simulation tab also uses a client-side math model (`mathModel.js`) for instant (<100ms) fix toggle previews. The server-side Monte Carlo is used for the full statistical analysis with P10/P50/P90 confidence intervals.

---

## Validation

### `POST /api/validate`

Validates selected fixes.

**Request body**:
```json
{
  "sessionId": "fabric_a1b2c3d4",
  "selectedFixes": ["instruction_trim", "schema_scope"]
}
```

---

## Export

### `POST /api/pdf`

Generates a PDF report of the analysis.

**Request body**:
```json
{
  "sessionId": "fabric_a1b2c3d4",
  "findings": [ ... ],
  "traces": [ ... ],
  "monteCarloResults": { ... },
  "domain": "CLINICAL_INPATIENT",
  "modelName": "LOS_Bad_Model"
}
```

**Response**: Binary PDF (Content-Type: `application/pdf`).

Uses Puppeteer headless Chrome to render an inline HTML template to PDF.

---

## Session Management

### `POST /api/reset`

Resets session data.

**Request body**:
```json
{
  "scope": "full | findings_only | ui_only",
  "sessionId": "fabric_a1b2c3d4"
}
```

| Scope | Effect |
|-------|--------|
| `full` | Deletes session DB, clears all state |
| `findings_only` | Clears findings, simulation, validation (keeps traces) |
| `ui_only` | No backend changes (UI refresh only) |

---

## ChromaDB

### `GET /api/chromadb/status`

Returns ChromaDB collection status and chunk counts.

### `POST /api/chromadb/query`

Queries the ChromaDB knowledge base.

**Request body**:
```json
{
  "query": "fabric data agent instruction limit",
  "collection": "microsoft_docs",
  "n_results": 5
}
```

---

## Environment Variables

Configure in `server/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_ENDPOINT` | (required) | Azure OpenAI base URL |
| `LLM_API_KEY` | (required) | Azure OpenAI API key |
| `LLM_MODEL` | `DeepSeek-V3.2-Speciale` | Default LLM model ID |
| `CHROMADB_PATH` | `./chroma_db` | Path to ChromaDB persistent storage |
| `SQLITE_DIR` | `./data` | Directory for session SQLite databases |
| `TMP_DIR` | `./tmp` | Temp directory for curl request bodies |
| `SYNTHETIC_ROW_SCALE` | `0.025` | Scale factor for synthetic data generation |
| `BATTERY_TIMEOUT_MS` | `30000` | Question battery timeout |
| `CALIBRATION_FACTOR` | `3.2` | Monte Carlo calibration factor |
| `MONTE_CARLO_N` | `500` | Number of Monte Carlo iterations |
| `PORT` | `3001` | Express server port |
| `PYTHON_PATH` | `python3` | Path to Python 3 executable |
