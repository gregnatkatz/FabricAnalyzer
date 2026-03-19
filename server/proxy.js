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
const CHROMADB_PATH = resolve(process.env.CHROMADB_PATH || './chroma_db');
const PYTHON_PATH = process.env.PYTHON_PATH || 'python3';

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
    const endpoint = process.env.LLM_ENDPOINT;
    const apiKey = process.env.LLM_API_KEY;
    const model = modelOverride || process.env.LLM_MODEL;

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

  // Read traces from sample.db
  const pythonScript = `
import sqlite3, json, sys
db = sqlite3.connect('${sampleDbPath}')
db.row_factory = sqlite3.Row
traces = [dict(r) for r in db.execute('SELECT * FROM traces').fetchall()]
config = dict(db.execute('SELECT * FROM agent_config LIMIT 1').fetchone() or {})
model = dict(db.execute('SELECT * FROM models LIMIT 1').fetchone() or {})
print(json.dumps({'traces': traces, 'config': config, 'model': model}))
db.close()
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
print(json.dumps({'traces': traces, 'config': config, 'model': model}))
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

// PDF export
app.post('/api/pdf', async (req, res) => {
  try {
    const puppeteer = await import('puppeteer');
    const browser = await puppeteer.default.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const page = await browser.newPage();
    await page.goto('http://localhost:5173/report', { waitUntil: 'networkidle0', timeout: 30000 });
    await page.waitForSelector('#report-ready', { timeout: 10000 });
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
