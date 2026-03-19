import express from 'express';
import cors from 'cors';
import { config } from 'dotenv';
import { fileURLToPath } from 'url';
import { dirname, join, resolve } from 'path';
import { existsSync, mkdirSync, readFileSync, readdirSync } from 'fs';
import { spawn } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

config({ path: join(__dirname, '.env') });

const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb' }));

const PORT = process.env.PORT || 3001;
const SQLITE_DIR = resolve(process.env.SQLITE_DIR || './data');
const TMP_DIR = resolve(process.env.TMP_DIR || './tmp');
const CHROMADB_PATH = resolve(process.env.CHROMADB_PATH || join(__dirname, '..', 'chroma_db'));
const PYTHON_PATH = process.env.PYTHON_PATH || 'python3';

// Per-model endpoint configuration — supports routing different models to different Azure AI endpoints
// If a model has its own endpoint env var, use that; otherwise fall back to default LLM_ENDPOINT
const MODEL_ENDPOINTS = {
  'gpt-5.4-pro-2': {
    endpoint: process.env.LLM_ENDPOINT_GPT || process.env.LLM_ENDPOINT,
    apiKey: process.env.LLM_API_KEY_GPT || process.env.LLM_API_KEY,
  },
  'grok-4-1-fast-reasoning': {
    endpoint: process.env.LLM_ENDPOINT_GROK || process.env.LLM_ENDPOINT,
    apiKey: process.env.LLM_API_KEY_GROK || process.env.LLM_API_KEY,
  },
  'DeepSeek-V3.2-Speciale': {
    endpoint: process.env.LLM_ENDPOINT_DEEPSEEK || process.env.LLM_ENDPOINT,
    apiKey: process.env.LLM_API_KEY_DEEPSEEK || process.env.LLM_API_KEY,
  },
  'Phi-4-reasoning': {
    endpoint: process.env.LLM_ENDPOINT_PHI || process.env.LLM_ENDPOINT,
    apiKey: process.env.LLM_API_KEY_PHI || process.env.LLM_API_KEY,
  },
};

function getModelConfig(modelId) {
  const config = MODEL_ENDPOINTS[modelId];
  if (config && config.endpoint) return config;
  return { endpoint: process.env.LLM_ENDPOINT, apiKey: process.env.LLM_API_KEY };
}

// Ensure directories exist
[SQLITE_DIR, TMP_DIR, CHROMADB_PATH].forEach(dir => {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
});

// Validate required env vars (LLM_API_KEY optional when using Azure AD auth)
const REQUIRED_ENV = ['LLM_ENDPOINT', 'LLM_MODEL'];
const missing = REQUIRED_ENV.filter(k => !process.env[k]);
const LLM_AUTH_MODE = process.env.LLM_API_KEY && process.env.LLM_API_KEY !== 'placeholder-api-key'
  ? 'api-key'
  : 'azure-ad';

// Azure AD token cache for LLM auth
let azureAdToken = null;
let azureAdTokenExpiry = 0;

async function getAzureAdToken() {
  // If we have a valid cached token, return it
  if (azureAdToken && Date.now() < azureAdTokenExpiry - 60000) {
    return azureAdToken;
  }
  try {
    // Try DefaultAzureCredential via @azure/identity
    const { DefaultAzureCredential } = await import('@azure/identity');
    const credential = new DefaultAzureCredential();
    const tokenResponse = await credential.getToken('https://cognitiveservices.azure.com/.default');
    azureAdToken = tokenResponse.token;
    azureAdTokenExpiry = tokenResponse.expiresOnTimestamp;
    return azureAdToken;
  } catch (err) {
    console.warn('[server] Azure AD auth not available:', err.message);
    console.warn('[server] LLM agents will be disabled. Set LLM_API_KEY in .env or configure Azure AD credentials.');
    return null;
  }
}

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    chromadb: existsSync(CHROMADB_PATH) ? 'connected' : 'missing',
    sqlite_dir: SQLITE_DIR,
    llm_model: process.env.LLM_MODEL,
    missing_env: missing.length > 0 ? missing : undefined,
  });
});

// Available models endpoint
app.get('/api/models', (req, res) => {
  res.json({
    models: [
      { id: 'gpt-5.4-pro-2', name: 'GPT-5.4 Pro', provider: 'Azure OpenAI', authMethods: ['api-key', 'entra-id'] },
      { id: 'grok-4-1-fast-reasoning', name: 'Grok 4.1 Fast Reasoning', provider: 'Azure AI (xAI)', authMethods: ['entra-id'] },
      { id: 'DeepSeek-V3.2-Speciale', name: 'DeepSeek V3.2 Speciale', provider: 'Azure AI (DeepSeek)', authMethods: ['api-key'] },
      { id: 'Phi-4-reasoning', name: 'Phi-4 Reasoning', provider: 'Azure AI (Microsoft)', authMethods: ['api-key'] },
    ],
    defaultModel: process.env.LLM_MODEL,
    authMode: LLM_AUTH_MODE,
  });
});

// LLM proxy — forwards to Azure OpenAI (or any OpenAI-compatible endpoint)
app.post('/api/agent', async (req, res) => {
  try {
    const { system, userMsg, maxTokens = 1200, modelOverride } = req.body;
    const model = modelOverride || process.env.LLM_MODEL;
    const modelConfig = getModelConfig(model);
    const endpoint = modelConfig.endpoint;
    const apiKey = modelConfig.apiKey;

    // Build Azure OpenAI compatible request
    const llmUrl = endpoint.includes('openai.azure.com')
      ? `${endpoint.replace(/\/+$/, '')}/chat/completions?api-version=2024-12-01-preview`
      : `${endpoint.replace(/\/+$/, '')}/chat/completions`;

    const headers = {
      'Content-Type': 'application/json',
    };

    // Determine auth: API key or Azure AD token
    if (LLM_AUTH_MODE === 'api-key') {
      if (endpoint.includes('openai.azure.com')) {
        headers['api-key'] = apiKey;
      } else {
        headers['Authorization'] = `Bearer ${apiKey}`;
      }
    } else {
      // Azure AD auth
      const adToken = await getAzureAdToken();
      if (!adToken) {
        return res.status(503).json({ error: 'LLM not available — no API key and Azure AD auth failed. Set LLM_API_KEY in server/.env' });
      }
      headers['Authorization'] = `Bearer ${adToken}`;
    }

    const body = {
      model,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: userMsg },
      ],
      max_tokens: maxTokens,
      temperature: 0.2,
    };

    const response = await fetch(llmUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const text = await response.text();
      console.error('LLM error:', response.status, text);
      return res.status(response.status).json({ error: text });
    }

    const data = await response.json();
    const content = data.choices?.[0]?.message?.content || '';
    res.json({ content, usage: data.usage });
  } catch (err) {
    console.error('LLM proxy error:', err);
    res.status(500).json({ error: err.message });
  }
});

