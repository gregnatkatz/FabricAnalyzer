# Extending FabricAnalyzer

Guide for adding new agents, rules, fix types, issue catalog entries, and domains.

---

## Adding a New Deterministic Rule

### 1. Choose the Agent

Rules belong to one of three agents based on what they analyze:

| Agent File | Data Sources | Focus |
|-----------|-------------|-------|
| `agents/schema_checks.py` | `agent_config`, `tables`, `measures`, `columns` | Model structure |
| `agents/dax_checks.py` | `traces` | DAX generation patterns |
| `agents/execution_checks.py` | `traces`, `cu_metrics`, `models`, `tables` | Runtime performance |

### 2. Add the Rule

Add a new block inside the `run_checks(db_path)` function. Follow the existing pattern:

```python
# Rule N: Description
if condition:
    findings.append({
        'issue': f'Human-readable description with {value}',
        'severity': 'CRITICAL',  # CRITICAL | HIGH | MEDIUM | LOW
        'evidence': f'Technical evidence: field = {value}',
        'impact_ms': 5000,  # Estimated latency impact
        'fix': 'Recommended action',
        'agent_id': 'schema',  # Must match the agent
    })
```

### 3. Update Documentation

Add the rule to `docs/DETERMINISTIC_RULES.md` in the appropriate section.

---

## Adding a New Fix Type

Fixes are defined in three places that must stay synchronized:

### 1. Client-Side Math Model

Edit `client/src/constants/fixes.js`:

```javascript
export const FIXES = {
  // ... existing fixes ...
  my_new_fix: {
    key: 'my_new_fix',
    label: 'My New Fix',
    description: 'Detailed description of what this fix does...',
    schemaF: 0.10,  // Fraction of schema latency reduced (0.0-1.0)
    daxF: 0.20,     // Fraction of DAX latency reduced
    execF: 0.05,    // Fraction of execution latency reduced
    effort: 'Medium',  // Low | Medium | High
    owner: 'Data Engineer',  // Who implements this
  },
};
```

### 2. Server-Side Monte Carlo

Edit `synthetic/monte_carlo_engine.py`:

```python
FIX_DISTRIBUTIONS = {
    # ... existing fixes ...
    'my_new_fix': {
        'schema': (0.10, 0.04),   # (mean_reduction, stddev)
        'dax':    (0.20, 0.06),
        'exec':   (0.05, 0.02),
    },
}
```

The Monte Carlo engine samples from Gaussian distributions, so provide both mean and standard deviation. Higher stddev = less certainty about the fix's impact.

### 3. Phase Caps

If your fix could push cumulative reduction beyond current caps, consider adjusting:

```python
CAPS = {'schema': 0.78, 'dax': 0.82, 'exec': 0.65}
```

These caps prevent unrealistic projections (e.g., claiming 95% latency reduction).

---

## Adding a New Agent

### 1. Create the Agent Module

Create `agents/my_agent.py`:

```python
"""Agent N - My Agent — Description."""
import sqlite3


def run(db_path, session_state=None):
    """Run My Agent analysis."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    findings = []

    # Your analysis logic here
    traces = [dict(r) for r in db.execute('SELECT * FROM traces').fetchall()]

    for trace in traces:
        if some_condition(trace):
            findings.append({
                'issue': 'Description',
                'severity': 'HIGH',
                'evidence': 'Evidence',
                'impact_ms': 3000,
                'fix': 'Fix recommendation',
                'agent_id': 'my_agent',
            })

    db.close()
    return {
        'findings': findings,
        'custom_data': {},  # Any additional agent-specific output
    }
```

### 2. Register in Pipeline

Edit `agents/pipeline.py` to add the agent to the orchestration:

```python
# In run_pipeline(), add after existing agents:
from agents.my_agent import run as run_my_agent

# Add the agent call (between existing agents):
my_result = run_my_agent(db_path, session_state=results)
results['my_agent'] = my_result
all_findings.extend(my_result.get('findings', []))
```

### 3. Add LLM Prompt (Optional)

If your agent uses LLM enhancement, add to `agents/prompts.py`:

```python
MY_AGENT_SYSTEM = """You are a specialist agent analyzing...
Context: {context}
Findings so far: {findings_json}
Provide your analysis as JSON..."""

# Add to CHROMADB_QUERIES:
CHROMADB_QUERIES['my_agent'] = 'relevant search terms for RAG'

# Add to AGENT_TOPICS:
AGENT_TOPICS['my_agent'] = 'my_topic'
```

### 4. Add UI Metadata

Edit `client/src/constants/agentMeta.js`:

```javascript
export const AGENTS = {
  // ... existing agents ...
  my_agent: {
    id: 'my_agent',
    name: 'My Agent',
    glyph: '🔬',
    accent: 'var(--blue)',
    order: 10,
    description: 'Description of what this agent does',
  },
};

export const AGENT_ORDER = [
  // ... existing order ...
  'my_agent',
];
```

---

## Adding Issue Catalog Entries

### 1. Add to Catalog

Edit `knowledge/issue_catalog.py`. Each category has 20 entries. To add a new category:

```python
NEW_CATEGORY = [
    {
        'id': 'ISS-0501',
        'category': 'NEW_CATEGORY',
        'title': 'Issue Title',
        'severity': 'HIGH',
        'description': 'Detailed description of the issue...',
        'impact_ms': 3000,
        'fix': 'How to fix this issue',
        'detection_hint': 'How to detect this issue programmatically',
    },
    # ... 19 more entries ...
]
```

### 2. Register the Category

Add your category to the `ALL_ISSUES` list at the bottom of `issue_catalog.py`:

```python
ALL_ISSUES = SCHEMA_DESIGN + SCHEMA_SCOPE + ... + NEW_CATEGORY
```

### 3. Re-embed

After adding entries, re-embed the knowledge base:

```bash
cd server && python3 -c "from knowledge.embedder import embed_knowledge; embed_knowledge()"
```

This rebuilds the ChromaDB `microsoft_docs` collection with the new entries.

---

## Adding a New Domain

### 1. Add Domain Signals

Edit `agents/domain_intelligence.py`:

```python
DOMAIN_SIGNALS = {
    # ... existing domains ...
    'MY_DOMAIN': ['keyword1', 'keyword2', 'keyword3', ...],
}
```

### 2. Add Domain-Specific Traces (Optional)

If you want auto-generated traces for the domain, edit `server/proxy.js` in the direct collection endpoint. Add a domain trace generator function that produces realistic latency breakdowns.

### 3. Add Domain Scenarios (Optional)

Create `sample_dataset/scenarios/my_domain.json`:

```json
{
  "domain": "MY_DOMAIN",
  "tables": [
    { "name": "fact_table", "row_count": 100000, "column_count": 15 }
  ],
  "measures": [
    { "name": "Total Count", "expression": "COUNTROWS(fact_table)" }
  ],
  "traces": [
    {
      "question": "What is the total count?",
      "total_ms": 25000,
      "bd_schema": 5000,
      "bd_nldax": 12000,
      "bd_exec": 6000
    }
  ]
}
```

---

## Adding an LLM Model

### 1. Add Model Endpoint

Edit `server/proxy.js` in the `MODEL_ENDPOINTS` object:

```javascript
const MODEL_ENDPOINTS = {
  // ... existing models ...
  'My-Model-Name': {
    base: 'https://your-endpoint.openai.azure.com/openai/v1',
    key: process.env.MY_MODEL_KEY || process.env.LLM_API_KEY,
  },
};
```

### 2. Add to Available Models

Edit the `/api/models` endpoint response or `client/src/constants/models.js`:

```javascript
export const MODELS = [
  // ... existing models ...
  { id: 'My-Model-Name', name: 'My Model Display Name' },
];
```

### 3. Limitations

- Models must support the Azure OpenAI `/chat/completions` API
- Reasoning-only models (e.g., GPT-5.4 Pro) that only support the `/responses` API require a separate code path (not yet implemented)
- The proxy uses `curl` via `execSync`; ensure the model endpoint responds within 180s

---

## Testing Changes

### Run Deterministic Rules Only (No LLM)

```bash
cd server
python3 -c "
from agents.schema_checks import run_checks
findings = run_checks('./data/sample.db')
for f in findings:
    print(f'{f[\"severity\"]}: {f[\"issue\"]}')
"
```

### Run Full Pipeline

```bash
cd server
python3 ../agents/pipeline.py \
  --db ./data/sample.db \
  --session-id test \
  --agent all \
  --proxy-url http://localhost:3001 \
  --sample-mode
```

### Run Monte Carlo Only

```bash
python3 synthetic/monte_carlo_engine.py \
  --db server/data/sample.db \
  --n 500 \
  --fixes instruction_trim,schema_scope,verified_answers
```

### Verify ChromaDB Embeddings

```bash
python3 -c "
import chromadb
client = chromadb.PersistentClient(path='./chroma_db')
col = client.get_collection('microsoft_docs')
print(f'Total chunks: {col.count()}')
results = col.query(query_texts=['schema scope bloat'], n_results=3)
for doc in results['documents'][0]:
    print(doc[:100])
"
```
