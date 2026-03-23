import React, { useState, useEffect } from 'react';
import { loginPopup, logout, getAccessToken, setClientConfig, getClientConfig, setManualToken } from '../auth/msalConfig';
import { loadSampleDataset, getWorkspaces, getModels, getAgents, collectData, collectDataDirect, collectLive, collectParallel, setLlmToken, collectXmla, getScenarios, loadScenario, healthCheck } from '../api/proxy';

// Comprehensive setup checklist for Fabric Data Agent testing
const SETUP_STEPS = [
  {
    id: 'azure_app',
    title: '1. Register Azure AD App (MSAL)',
    description: 'Create an App Registration in Azure Portal → Authentication → Add SPA platform → Redirect URI: http://localhost:5173. Copy the Application (Client) ID.',
    link: 'https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/CreateApplicationBlade',
    linkText: 'Open Azure Portal',
    testable: false,
    category: 'auth',
  },
  {
    id: 'api_permissions',
    title: '2. Add API Permissions (Delegated)',
    description: 'Azure Portal → App Registration → API Permissions → Add: Power BI Service (Dataset.Read.All, Workspace.Read.All) + Microsoft Graph (User.Read). Click "Grant admin consent" if you have admin rights.',
    link: 'https://learn.microsoft.com/en-us/power-bi/developer/embedded/register-app',
    linkText: 'Permission Docs',
    testable: false,
    category: 'auth',
  },
  {
    id: 'client_config',
    title: '3. Configure Client ID & Tenant',
    description: 'Paste your Application (Client) ID and Tenant ID in the "Quick Setup" section below. No config files to edit.',
    testable: false,
    category: 'auth',
  },
  {
    id: 'backend_running',
    title: '4. Backend Server Running',
    description: 'Express proxy on port 3001 — handles LLM calls, Fabric REST API, SQLite storage, and Python pipeline.',
    testable: true,
    testAction: 'backend',
    category: 'infra',
  },
  {
    id: 'llm_configured',
    title: '5. LLM Endpoint Configured',
    description: 'Azure OpenAI or compatible endpoint set in server/.env → LLM_ENDPOINT, LLM_API_KEY, LLM_MODEL. Needed for AI agent analysis (not required for deterministic rule checks).',
    testable: true,
    testAction: 'llm',
    category: 'infra',
  },
  {
    id: 'chromadb_ready',
    title: '6. ChromaDB Knowledge Base',
    description: '500 Fabric latency issue patterns embedded for RAG grounding. Built automatically by setup.sh or run: python3 knowledge/embedder.py',
    testable: true,
    testAction: 'chromadb',
    category: 'infra',
  },
  {
    id: 'fabric_capacity',
    title: '7. Fabric Capacity Available',
    description: 'Ensure your Fabric capacity (F2/F4/F64+) is active and not paused. Data Agents require Fabric capacity — not Power BI Pro/Premium Per User alone.',
    link: 'https://learn.microsoft.com/en-us/fabric/enterprise/licenses',
    linkText: 'Capacity Docs',
    testable: false,
    category: 'fabric',
  },
  {
    id: 'xmla_endpoint',
    title: '8. XMLA Endpoint Enabled',
    description: 'Fabric Admin Portal → Capacity Settings → Enable XMLA read/write endpoint. Required for semantic model metadata inspection and DAX query profiling.',
    link: 'https://learn.microsoft.com/en-us/power-bi/enterprise/service-premium-connect-tools',
    linkText: 'XMLA Docs',
    testable: false,
    category: 'fabric',
  },
  {
    id: 'semantic_model',
    title: '9. Semantic Model in Lakehouse/Warehouse',
    description: 'Your Data Agent must have a semantic model (dataset) connected to a Lakehouse or Warehouse with tables and measures defined. Direct Lake or Import mode.',
    link: 'https://learn.microsoft.com/en-us/fabric/data-warehouse/semantic-models',
    linkText: 'Semantic Model Docs',
    testable: false,
    category: 'fabric',
  },
  {
    id: 'data_agent_created',
    title: '10. Data Agent Created & Published',
    description: 'Fabric workspace → New → Data Agent → Select semantic model → Add instructions → Publish. Note the Workspace ID from the URL.',
    link: 'https://learn.microsoft.com/en-us/fabric/data-agents/concept-data-agents',
    linkText: 'Data Agent Docs',
    testable: false,
    category: 'fabric',
  },
  {
    id: 'oauth_login',
    title: '11. Sign In via OAuth (MSAL)',
    description: 'Click "Connect to Fabric (OAuth)" below. Authenticates as YOUR user via browser popup — no service principal needed. Tests one Data Agent at a time.',
    testable: false,
    category: 'connect',
  },
  {
    id: 'workspace_select',
    title: '12. Select Workspace & Data Agent',
    description: 'After sign-in, enter your Workspace ID → Load models → Select the Data Agent to analyze. Each run tests one agent with 30-50 domain-specific prompts.',
    testable: false,
    category: 'connect',
  },
];