// Sample dataset loader
app.post('/api/sample', (req, res) => {
  const sampleDbPath = join(__dirname, '..', 'sample_dataset', 'sample.db');
  if (!existsSync(sampleDbPath)) {
    return res.status(404).json({ error: 'sample.db not found — run Phase 3 first' });
  }

  const sessionId = `sample_${Date.now()}`;

  // Read traces + CU metrics + run deterministic rules from sample.db
  const pythonScript = `
import sqlite3, json, sys

db = sqlite3.connect('${sampleDbPath}')
db.row_factory = sqlite3.Row
traces = [dict(r) for r in db.execute('SELECT * FROM traces').fetchall()]
config = dict(db.execute('SELECT * FROM agent_config LIMIT 1').fetchone() or {})
model = dict(db.execute('SELECT * FROM models LIMIT 1').fetchone() or {})
tables = [dict(r) for r in db.execute('SELECT * FROM tables').fetchall()]
measures = [dict(r) for r in db.execute('SELECT * FROM measures').fetchall()]
columns = [dict(r) for r in db.execute('SELECT * FROM columns').fetchall()]
relationships = [dict(r) for r in db.execute('SELECT * FROM relationships').fetchall()]
try:
    cu = dict(db.execute('SELECT * FROM cu_metrics LIMIT 1').fetchone() or {})
except:
    cu = {}
db.close()

model_name = model.get('name', 'Unknown Model')
findings = []
fid = 0

# ---- SCHEMA RULES ----
instr_chars = config.get('instr_chars', 0)
tables_checked = config.get('tables_checked', 0)
va_count = config.get('va_count', 0)
table_names = [t['name'] for t in tables]
visible_tables = [t['name'] for t in tables if not t.get('is_hidden')]
hidden_tables = [t['name'] for t in tables if t.get('is_hidden')]

# Rule 1: Instruction char limit exceeded (>4800)
if instr_chars > 4800:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'CRITICAL', 'impact_ms': 8000,
        'issue': f'Instruction text exceeds 4,800-char hard limit ({instr_chars:,} chars)',
        'affected_object': f'Agent Config \u2192 {model_name}',
        'explanation': f'The Data Agent instruction text is {instr_chars:,} characters, exceeding the 4,800-char hard limit. Fabric silently truncates instructions beyond this limit, which means routing rules and metric definitions at the end of the instruction text are lost. This causes the agent to misroute queries, generate incorrect DAX, and retry \u2014 adding 6\u201312 seconds of latency per affected query.',
        'affected_tables': [],
        'affected_traces': [t['trace_id'] for t in traces],
        'evidence': f'agent_config.instr_chars = {instr_chars:,} (limit: 4,800)',
        'fix': 'Use LLM summarization to compress instructions to under 3,800 chars while preserving all routing rules, metric definitions, and domain-specific terminology. Prioritize routing rules at the top of the instruction block.',
        'resolution_steps': [
            'Export current instruction text from Fabric Data Agent settings',
            f'Reduce from {instr_chars:,} to under 3,800 chars using LLM summarization',
            'Prioritize routing rules and metric definitions (put them first)',
            'Remove redundant examples and verbose explanations',
            'Re-deploy instruction text to Data Agent via Prep for AI',
            'Re-run question battery to verify no routing regressions'
        ],
        'latency_contribution': f'Estimated {8000}ms added per query due to silent truncation causing misrouting and retries'
    })

# Rule 2: Instructions near limit (>4000)
elif instr_chars > 4000:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'HIGH', 'impact_ms': 4000,
        'issue': f'Instructions near character limit ({instr_chars:,} chars, limit: 4,800)',
        'affected_object': f'Agent Config \u2192 {model_name}',
        'explanation': f'Instructions are at {instr_chars:,} chars, approaching the 4,800 hard limit. Any additions (new routing rules, measures) risk pushing past the limit and triggering silent truncation.',
        'affected_tables': [],
        'affected_traces': [t['trace_id'] for t in traces],
        'evidence': f'agent_config.instr_chars = {instr_chars:,} (warning threshold: 4,000)',
        'fix': 'Proactively trim instructions to under 3,800 chars to leave headroom for future additions.',
        'resolution_steps': ['Audit instruction text for redundancy', 'Compress to under 3,800 chars', 'Test with question battery after changes'],
        'latency_contribution': f'Risk of {4000}ms increase if instructions grow past 4,800 chars'
    })

# Rule 3: Extreme schema scope bloat (>30 tables)
if tables_checked > 30:
    fid += 1
    excess = tables_checked - 12
    stg_tables = [t for t in table_names if 'Stg' in t or 'Tmp' in t or 'Archive' in t or 'Sys' in t]
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'CRITICAL', 'impact_ms': 6000,
        'issue': f'Extreme schema scope bloat: {tables_checked} tables in scope (recommended: 12)',
        'affected_object': f'Semantic Model \u2192 {model_name} \u2192 tables_in_schema',
        'explanation': f'The semantic model exposes {tables_checked} tables to the Data Agent, but only ~12 core tables are needed for analysis. The extra {excess} tables ({", ".join(stg_tables[:5])}{"..." if len(stg_tables) > 5 else ""}) include staging, archive, system, and temporary tables that confuse the NL-to-DAX engine. Each extra table adds ~200ms to schema resolution as the agent evaluates relevance.',
        'affected_tables': stg_tables,
        'affected_traces': [t['trace_id'] for t in traces if t.get('bd_schema', 0) > 5000],
        'evidence': f'tables_checked = {tables_checked} | Staging/System tables: {", ".join(stg_tables)}',
        'fix': f'Remove {len(stg_tables)} non-core tables from AI Data Schema scope. Keep only Fact* and Dim* tables used by active measures.',
        'resolution_steps': [
            f'Open Prep for AI \u2192 {model_name} \u2192 Schema Settings',
            f'Uncheck these tables: {", ".join(stg_tables)}',
            'Verify remaining tables cover all active measures and relationships',
            'Re-deploy and re-run question battery'
        ],
        'latency_contribution': f'{excess} excess tables \u00d7 ~200ms each = ~{excess * 200}ms added to schema resolution'
    })
elif tables_checked > 20:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'HIGH', 'impact_ms': 3000,
        'issue': f'High schema scope bloat: {tables_checked} tables (recommended: 12)',
        'affected_object': f'Semantic Model \u2192 {model_name}',
        'explanation': f'{tables_checked} tables in scope is above optimal. Extra tables slow schema resolution.',
        'affected_tables': [t for t in table_names if 'Stg' in t or 'Tmp' in t or 'Archive' in t],
        'affected_traces': [t['trace_id'] for t in traces if t.get('bd_schema', 0) > 5000],
        'evidence': f'tables_checked = {tables_checked}',
        'fix': 'Reduce to 12-15 core tables by removing staging, archive, and temporary tables.',
        'resolution_steps': ['Audit table usage', 'Remove unused tables from scope', 'Re-test'],
        'latency_contribution': f'~{(tables_checked - 12) * 200}ms excess schema resolution time'
    })

# Rule 5: Zero verified answers
if va_count == 0:
    fid += 1
    high_freq = [t for t in traces if t.get('category') in ('simple_kpi', 'filtered_aggregate')]
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'HIGH', 'impact_ms': 4500,
        'issue': 'Zero verified answers configured',
        'affected_object': f'Agent Config \u2192 {model_name} \u2192 Verified Answers',
        'explanation': f'No verified answer DAX patterns are configured. Verified answers let the agent bypass NL-to-DAX generation entirely for known query patterns, reducing latency by 40-60% for matched queries. Without them, every query goes through full DAX generation ({sum(t.get("bd_nldax", 0) for t in traces) / max(len(traces), 1):.0f}ms avg).',
        'affected_tables': [],
        'affected_traces': [t['trace_id'] for t in high_freq] if high_freq else [t['trace_id'] for t in traces[:3]],
        'evidence': f'va_count = 0 | {len(high_freq)} high-frequency KPI queries could benefit from verified answers',
        'fix': 'Add 8-12 verified answer DAX patterns for the most common KPI queries (simple aggregates, filtered counts, rankings).',
        'resolution_steps': [
            'Identify top 8-12 most common query patterns from trace history',
            'Write verified answer DAX for each (e.g., "Total Encounters" \u2192 EVALUATE {{[Total Encounters]}})',
            'Add via Prep for AI \u2192 Verified Answers tab',
            'Include TOPN guards for ranking queries',
            'Re-run question battery to confirm VA matches fire correctly'
        ],
        'latency_contribution': f'Avg DAX generation = {sum(t.get("bd_nldax", 0) for t in traces) / max(len(traces), 1):.0f}ms \u2014 verified answers would eliminate this for matched queries'
    })
elif va_count < 5:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'MEDIUM', 'impact_ms': 2000,
        'issue': f'Low verified answer count ({va_count})',
        'affected_object': f'Agent Config \u2192 {model_name}',
        'explanation': f'Only {va_count} verified answers. Recommend 8+ for optimal coverage.',
        'affected_tables': [], 'affected_traces': [],
        'evidence': f'va_count = {va_count}',
        'fix': 'Add more verified answer DAX patterns for high-frequency queries.',
        'resolution_steps': ['Identify additional common queries', 'Add verified answer DAX', 'Test matches'],
        'latency_contribution': f'Each missing VA adds ~{2000}ms for DAX generation on matched patterns'
    })

# Rule 7/8: Duplicate measures
measure_names = [m['name'] for m in measures]
seen = {}
exact_dups = []
for m in measures:
    if m['name'] in seen:
        exact_dups.append((m['name'], m.get('table_id', ''), seen[m['name']]))
    else:
        seen[m['name']] = m.get('table_id', '')

if exact_dups:
    fid += 1
    dup_names = list(set(d[0] for d in exact_dups))
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'CRITICAL', 'impact_ms': 5000,
        'issue': f'Exact duplicate measure names detected: {", ".join(dup_names)}',
        'affected_object': f'Semantic Model \u2192 {model_name} \u2192 Measures',
        'explanation': f'Multiple measures share identical names ({", ".join(dup_names)}). When the agent generates DAX referencing these measures, it cannot disambiguate and may pick the wrong one, causing incorrect results or retries. Each disambiguation failure adds 3-5 seconds.',
        'affected_tables': list(set(d[1] for d in exact_dups)),
        'affected_traces': [t['trace_id'] for t in traces if t.get('retries', 0) > 1],
        'evidence': f'Duplicate names: {", ".join(dup_names)} | Total measures: {len(measures)}',
        'fix': f'Rename or hide {len(exact_dups)} duplicate measures. Keep one canonical version per metric.',
        'resolution_steps': [
            f'In Power BI Desktop, open {model_name} semantic model',
            f'Locate duplicate measures: {", ".join(dup_names)}',
            'Hide non-canonical versions (set IsHidden = true) or rename with qualifier (e.g., "Total Encounters (Count)" vs "Total Encounters (Rows)")',
            'Publish updated model to Fabric workspace',
            'Verify Data Agent uses correct measures via question battery'
        ],
        'latency_contribution': f'Each disambiguation failure adds ~3,000-5,000ms in retries'
    })

# Fuzzy duplicates (detect similar measure names)
from difflib import SequenceMatcher
fuzzy_dups = []
unique_names = list(set(measure_names))
for i in range(len(unique_names)):
    for j in range(i+1, len(unique_names)):
        ratio = SequenceMatcher(None, unique_names[i].lower(), unique_names[j].lower()).ratio()
        if ratio > 0.85 and unique_names[i] != unique_names[j]:
            fuzzy_dups.append((unique_names[i], unique_names[j], f'{ratio:.0%}'))
if fuzzy_dups:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'HIGH', 'impact_ms': 3000,
        'issue': f'Fuzzy duplicate measures: {len(fuzzy_dups)} pairs with >85% name similarity',
        'affected_object': f'Semantic Model \u2192 {model_name} \u2192 Measures',
        'explanation': f'Measures with very similar names confuse the NL-to-DAX engine: {"; ".join(f"{a} vs {b} ({s})" for a,b,s in fuzzy_dups[:3])}. The agent may pick the wrong measure or retry multiple times.',
        'affected_tables': [],
        'affected_traces': [t['trace_id'] for t in traces if t.get('retries', 0) > 0],
        'evidence': f'Similar pairs: {"; ".join(f"{a} \u2194 {b} ({s})" for a,b,s in fuzzy_dups)}',
        'fix': 'Consolidate similar measures or add clear descriptions to disambiguate.',
        'resolution_steps': ['Review measure pairs', 'Rename for clarity or hide duplicates', 'Add descriptions', 'Re-test'],
        'latency_contribution': f'~{3000}ms per query affected by measure ambiguity'
    })

# Rule 10: Hidden columns referenced
hidden_cols = [c for c in columns if c.get('is_hidden')]
if hidden_cols:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'MEDIUM', 'impact_ms': 1500,
        'issue': f'{len(hidden_cols)} hidden columns in scope ({", ".join(c["name"] for c in hidden_cols[:3])})',
        'affected_object': f'Semantic Model \u2192 {model_name} \u2192 Columns',
        'explanation': f'Hidden columns ({", ".join(c["name"] for c in hidden_cols)}) are still visible to the Data Agent schema resolver. If DAX references them, the query may fail or produce unexpected results.',
        'affected_tables': list(set(c.get('table_id', '') for c in hidden_cols)),
        'affected_traces': [],
        'evidence': f'Hidden columns: {", ".join(c["name"] for c in hidden_cols)}',
        'fix': 'Either fully exclude hidden columns from AI Data Schema or make them visible if needed.',
        'resolution_steps': ['Review hidden columns', 'Exclude from AI scope or make visible', 'Re-test'],
        'latency_contribution': f'~{1500}ms risk if agent references hidden columns causing errors'
    })

# Rule 9: Missing table descriptions
tables_no_desc = [t for t in tables if not t.get('description') and not t.get('is_hidden')]
if len(tables_no_desc) > len(visible_tables) * 0.3:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'MEDIUM', 'impact_ms': 2000,
        'issue': f'{len(tables_no_desc)}/{len(visible_tables)} visible tables missing descriptions',
        'affected_object': f'Semantic Model \u2192 {model_name} \u2192 Table Descriptions',
        'explanation': f'Most tables lack descriptions. The agent relies on table names alone to determine which tables to query, increasing misrouting risk.',
        'affected_tables': [t['name'] for t in tables_no_desc[:5]],
        'affected_traces': [t['trace_id'] for t in traces if t.get('retries', 0) > 0],
        'evidence': f'{len(tables_no_desc)} of {len(visible_tables)} visible tables have no description',
        'fix': 'Add concise descriptions to all visible tables explaining their purpose and grain.',
        'resolution_steps': ['Open model in Power BI Desktop', 'Add descriptions to each table', 'Publish to Fabric'],
        'latency_contribution': f'~{2000}ms from misrouting due to ambiguous table purposes'
    })

# Bidirectional cross-filter
bidir_rels = [r for r in relationships if r.get('cross_filter') == 'both']
if bidir_rels:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'schema', 'severity': 'HIGH', 'impact_ms': 3500,
        'issue': f'Bi-directional cross-filter on {len(bidir_rels)} relationship(s)',
        'affected_object': f'Semantic Model \u2192 {model_name} \u2192 Relationships',
        'explanation': f'Bi-directional cross-filter between {" and ".join(f"{r.get("from_table")}\u2194{r.get("to_table")}" for r in bidir_rels)} creates ambiguous filter propagation. The DAX engine must evaluate multiple filter paths, increasing execution time.',
        'affected_tables': list(set(r.get('from_table', '') for r in bidir_rels) | set(r.get('to_table', '') for r in bidir_rels)),
        'affected_traces': [t['trace_id'] for t in traces if t.get('bd_exec', 0) > 4000],
        'evidence': f'Bi-directional: {", ".join(f"{r.get("from_table")}\u2194{r.get("to_table")}" for r in bidir_rels)}',
        'fix': 'Change to single-direction cross-filter unless bi-directional is explicitly required.',
        'resolution_steps': ['Open model relationships in Power BI Desktop', 'Change cross-filter to Single for each flagged relationship', 'Test DAX queries for correctness', 'Publish to Fabric'],
        'latency_contribution': f'~{3500}ms from ambiguous filter paths in execution engine'
    })

# ---- DAX RULES ----
# High retry traces
high_retry_traces = [t for t in traces if t.get('retries', 0) > 2]
if high_retry_traces:
    fid += 1
    worst = max(high_retry_traces, key=lambda t: t.get('retries', 0))
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'dax', 'severity': 'CRITICAL', 'impact_ms': 7000,
        'issue': f'{len(high_retry_traces)} queries with >2 retries (worst: {worst.get("retries")} retries on "{worst.get("question", "")[:60]}...")',
        'affected_object': f'Data Agent \u2192 {model_name} \u2192 Query Routing',
        'explanation': f'Queries are retrying 3-4 times before succeeding. Each retry re-runs the full NL-to-DAX pipeline (schema+DAX generation), typically adding 8-15 seconds total. This indicates the agent is targeting wrong tables on first attempt due to missing or insufficient routing rules in the instructions.',
        'affected_tables': list(set(t.get('tables_used', '').split(',')[0] for t in high_retry_traces if t.get('tables_used'))),
        'affected_traces': [t['trace_id'] for t in high_retry_traces],
        'evidence': f'Traces with >2 retries: {", ".join(t.get("question","")[:40] + "..." for t in high_retry_traces[:3])} | Retry counts: {", ".join(str(t.get("retries",0)) for t in high_retry_traces)}',
        'fix': 'Add explicit routing rules to instructions mapping query keywords to correct tables. Add verified answers for repeatedly-retried query patterns.',
        'resolution_steps': [
            'Identify query patterns causing retries from trace data',
            'Add routing rules to instruction text: "When user asks about X, use table Y"',
            'Add verified answer DAX for the most common retried patterns',
            'Re-run question battery and verify retry count drops to 0-1'
        ],
        'latency_contribution': f'Avg {sum(t.get("retries",0) for t in high_retry_traces)/len(high_retry_traces):.1f} retries \u00d7 ~3,000ms each = ~{int(sum(t.get("retries",0) for t in high_retry_traces)/len(high_retry_traces)*3000)}ms per affected query'
    })

# TOPN absent on ranking/cross-entity queries
topn_missing = [t for t in traces if t.get('category') in ('ranking', 'cross_entity') and 'TOPN' not in (t.get('dax_generated') or '')]
if topn_missing:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'dax', 'severity': 'HIGH', 'impact_ms': 3500,
        'issue': f'TOPN absent in {len(topn_missing)} cross-entity/ranking queries',
        'affected_object': f'Data Agent \u2192 {model_name} \u2192 DAX Generation',
        'explanation': f'Cross-entity and ranking queries are generating full SUMMARIZE/SUMMARIZECOLUMNS without TOPN guards. This forces the VertiPaq engine to materialize the complete result set before filtering, which on tables with 750K+ rows causes significant execution overhead.',
        'affected_tables': list(set(t.get('tables_used', '').split(',')[0] for t in topn_missing if t.get('tables_used'))),
        'affected_traces': [t['trace_id'] for t in topn_missing],
        'evidence': f'Queries missing TOPN: {", ".join(t.get("question","")[:40] for t in topn_missing[:3])}',
        'fix': 'Add few-shot examples with TOPN(25, ...) patterns to instructions or verified answers.',
        'resolution_steps': ['Add TOPN few-shot examples to instruction text', 'Create verified answers with TOPN guards for ranking queries', 'Re-test ranking queries'],
        'latency_contribution': f'~{3500}ms per query from full table materialization without TOPN'
    })

# Physician/provider visible
physician_traces = [t for t in traces if t.get('physician_visible')]
if physician_traces:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'dax', 'severity': 'CRITICAL', 'impact_ms': 0,
        'issue': f'Physician/provider data exposed in {len(physician_traces)} query results',
        'affected_object': f'Data Agent \u2192 {model_name} \u2192 Governance',
        'explanation': f'Query results are exposing physician/provider names in response text. In healthcare contexts, this may violate data governance policies. The agent should be instructed to exclude provider-level detail from responses or aggregate to department level.',
        'affected_tables': ['DimPhysician'],
        'affected_traces': [t['trace_id'] for t in physician_traces],
        'evidence': f'Physician visible in: {", ".join(t.get("question","")[:50] for t in physician_traces)}',
        'fix': 'Add governance rule to instructions: "Never display individual physician or provider names in results. Aggregate to department or specialty level."',
        'resolution_steps': ['Add governance instruction to agent config', 'Consider RLS on DimPhysician table', 'Re-test queries involving physician data'],
        'latency_contribution': 'Governance issue \u2014 no direct latency impact but compliance risk'
    })

# Failed queries
failed = [t for t in traces if t.get('pass_fail') == 'fail']
if failed:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'dax', 'severity': 'HIGH', 'impact_ms': 5000,
        'issue': f'{len(failed)} queries returned failures or empty results',
        'affected_object': f'Data Agent \u2192 {model_name} \u2192 DAX Generation',
        'explanation': f'These queries failed to produce valid results: {"; ".join(t.get("question","")[:50] for t in failed)}. Failed queries waste the full latency budget (schema+DAX+execution) without returning useful data. Common causes: referencing measures that do not exist, querying tables outside the model, or domain-specific terminology the agent does not understand.',
        'affected_tables': list(set(t.get('tables_used', '').split(',')[0] for t in failed if t.get('tables_used'))),
        'affected_traces': [t['trace_id'] for t in failed],
        'evidence': f'Failed questions: {"; ".join(t.get("question","") for t in failed)}',
        'fix': 'Add verified answers for failed query patterns. Ensure all referenced measures exist in the model. Add domain glossary to instructions.',
        'resolution_steps': ['Review failed DAX in trace data', 'Add missing measures or verified answers', 'Add domain terminology to instructions', 'Re-test each failed query'],
        'latency_contribution': f'Each failed query wastes full latency budget (~{sum(t.get("total_ms",0) for t in failed)//len(failed):,}ms avg) with no useful result'
    })

# ---- EXECUTION RULES ----
# Outlier traces (>45s)
outliers = [t for t in traces if t.get('total_ms', 0) > 45000]
if outliers:
    fid += 1
    worst = max(outliers, key=lambda t: t.get('total_ms', 0))
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'execution', 'severity': 'CRITICAL', 'impact_ms': int(worst['total_ms']),
        'issue': f'{len(outliers)} outlier trace(s) exceeding 45s (worst: {worst["total_ms"]/1000:.1f}s on "{worst.get("question","")[:50]}...")',
        'affected_object': f'Data Agent \u2192 {model_name} \u2192 Execution Engine',
        'explanation': f'Query "{worst.get("question","")}" took {worst["total_ms"]/1000:.1f}s total: Schema={worst.get("bd_schema",0)}ms, DAX Generation={worst.get("bd_nldax",0)}ms, Execution={worst.get("bd_exec",0)}ms, Retries={worst.get("retries",0)}. The dominant phase is {"DAX Generation" if worst.get("bd_nldax",0) > worst.get("bd_exec",0) else "Execution"} at {max(worst.get("bd_nldax",0), worst.get("bd_exec",0))}ms. This query is {worst["total_ms"]/1000:.1f}x the 10s SLA target.',
        'affected_tables': worst.get('tables_used', '').split(',') if worst.get('tables_used') else [],
        'affected_traces': [t['trace_id'] for t in outliers],
        'evidence': f'Outlier: "{worst.get("question","")}" = {worst["total_ms"]/1000:.1f}s | Tables: {worst.get("tables_used","")} | Retries: {worst.get("retries",0)}',
        'fix': f'Add verified answer DAX for this query pattern. Reduce table scope. {"Add TOPN guard to prevent full table scan." if worst.get("bd_exec",0) > 5000 else "Simplify instruction text to speed DAX generation."}',
        'resolution_steps': ['Create verified answer DAX for outlier query pattern', 'Add TOPN(25, ...) guard if execution-dominant', 'Reduce table scope if schema-dominant', 'Re-test and verify latency drops below 15s'],
        'latency_contribution': f'{worst["total_ms"]/1000:.1f}s \u2014 {worst["total_ms"]/1000/10:.1f}x above 10s SLA target'
    })

# DAX generation dominant (>55% of total for any trace)
dax_dominant = [t for t in traces if t.get('total_ms', 0) > 0 and t.get('bd_nldax', 0) / t['total_ms'] > 0.55]
if dax_dominant:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'execution', 'severity': 'HIGH', 'impact_ms': 4000,
        'issue': f'DAX generation dominant in {len(dax_dominant)} queries (>55% of total latency)',
        'affected_object': f'Data Agent \u2192 {model_name} \u2192 NL-to-DAX Engine',
        'explanation': f'In {len(dax_dominant)} queries, DAX generation consumes over 55% of total latency. This means the NL-to-DAX engine is spending too long interpreting instructions and generating DAX. Causes: overly complex instructions, too many tables in scope, missing routing rules.',
        'affected_tables': [],
        'affected_traces': [t['trace_id'] for t in dax_dominant],
        'evidence': f'DAX-dominant queries: {len(dax_dominant)} of {len(traces)} traces | Avg DAX gen: {sum(t.get("bd_nldax",0) for t in dax_dominant)//max(len(dax_dominant),1):,}ms',
        'fix': 'Trim instructions, add routing rules, add verified answers for complex patterns.',
        'resolution_steps': ['Simplify instruction text', 'Add explicit routing rules', 'Create verified answers for DAX-dominant query patterns'],
        'latency_contribution': f'Avg DAX gen = {sum(t.get("bd_nldax",0) for t in dax_dominant)//len(dax_dominant):,}ms in affected queries'
    })

# Execution dominant (>35% for any trace)
exec_dominant = [t for t in traces if t.get('total_ms', 0) > 0 and t.get('bd_exec', 0) / t['total_ms'] > 0.35]
if exec_dominant:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'execution', 'severity': 'HIGH', 'impact_ms': 3500,
        'issue': f'Execution phase dominant in {len(exec_dominant)} queries (>35% of total)',
        'affected_object': f'Semantic Model \u2192 {model_name} \u2192 VertiPaq Engine',
        'explanation': f'In {len(exec_dominant)} queries, the VertiPaq execution engine consumes over 35% of total latency. This suggests the generated DAX is performing expensive operations: full table scans, iterators on large tables, or complex CROSSJOIN operations.',
        'affected_tables': list(set(t.get('tables_used', '').split(',')[0] for t in exec_dominant if t.get('tables_used'))),
        'affected_traces': [t['trace_id'] for t in exec_dominant],
        'evidence': f'Exec-dominant queries: {len(exec_dominant)} of {len(traces)} | Avg exec: {sum(t.get("bd_exec",0) for t in exec_dominant)//len(exec_dominant):,}ms',
        'fix': 'Add TOP/TOPN limits, optimize DAX patterns, consider V-Order for Direct Lake tables.',
        'resolution_steps': ['Add TOPN(25) guards to prevent full scans', 'Review DAX for iterator usage on large tables', 'Apply V-Order optimization if using Direct Lake', 'Re-test affected queries'],
        'latency_contribution': f'Avg execution = {sum(t.get("bd_exec",0) for t in exec_dominant)//len(exec_dominant):,}ms in affected queries'
    })

# CU throttling
throttle = cu.get('throttle_events', 0)
if throttle > 50:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'execution', 'severity': 'CRITICAL', 'impact_ms': 5000,
        'issue': f'High CU throttling: {throttle} throttle events in 28-day window',
        'affected_object': f'Fabric Capacity \u2192 {model_name} workspace',
        'explanation': f'{throttle} throttle events detected over the last 28 days. Each throttle event adds 2-8 seconds of queuing delay as Fabric rate-limits the capacity unit consumption. With AI CU={cu.get("ai_cu_28d",0):,.0f} and Query CU={cu.get("query_cu_28d",0):,.0f}, the workspace is consistently hitting capacity limits.',
        'affected_tables': [],
        'affected_traces': [t['trace_id'] for t in traces],
        'evidence': f'Throttle events: {throttle} | AI CU (28d): {cu.get("ai_cu_28d",0):,.0f} | Query CU (28d): {cu.get("query_cu_28d",0):,.0f} | P50/P95: {cu.get("p50_ms",0)/1000:.1f}s/{cu.get("p95_ms",0)/1000:.1f}s',
        'fix': 'Reduce CU consumption by optimizing queries (TOPN, fewer tables) or increase capacity tier.',
        'resolution_steps': [
            'Review CU consumption in Fabric Capacity Metrics app',
            'Optimize top CU-consuming queries (add TOPN, reduce table scope)',
            'Consider upgrading capacity tier if optimization insufficient',
            'Set up CU alerting to catch throttling early'
        ],
        'latency_contribution': f'{throttle} throttle events \u00d7 ~2-8s queuing = significant cumulative delay'
    })

# Schema lookup dominant (>25%)
schema_dominant = [t for t in traces if t.get('total_ms', 0) > 0 and t.get('bd_schema', 0) / t['total_ms'] > 0.25]
if schema_dominant:
    fid += 1
    findings.append({
        'finding_id': f'F{fid:03d}', 'agent_id': 'execution', 'severity': 'HIGH', 'impact_ms': 3000,
        'issue': f'Schema lookup dominant in {len(schema_dominant)} queries (>25% of total)',
        'affected_object': f'Data Agent \u2192 {model_name} \u2192 Schema Resolution',
        'explanation': f'Schema resolution is consuming >25% of total latency in {len(schema_dominant)} queries. The agent is spending too long determining which tables and columns to use. This correlates directly with schema scope bloat ({tables_checked} tables).',
        'affected_tables': [],
        'affected_traces': [t['trace_id'] for t in schema_dominant],
        'evidence': f'Schema-dominant: {len(schema_dominant)} queries | Avg schema: {sum(t.get("bd_schema",0) for t in schema_dominant)//len(schema_dominant):,}ms | Tables in scope: {tables_checked}',
        'fix': 'Reduce table scope, add table descriptions, add routing rules.',
        'resolution_steps': ['Remove staging/archive tables from scope', 'Add descriptions to remaining tables', 'Add routing rules to instructions'],
        'latency_contribution': f'Avg schema resolution = {sum(t.get("bd_schema",0) for t in schema_dominant)//len(schema_dominant):,}ms in affected queries'
    })

# Sort findings by impact_ms descending (biggest offenders first)
findings.sort(key=lambda f: f.get('impact_ms', 0), reverse=True)

result = {
    'traces': traces,
    'config': config,
    'model': model,
    'cuMetrics': cu,
    'findings': findings,
    'tables': [{'name': t['name'], 'row_count': t.get('row_count',0), 'is_hidden': t.get('is_hidden',0)} for t in tables],
    'measures': [{'name': m['name'], 'table': m.get('table_id',''), 'expression': m.get('expression','')} for m in measures],
    'relationships': [{'from_table': r.get('from_table',''), 'to_table': r.get('to_table',''), 'cross_filter': r.get('cross_filter','')} for r in relationships],
}
print(json.dumps(result))
`;

  const py = spawn(PYTHON_PATH, ['-c', pythonScript]);
  let output = '';
  let stderr = '';
  py.stdout.on('data', d => output += d);
  py.stderr.on('data', d => stderr += d);
  py.on('close', (code) => {
    if (code !== 0) {
      console.error('Sample load error:', stderr);
      return res.status(500).json({ error: stderr || 'Failed to load sample' });
    }
    try {
      const data = JSON.parse(output);
      res.json({
        sessionId,
        dbPath: sampleDbPath,
        modelName: data.model?.name || 'LOS Sample Model',
        domain: 'CLINICAL_INPATIENT',
        traces: data.traces || [],
        cuMetrics: data.cuMetrics || null,
        findings: data.findings || [],
      });
    } catch (e) {
      res.status(500).json({ error: `Parse error: ${e.message}` });
    }
  });
});

