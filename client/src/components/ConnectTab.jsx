import React, { useState, useEffect } from 'react';
import { loginPopup, logout, getAccessToken, setClientConfig, getClientConfig } from '../auth/msalConfig';
import { loadSampleDataset, getWorkspaces, getModels, collectData, getScenarios, loadScenario, healthCheck } from '../api/proxy';

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
      setError(`Sign-in failed: ${err.message}`);
    } finally {
      setLoading(false);
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
              {loading && showScenarios ? 'Loading...' : `Test Scenarios (20)`}
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

        {/* Workspace ID Input */}
        {session.connected && !session.sampleMode && (
          <div style={{ marginBottom: 24 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Workspace ID (from Power BI URL)
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                type="text"
                value={workspaceId}
                onChange={e => setWorkspaceId(e.target.value)}
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
                }}
              />
              <button className="btn-primary" onClick={handleFetchModels} disabled={loading} style={{ padding: '10px 16px' }}>
                Load
              </button>
            </div>
          </div>
        )}

        {/* Model Selector */}
        {models.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Select Data Agent
            </label>
            <select
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 14px',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                color: 'var(--text)',
                fontFamily: 'var(--font-display)',
                fontSize: 14,
                outline: 'none',
              }}
            >
              <option value="">Choose a model...</option>
              {models.map(m => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Collect Data Button */}
        {selectedModel && (
          <button
            className="btn-primary"
            onClick={handleCollect}
            disabled={loading}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            {loading ? status || 'Collecting...' : 'Collect Data'}
          </button>
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