export default function ConnectTab({ session, updateSession, onNavigate }) {
  const [workspaceId, setWorkspaceId] = useState('');
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [scenarios, setScenarios] = useState([]);
  const [showScenarios, setShowScenarios] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState(null);
  const [showChecklist, setShowChecklist] = useState(false);
  const [checkedSteps, setCheckedSteps] = useState({});
  const [testResults, setTestResults] = useState({});
  const [quickClientId, setQuickClientId] = useState(getClientConfig().clientId);
  const [quickTenantId, setQuickTenantId] = useState(getClientConfig().tenantId === 'common' ? '' : getClientConfig().tenantId);
  const [configSaved, setConfigSaved] = useState(false);
  const [showManualToken, setShowManualToken] = useState(false);
  const [manualTokenInput, setManualTokenInput] = useState('');
  const [directAgentId, setDirectAgentId] = useState('');
  const [directAgentName, setDirectAgentName] = useState('');
  const [directInstructions, setDirectInstructions] = useState('');
  const [showDirectEntry, setShowDirectEntry] = useState(false);
  const [agents, setAgents] = useState([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [xmlaStatus, setXmlaStatus] = useState(''); // '', 'collecting', 'complete', 'error'
  const [xmlaError, setXmlaError] = useState('');
  const [xmlaSummary, setXmlaSummary] = useState(null);
  const [llmTokenInput, setLlmTokenInput] = useState('');
  const [llmTokenStatus, setLlmTokenStatus] = useState(''); // '', 'set', 'error'

  const toggleStep = (stepId) => {
    setCheckedSteps(prev => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  const handleTestConnection = async (testAction) => {
    try {
      setTestResults(prev => ({ ...prev, [testAction]: 'testing' }));
      if (testAction === 'backend') {
        const result = await healthCheck();
        setTestResults(prev => ({
          ...prev,
          backend: result.status === 'ok' ? 'pass' : 'fail',
        }));
        if (result.status === 'ok') {
          setCheckedSteps(prev => ({ ...prev, backend_running: true }));
        }
      } else if (testAction === 'llm') {
        const result = await healthCheck();
        const hasLlm = result.llm_model && !result.missing_env?.includes('LLM_ENDPOINT');
        setTestResults(prev => ({
          ...prev,
          llm: hasLlm ? 'pass' : 'fail',
          llm_detail: hasLlm
            ? `Model: ${result.llm_model}`
            : `Missing: ${(result.missing_env || []).join(', ') || 'LLM_API_KEY or Azure AD'}`,
        }));
        if (hasLlm) {
          setCheckedSteps(prev => ({ ...prev, llm_configured: true }));
        }
      } else if (testAction === 'chromadb') {
        const res = await fetch('/api/knowledge/status');
        if (res.ok) {
          const data = await res.json();
          const total = Object.values(data.collections || {}).reduce((s, v) => s + v, 0);
          setTestResults(prev => ({
            ...prev,
            chromadb: total > 0 ? 'pass' : 'fail',
            chromadb_detail: total > 0 ? `${total} issue patterns embedded` : 'No embeddings found — run: python3 knowledge/embedder.py',
          }));
          if (total > 0) {
            setCheckedSteps(prev => ({ ...prev, chromadb_ready: true }));
          }
        } else {
          setTestResults(prev => ({ ...prev, chromadb: 'fail', chromadb_detail: 'ChromaDB endpoint not responding' }));
        }
      }
    } catch (err) {
      setTestResults(prev => ({ ...prev, [testAction]: 'fail', [`${testAction}_detail`]: err.message }));
    }
  };

  const completedCount = SETUP_STEPS.filter(s => checkedSteps[s.id]).length;

  const handleSignIn = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await loginPopup();
      updateSession({
        connected: true,
        user: response.account.name || response.account.username,
      });
    } catch (err) {
      setError(`Sign-in failed: ${err.message}. Try "Paste Token" below if popup is blocked.`);
    } finally {
      setLoading(false);
    }
  };

  const handleManualToken = () => {
    if (!manualTokenInput.trim()) return;
    setManualToken(manualTokenInput.trim());
    // Decode JWT to get user info
    try {
      const payload = JSON.parse(atob(manualTokenInput.trim().split('.')[1]));
      updateSession({
        connected: true,
        user: payload.name || payload.upn || payload.unique_name || 'Token User',
      });
      setError('');
      setShowManualToken(false);
    } catch {
      updateSession({ connected: true, user: 'Token User' });
      setError('');
      setShowManualToken(false);
    }
  };

  const handleSignOut = async () => {
    try {
      await logout();
      updateSession({ connected: false, user: null });
    } catch (err) {
      console.error('Sign-out error:', err);
    }
  };

  const handleLoadSample = async () => {
    try {
      setLoading(true);
      setStatus('Loading sample dataset...');
      setError('');
      const result = await loadSampleDataset();
      const hasFindings = (result.findings || []).length > 0;
      updateSession({
        connected: true,
        sampleMode: true,
        sessionId: result.sessionId,
        dbPath: result.dbPath,
        modelName: result.modelName || 'LOS Sample Model',
        domain: result.domain || 'CLINICAL_INPATIENT',
        traces: result.traces || [],
        cuMetrics: result.cuMetrics || null,
        findings: result.findings || [],
        collectionComplete: true,
        analysisComplete: hasFindings,
      });
      setStatus('Sample dataset loaded successfully');
      onNavigate('traces');
    } catch (err) {
      setError(`Failed to load sample: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleShowScenarios = async () => {
    try {
      setLoading(true);
      setError('');
      const result = await getScenarios();
      setScenarios(result.scenarios || []);
      setShowScenarios(true);
    } catch (err) {
      setError(`Failed to load scenarios: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadScenario = async (scenarioId) => {
    try {
      setLoading(true);
      setError('');
      const scenario = scenarios.find(s => s.id === scenarioId);
      setStatus(`Loading scenario ${scenarioId}: ${scenario?.name || ''}...`);
      const result = await loadScenario(scenarioId);
      updateSession({
        connected: true,
        sampleMode: true,
        sessionId: result.sessionId,
        dbPath: result.dbPath,
        modelName: result.modelName,
        domain: result.domain,
        traces: result.traces || [],
        cuMetrics: result.cuMetrics || null,
        collectionComplete: true,
        scenarioId: result.scenarioId,
        scenarioName: result.scenarioName,
      });
      setStatus(`Loaded: ${result.scenarioName}`);
      onNavigate('traces');
    } catch (err) {
      setError(`Failed to load scenario: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleFetchModels = async () => {
    if (!workspaceId.trim()) return;
    try {
      setLoading(true);
      setError('');
      const token = await getAccessToken();
      const result = await getModels(workspaceId.trim(), token);
      setModels(result.models || []);
      updateSession({ workspaceId: workspaceId.trim() });
    } catch (err) {
      setError(`Failed to fetch models: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCollect = async () => {
    if (!selectedModel) return;
    try {
      setLoading(true);
      setError('');
      setStatus('Collecting data from Fabric workspace...');
      const token = await getAccessToken();
      const result = await collectData(workspaceId, selectedModel, token);
      updateSession({
        sessionId: result.sessionId,
        dbPath: result.dbPath,
        modelId: selectedModel,
        modelName: result.modelName,
        domain: result.domain,
        traces: result.traces || [],
        collectionComplete: true,
      });
      setStatus('Data collection complete');
      onNavigate('traces');
    } catch (err) {
      setError(`Collection failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const runAutoXmla = async (wsId, modelId, dbPath) => {
    try {
      setXmlaStatus('collecting');
      setXmlaError('');
      const token = await getAccessToken().catch(() => manualTokenInput.trim());
      const result = await collectXmla(wsId, modelId, token, dbPath);
      setXmlaSummary(result.summary || {});
      setXmlaStatus('complete');
      updateSession({ xmlaComplete: true });
    } catch (err) {
      setXmlaError(err.message);
      setXmlaStatus('error');
    }
  };

  const handleFetchAgents = async () => {
    if (!workspaceId.trim()) return;
    try {
      setAgentsLoading(true);
      setError('');
      const token = await getAccessToken().catch(() => manualTokenInput.trim());
      const result = await getAgents(workspaceId.trim(), token);
      setAgents(result.agents || []);
      updateSession({ workspaceId: workspaceId.trim() });
    } catch (err) {
      setError(`Failed to fetch agents: ${err.message}`);
    } finally {
      setAgentsLoading(false);
    }
  };

  const handleSelectAgent = (agentId) => {
    setSelectedAgentId(agentId);
    const agent = agents.find(a => a.id === agentId);
    if (agent) {
      setDirectAgentId(agent.id);
      setDirectAgentName(agent.name);
      setDirectInstructions(agent.description || `Data Agent: ${agent.name}`);
    }
  };

  const [liveProgress, setLiveProgress] = useState({ current: 0, total: 0, question: '' });
  const [liveLog, setLiveLog] = useState([]);

  // ── Parallel Multi-Agent Collection ──
  const handleParallelCollect = async () => {
    if (!workspaceId.trim() || agents.length === 0) return;
    try {
      setLoading(true);
      setError('');
      const token = await getAccessToken().catch(() => manualTokenInput.trim());
      const qPerAgent = Math.max(5, Math.ceil(50 / agents.length));
      const totalQ = qPerAgent * agents.length;
      setStatus(`Parallel collection: ${agents.length} agents × ${qPerAgent} questions = ${totalQ} total`);
      setLiveProgress({ current: 0, total: totalQ, question: 'Starting parallel collection...' });
      setLiveLog([{ text: `Parallel collection: ${agents.length} agents × ${qPerAgent} questions each`, status: 'info' }]);

      collectParallel(
        {
          workspaceId: workspaceId.trim(),
          agents: agents.map(a => ({ agentId: a.id, agentName: a.name, agentInstructions: a.description || '' })),
          questionsPerAgent: qPerAgent,
        },
        token,
        // onProgress
        (data) => {
          if (data.type === 'start') {
            setLiveProgress({ current: 0, total: data.total, question: `${data.agents?.length || agents.length} agents running in parallel...` });
            setLiveLog(prev => [...prev, { text: `Started ${data.agents?.length || agents.length} agents in parallel`, status: 'info' }]);
          } else if (data.type === 'progress') {
            setLiveProgress(prev => ({ ...prev, current: data.completed || prev.current + 1, question: `[${data.agentName}] ${data.question || ''}` }));
            const icon = data.status === 'pass' ? 'OK' : data.status === 'fail' ? 'FAIL' : '';
            const latency = data.elapsed ? ` in ${(data.elapsed / 1000).toFixed(1)}s` : '';
            setStatus(`[${data.completed}/${data.total}] ${data.agentName}: ${icon}${latency}`);
            setLiveLog(prev => [...prev, {
              text: `[${data.agentName}] Q${data.completed}: ${icon}${latency} — "${(data.question || '').substring(0, 40)}"`,
              status: data.status === 'pass' ? 'pass' : data.status === 'fail' ? 'fail' : 'pending',
            }]);
          } else if (data.type === 'status') {
            setStatus(data.message || '');
            setLiveLog(prev => [...prev, { text: data.message || '', status: 'info' }]);
          } else if (data.type === 'building') {
            setStatus('All agents done — building aggregated trace database...');
            setLiveLog(prev => [...prev, { text: 'Building aggregated trace database...', status: 'info' }]);
          }
        },
        // onTrace (individual trace)
        (data) => {},
        // onComplete
        (result) => {
          updateSession({
            connected: true,
            sessionId: result.sessionId,
            dbPath: result.dbPath,
            modelId: 'multi-agent',
            modelName: result.modelName || `Multi-Agent Parallel (${agents.length} agents)`,
            domain: result.domain || 'MULTI_AGENT',
            traces: result.traces || [],
            collectionComplete: true,
            workspaceId: workspaceId.trim(),
            liveCollection: true,
            parallelCollection: true,
          });
          const totalSec = result.totalTimeMs ? (result.totalTimeMs / 1000).toFixed(0) : '?';
          setStatus(`Parallel collection complete — ${(result.traces || []).length} traces from ${agents.length} agents in ${totalSec}s`);
          setLoading(false);
          setLiveProgress({ current: 0, total: 0, question: '' });
          onNavigate('traces');
        },
        // onError
        (err) => {
          setError(`Parallel collection failed: ${err.message}`);
          setLoading(false);
        },
      );
    } catch (err) {
      setError(`Parallel collection failed: ${err.message}`);
      setLoading(false);
    }
  };

  const handleDirectCollect = async (tracesFromPortal) => {
    if (!workspaceId.trim() || !directAgentId.trim()) return;
    try {
      setLoading(true);
      setError('');
      const token = await getAccessToken().catch(() => manualTokenInput.trim());

      // Use live collection — sends real questions to the Data Agent /chat API
      setStatus('Connecting to Data Agent...');
      setLiveProgress({ current: 0, total: 50, question: 'Starting...' });
      setLiveLog([]);

      collectLive(
        {
          workspaceId: workspaceId.trim(),
          agentId: directAgentId.trim(),
          agentName: directAgentName.trim() || 'Data Agent',
          agentInstructions: directInstructions.trim(),
        },
        token,
        // onProgress
        (data) => {
          if (data.type === 'start') {
            setLiveProgress({ current: 0, total: data.total, question: 'Creating assistant...' });
            setStatus(`Starting collection - ${data.total} questions queued`);
            setLiveLog([{ text: `Connected to ${directAgentName.trim() || 'Data Agent'} - sending ${data.total} diagnostic questions`, status: 'info' }]);
          } else if (data.type === 'progress') {
            setLiveProgress(prev => ({ ...prev, current: data.index + 1, question: data.question }));
            setStatus(`Q${data.index + 1}/${data.total || 50}: Asking "${data.question}"`);
            setLiveLog(prev => [...prev, { text: `Q${data.index + 1}: Sending >> "${data.question}"`, status: 'pending' }]);
          } else if (data.type === 'building') {
            setStatus('All questions answered - building trace database...');
            setLiveLog(prev => [...prev, { text: 'Building trace database from responses...', status: 'info' }]);
          } else if (data.type === 'retry') {
            setStatus(`Rate limited - retrying in ${data.retryAfter}s...`);
            setLiveLog(prev => [...prev, { text: `Rate limited - waiting ${data.retryAfter}s before retry`, status: 'warn' }]);
          }
        },
        // onTrace
        (data) => {
          const t = data.trace;
          const latency = (t.responseTimeMs / 1000).toFixed(1);
          const ok = t.status === 'pass';
                    setStatus(`Q${data.index + 1}: ${ok ? 'OK' : 'FAIL'} in ${latency}s - "${t.question.substring(0, 50)}"`);
                    setLiveLog(prev => {
                      const updated = [...prev];
                      // Find the pending entry for this question and update it
                      const idx = updated.findLastIndex(e => e.status === 'pending');
                      if (idx >= 0) {
                        updated[idx] = { text: `Q${data.index + 1}: ${ok ? 'OK' : 'FAIL'} in ${latency}s - "${t.question.substring(0, 45)}"`, status: ok ? 'pass' : 'fail' };
            }
            return updated;
          });
        },
        // onComplete
        (result) => {
          updateSession({
            connected: true,
            sessionId: result.sessionId,
            dbPath: result.dbPath,
            modelId: directAgentId.trim(),
            modelName: result.modelName,
            domain: result.domain || 'healthcare',
            traces: result.traces || [],
            collectionComplete: true,
            workspaceId: workspaceId.trim(),
            liveCollection: true,
          });
          setStatus(`Real trace collection complete — ${(result.traces || []).length} traces from live Data Agent`);
          setLoading(false);
          setLiveProgress({ current: 0, total: 0, question: '' });
          onNavigate('traces');
          // Auto-trigger XMLA collection in background
          runAutoXmla(workspaceId.trim(), directAgentId.trim(), result.dbPath);
        },
        // onError
        (err) => {
          setError(`Live collection failed: ${err.message}. Falling back to synthetic traces...`);
          // Fallback to synthetic collection
          collectDataDirect({
            workspaceId: workspaceId.trim(),
            agentId: directAgentId.trim(),
            agentName: directAgentName.trim() || 'Data Agent',
            agentInstructions: directInstructions.trim(),
            tables: [],
            traces: tracesFromPortal || [],
          }).then(result => {
            updateSession({
              connected: true,
              sessionId: result.sessionId,
              dbPath: result.dbPath,
              modelId: directAgentId.trim(),
              modelName: result.modelName,
              domain: result.domain || 'healthcare',
              traces: result.traces || [],
              collectionComplete: true,
              workspaceId: workspaceId.trim(),
            });
            setStatus('Loaded with synthetic traces (live collection unavailable)');
            setLoading(false);
            onNavigate('traces');
          }).catch(fallbackErr => {
            setError(`Collection failed: ${fallbackErr.message}`);
            setLoading(false);
          });
        },
      );
    } catch (err) {
      setError(`Direct collection failed: ${err.message}`);
      setLoading(false);
    }
  };

  return (
    <div className="fade-in" style={{ maxWidth: 600, margin: '0 auto' }}>
      <div className="glass" style={{ padding: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 24 }}>
          Connect to Fabric Workspace
        </h2>

        {/* Setup Checklist */}
        <div style={{ marginBottom: 24 }}>
          <button
            onClick={() => setShowChecklist(!showChecklist)}
            style={{
              width: '100%',
              padding: '12px 16px',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              color: 'var(--text)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 14,
              fontWeight: 500,
            }}
          >
            <span>Setup Checklist</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                fontSize: 12,
                color: completedCount === SETUP_STEPS.length ? 'var(--green)' : 'var(--text-muted)',
              }}>
                {completedCount}/{SETUP_STEPS.length} complete
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {showChecklist ? '\u25B2' : '\u25BC'}
              </span>
            </span>
          </button>

          {showChecklist && (
            <div style={{
              border: '1px solid var(--border)',
              borderTop: 'none',
              borderRadius: '0 0 8px 8px',
              background: 'rgba(0,0,0,0.15)',
              padding: '8px 0',
            }}>
              {SETUP_STEPS.map((step, idx) => {
                const isChecked = checkedSteps[step.id];
                const testResult = testResults[step.testAction];
                // Show category header before first item in each category
                const prevCategory = idx > 0 ? SETUP_STEPS[idx - 1].category : null;
                const showCategoryHeader = step.category !== prevCategory;
                const categoryLabels = {
                  auth: 'Authentication & MSAL Setup',
                  infra: 'Infrastructure & Services',
                  fabric: 'Fabric Environment',
                  connect: 'Connect & Test',
                };
                const categoryColors = {
                  auth: 'var(--cyan)',
                  infra: 'var(--teal)',
                  fabric: 'var(--blue)',
                  connect: 'var(--green)',
                };
                return (
                  <React.Fragment key={step.id}>
                    {showCategoryHeader && (
                      <div style={{
                        padding: '10px 16px 6px',
                        fontSize: 11,
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: categoryColors[step.category] || 'var(--text-muted)',
                        borderTop: idx > 0 ? '1px solid rgba(255,255,255,0.08)' : 'none',
                        marginTop: idx > 0 ? 4 : 0,
                      }}>
                        {categoryLabels[step.category] || step.category}
                      </div>
                    )}
                    <div
                      style={{
                        padding: '10px 16px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 10,
                        borderBottom: idx < SETUP_STEPS.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                      }}
                    >
                    <input
                      type="checkbox"
                      checked={!!isChecked}
                      onChange={() => toggleStep(step.id)}
                      style={{ marginTop: 3, cursor: 'pointer', accentColor: 'var(--green)' }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: isChecked ? 'var(--green)' : 'var(--text)',
                        textDecoration: isChecked ? 'line-through' : 'none',
                        opacity: isChecked ? 0.7 : 1,
                      }}>
                        {step.title}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, paddingLeft: 28 }}>
                        {step.description}
                      </div>
                      <div style={{ paddingLeft: 28, marginTop: 6, display: 'flex', gap: 8, alignItems: 'center' }}>
                        {step.link && (
                          <a
                            href={step.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ fontSize: 11, color: 'var(--cyan)', textDecoration: 'none' }}
                          >
                            {step.linkText || 'Learn More'} &#8599;
                          </a>
                        )}
                        {step.testable && (
                          <button
                            onClick={() => handleTestConnection(step.testAction)}
                            disabled={testResult === 'testing'}
                            style={{
                              fontSize: 11,
                              padding: '3px 10px',
                              borderRadius: 4,
                              border: '1px solid var(--border)',
                              background: testResult === 'pass' ? 'rgba(34,197,94,0.15)'
                                : testResult === 'fail' ? 'rgba(239,68,68,0.15)'
                                : 'rgba(255,255,255,0.05)',
                              color: testResult === 'pass' ? 'var(--green)'
                                : testResult === 'fail' ? 'var(--red)'
                                : 'var(--text-muted)',
                              cursor: testResult === 'testing' ? 'wait' : 'pointer',
                            }}
                          >
                            {testResult === 'testing' ? 'Testing...'
                              : testResult === 'pass' ? 'Connected'
                              : testResult === 'fail' ? 'Failed — Retry'
                              : 'Test Connection'}
                          </button>
                        )}
                        {testResults[`${step.testAction}_detail`] && (
                          <span style={{
                            fontSize: 10,
                            color: testResult === 'pass' ? 'var(--green)' : 'var(--red)',
                          }}>
                            {testResults[`${step.testAction}_detail`]}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  </React.Fragment>
                );
              })}
            </div>
          )}
        </div>

        {/* Sample Dataset Buttons */}
        <div style={{ marginBottom: 32, paddingBottom: 24, borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn-primary"
              onClick={handleLoadSample}
              disabled={loading}
              style={{ flex: 1, justifyContent: 'center' }}
            >
              {loading && !showScenarios ? 'Loading...' : 'Sample Dataset'}
            </button>
            <button
              className="btn-secondary"
              onClick={handleShowScenarios}
              disabled={loading}
              style={{ flex: 1, justifyContent: 'center' }}
            >
              {loading && showScenarios ? 'Loading...' : `Test Scenarios (${scenarios.length || 25})`}
            </button>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8, textAlign: 'center' }}>
            Load pre-built sample data — no Fabric connection required
          </p>

          {/* Scenario Picker */}
          {showScenarios && scenarios.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{
                maxHeight: 360,
                overflowY: 'auto',
                border: '1px solid var(--border)',
                borderRadius: 8,
                background: 'rgba(0,0,0,0.15)',
              }}>
                {scenarios.map(s => {
                  const severityColor = {
                    CLINICAL_INPATIENT: '#ef4444',
                    CLINICAL_QUALITY: '#f97316',
                    REVENUE_CYCLE: '#22c55e',
                    WORKFORCE: '#3b82f6',
                    SUPPLY_CHAIN: '#a855f7',
                    PATIENT_EXPERIENCE: '#ec4899',
                    OPERATIONAL: '#eab308',
                    FINANCIAL: '#06b6d4',
                  }[s.domain] || '#888';

                  return (
                    <div
                      key={s.id}
                      onClick={() => !loading && handleLoadScenario(s.id)}
                      style={{
                        padding: '10px 14px',
                        borderBottom: '1px solid var(--border)',
                        cursor: loading ? 'wait' : 'pointer',
                        transition: 'background 0.15s',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <span style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: '#000',
                        background: severityColor,
                        padding: '2px 6px',
                        borderRadius: 4,
                        minWidth: 28,
                        textAlign: 'center',
                      }}>
                        {s.id}
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>
                          {s.name}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                          {s.domain} — {(s.key_issues || []).slice(0, 3).join(', ')}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Quick Setup — Fabric Connection */}
        <div style={{ marginBottom: 24 }}>
          <div style={{
            border: '1px solid var(--border)',
            borderRadius: 8,
            background: 'rgba(0,0,0,0.15)',
            padding: 16,
            marginBottom: 16,
          }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--teal)' }}>
              Quick Setup — Connect to Fabric
            </h3>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
              Paste your App Registration Client ID to connect. No config files to edit.
              <a href="https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/CreateApplicationBlade"
                target="_blank" rel="noopener noreferrer"
                style={{ color: 'var(--cyan)', marginLeft: 4 }}>
                Create App Registration &#8599;
              </a>
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Application (Client) ID *
                </label>
                <input
                  type="text"
                  value={quickClientId}
                  onChange={e => { setQuickClientId(e.target.value); setConfigSaved(false); }}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    color: 'var(--text)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 12,
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                  Tenant ID <span style={{ opacity: 0.5 }}>(optional — defaults to multi-tenant)</span>
                </label>
                <input
                  type="text"
                  value={quickTenantId}
                  onChange={e => { setQuickTenantId(e.target.value); setConfigSaved(false); }}
                  placeholder="common (multi-tenant)"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    color: 'var(--text)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 12,
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button
                  onClick={() => {
                    if (!quickClientId.trim()) return;
                    setClientConfig(quickClientId.trim(), quickTenantId.trim() || 'common');
                    setConfigSaved(true);
                    setCheckedSteps(prev => ({ ...prev, client_config: true, azure_app: true }));
                  }}
                  disabled={!quickClientId.trim()}
                  style={{
                    padding: '8px 16px',
                    borderRadius: 6,
                    border: '1px solid var(--border)',
                    background: configSaved ? 'rgba(34,197,94,0.15)' : 'var(--teal)',
                    color: configSaved ? 'var(--green)' : '#000',
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: quickClientId.trim() ? 'pointer' : 'not-allowed',
                    opacity: quickClientId.trim() ? 1 : 0.5,
                  }}
                >
                  {configSaved ? 'Saved' : 'Save & Configure'}
                </button>
                {configSaved && (
                  <span style={{ fontSize: 11, color: 'var(--green)' }}>
                    Ready — click Sign In below
                  </span>
                )}
              </div>
            </div>
          </div>

          {!session.connected ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button
                className="btn-secondary"
                onClick={handleSignIn}
                disabled={loading || !quickClientId.trim()}
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  opacity: quickClientId.trim() ? 1 : 0.5,
                }}
              >
                {!quickClientId.trim() ? 'Enter Client ID above to Sign In' : 'Connect to Fabric (OAuth)'}  
              </button>

              {/* Manual Token Paste — always visible */}
              <div style={{
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: 12,
                background: 'rgba(0,0,0,0.15)',
                marginTop: 4,
              }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>
                  Or paste a Fabric API token directly
                </p>
                <div style={{
                  background: 'rgba(0,200,150,0.08)',
                  border: '1px solid rgba(0,200,150,0.2)',
                  borderRadius: 6,
                  padding: '8px 10px',
                  marginBottom: 10,
                }}>
                  <p style={{ fontSize: 11, color: 'var(--teal)', marginBottom: 4, fontWeight: 600 }}>
                    How to get a token (Azure Cloud Shell or local CLI):
                  </p>
                  <code style={{
                    display: 'block',
                    fontSize: 10,
                    color: 'var(--text)',
                    background: 'rgba(0,0,0,0.3)',
                    padding: '6px 8px',
                    borderRadius: 4,
                    fontFamily: 'var(--font-mono)',
                    wordBreak: 'break-all',
                    marginBottom: 4,
                    userSelect: 'all',
                  }}>
                    az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv
                  </code>
                  <p style={{ fontSize: 10, color: 'var(--text-muted)', margin: 0 }}>
                    Requires: <code style={{ fontSize: 10 }}>az login</code> first. Token expires in ~60 min. Use <a href="https://shell.azure.com" target="_blank" rel="noreferrer" style={{ color: 'var(--teal)' }}>shell.azure.com</a> if no local CLI.
                  </p>
                </div>
                <textarea
                  value={manualTokenInput}
                  onChange={e => setManualTokenInput(e.target.value)}
                  placeholder="Paste access token here (eyJ...)"
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    color: 'var(--text)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    outline: 'none',
                    resize: 'vertical',
                    boxSizing: 'border-box',
                  }}
                />
                <button
                  onClick={handleManualToken}
                  disabled={!manualTokenInput.trim()}
                  style={{
                    marginTop: 8,
                    padding: '6px 16px',
                    borderRadius: 6,
                    border: '1px solid var(--border)',
                    background: manualTokenInput.trim() ? 'var(--teal)' : 'rgba(255,255,255,0.05)',
                    color: manualTokenInput.trim() ? '#000' : 'var(--text-muted)',
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: manualTokenInput.trim() ? 'pointer' : 'not-allowed',
                  }}
                >
                  Connect with Token
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 14, color: 'var(--green)' }}>
                Signed in as {session.user}
              </span>
              <button className="btn-secondary" onClick={handleSignOut} style={{ fontSize: 12, padding: '4px 12px' }}>
                Sign Out
              </button>
            </div>
          )}
        </div>

        {/* Workspace & Agent Entry */}
        {session.connected && !session.sampleMode && (
          <div style={{ marginBottom: 24 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Workspace ID (from Fabric URL)
            </label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <input
                type="text"
                value={workspaceId}
                onChange={e => { setWorkspaceId(e.target.value); setAgents([]); setSelectedAgentId(''); }}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--text)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 13,
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
              <button
                onClick={handleFetchAgents}
                disabled={!workspaceId.trim() || agentsLoading}
                style={{
                  padding: '10px 16px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: workspaceId.trim() ? 'var(--teal)' : 'rgba(255,255,255,0.05)',
                  color: workspaceId.trim() ? '#000' : 'var(--text-muted)',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: workspaceId.trim() ? 'pointer' : 'not-allowed',
                  whiteSpace: 'nowrap',
                }}
              >
                {agentsLoading ? 'Loading...' : 'Load Agents'}
              </button>
            </div>

            {agents.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Select Data Agent ({agents.length} found)
                </label>
                <select
                  value={selectedAgentId}
                  onChange={e => handleSelectAgent(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    color: 'var(--text)',
                    fontSize: 13,
                    outline: 'none',
                    boxSizing: 'border-box',
                    cursor: 'pointer',
                  }}
                >
                  <option value="">-- Choose an agent --</option>
                  {agents.map(a => (
                    <option key={a.id} value={a.id}>
                      {a.name}{a.description ? ` — ${a.description.slice(0, 60)}` : ''}
                    </option>
                  ))}
                </select>
                {selectedAgentId && (
                  <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    Agent ID: {selectedAgentId}
                  </div>
                )}
              </div>
            )}

            {agents.length === 0 && (
              <>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Data Agent ID (from Fabric URL: /aiskills/&lt;this-id&gt;)
                </label>
                <input
                  type="text"
                  value={directAgentId}
                  onChange={e => setDirectAgentId(e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    color: 'var(--text)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 13,
                    outline: 'none',
                    marginBottom: 12,
                    boxSizing: 'border-box',
                  }}
                />

                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Agent Name
                </label>
                <input
                  type="text"
                  value={directAgentName}
                  onChange={e => setDirectAgentName(e.target.value)}
                  placeholder="e.g. LOS_Bad_Agent"
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    color: 'var(--text)',
                    fontSize: 13,
                    outline: 'none',
                    marginBottom: 12,
                    boxSizing: 'border-box',
                  }}
                />
              </>
            )}

            <button
              onClick={() => setShowDirectEntry(!showDirectEntry)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                fontSize: 11,
                cursor: 'pointer',
                textDecoration: 'underline',
                padding: 4,
                marginBottom: 8,
              }}
            >
              {showDirectEntry ? 'Hide agent instructions' : 'Paste agent instructions (optional)'}
            </button>

            {showDirectEntry && (
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Agent Instructions (paste from Fabric portal)
                </label>
                <textarea
                  value={directInstructions}
                  onChange={e => setDirectInstructions(e.target.value)}
                  placeholder="Paste the agent's system prompt / instructions here..."
                  rows={6}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    color: 'var(--text)',
                    fontSize: 12,
                    outline: 'none',
                    resize: 'vertical',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            )}

            <button
              className="btn-primary"
              onClick={() => handleDirectCollect([])}
              disabled={loading || !workspaceId.trim() || !directAgentId.trim()}
              style={{
                width: '100%',
                justifyContent: 'center',
                opacity: (workspaceId.trim() && directAgentId.trim()) ? 1 : 0.5,
              }}
            >
              {loading ? status || 'Collecting...' : 'Analyze Data Agent'}
            </button>

            {/* Parallel Collection Button — shows when agents are loaded */}
            {agents.length >= 2 && (
              <button
                className="btn-primary"
                onClick={handleParallelCollect}
                disabled={loading || !workspaceId.trim()}
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  marginTop: 8,
                  background: loading ? undefined : 'linear-gradient(135deg, var(--teal), #6366f1)',
                  opacity: loading ? 0.5 : 1,
                }}
              >
                {loading ? status || 'Running...' : `Parallel Collection — All ${agents.length} Agents (${Math.max(5, Math.ceil(50 / agents.length))}q each, ~1 min)`}
              </button>
            )}

            {/* Live Collection Progress Log */}
            {loading && liveLog.length > 0 && (
              <div style={{
                marginTop: 12,
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: 12,
                background: 'rgba(0,0,0,0.2)',
                maxHeight: 220,
                overflowY: 'auto',
              }}>
                {/* Progress bar */}
                {liveProgress.total > 0 && (
                  <div style={{ marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
                      <span>Progress: {liveProgress.current}/{liveProgress.total}</span>
                      <span>{liveProgress.total > 0 ? Math.round((liveProgress.current / liveProgress.total) * 100) : 0}%</span>
                    </div>
                    <div style={{ height: 4, background: 'rgba(255,255,255,0.08)', borderRadius: 2 }}>
                      <div style={{
                        height: '100%',
                        width: `${(liveProgress.current / liveProgress.total) * 100}%`,
                        background: 'var(--teal)',
                        borderRadius: 2,
                        transition: 'width 0.5s ease',
                      }} />
                    </div>
                  </div>
                )}
                {liveLog.map((entry, i) => (
                  <div key={i} style={{
                    fontSize: 11,
                    fontFamily: 'var(--font-mono)',
                    padding: '3px 0',
                    color: entry.status === 'pass' ? 'var(--green)'
                      : entry.status === 'fail' ? 'var(--red)'
                      : entry.status === 'warn' ? 'var(--amber)'
                      : entry.status === 'pending' ? 'var(--teal)'
                      : 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}>
                    <span style={{ flexShrink: 0, width: 14, textAlign: 'center' }}>
                      {entry.status === 'pass' ? '\u2713' : entry.status === 'fail' ? '\u2717' : entry.status === 'pending' ? '\u25CB' : '\u2022'}
                    </span>
                    <span>{entry.text}</span>
                  </div>
                ))}
              </div>
            )}

            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, textAlign: 'center' }}>
              Find IDs in the Fabric URL: /groups/&lt;workspace-id&gt;/aiskills/&lt;agent-id&gt;
            </p>

            {/* XMLA Deep Analysis — Auto Status */}
            {xmlaStatus && (
              <div style={{
                marginTop: 16,
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: 12,
                background: xmlaStatus === 'complete' ? 'rgba(34,197,94,0.08)'
                  : xmlaStatus === 'error' ? 'rgba(239,68,68,0.08)'
                  : 'rgba(0,188,212,0.08)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <span style={{ fontSize: 14 }}>
                    {xmlaStatus === 'collecting' ? '...' : xmlaStatus === 'complete' ? 'OK' : '!'}
                  </span>
                  <span style={{
                    fontWeight: 600,
                    color: xmlaStatus === 'complete' ? 'var(--green)'
                      : xmlaStatus === 'error' ? 'var(--red)'
                      : 'var(--teal)',
                  }}>
                    {xmlaStatus === 'collecting' ? 'Collecting model metadata (XMLA)...'
                      : xmlaStatus === 'complete'
                        ? `XMLA Complete: ${xmlaSummary?.column_stats_count || 0} columns, ${xmlaSummary?.relationship_stats_count || 0} relationships`
                        : 'XMLA collection failed'}
                  </span>
                </div>
                {xmlaStatus === 'error' && xmlaError && (
                  <p style={{ fontSize: 11, color: 'var(--red)', marginTop: 6 }}>{xmlaError}</p>
                )}
                {xmlaStatus === 'error' && (
                  <button
                    onClick={() => {
                      if (session.dbPath && session.workspaceId) {
                        runAutoXmla(session.workspaceId, session.modelId || directAgentId.trim(), session.dbPath);
                      }
                    }}
                    style={{
                      marginTop: 8,
                      padding: '4px 12px',
                      borderRadius: 4,
                      border: '1px solid var(--border)',
                      background: 'rgba(255,255,255,0.05)',
                      color: 'var(--text-muted)',
                      fontSize: 11,
                      cursor: 'pointer',
                    }}
                  >
                    Retry XMLA
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Status & Error */}
        {status && !error && (
          <p style={{ fontSize: 13, color: 'var(--green)', marginTop: 16, textAlign: 'center' }}>{status}</p>
        )}
        {error && (
          <p style={{ fontSize: 13, color: 'var(--red)', marginTop: 16, textAlign: 'center' }}>{error}</p>
        )}
      </div>
    </div>
  );
}