// List available test scenarios
app.get('/api/scenarios', (req, res) => {
  const scenariosDir = join(__dirname, '..', 'sample_dataset', 'scenarios');
  const metaPath = join(scenariosDir, 'scenarios_meta.json');
  if (!existsSync(metaPath)) {
    return res.json({ scenarios: [] });
  }
  try {
    const meta = JSON.parse(readFileSync(metaPath, 'utf8'));
    res.json({ scenarios: meta });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Load a specific test scenario
app.post('/api/sample/scenario', (req, res) => {
  const { scenarioId } = req.body;
  if (!scenarioId) return res.status(400).json({ error: 'scenarioId required' });

  const dbPath = join(__dirname, '..', 'sample_dataset', 'scenarios', `scenario_${String(scenarioId).padStart(2, '0')}.db`);
  if (!existsSync(dbPath)) {
    return res.status(404).json({ error: `scenario_${String(scenarioId).padStart(2, '0')}.db not found` });
  }

  const sessionId = `scenario_${scenarioId}_${Date.now()}`;
  const metaPath = join(__dirname, '..', 'sample_dataset', 'scenarios', 'scenarios_meta.json');
  let scenarioMeta = {};
  if (existsSync(metaPath)) {
    const allMeta = JSON.parse(readFileSync(metaPath, 'utf8'));
    scenarioMeta = allMeta.find(s => s.id === Number(scenarioId)) || {};
  }

  const pythonScript = `
import sqlite3, json, sys
db = sqlite3.connect('${dbPath}')
db.row_factory = sqlite3.Row
traces = [dict(r) for r in db.execute('SELECT * FROM traces').fetchall()]
config = dict(db.execute('SELECT * FROM agent_config LIMIT 1').fetchone() or {})
model = dict(db.execute('SELECT * FROM models LIMIT 1').fetchone() or {})
try:
    cu = dict(db.execute('SELECT * FROM cu_metrics LIMIT 1').fetchone() or {})
except:
    cu = {}
print(json.dumps({'traces': traces, 'config': config, 'model': model, 'cuMetrics': cu}))
db.close()
`;

  const py = spawn(PYTHON_PATH, ['-c', pythonScript]);
  let output = '';
  let stderr = '';
  py.stdout.on('data', d => output += d);
  py.stderr.on('data', d => stderr += d);
  py.on('close', (code) => {
    if (code !== 0) {
      console.error('Scenario load error:', stderr);
      return res.status(500).json({ error: stderr || 'Failed to load scenario' });
    }
    try {
      const data = JSON.parse(output);
      res.json({
        sessionId,
        dbPath,
        modelName: data.model?.name || scenarioMeta.name || `Scenario ${scenarioId}`,
        domain: scenarioMeta.domain || 'auto',
        traces: data.traces || [],
        cuMetrics: data.cuMetrics || null,
        scenarioId: Number(scenarioId),
        scenarioName: scenarioMeta.name || `Scenario ${scenarioId}`,
        scenarioDescription: scenarioMeta.description || '',
        keyIssues: scenarioMeta.key_issues || [],
      });
    } catch (e) {
      res.status(500).json({ error: `Parse error: ${e.message}` });
    }
  });
});

// Run analysis pipeline
app.post('/api/analyze', (req, res) => {
  const { dbPath, sessionId, agentId, domain, sampleMode, modelOverride } = req.body;
  if (!dbPath) return res.status(400).json({ error: 'dbPath required' });

  const pipelineScript = join(__dirname, '..', 'agents', 'pipeline.py');
  const args = [
    pipelineScript,
    '--db', dbPath,
    '--session-id', sessionId || 'default',
    '--agent', agentId || 'all',
    '--domain', domain || 'auto',
    '--llm-endpoint', process.env.LLM_ENDPOINT || '',
    '--llm-key', process.env.LLM_API_KEY || '',
    '--llm-model', modelOverride || process.env.LLM_MODEL || '',
    '--chromadb-path', CHROMADB_PATH,
    '--proxy-url', `http://localhost:${PORT}`,
  ];
  if (sampleMode) args.push('--sample-mode');

  const py = spawn(PYTHON_PATH, args, {
    cwd: join(__dirname, '..'),
    env: { ...process.env, PYTHONPATH: join(__dirname, '..') },
  });

  let output = '';
  let stderr = '';
  py.stdout.on('data', d => output += d);
  py.stderr.on('data', d => { stderr += d; console.error('[pipeline]', d.toString()); });
  py.on('close', (code) => {
    if (code !== 0) {
      return res.status(500).json({ error: stderr || 'Pipeline failed', code });
    }
    try {
      const result = JSON.parse(output);
      res.json(result);
    } catch (e) {
      res.json({ findings: [], message: output || 'Pipeline completed' });
    }
  });
});

// Reset endpoint
app.post('/api/reset', async (req, res) => {
  const { scope = 'full', sessionId } = req.body;

  const resetScript = join(__dirname, 'reset.js');
  // Inline reset logic
  const { rmSync } = await import('fs');

  try {
    if (scope === 'full' || scope === 'findings_only') {
      // Clear SQLite data
      if (scope === 'full' && existsSync(SQLITE_DIR)) {
        const files = (await import('fs')).readdirSync(SQLITE_DIR);
        for (const f of files) {
          if (f.endsWith('.db')) {
            rmSync(join(SQLITE_DIR, f), { force: true });
          }
        }
      }
      // Clear synthetic data
      if (scope === 'full' && sessionId) {
        const sessionDir = join(TMP_DIR, sessionId);
        if (existsSync(sessionDir)) {
          rmSync(sessionDir, { recursive: true, force: true });
          if (existsSync(sessionDir)) {
            return res.status(500).json({ error: 'Wipe verification failed — files remain' });
          }
        }
      }
    }
    res.json({ status: 'ok', scope });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Validation SSE endpoint
app.get('/api/validate', (req, res) => {
  const { sessionId, fixes } = req.query;
  if (!sessionId || !fixes) {
    return res.status(400).json({ error: 'sessionId and fixes required' });
  }

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
  });

  const fixList = fixes.split(',');
  const validateScript = join(__dirname, '..', 'synthetic', 'fix_applicator.py');
  const args = [
    validateScript,
    '--session-id', sessionId,
    '--fixes', fixes,
    '--db-dir', SQLITE_DIR,
    '--tmp-dir', TMP_DIR,
    '--proxy-url', `http://localhost:${PORT}`,
  ];

  const py = spawn(PYTHON_PATH, args, {
    cwd: join(__dirname, '..'),
    env: { ...process.env, PYTHONPATH: join(__dirname, '..') },
  });

  py.stdout.on('data', (data) => {
    const lines = data.toString().split('\n').filter(l => l.trim());
    for (const line of lines) {
      try {
        const parsed = JSON.parse(line);
        res.write(`data: ${JSON.stringify(parsed)}\n\n`);
      } catch (e) {
        // Non-JSON output — ignore
      }
    }
  });

  py.stderr.on('data', d => console.error('[validation]', d.toString()));

  py.on('close', (code) => {
    if (code !== 0) {
      res.write(`data: ${JSON.stringify({ type: 'error', message: 'Validation process failed' })}\n\n`);
    }
    res.end();
  });

  req.on('close', () => py.kill());
});

// ChromaDB query endpoint
app.post('/api/knowledge/query', (req, res) => {
  const { query, nResults = 5, collection = 'microsoft_docs' } = req.body;
  if (!query) return res.status(400).json({ error: 'query required' });

  const pythonScript = `
import chromadb, json, sys
try:
    client = chromadb.PersistentClient(path='${CHROMADB_PATH}')
    col = client.get_collection('${collection}')
    results = col.query(query_texts=['''${query.replace(/'/g, "\\'")}'''], n_results=${nResults})
    docs = []
    for i in range(len(results['documents'][0])):
        docs.append({
            'id': results['ids'][0][i],
            'document': results['documents'][0][i][:500],
            'metadata': results['metadatas'][0][i],
            'distance': results['distances'][0][i] if results.get('distances') else None,
        })
    print(json.dumps({'results': docs, 'total': col.count()}))
except Exception as e:
    print(json.dumps({'error': str(e)}))
`;

  const py = spawn(PYTHON_PATH, ['-c', pythonScript], {
    cwd: join(__dirname, '..'),
  });
  let output = '';
  let stderr = '';
  py.stdout.on('data', d => output += d);
  py.stderr.on('data', d => stderr += d);
  py.on('close', (code) => {
    try {
      const data = JSON.parse(output);
      if (data.error) return res.status(500).json({ error: data.error });
      res.json(data);
    } catch (e) {
      res.status(500).json({ error: stderr || 'ChromaDB query failed' });
    }
  });
});

// ChromaDB status endpoint
app.get('/api/knowledge/status', (req, res) => {
  const pythonScript = `
import json, sys
try:
    import chromadb
    client = chromadb.PersistentClient(path='${CHROMADB_PATH}')
    collections = {}
    for name in ['microsoft_docs', 'past_findings']:
        try:
            col = client.get_collection(name)
            collections[name] = col.count()
        except:
            collections[name] = 0
    print(json.dumps({'status': 'ok', 'collections': collections}))
except ImportError:
    print(json.dumps({'status': 'not_installed', 'error': 'chromadb not installed'}))
except Exception as e:
    print(json.dumps({'status': 'error', 'error': str(e)}))
`;

  const py = spawn(PYTHON_PATH, ['-c', pythonScript], {
    cwd: join(__dirname, '..'),
  });
  let output = '';
  py.stdout.on('data', d => output += d);
  py.on('close', () => {
    try {
      res.json(JSON.parse(output));
    } catch (e) {
      res.json({ status: 'error', error: 'Failed to check ChromaDB' });
    }
  });
});

// PDF export
app.post('/api/pdf', async (req, res) => {
  try {
    const sessionData = req.body || {};
    const puppeteer = await import('puppeteer');
    const browser = await puppeteer.default.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const page = await browser.newPage();

    // Inject session data into the page before React renders
    await page.evaluateOnNewDocument((data) => {
      window.__REPORT_DATA__ = data;
    }, sessionData);

    await page.goto('http://localhost:5173/report', { waitUntil: 'networkidle0', timeout: 30000 });
    await page.waitForSelector('#report-ready', { timeout: 10000 });

    // Wait for React to re-render with injected data
    await page.evaluate(() => new Promise(resolve => setTimeout(resolve, 500)));

    const pdf = await page.pdf({
      format: 'A4',
      margin: { top: '20mm', bottom: '20mm', left: '15mm', right: '15mm' },
      printBackground: true,
    });
    await browser.close();
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'attachment; filename=analysis-report.pdf');
    res.send(pdf);
  } catch (err) {
    console.error('PDF error:', err);
    res.status(500).json({ error: err.message });
  }
});

// Fabric API proxy endpoints
app.get('/api/fabric/workspaces', async (req, res) => {
  try {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.status(401).json({ error: 'No token provided' });

    const response = await fetch('https://api.powerbi.com/v1.0/myorg/groups', {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    res.json({ workspaces: (data.value || []).map(w => ({ id: w.id, name: w.name })) });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/fabric/workspaces/:workspaceId/models', async (req, res) => {
  try {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.status(401).json({ error: 'No token provided' });

    const response = await fetch(
      `https://api.powerbi.com/v1.0/myorg/groups/${req.params.workspaceId}/datasets`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const data = await response.json();
    res.json({ models: (data.value || []).map(d => ({ id: d.id, name: d.name })) });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/fabric/collect', (req, res) => {
  const { workspaceId, modelId } = req.body;
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.status(401).json({ error: 'No token provided' });

  const collectScript = join(__dirname, '..', 'collector', 'fabric_collector.py');
  const args = [
    collectScript,
    '--workspace-id', workspaceId,
    '--model-id', modelId,
    '--token', token,
    '--output-dir', SQLITE_DIR,
    '--tmp-dir', TMP_DIR,
  ];

  const py = spawn(PYTHON_PATH, args, {
    cwd: join(__dirname, '..'),
    env: { ...process.env, PYTHONPATH: join(__dirname, '..') },
  });

  let output = '';
  let stderr = '';
  py.stdout.on('data', d => output += d);
  py.stderr.on('data', d => { stderr += d; console.error('[collector]', d.toString()); });
  py.on('close', (code) => {
    if (code !== 0) {
      return res.status(500).json({ error: stderr || 'Collection failed' });
    }
    try {
      const result = JSON.parse(output);
      res.json(result);
    } catch (e) {
      res.status(500).json({ error: `Parse error: ${e.message}` });
    }
  });
});

app.listen(PORT, () => {
  console.log(`[server] Express proxy running on http://localhost:${PORT}`);
  console.log(`[server] LLM: ${process.env.LLM_MODEL} via ${process.env.LLM_ENDPOINT}`);
  console.log(`[server] LLM auth mode: ${LLM_AUTH_MODE}`);
  if (missing.length > 0) {
    console.warn(`[server] WARNING: Missing env vars: ${missing.join(', ')}`);
  }
});
